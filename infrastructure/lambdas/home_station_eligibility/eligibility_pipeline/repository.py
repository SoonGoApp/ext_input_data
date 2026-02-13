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
                        "cle_interop_adr": stmt.excluded.cle_interop_adr,
                        "building_usage": stmt.excluded.building_usage,
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

        with engine.begin() as conn:

            conn.execute(text(rf"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.{ELIGIBILITY_TABLE} (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    collaborator_id UUID NOT NULL UNIQUE,

                    personal_address TEXT,
                    cle_interop_adr TEXT,
                    building_usage TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))

    except Exception as e:
        logger.exception(f"Failed to create output tables, Exception: {e}")
        raise



def get_collaborators_to_process(config: dict, limit: int | None = None) -> pd.DataFrame:
    try:
        SCHEMA = config["database"]["schema"]
        ELIGIBILITY_TABLE = config["tables"]["output"]["eligibility_table"]
        COLLABORATORS_TABLE = config["tables"]["input"]["collaborators_table"]

        ensure_tables_exist(config=config)

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