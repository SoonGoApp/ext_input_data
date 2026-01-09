import os

import pandas as pd
import pytest

from infrastructure.lambdas.high_mobility.app import process_json


@pytest.mark.parametrize("s3_client", ["soongo-test-hm"], indirect=True)
@pytest.mark.parametrize(
    "path",
    [
        "first_trip",
        "new_trip",
        "update_trip",
        "old_point",
        "noise_filtering",
        "mixed_trip",
        "live",
        "long_trip",
        "engine_off_trip",
    ],
)
def test_process_json(s3_client, postgres_container, pg_conn, path, assert_df_equal, logger):
    """
    Test processing high mobility points json and loading into Postgres.
    :param s3_client: S3 client fixture.
    :param postgres_container: Postgres container fixture.
    :param pg_conn: Postgres connection fixture.
    :param path: Test case path.
    :param assert_df_equal: DataFrame equality assertion function.
    :param logger: Logger fixture.
    """
    # init db
    cursor, conn = pg_conn
    csv_in_path = os.path.join(os.path.dirname(__file__), "data", "high_mobility", path, "in.csv")
    cursor.copy_expert(
        """
        COPY publ.trips(vehicle_id,geometry,start_location,end_location,start_at,end_at)
        FROM STDIN WITH (FORMAT CSV, HEADER TRUE)
        """,
        open(csv_in_path),
    )
    conn.commit()

    # process json located in s3
    pg_url = postgres_container.get_connection_url().replace(f"+{postgres_container.driver}", "")
    session, s3 = s3_client
    new_points_path = os.path.join(os.path.dirname(__file__), "data", "high_mobility", path, "points.json")
    s3_path = f"s3://soongo-test-hm{new_points_path}"
    creds = session.get_credentials().get_frozen_credentials()
    s3_params = {
        "s3_access_key_id": creds.access_key,
        "s3_secret_access_key": creds.secret_key,
        "s3_endpoint": s3.meta.endpoint_url[7:],  # remove http://
        "s3_url_style": "path",
    }
    process_json(s3_path, logger, s3_params, pg_url)

    # validate output against expected csv
    csv_out_path = os.path.join(os.path.dirname(__file__), "data", "high_mobility", path, "out.csv")
    expected_df = pd.read_csv(csv_out_path)
    expected_df.sort_values(["end_at", "geometry", "start_at", "vehicle_id"], inplace=True)

    cursor.execute(
        "select vehicle_id, st_astext(geometry), start_location, end_location, start_at, end_at from publ.trips;"
    )
    output_df = pd.DataFrame(
        cursor.fetchall(), columns=["vehicle_id", "geometry", "start_location", "end_location", "start_at", "end_at"]
    )
    output_df.sort_values(["end_at", "geometry", "start_at", "vehicle_id"], inplace=True)

    assert_df_equal(expected_df, output_df, ignore_index=True)
