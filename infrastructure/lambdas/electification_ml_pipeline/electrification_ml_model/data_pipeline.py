
import pandas as pd
from typing import Dict, List
from soongo_data.utils.db import gen_engine
from soongo_data.utils.logging_utils import gen_logger
from electification_ml_pipeline.electrification_ml_model.sql_requests import queries
from sqlalchemy import text


logger = gen_logger('Data_Load')



class DataPreprocessor:
    """Preprocesses raw data for feature engineering."""
     
    @staticmethod
    def handle_invalid_mileage(mileage_df: pd.DataFrame) -> pd.DataFrame:

        df = mileage_df.copy()
        
        # Convert date column
        df['mileage_date'] = pd.to_datetime(df['mileage_date'], errors='coerce')
        
        # Remove negative mileages
        if 'mileage' in df.columns:
            before = len(df)
            df = df[df['mileage'] >= 0]
            logger.info(f"Removed {before - len(df)} negative mileage readings")
        
        # Remove implausible daily increases (>2000 km)
        df = df.sort_values(['vehicle_id', 'mileage_date'])
        df['mileage_diff'] = df.groupby('vehicle_id')['mileage'].diff()
        
        before = len(df)
        df = df[(df['mileage_diff'].isna()) | (df['mileage_diff'] <= 2000)]
        logger.info(f"Removed {before - len(df)} implausible mileage increases")
        
        df = df.drop('mileage_diff', axis=1)
            
        return df
    

    def preprocess_tables(self, tables: dict) -> dict:

        # Handle invalid mileage
        if 'mileages' in tables:
            tables['mileages'] = self.handle_invalid_mileage(
                tables['mileages']
            )
        
        # Standardize dates
        date_columns_map = {
            'vehicles': ['lease_start_date', 'lease_end_date', 'entry_into_fleet_date'],
            'mileages': ['mileage_date'],
            'expenses': ['billing_date', 'transaction_start_date', 'transaction_end_date']
        }
        
        for table_name, date_cols in date_columns_map.items():
            if table_name in tables:
                tables[table_name] = self.standardize_dates(
                    tables[table_name], date_cols
                )
        
        return tables
    

    @staticmethod
    def standardize_dates(df: pd.DataFrame, date_columns: List[str]) -> pd.DataFrame:

        df = df.copy()
        
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                logger.info(f"Converted {col} to datetime")
        
        return df




class DataLoader:
    """Handles data loading from various sources."""
    def __init__(self):
        self.engine = gen_engine()
        self.preprocessor = DataPreprocessor()
    

    def create_vehicles_current_collaborators_view(self) -> Dict[str, pd.DataFrame]:
        try:
            # Create the view
            with self.engine.begin() as conn:
                conn.execute(text(queries['vehicles_current_collaborator']))
                logger.info("Created vehicles_with_current_collaborator view")
        except Exception as e:
            logger.error(f"Could not create view (may already exist): {e}")


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
    

    def load_all_tables(self) -> Dict[str, pd.DataFrame]:
        """Load all tables from SQL database."""
        
        self.create_vehicles_current_collaborators_view()

        tables = {}
        # Load each table
        queries.pop('vehicles_current_collaborator')
        for table_name, query in queries.items():
            try:
                tables[table_name] = self.load_from_sql(query, table_name)
            except Exception as e:
                logger.error(f"Could not load {table_name}: {e}")
        
        return self.preprocessor.preprocess_tables(tables)





    


