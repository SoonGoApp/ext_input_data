import json
import logging
import os

import boto3
import duckdb
import pandas as pd
from sqlalchemy import text

from soongo_data.utils.db import gen_session
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.secrets_utils import get_local_secret


def execute_query(path, con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyRelation:
    """
    Reads and executes a SQL query from a file.
    :param path: Path to the SQL file.
    :param con: DuckDB connection.
    :return: Resulting DuckDB relation.
    """
    query = open(os.path.join(os.path.dirname(__file__), path)).read()
    return con.execute(query).df()


def process_json(s3_uri: str, logger: logging.Logger, s3_params: dict, pg_uri: str) -> dict[str, list[int]]:
    """Process the new points json file and load it into Postgres using DuckDB.
    :param path: s3 uri to the json file
    :param logger:
    :param s3_params: S3 connection parameters
    :param pg_uri: database URI
    :return: dict with created and upserted trip ids
    """

    con = duckdb.connect()

    # install dependencies
    con.execute("""
        SET home_directory='/tmp';
        INSTALL httpfs;
        LOAD httpfs;
        INSTALL spatial;
        LOAD spatial;
        INSTALL 'json';
        LOAD 'json';
        INSTALL postgres;
        LOAD postgres;
    """)

    # attach s3 client
    s3_params_str = "; ".join([f"SET {k}='{v}'" for k, v in s3_params.items()])
    con.execute(s3_params_str)

    # attach postgres db
    con.query(f"ATTACH '{pg_uri}' AS db (TYPE postgres, SCHEMA 'publ');")

    # create raw
    con.query(f"""
        CREATE OR REPLACE TABLE raw AS
        SELECT
            vin,
            data,
            capability
        from read_json_auto(
            '{s3_uri}',
            columns = {{vin: 'VARCHAR(17)', data: 'JSON', capability: 'TEXT'}},
            auto_detect = False,
            format='array'
        ) as j
        WHERE CASE capability
            WHEN 'vehicle_location' THEN json_keys(j.data.vehicle_location) = ['coordinates']
            WHEN 'engine' THEN json_keys(j.data.engine) = ['status']
        END;
    """)

    # clean raw
    df: pd.Datarame = execute_query("points.sql", con)
    stats = df.iloc[0]
    logger.info(
        f"{stats.vehicles_nb} new points received for {stats.vehicles_distinct_nb} vehicles "
        f"from {stats.min_ts} to {stats.max_ts}"
    )

    # get trips upserts
    execute_query("trips.sql", con)

    # update trips
    updated: pd.DataFrame = execute_query("update_trip.sql", con)
    for update in updated.itertuples():
        logger.info(f"update trip - id: {update.id} - Start: {update.start_at} - End: {update.end_at}")
    updated_ids = updated.id.to_list()

    # insert trips
    inserted: pd.DataFrame = execute_query("insert_trip.sql", con)
    for insert in inserted.itertuples():
        logger.info(
            f"insert new trip - vehicle id: {insert.vehicle_id} - Start: {insert.start_at} - End: {insert.end_at}"
        )
    inserted_ids = inserted.id.to_list()

    # upsert trips start/end locations
    trip_ids = inserted_ids + updated_ids
    if trip_ids:
        with gen_session(database_url=pg_uri) as session:
            query = text(open(os.path.join(os.path.dirname(__file__), "update_location.sql")).read())
            logger.info(f"Updating locations for {len(trip_ids)} trips")
            session.execute(query, {"trip_ids": tuple(map(str, trip_ids))})
            session.commit()

    return {"inserted": inserted_ids, "updated": updated_ids}


def lambda_handler(event, context):
    logger = gen_logger(__name__)

    logger.info(f"Event received: {json.dumps(event)}")

    # Extract S3 object path
    bucket = event["detail"]["bucket"]["name"]
    key = event["detail"]["object"]["key"]
    s3_uri = f"s3://{bucket}/{key}"

    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()
    s3_params = {
        "s3_region": "eu-west-1",
        "s3_access_key_id": creds.access_key,
        "s3_secret_access_key": creds.secret_key,
        "s3_session_token": creds.token,
    }
    db_info = get_local_secret(logger=logger)

    logger.info(f"Processing {s3_uri}")
    process_json(s3_uri, logger, s3_params, db_info["DATABASE_URL"])

    return {"status": "success"}
