import pandas as pd
import numpy as np
from typing import List
from soongo_data.utils.logging_utils import gen_logger

logger = gen_logger('Feature_Engineering')



class FeatureEngineer:
    """Handles feature engineering for electrification eligibility prediction."""
    
    def __init__(self, config):
        self.feature_metadata = {}
        self.config = config


    def create_target_variable(self, mileage_df: pd.DataFrame, vehicle_df: pd.DataFrame, threshold_km: float = 300.0) -> pd.DataFrame:

        logger.info("Creating target variable...")
        
        # Calculate differences
        mileages_copy = mileage_df.copy()
        mileages_copy['prev_mileage'] = mileages_copy.groupby('vehicle_id')['mileage'].shift(1)
        mileages_copy['prev_date'] = mileages_copy.groupby('vehicle_id')['mileage_date'].shift(1)

        # Calculate days and distance between readings
        mileages_copy['days_diff'] = (
            mileages_copy['mileage_date'] - mileages_copy['prev_date']
        ).dt.days

        mileages_copy['km_diff'] = mileages_copy['mileage'] - mileages_copy['prev_mileage']

        # Calculate daily km (average per day between readings)
        mileages_copy['daily_km'] = np.where(
            (mileages_copy['days_diff'] > 0) & (mileages_copy['km_diff'] > 0),
            mileages_copy['km_diff'] / mileages_copy['days_diff'],
            np.nan
        )

        # Remove outliers (daily km > 2000)
        mileages_copy.loc[mileages_copy['daily_km'] > 2000, 'daily_km'] = np.nan

        # Create target_mileage = 1 if vehicle ever drives > THRESHOLD_KM daily km, else 0
        target_mileage = (
            mileages_copy
            .groupby('vehicle_id')['daily_km']
            .max()
            .fillna(0)
            .gt(threshold_km)
            .astype(int)
            .reset_index(name='target_mileage')
        )

        # Identify electric vehicles (case-insensitive matching)
        vehicle_df['is_electric'] = (
            vehicle_df['energy']
            .fillna('')
            .str.upper()
            .isin(['ELECTRIC'])
            .astype(int)
        )

        vehicle_df['vehicle_id'] = vehicle_df['id']

        # Merge target_mileage and electric flag on vehicle_id
        target_df = target_mileage.merge(
            vehicle_df[['vehicle_id', 'is_electric']],
            on='vehicle_id',
            how='left'
        )

        # Assume non-electric if no info
        target_df['is_electric'] = target_df['is_electric'].fillna(0).astype(int)

        # Final target: 1 if electric or drives > threshold daily km, else 0
        target_df['target'] = ((target_df['target_mileage'] == 1) | (target_df['is_electric'] == 1)).astype(int)

        # Keep only vehicle_id and target columns
        target_df = target_df[['vehicle_id', 'target']]
        
        logger.info(f"Target distribution: {target_df['target'].value_counts().to_dict()}")
        logger.info(f"Total vehicles in target: {len(target_df)}")
        
        return target_df
    

    def extract_vehicle_features(self, vehicle_df: pd.DataFrame) -> pd.DataFrame:
        """Extract features from vehicle table."""
        logger.info("Extracting vehicle features...")
        
        features = vehicle_df.copy()
        
        # Lease features
        if 'lease_start_date' in features.columns:
            features['lease_start_date'] = pd.to_datetime(features['lease_start_date'], errors='coerce')
            features['lease_end_date'] = pd.to_datetime(features['lease_end_date'], errors='coerce')
            features['lease_duration_months'] = (
                (features['lease_end_date'] - features['lease_start_date']).dt.days / 30.44
            )
        
        # Fuel consumption
        features['fuel_consumption'] = pd.to_numeric(
            features['theoretical_fuel_consumption'], errors='coerce'
        )
        
        # CO2 emissions
        features['co2_emissions'] = pd.to_numeric(features['co2_per_km'], errors='coerce')
        
        # Vehicle characteristics
        features['fiscal_power_num'] = pd.to_numeric(features['fiscal_power'], errors='coerce')
        features['motor_power_num'] = pd.to_numeric(features['motor_power'], errors='coerce')
        features['seat_count_num'] = pd.to_numeric(features['seat_count'], errors='coerce')
        
        # Energy type (categorical)
        features['energy_type'] = features['energy'].fillna('UNKNOWN')
        
        # Assignment and fiscal type
        features['assignment_type'] = features['assignment_type'].fillna('UNKNOWN')
        features['fiscal_type'] = features['fiscal_type'].fillna('UNKNOWN')
        
        # Vehicle status
        features['is_active'] = (features['vehicle_status'] == 'ACTIVE').astype(int)
        
        return features[['id'] + [col for col in features.columns if col != 'id']]
    



    def extract_mileage_features(self, mileage_primitive_df: pd.DataFrame) -> pd.DataFrame:
        """Extract aggregated mileage features per vehicle."""
        logger.info("Extracting mileage features...")
        
        agg_features = mileage_primitive_df.groupby('vehicle_id').agg({
            'mileage_driven': ['mean', 'std', 'max', 'min', 'sum'],
            'mileage_month': 'count',
            'first_days_diff': 'mean',
            'next_days_diff': 'mean'
        }).reset_index()
        
        # Flatten column names
        agg_features.columns = ['vehicle_id'] + [
            f'{col}_{stat}' for col, stat in agg_features.columns[1:]
        ]
        
        # Additional features
        agg_features['mileage_variability'] = (
            agg_features['mileage_driven_std'] / 
            (agg_features['mileage_driven_mean'] + 1)
        )
        
        agg_features['avg_days_between_readings'] = (
            agg_features['first_days_diff_mean'] + agg_features['next_days_diff_mean']
        ) / 2
        
        return agg_features
    


    def extract_expense_features(
        self, 
        expense_primitive_df: pd.DataFrame,
        expenses_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Extract expense-related features."""
        logger.info("Extracting expense features...")

        expense_agg = expense_primitive_df.groupby('vehicle_id').agg({
            'amount_tax_exc': ['sum', 'mean', 'std'],
            'net_amount': ['sum', 'mean'],
            'quantity': 'sum',
            'co2_usage_scope_1': 'sum',
            'co2_usage_scope_2': 'sum',
            'co2_usage_scope_3': 'sum',
            'month_start': 'nunique'
        }).reset_index()

        expense_agg.columns = ['vehicle_id'] + [
            f'expense_{col}_{stat}' for col, stat in expense_agg.columns[1:]
        ]

        if 'soongo_category' in expenses_df.columns:
            fuel_expenses = expenses_df[
                expenses_df['soongo_category']
                .str.contains('fuel|carburant', case=False, na=False)
            ].copy()

            fuel_agg = fuel_expenses.groupby('vehicle_id').agg({
                'amount_tax_exc': ['sum', 'mean', 'count'],
                'quantity': 'sum'
            }).reset_index()

            fuel_agg.columns = ['vehicle_id'] + [
                f'fuel_{col}_{stat}' for col, stat in fuel_agg.columns[1:]
            ]

            expense_agg = expense_agg.merge(
                fuel_agg,
                on='vehicle_id',
                how='left'
            )

        if not fuel_expenses.empty and 'billing_date' in fuel_expenses.columns:
            fuel_expenses['billing_date'] = pd.to_datetime(
                fuel_expenses['billing_date'], utc=True, errors='coerce'
            )

            fuel_expenses = fuel_expenses.sort_values(
                ['vehicle_id', 'billing_date']
            )

            fuel_expenses['prev_billing_date'] = (
                fuel_expenses.groupby('vehicle_id')['billing_date'].shift(1)
            )

            fuel_expenses['days_between_refuels'] = (
                fuel_expenses['billing_date'] -
                fuel_expenses['prev_billing_date']
            ).dt.days

            SHORT_REFILL_THRESHOLD = 3

            fuel_time_agg = fuel_expenses.groupby('vehicle_id').agg(
                fuel_refill_count=('billing_date', 'count'),
                fuel_days_between_mean=('days_between_refuels', 'mean'),
                fuel_days_between_min=('days_between_refuels', 'min'),
                fuel_refill_close_ratio=(
                    'days_between_refuels',
                    lambda x: (x <= SHORT_REFILL_THRESHOLD).mean()
                )
            ).reset_index()

            expense_agg = expense_agg.merge(
                fuel_time_agg,
                on='vehicle_id',
                how='left'
            )

        toll_df = expenses_df[
            expenses_df['product']
            .str.contains('peage|péage|toll|autoroute', case=False, na=False)
        ]

        toll_agg = toll_df.groupby('vehicle_id').agg(
            toll_total_amount=('amount_tax_exc', 'sum'),
            toll_max_amount=('amount_tax_exc', 'max'),
            toll_mean_amount=('amount_tax_exc', 'mean'),
            toll_count=('amount_tax_exc', 'count')
        ).reset_index()

        expense_agg = expense_agg.merge(
            toll_agg,
            on='vehicle_id',
            how='left'
        )

        expense_agg['monthly_expense_avg'] = (
            expense_agg['expense_amount_tax_exc_sum'] /
            (expense_agg['expense_month_start_nunique'] + 1)
        )

        expense_agg = expense_agg.fillna(0)

        logger.info(f"Final expense features: {expense_agg.columns.tolist()}")

        return expense_agg

    
    
    def engineer_features(
        self,
        vehicle_df: pd.DataFrame,
        mileage_df: pd.DataFrame,
        mileage_primitive_df: pd.DataFrame,
        expense_primitive_df: pd.DataFrame,
        expenses_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Main method to engineer all features.
        
        Returns:
            DataFrame with vehicle_id and all engineered features
        """
        logger.info("Starting feature engineering pipeline...")
        
        # Extract features from each source
        vehicle_features = self.extract_vehicle_features(vehicle_df)
        mileage_features = self.extract_mileage_features(mileage_primitive_df)
        expense_features = self.extract_expense_features(expense_primitive_df, expenses_df)

        
        # Merge all features
        features = vehicle_features.merge(
            mileage_features, 
            left_on='id', 
            right_on='vehicle_id', 
            how='left'
        )
        
        features = features.merge(expense_features, on='vehicle_id', how='left')
        
        # Use vehicle_id as primary key
        features['vehicle_id'] = features['id']
        
        # Fill remaining NaN values with 0
        numeric_cols = features.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if features[col].isnull().any():
                features[col] = features[col].fillna(features[col].median())
        
        logger.info(f"Feature engineering complete. Shape: {features.shape}")
        return features
    


    def select_features(self, features_df: pd.DataFrame) -> List[str]:
        """
        Select final features for modeling.
        
        Returns:
            List of feature column names
        """

        numeric_features = [
        #Vehicle
        'vehicle_age_years',
        'lease_duration_months',
        'fiscal_power_num',
        'motor_power_num',
        #Global expense behavior
        'expense_amount_tax_exc_sum',
        #Average expense amount per transaction
        'expense_amount_tax_exc_mean',
        'expense_amount_tax_exc_std',
        'monthly_expense_avg',
        #Fuel behavior
        'fuel_amount_tax_exc_sum',
        'fuel_amount_tax_exc_mean',
        'fuel_amount_tax_exc_count',
        'fuel_quantity_sum',
        'fuel_refill_count',
        'fuel_days_between_mean',
        'fuel_days_between_min',
        'fuel_refill_close_ratio',

        # péage behavior
        'toll_total_amount',
        'toll_max_amount',
        'toll_mean_amount',
        'toll_count'
    ]
        
        # Categorical features
        categorical_features = [
            'energy_type', 'assignment_type', 'fiscal_type', 'is_active'
        ]
        
        # Filter to existing columns
        final_df = [
            f for f in numeric_features + categorical_features 
            if f in features_df.columns
        ]
        
        logger.info(f"Selected {len(final_df)} features for modeling")
        return final_df
    


    def create_features(self, tables: dict) -> pd.DataFrame:

        logger.info("\n" + "="*60)
        logger.info("STEP 3: FEATURE ENGINEERING")
        logger.info("="*60)
        
        # Engineer features
        features = self.engineer_features(
            vehicle_df=tables.get('vehicles'),
            mileage_df=tables.get('mileages'),
            mileage_primitive_df=tables.get('mileage_primitive_view'),
            expense_primitive_df=tables.get('expense_primitive_view'),
            expenses_df=tables.get('expenses')
        )
            
        return features
    
    
    def create_target(self, tables: dict) -> pd.DataFrame:

        logger.info("\n" + "="*60)
        logger.info("STEP 4: TARGET VARIABLE CREATION")
        logger.info("="*60)
        
        threshold_km = self.config.get('target_threshold_km', 300.0)
        
        target = self.create_target_variable(
            tables.get('mileages'),
            tables.get('vehicles'),
            threshold_km=threshold_km
        )

        return target