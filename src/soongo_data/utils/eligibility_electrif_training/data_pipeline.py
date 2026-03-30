import os
import pandas as pd
from soongo_data.utils.db import gen_engine
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.eligibility_electrif_training.sql_requests import SELECT_ALL_FEATURES_TRAINING
from sqlalchemy import text


logger = gen_logger('Elec_Eligibility_Training - Data_Load')


class DataLoader:
    """Handles data loading from various sources."""
    def __init__(self):
        self.engine = gen_engine(
            database_url=os.environ["DATABASE_URL"]
        )

    def load_data(self) -> pd.DataFrame:
        """Load data from database using SQL query."""
        try:
                with self.engine.connect() as conn:
                    df = pd.read_sql(text(SELECT_ALL_FEATURES_TRAINING), conn)
                logger.info(f"Loaded {len(df)} rows from ALL_PROCESSED_VEHICLES_SQL")
                return df
            
        except Exception as e:
            logger.error(f"Failed to load ALL_PROCESSED_VEHICLES_SQL: {e}")
            raise    