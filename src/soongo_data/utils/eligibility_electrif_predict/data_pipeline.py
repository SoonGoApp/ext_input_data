
import os
import pandas as pd
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.db import gen_engine
from soongo_data.utils.eligibility_electrif_predict.sql_requests import SELECT_ALL_FEATURES_PREDICTION
from sqlalchemy import text, Table, MetaData, insert


logger = gen_logger('Data_Load')


class DataLoader:
    """Handles data loading from various sources."""
    def __init__(self, config: dict):
        self.engine = gen_engine(
            database_url=os.environ["DATABASE_URL"]
        )
        self.config = config
        self.output_table = self.config['scores_table']
        self.output_mv = self.config['scores_m_view']
        self.schema = self.config['schema']

    def load_data(self) -> pd.DataFrame:
        """Load data from database using SQL query."""
        try:
                with self.engine.connect() as conn:
                    df = pd.read_sql(text(SELECT_ALL_FEATURES_PREDICTION), conn)
                logger.info(f"Loaded {len(df)} rows from ALL_PROCESSED_VEHICLES_SQL")
                logger.info(f"Data Shape {df.shape}")
                return df
            
        except Exception as e:
            logger.error(f"Failed to load ALL_PROCESSED_VEHICLES_SQL : {e}")
            raise
    

    def ensure_table_exist(self, conn):
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.{self.output_table} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                vehicle_id UUID NOT NULL,
                score DOUBLE PRECISION,
                model TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """))


    def delete_todays_rows(self, conn):
        delete_sql = f"""
            DELETE FROM {self.schema}.{self.output_table}
            WHERE created_at::date = CURRENT_DATE;
        """
        conn.execute(text(delete_sql))
    

    def insert_predictions_to_table(self, conn, df: pd.DataFrame):
        metadata = MetaData(schema=self.schema)
        table = Table(self.output_table, metadata, autoload_with=conn)
        records = df.to_dict(orient="records")
        stmt = insert(table)
        conn.execute(stmt, records)

    
    def refresh_today_materialized_view(self, conn):
        conn.execute(
            text(f"DROP MATERIALIZED VIEW IF EXISTS {self.schema}.{self.output_mv};")
        )

        conn.execute(
            text(f"""
                CREATE MATERIALIZED VIEW {self.schema}.{self.output_mv} AS
                SELECT *
                FROM {self.schema}.{self.output_table}
                WHERE created_at::date = CURRENT_DATE;
            """)
        )


    def write_results_to_db(self, df: pd.DataFrame):
        """Main function to write all results to db in a single transaction"""
        
        try:
            with self.engine.begin() as conn:
                self.ensure_table_exist(conn)
                self.delete_todays_rows(conn)
                self.insert_predictions_to_table(conn, df)
                self.refresh_today_materialized_view(conn)

        except Exception as e:
            logger.exception(f"Failed writing results to DB: {e}")
            raise