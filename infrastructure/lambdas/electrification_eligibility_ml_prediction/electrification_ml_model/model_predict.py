
import pandas as pd
import numpy as np
import joblib
import json
import shutil
from pathlib import Path
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.aws import pull_folder_from_s3, get_most_recent_s3_model_name


logger = gen_logger('Model_PREDICITON')

class ElectrificationModel:
    """Handles model training and prediction for electrification eligibility."""
    
    def __init__(self, config):
        """
        Initialize the model.
        
        Args:
            model_type: Type of model ('random_forest', 'gradient_boosting', 'logistic')
        """
        self.config = config
        self.model_type = self.config.get('model_type', 'random_forest')
        self.model = None
        self.scaler = None
        self.label_encoders = {}

        self.feature_names = None
        self.categorical_features = []
        self.numeric_features = []
        self.metrics = {}
        self.results = {}
        
        self.model_local_path = self.load_model_from_s3()
        self.load_model_artifacts(self.model_local_path)
    

    def load_model_from_s3(self):
        last_model_name = get_most_recent_s3_model_name(
            bucket_name=self.config['bucket_name'],
            prefix=self.config['model_folder']
        )

        models_dir = Path(self.config["models_dir"])
        local_model_dir = models_dir / last_model_name

        pull_folder_from_s3(
            s3_prefix=f"{self.config['model_folder']}/{last_model_name}",
            local_dir=str(local_model_dir),
        )
        return local_model_dir


    def load_model_artifacts(self, path: str):
        """Load model and related artifacts from disk."""

        model_path = Path(path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_path}")

        self.model = joblib.load(model_path / "model.joblib")
        self.scaler = joblib.load(model_path / "scaler.joblib")
        self.label_encoders = joblib.load(model_path / "label_encoders.joblib")

        with open(model_path / "metadata.json", "r") as f:
            metadata = json.load(f)

        self.model_type = metadata.get("model_type")
        self.feature_names = metadata.get("feature_names")
        self.categorical_features = metadata.get("categorical_features")
        self.numeric_features = metadata.get("numeric_features")
        self.metrics = metadata.get("metrics")
        self.median_values_ = metadata.get("median_values")
    

    def remove_model_folder_from_local(self):
        local_folder = Path(self.config['models_dir'])
        try:
            shutil.rmtree(local_folder)
        except Exception as e:
            print(f"Failed to delete folder {local_folder}: {e}")



    def preprocess_features(
        self, 
        df: pd.DataFrame, 
        feature_list: list,
    ) -> np.ndarray:
        df = df.copy()
        
        # Separate numeric and categorical features
        
        self.categorical_features = df[feature_list].select_dtypes(
                include=['object', 'category']
            ).columns.tolist()
        
        self.numeric_features = [
            f for f in feature_list if f not in self.categorical_features
        ]
        
        # Handle categorical features
        for col in self.categorical_features:
            if col in df.columns:
                # Handle unseen categories by replacing with the most frequent seen category
                filled_col = df[col].astype(str).fillna('MISSING')
                
                # Get valid classes from encoder
                valid_classes = set(self.label_encoders[col].classes_)
                
                # Replace unseen values with first valid class (typically 'MISSING' or most common)
                default_class = self.label_encoders[col].classes_[0]
                filled_col = filled_col.apply(
                    lambda x: x if x in valid_classes else default_class
                )
                df[col] = self.label_encoders[col].transform(filled_col)
        
        # Handle numeric features
        for col in self.numeric_features:
            if col in df.columns:
                # Fill missing with median
                df[col] = df[col].fillna(self.median_values_.get(col, 0))
        
        # Convert to matrix
        X = df[feature_list].values
        
        # Handle infinite and extremely large values
        logger.info(f"Checking features for infinite/extreme values...")
        
        # Replace inf with NaN first
        X = np.where(np.isinf(X), np.nan, X)
        
        # Handle NaN values before scaling
        col_means = np.nanmean(X, axis=0)
        col_stds = np.nanstd(X, axis=0)
        
        for i, col_idx in enumerate(feature_list):
            col_mean = col_means[i]
            col_std = col_stds[i]
            
            # Replace NaN with mean
            X[np.isnan(X[:, i]), i] = col_mean if not np.isnan(col_mean) else 0
            
            # Clip extreme values (beyond 5 standard deviations)
            if not np.isnan(col_std) and col_std > 0:
                lower_bound = col_mean - 5 * col_std
                upper_bound = col_mean + 5 * col_std
                X[:, i] = np.clip(X[:, i], lower_bound, upper_bound)
        
        # Final check for any remaining NaN or inf
        if np.any(~np.isfinite(X)):
            logger.warning("Still found non-finite values after cleaning, replacing with 0")
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Scale features
        X = self.scaler.transform(X)
        
        return X
    
    

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict probability scores (0-1).
        
        Args:
            X: Input features
            
        Returns:
            Array of probability scores
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        X_processed = self.preprocess_features(X, self.feature_names)
        return self.model.predict_proba(X_processed)[:, 1]
    

    def predict_score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict scores (0-100).
        
        Args:
            X: Input features
            
        Returns:
            Array of scores from 0 to 100
        """
        probas = self.predict_proba(X)
        return probas * 100
