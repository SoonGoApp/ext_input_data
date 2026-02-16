
import os
import pandas as pd
from soongo_data.utils.db import gen_engine
from soongo_data.utils.logging_utils import gen_logger
from electrification_ml_model.sql_requests import SELECT_ALL_FEATURES_TRAINING
from sqlalchemy import text


logger = gen_logger('Data_Load')


class DataLoader:
    """Handles data loading from various sources."""
    def __init__(self):
        self.engine = gen_engine(
            database_url=os.environ["DATABASE_URL"]
        )

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
        df = self.load_from_sql(SELECT_ALL_FEATURES_TRAINING, "ALL_DATA_preprocessed")
        logger.info("Traget Distribution ")
        print(df['target'].value_counts())
        return df