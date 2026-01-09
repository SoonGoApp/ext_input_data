import os
from typing import Generator

import boto3
import pandas as pd
import psycopg2
import pytest
from pandas.testing import assert_frame_equal
from testcontainers.localstack import LocalStackContainer
from testcontainers.postgres import PostgresContainer

from soongo_data.utils.logging_utils import gen_logger


def normalize_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert all datetime-like columns to UTC timezone-aware format.
    Additionally, any column ending with '_date' or '_at' is converted to datetime.
    """
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]) or col.lower().endswith(("_date", "_at")):
            try:
                df[col] = pd.to_datetime(df[col], utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as exc:
                # Not a datetime column or unparsable -> ignore
                print(exc)
                pass
    return df


@pytest.fixture
def assert_df_equal():
    def _assert_df_equal(df1, df2, **kwargs):
        df1_norm = normalize_datetime_columns(df1)
        df2_norm = normalize_datetime_columns(df2)

        # Sort column order if needed
        if kwargs.pop("sort_columns", False):
            df1_norm = df1_norm.reindex(sorted(df1_norm.columns), axis=1)
            df2_norm = df2_norm.reindex(sorted(df2_norm.columns), axis=1)

        # Reset index if you want index-insensitive comparison
        if kwargs.pop("ignore_index", False):
            df1_norm = df1_norm.reset_index(drop=True)
            df2_norm = df2_norm.reset_index(drop=True)

        return assert_frame_equal(df1_norm, df2_norm, check_dtype=False, **kwargs)

    return _assert_df_equal


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgis/postgis:16-3.4") as pg:
        yield pg


@pytest.fixture
def pg_conn(postgres_container):
    url = postgres_container.get_connection_url()
    conn = psycopg2.connect(f"postgresql://{url.split('://')[1]}")
    cursor = conn.cursor()
    cursor.execute("DROP SCHEMA IF EXISTS publ cascade;")
    query = open("infrastructure/lambdas/high_mobility/schema.sql").read()
    cursor.execute(query)
    vehicle_path = os.path.join(os.path.dirname(__file__), "data", "high_mobility", "vehicles.csv")
    cursor.copy_expert(
        "COPY publ.vehicles(id,vin) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)",
        open(vehicle_path),
    )
    adress_path = os.path.join(os.path.dirname(__file__), "data", "high_mobility", "addresses.csv")
    cursor.copy_expert(
        "COPY publ.ban_addresses(number,street,postal_code,city,geom) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)",
        open(adress_path),
    )
    conn.commit()
    yield cursor, conn
    conn.rollback()
    cursor.close()
    conn.close()


@pytest.fixture(scope="session")
def localstack_container() -> Generator[LocalStackContainer, None, None]:
    with LocalStackContainer("localstack/localstack:s3-latest") as localstack:
        yield localstack


def setup_s3(request: pytest.FixtureRequest, s3_client):
    """Creates the buckets received in `request.params`.

    Args:
        request (FixtureRequest): fixture arguments.
        s3_client (S3): s3 client.
    """
    bucket = request.param
    try:
        s3_client.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        pass
    data_path = f"{os.path.abspath(os.path.dirname(__file__))}/data/"
    for basepath, _, files in os.walk(data_path):
        for filename in files:
            if filename.endswith(".json"):
                key = f"{basepath[1:]}/{filename}"
                s3_client.upload_file(Bucket=bucket, Key=key, Filename=f"{basepath}/{filename}")


@pytest.fixture()
def s3_client(request: pytest.FixtureRequest, localstack_container: LocalStackContainer) -> Generator:
    session = boto3.Session()
    client = session.client("s3", endpoint_url=localstack_container.get_url(), region_name="eu-west-1")
    setup_s3(request, client)
    yield session, client


@pytest.fixture
def logger():
    yield gen_logger("test")
