import pandas as pd
from eligibility_pipeline.logger import get_logger
from eligibility_pipeline.db import get_pg_engine
from eligibility_pipeline.functions import create_full_address
from sqlalchemy import text


logger = get_logger("DB_INTERACTIONS")


def ensure_tables_exist(pipeline_config: dict, engine):
    try:
        SCHEMA = pipeline_config["database"]["schema"]
        ELIGIBILITY_TABLE = pipeline_config["tables"]["output"]["eligibility_table"]
        GEOCODE_TABLE = pipeline_config["tables"]["output"]["geocode_table"]

        with engine.begin() as conn:
            
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.{GEOCODE_TABLE} (
                    collaborator_id uuid NOT NULL,
                    cle_interop_adr TEXT,
                    longitude DOUBLE PRECISION,
                    latitude DOUBLE PRECISION,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))

            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.{ELIGIBILITY_TABLE} (
                    collaborator_id uuid NOT NULL,
                    eligible TEXT,
                    usage_batiment TEXT,
                    type_batiment TEXT,
                    nb_logement INTEGER,
                    nb_niveau INTEGER,
                    s_geom DOUBLE PRECISION,
                    surface DOUBLE PRECISION,
                    garden TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))

    except Exception as e:
        logger.exception(f"Failed to create output tables, Exception: {e}")
        raise


def get_source_data_sql(pipeline_config: dict, limit: int | None = None) -> pd.DataFrame:
    try:

        SCHEMA = pipeline_config["database"]["schema"]
        ELIGIBILITY_TABLE = pipeline_config["tables"]["output"]["eligibility_table"]
        COLLABORATORS_TABLE = pipeline_config["tables"]["input"]["collaborators_table"]

        engine = get_pg_engine()
        ensure_tables_exist(pipeline_config, engine)

        query = f"""
            SELECT c.id,
                c.personal_address,
                c.personal_street_number,
                c.personal_street_name,
                c.personal_postal_code,
                c.personal_city
            FROM {SCHEMA}.{COLLABORATORS_TABLE} c
            LEFT JOIN {SCHEMA}.{ELIGIBILITY_TABLE} e
            ON c.id = e.collaborator_id
            WHERE e.collaborator_id IS NULL;
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
        logger.exception(f"Failed to load collaborators source table, Exception: {e}")
        raise



def get_processed_collaborators_data(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df["full_address"] = df.apply(create_full_address, axis=1)
        df = df.dropna(subset=['full_address'])
        df = df[['id', 'full_address']]
        return df

    except Exception as e:
        logger.exception(f"Failed process collaborators input data, Exception: {e}")
        raise



def get_collaborators(pipeline_config: dict) -> pd.DataFrame:
    df = get_source_data_sql(pipeline_config=pipeline_config)
    df = get_processed_collaborators_data(df)
    return df



def get_collaborators_geocode_data(pipeline_config: dict, limit: int | None = None) -> pd.DataFrame:
    try:
        SCHEMA = pipeline_config["database"]["schema"]
        ELIGIBILITY_TABLE = pipeline_config["tables"]["output"]["eligibility_table"]
        GEOCODE_TABLE = pipeline_config["tables"]["output"]["geocode_table"]

        engine = get_pg_engine()

        query = f"""
            SELECT g.collaborator_id,
                g.cle_interop_adr
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


def insert_collaborators_geocode_data(pipeline_config: dict, df: pd.DataFrame):
    try:
        SCHEMA = pipeline_config["database"]["schema"]
        GEOCODE_TABLE = pipeline_config["tables"]["output"]["geocode_table"]

        engine = get_pg_engine()

        with engine.begin() as conn:
            df.to_sql(
                f"{GEOCODE_TABLE}",
                conn,
                schema=f"{SCHEMA}",
                if_exists="append",
                index=False,
                method="multi",
                chunksize=1000
            )
    except Exception as e:
        logger.exception(f"Failed insert geocode data, Exception: {e}")
        raise



def insert_collaborators_eligibility_data(pipeline_config: dict, df: pd.DataFrame):
    try:
        SCHEMA = pipeline_config["database"]["schema"]
        ELIGIBILITY_TABLE = pipeline_config["tables"]["output"]["eligibility_table"]

        engine = get_pg_engine()

        with engine.begin() as conn:
            df.to_sql(
                f"{ELIGIBILITY_TABLE}",
                conn,
                schema=f"{SCHEMA}",
                if_exists="append",
                index=False,
                method="multi",
                chunksize=1000
            )
    except Exception as e:
        logger.exception(f"Failed insert eligibility data, Exception: {e}")
        raise