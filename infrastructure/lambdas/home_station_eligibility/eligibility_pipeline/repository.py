import os
import pandas as pd
from sqlalchemy import text, Table, MetaData, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.db import gen_engine






logger = gen_logger("DB_INTERACTIONS")

engine = gen_engine(
    database_url=os.environ["DATABASE_URL"]
)



def get_collaborators_geocode_to_process(config: dict, limit: int | None = None) -> pd.DataFrame:
    try:
        SCHEMA = config["database"]["schema"]
        ELIGIBILITY_TABLE = config["tables"]["output"]["eligibility_table"]
        GEOCODE_TABLE = config["tables"]["output"]["geocode_table"]

        query = rf"""
            SELECT g.collaborator_id,
                g.cle_interop_adr,
                g.personal_address
            FROM {SCHEMA}.{GEOCODE_TABLE} g
            LEFT JOIN {SCHEMA}.{ELIGIBILITY_TABLE} e
                ON g.collaborator_id = e.collaborator_id
            WHERE e.collaborator_id IS NULL
        """

        if limit:
            query += " LIMIT :limit"

        with engine.connect() as conn:
            return pd.read_sql(
                text(query),
                conn,
                params={"limit": limit} if limit else None
            )
    
    except Exception as e:
        logger.exception(f"Failed load geocode data, Exception: {e}")
        raise


def get_collaborators_geocode_to_update(config: dict, limit: int | None = None) -> pd.DataFrame:
    try:
        SCHEMA = config["database"]["schema"]
        ELIGIBILITY_TABLE = config["tables"]["output"]["eligibility_table"]
        GEOCODE_TABLE = config["tables"]["output"]["geocode_table"]

        query = rf"""
            SELECT g.collaborator_id,
                   g.cle_interop_adr,
                   g.personal_address
            FROM {SCHEMA}.{GEOCODE_TABLE} g
            INNER JOIN {SCHEMA}.{ELIGIBILITY_TABLE} e
                ON g.collaborator_id = e.collaborator_id
            WHERE g.personal_address IS DISTINCT FROM e.personal_address
        """

        if limit:
            query += " LIMIT :limit"

        with engine.connect() as conn:
            return pd.read_sql(
                text(query),
                conn,
                params={"limit": limit} if limit else None
            )
    
    except Exception as e:
        logger.exception(f"Failed load geocode data, Exception: {e}")
        raise



def insert_collaborators_geocode_data(config: dict, df: pd.DataFrame, process_type: str):
    try:
        SCHEMA = config["database"]["schema"]
        GEOCODE_TABLE = config["tables"]["output"]["geocode_table"]

        metadata = MetaData(schema=SCHEMA)
        table = Table(GEOCODE_TABLE, metadata, autoload_with=engine)

        with engine.begin() as conn:
            if process_type == "insert":
                stmt = insert(table)
                conn.execute(stmt, df.to_dict(orient="records"))

            elif process_type == "update":
                stmt = pg_insert(table).values(df.to_dict(orient="records"))
                stmt = stmt.on_conflict_do_update(
                    index_elements=["collaborator_id"],
                    set_={
                        "personal_address": stmt.excluded.personal_address,
                        "cle_interop_adr": stmt.excluded.cle_interop_adr,
                        "longitude": stmt.excluded.longitude,
                        "latitude": stmt.excluded.latitude,
                        "source": stmt.excluded.source,
                        "created_at": stmt.excluded.created_at,
                    }
                )
                conn.execute(stmt)
            else:
                raise ValueError(f"Unknown process_type: {process_type}")

    except Exception as e:
        logger.exception(f"Failed insert/update geocode data, Exception: {e}")
        raise



def insert_collaborators_eligibility_data(config: dict, df: pd.DataFrame, process_type: str):
    try:
        SCHEMA = config["database"]["schema"]
        ELIGIBILITY_TABLE = config["tables"]["output"]["eligibility_table"]

        metadata = MetaData(schema=SCHEMA)
        table = Table(ELIGIBILITY_TABLE, metadata, autoload_with=engine)

        records = df.to_dict(orient="records")

        with engine.begin() as conn:
            if process_type == "insert":
                stmt = insert(table)
                conn.execute(stmt, records)

            elif process_type == "update":
                stmt = pg_insert(table).values(records)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["collaborator_id"], 
                    set_={
                        "personal_address": stmt.excluded.personal_address,
                        "eligibility_status": stmt.excluded.eligibility_status,
                        "building_usage": stmt.excluded.building_usage,
                        "building_type": stmt.excluded.building_type,
                        "housing_units": stmt.excluded.housing_units,
                        "building_levels": stmt.excluded.building_levels,
                        "ground_surface": stmt.excluded.ground_surface,
                        "total_surface": stmt.excluded.total_surface,
                        "has_garden": stmt.excluded.has_garden,
                        "source": stmt.excluded.source,
                        "created_at": stmt.excluded.created_at,
                    }
                )
                conn.execute(stmt)

            else:
                raise ValueError(f"Unknown process_type: {process_type}")

    except Exception as e:
        logger.exception(f"Failed insert/update eligibility data, Exception: {e}")
        raise



def ensure_tables_exist(config: dict):
    try:
        SCHEMA = config["database"]["schema"]
        ELIGIBILITY_TABLE = config["tables"]["output"]["eligibility_table"]
        GEOCODE_TABLE = config["tables"]["output"]["geocode_table"]

        with engine.begin() as conn:

            conn.execute(text(rf"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.{GEOCODE_TABLE} (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    collaborator_id UUID NOT NULL UNIQUE,
                    personal_address TEXT,
                    cle_interop_adr TEXT,
                    longitude DOUBLE PRECISION,
                    latitude DOUBLE PRECISION,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))

            conn.execute(text(rf"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.{ELIGIBILITY_TABLE} (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    collaborator_id UUID NOT NULL UNIQUE,

                    personal_address TEXT,
                    eligibility_status TEXT,
                    building_usage TEXT,
                    building_type TEXT,
                    housing_units DOUBLE PRECISION,
                    building_levels DOUBLE PRECISION,
                    ground_surface DOUBLE PRECISION,
                    total_surface DOUBLE PRECISION,
                    has_garden TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))

    except Exception as e:
        logger.exception(f"Failed to create output tables, Exception: {e}")
        raise


def cleanup_geocode_table(config: dict):
    try:
        SCHEMA = config["database"]["schema"]
        ELIGIBILITY_TABLE = config["tables"]["output"]["eligibility_table"]
        GEOCODE_TABLE = config["tables"]["output"]["geocode_table"]

        with engine.begin() as conn:
            conn.execute(text(rf"""
                DELETE FROM {SCHEMA}.{GEOCODE_TABLE} g
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM {SCHEMA}.{ELIGIBILITY_TABLE} e
                    WHERE e.collaborator_id = g.collaborator_id
                );
            """))

    except Exception as e:
        logger.exception(f"Failed to cleanup geocode table, Exception: {e}")
        raise




def get_collaborators_to_process(config: dict, limit: int | None = None) -> pd.DataFrame:
    try:
        SCHEMA = config["database"]["schema"]
        ELIGIBILITY_TABLE = config["tables"]["output"]["eligibility_table"]
        COLLABORATORS_TABLE = config["tables"]["input"]["collaborators_table"]

        ensure_tables_exist(config=config)
        cleanup_geocode_table(config=config)

        query = rf"""
        SELECT
            c.id,

            CASE
                WHEN s.street_part IS NULL
                    OR TRIM(s.street_part) = ''
                    OR s.street_part !~ '[A-ZÀ-ÖØ-öø-ÿ]'
                THEN NULL
                ELSE UPPER(
                    TRIM(
                        s.street_part || ' ' ||
                        COALESCE(s.postal_code, '') || ' ' ||
                        COALESCE(s.city, '')
                    )
                )
            END AS full_address

        FROM {SCHEMA}.{COLLABORATORS_TABLE} c

        LEFT JOIN {SCHEMA}.{ELIGIBILITY_TABLE} e
            ON c.id = e.collaborator_id

        LEFT JOIN (
            SELECT
                c2.id,

                /* cleaned postal code */
                REGEXP_REPLACE(
                    REGEXP_REPLACE(TRIM(c2.personal_postal_code), '[\r\n\t]+', ' ', 'g'),
                    '\s{2,}', ' ',
                    'g'
                ) AS postal_code,

                /* cleaned city */
                REGEXP_REPLACE(
                    REGEXP_REPLACE(TRIM(c2.personal_city), '[\r\n\t]+', ' ', 'g'),
                    '\s{2,}', ' ',
                    'g'
                ) AS city,

                /* street_part logic */
                CASE
                    WHEN COALESCE(TRIM(c2.personal_address), '') = ''
                        AND COALESCE(TRIM(c2.personal_street_name), '') <> ''
                        AND COALESCE(
                            TRIM(REGEXP_REPLACE(c2.personal_street_number::text, '\.0$', '')),
                            ''
                        ) <> ''
                    THEN
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                CONCAT(
                                    REGEXP_REPLACE(c2.personal_street_number::text, '\.0$', ''),
                                    ' ',
                                    TRIM(c2.personal_street_name)
                                ),
                                '[\r\n\t]+', ' ', 'g'
                            ),
                            '\s{2,}', ' ',
                            'g'
                        )

                    WHEN COALESCE(TRIM(c2.personal_address), '') ~ '^[0-9]+'
                    THEN
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(TRIM(c2.personal_address), '[\r\n\t]+', ' ', 'g'),
                            '\s{2,}', ' ',
                            'g'
                        )

                    ELSE NULL
                END AS street_part

            FROM {SCHEMA}.{COLLABORATORS_TABLE} c2
        ) s
            ON s.id = c.id

        WHERE e.collaborator_id IS NULL;
        """

        if limit:
            query += " LIMIT :limit"
        
        with engine.connect() as conn:
            df = pd.read_sql(
                text(query),
                conn,
                params={"limit": limit} if limit else None
            )
            df = df[df["full_address"].notna() & (df["full_address"] != "")]
            return df

    except Exception as e:
        logger.exception(f"Failed to load collaborators source table, Exception: {e}")
        raise



def get_collaborators_to_update(config: dict, limit: int | None = None) -> pd.DataFrame:
    try:

        SCHEMA = config["database"]["schema"]
        ELIGIBILITY_TABLE = config["tables"]["output"]["eligibility_table"]
        COLLABORATORS_TABLE = config["tables"]["input"]["collaborators_table"]

        query = rf"""
        SELECT
            c.id,
            UPPER(
                TRIM(
                    s.street_part || ' ' ||
                    COALESCE(s.postal_code, '') || ' ' ||
                    COALESCE(s.city, '')
                )
            ) AS full_address

        FROM {SCHEMA}.{COLLABORATORS_TABLE} c

        INNER JOIN {SCHEMA}.{ELIGIBILITY_TABLE} e
            ON c.id = e.collaborator_id

        INNER JOIN (
            SELECT
                c2.id,

                -- Clean postal code
                REGEXP_REPLACE(
                    REGEXP_REPLACE(TRIM(c2.personal_postal_code), '[\r\n\t]+', ' ', 'g'),
                    '\s{2,}', ' ',
                    'g'
                ) AS postal_code,

                -- Clean city
                REGEXP_REPLACE(
                    REGEXP_REPLACE(TRIM(c2.personal_city), '[\r\n\t]+', ' ', 'g'),
                    '\s{2,}', ' ',
                    'g'
                ) AS city,

                -- Compute street part
                CASE
                    WHEN COALESCE(TRIM(c2.personal_address), '') = ''
                        AND COALESCE(TRIM(c2.personal_street_name), '') <> ''
                        AND COALESCE(
                            TRIM(REGEXP_REPLACE(c2.personal_street_number::text, '\.0$', '')),
                            ''
                        ) <> ''
                    THEN
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                CONCAT(
                                    REGEXP_REPLACE(c2.personal_street_number::text, '\.0$', ''),
                                    ' ',
                                    TRIM(c2.personal_street_name)
                                ),
                                '[\r\n\t]+', ' ', 'g'
                            ),
                            '\s{2,}', ' ',
                            'g'
                        )

                    WHEN COALESCE(TRIM(c2.personal_address), '') ~ '^[0-9]+'
                    THEN
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(TRIM(c2.personal_address), '[\r\n\t]+', ' ', 'g'),
                            '\s{2,}', ' ',
                            'g'
                        )

                    ELSE NULL
                END AS street_part

            FROM {SCHEMA}.{COLLABORATORS_TABLE} c2
        ) s
            ON s.id = c.id

        WHERE
            -- Computed full_address is valid
            s.street_part IS NOT NULL
            AND TRIM(s.street_part) <> ''

            -- And the address has changed
            AND TRIM(UPPER(e.personal_address)) <> UPPER(
                TRIM(
                    s.street_part || ' ' ||
                    COALESCE(s.postal_code, '') || ' ' ||
                    COALESCE(s.city, '')
                )
            );
        """

        if limit:
            query += " LIMIT :limit"
        
        with engine.connect() as conn:
            df = pd.read_sql(
                text(query),
                conn,
                params={"limit": limit} if limit else None
            )
            df = df[df["full_address"].notna() & (df["full_address"] != "")]
            return df

    except Exception as e:
        logger.exception(f"Failed to load collaborators to update, Exception: {e}")
        raise

