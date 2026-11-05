import os
import pandas as pd
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.db import gen_engine
from soongo_data.utils.sell_cost_predict.sql_requests import SELECT_ALL_FEATURES_PREDICTION
from sqlalchemy import text, Table, MetaData


logger = gen_logger('Sell_Cost_Predict - Data_Load')


class DataLoader:
    def __init__(self, config: dict):
        self.engine = gen_engine(
            database_url=os.environ["DATABASE_URL"]
        )
        self.config = config

    def load_data(self) -> pd.DataFrame:
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(SELECT_ALL_FEATURES_PREDICTION))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())

            logger.info(f"Loaded {len(df)} rows for sell cost prediction")
            logger.info(f"Data Shape {df.shape}")
            return df

        except Exception as e:
            logger.error(f"Failed to load ALL_PROCESSED_SQL : {e}")
            raise

    def insert_predictions_to_table(self, df: pd.DataFrame, conn):
        """Insertion dans la MÊME transaction que le DELETE (tout ou rien)."""
        try:
            table = Table("vehicles_sell_cost_predictions", MetaData(schema="publ"), autoload_with=conn)
            records = df.to_dict(orient="records")
            for i in range(0, len(records), 1000):
                conn.execute(table.insert(), records[i:i + 1000])
        except Exception as e:
            logger.exception(f"Failed insert sell cost predictions, Exception: {e}")
            raise

    def delete_todays_rows(self, conn):
        try:
            delete_sql = f"""
                DELETE FROM publ.vehicles_sell_cost_predictions
                WHERE created_at::date = CURRENT_DATE;
            """
            conn.execute(text(delete_sql))
        except Exception as e:
            logger.exception(f"Failed to delete today's rows from publ.vehicles_sell_cost_predictions: {e}")
            raise

    def write_results_to_db(self, df: pd.DataFrame):
        try:
            with self.engine.begin() as conn:
                self.delete_todays_rows(conn)
                self.insert_predictions_to_table(df, conn)
        except Exception as e:
            logger.exception(f"Failed writing results to DB: {e}")
            raise