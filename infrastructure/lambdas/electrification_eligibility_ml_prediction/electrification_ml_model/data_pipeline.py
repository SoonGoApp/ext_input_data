
import pandas as pd
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.db import gen_engine
from electrification_ml_model.sql_requests import SELECT_ALL_FEATURES_PREDICTION
from sqlalchemy import text, Table, MetaData, insert


logger = gen_logger('Data_Load')



class DataLoader:
    """Handles data loading from various sources."""
    def __init__(self):
        self.engine = gen_engine()
        self.output_table = "vehicles_electrification_eligibility_score"
        self.output_mv = "vehicles_electrification_eligibility_score_mv"
        self.schema = "publ"



    def load_from_sql(self, query: str, table_name: str) -> pd.DataFrame:
        """Load data from database using SQL query."""
        try:
                with self.engine.connect() as conn:
                    df = pd.read_sql(text(query), conn)
                logger.info(f"Loaded {len(df)} rows from {table_name}")
                return df
            
        except Exception as e:
            logger.error(f"Failed to load {table_name}: {e}")
            raise
    

    def load_data(self) -> pd.DataFrame:
        df = self.load_from_sql(SELECT_ALL_FEATURES_PREDICTION, "ALL_DATA_preprocessed")
        logger.info(f"Data Shape {df.shape}")

        return df
    
    

    def insert_predictions_to_table(self, df: pd.DataFrame):
        try:
            metadata = MetaData(schema=self.schema)
            table = Table(self.output_table, metadata, autoload_with=self.engine)

            records = df.to_dict(orient="records")

            with self.engine.begin() as conn:
                
                stmt = insert(table)
                conn.execute(stmt, records)

        except Exception as e:
            logger.exception(f"Failed insert/update eligibility data, Exception: {e}")
            raise


    def refresh_today_materialized_view(self):
        """
        Create or replace a materialized view with today's eligibility scores.
        """
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(f"DROP MATERIALIZED VIEW IF EXISTS {self.schema}.{self.output_mv};")
                )
                conn.execute(
                    text(rf"""
                        CREATE MATERIALIZED VIEW {self.schema}.{self.output_mv} AS
                            SELECT *
                            FROM {self.schema}.{self.output_table}
                            WHERE created_at::date = CURRENT_DATE;
                    """)
                )

        except Exception as e:
            logger.exception(f"Failed to refresh materialized view: {e}")
            raise


    def ensure_table_exist(self):
        try:
            with self.engine.begin() as conn:

                conn.execute(text(rf"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.{self.output_table} (
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        vehicle_id UUID NOT NULL,
                        score DOUBLE PRECISION,
                        model TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """))
        
        except Exception as e:
            logger.exception(f"Failed to create model prediction output table, Exception: {e}")
            raise


    def delete_todays_rows(self):
        """
        Delete rows from a table where created_at is today.
        """
        try:
            delete_sql = f"""
                DELETE FROM {self.schema}.{self.output_table}
                WHERE created_at::date = CURRENT_DATE;
            """
            with self.engine.begin() as conn:
                conn.execute(text(delete_sql))
            print(f"Deleted today's rows from {self.schema}.{self.output_table}")
        except Exception as e:
            logger.exception(f"Failed to delete today's rows from {self.schema}.{self.output_table}: {e}")
            raise



    def write_results_to_db(self, df: pd.DataFrame):
        """Main function to write all results to db"""
        self.ensure_table_exist()
        self.delete_todays_rows()
        self.insert_predictions_to_table(df)
        self.refresh_today_materialized_view()