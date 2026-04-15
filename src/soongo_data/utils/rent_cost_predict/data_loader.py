import os
import pandas as pd
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.db import gen_engine
from soongo_data.utils.rent_cost_predict.sql_requests import SELECT_ALL_FEATURES_PREDICTION
from sqlalchemy import text, Table, MetaData
from sqlalchemy.orm import registry, Session


logger = gen_logger('Rent_Cost_Predict - Data_Load')


class DataLoader:
    """Handles data loading from various sources."""
    def __init__(self, config: dict):
        self.engine = gen_engine(
            database_url=os.environ["DATABASE_URL"]
        )
        self.config = config


    def load_data(self) -> pd.DataFrame:
        """Load data from database using SQL query."""
        try:
                with self.engine.connect() as conn:
                    df = pd.read_sql(text(SELECT_ALL_FEATURES_PREDICTION), conn)
                logger.info(f"Loaded {len(df)} rows from ALL_PROCESSED_SQL")
                logger.info(f"Data Shape {df.shape}")
                return df
            
        except Exception as e:
            logger.error(f"Failed to load ALL_PROCESSED_SQL : {e}")
            raise
    
    
    def insert_predictions_to_table(self, df: pd.DataFrame):
        try:
            metadata = MetaData(schema='publ')
            predictions_table = Table("vehicles_rent_cost_predictions", metadata, autoload_with=self.engine)
            mapper_registry = registry()
            PredictionMapped = type("PredictionMapped", (object,), {})
            mapper_registry.map_imperatively(PredictionMapped, predictions_table)
            records = df.to_dict(orient="records")

            with Session(self.engine) as session:
                session.bulk_insert_mappings(PredictionMapped, records)
                session.commit()

        except Exception as e:
            logger.exception(f"Failed insert retcost data, Exception: {e}")
            raise


    def delete_todays_rows(self, conn):
        """
        Delete rows from a table where created_at is today.
        """
        try:
            delete_sql = f"""
                DELETE FROM publ.vehicles_rent_cost_predictions
                WHERE created_at::date = CURRENT_DATE;
            """

            conn.execute(text(delete_sql))

        except Exception as e:
            logger.exception(f"Failed to delete today's rows from publ.vehicles_rent_cost_predictions: {e}")
            raise


    def write_results_to_db(self, df: pd.DataFrame):
        """Main function to write all results to db in a single transaction"""
        try:
            with self.engine.begin() as conn:
                self.delete_todays_rows(conn)
                self.insert_predictions_to_table(df)

        except Exception as e:
            logger.exception(f"Failed writing results to DB: {e}")
            raise