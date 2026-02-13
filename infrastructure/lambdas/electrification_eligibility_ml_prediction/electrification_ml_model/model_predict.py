
import pandas as pd
import numpy as np
import json
import shutil
from pathlib import Path
import onnxruntime as ort
from sklearn.preprocessing import LabelEncoder, StandardScaler

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
        self.model_type = None
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


    # def load_model_artifacts(self, path: str):
    #     """Load model and related artifacts from disk."""

    #     model_path = Path(path)

    #     if not model_path.exists():
    #         raise FileNotFoundError(f"Model directory not found: {model_path}")

    #     self.model = joblib.load(model_path / "model.joblib")
    #     self.scaler = joblib.load(model_path / "scaler.joblib")
    #     self.label_encoders = joblib.load(model_path / "label_encoders.joblib")

    #     with open(model_path / "metadata.json", "r") as f:
    #         metadata = json.load(f)

    #     self.model_type = metadata.get("model_type")
    #     self.feature_names = metadata.get("feature_names")
    #     self.categorical_features = metadata.get("categorical_features")
    #     self.numeric_features = metadata.get("numeric_features")
    #     self.metrics = metadata.get("metrics")
    #     self.median_values_ = metadata.get("median_values")


    def load_model_artifacts(self, path: str):
        """Load model and related artifacts from disk (ONNX + JSON format)."""
        
        model_path = Path(path)
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_path}")
        
        # LOAD ONNX MODEL
        onnx_model_path = model_path / "model.onnx"
        if not onnx_model_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {onnx_model_path}")
        
        self.model = ort.InferenceSession(str(onnx_model_path))
        logger.info(f"Model loaded from {onnx_model_path}")
        
        # LOAD SCALER FROM JSON
        scaler_json_path = model_path / "scaler.json"
        
        if scaler_json_path.exists():
            with open(scaler_json_path, "r") as f:
                scaler_data = json.load(f)
            
            self.scaler = StandardScaler()
            if scaler_data.get("mean") is not None:
                self.scaler.mean_ = np.array(scaler_data["mean"])
            if scaler_data.get("var") is not None:
                self.scaler.var_ = np.array(scaler_data["var"])
            if scaler_data.get("scale") is not None:
                self.scaler.scale_ = np.array(scaler_data["scale"])
            self.scaler.n_features_in_ = scaler_data["n_features"]
            self.scaler.with_mean = scaler_data.get("with_mean", True)
            self.scaler.with_std = scaler_data.get("with_std", True)
            
            logger.info(f"StandardScaler loaded from {scaler_json_path}")
        else:
            self.scaler = None
            logger.info("No scaler found")
        
        # LOAD LABEL ENCODERS FROM JSON 
        encoders_path = model_path / "label_encoders.json"
        
        if encoders_path.exists():
            with open(encoders_path, "r") as f:
                encoders_data = json.load(f)
            
            self.label_encoders = {}
            for feature_name, encoder_info in encoders_data.items():
                encoder = LabelEncoder()
                encoder.classes_ = np.array(encoder_info["classes"])
                self.label_encoders[feature_name] = encoder
            
            logger.info(f"Label encoders loaded from {encoders_path}")
        else:
            self.label_encoders = None
            logger.info("No label encoders found")
        
        # LOAD METADATA
        metadata_path = model_path / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found: {metadata_path}")
        
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        self.model_type = metadata.get("model_type")
        self.feature_names = metadata.get("feature_names")
        self.categorical_features = metadata.get("categorical_features")
        self.numeric_features = metadata.get("numeric_features")
        self.metrics = metadata.get("metrics")
        self.median_values_ = metadata.get("median_values")
        
        logger.info(f"Metadata loaded from {metadata_path}")
        logger.info(f"Model artifacts loaded successfully from {model_path}")
    



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
    
    

    # def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
    #     """
    #     Predict probability scores (0-1).
        
    #     Args:
    #         X: Input features
            
    #     Returns:
    #         Array of probability scores
    #     """
    #     if self.model is None:
    #         raise ValueError("Model not trained. Call train() first.")
        
    #     X_processed = self.preprocess_features(X, self.feature_names)
    #     return self.model.predict_proba(X_processed)[:, 1]
    

    # def predict_score(self, X: pd.DataFrame) -> np.ndarray:
    #     """
    #     Predict scores (0-100).
        
    #     Args:
    #         X: Input features
            
    #     Returns:
    #         Array of scores from 0 to 100
    #     """
    #     probas = self.predict_proba(X)
    #     return probas * 100


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
        
        # Preprocess features
        X_processed = self.preprocess_features(X, self.feature_names)
        
        # Ensure X is float32 for ONNX
        X_processed = np.array(X_processed, dtype=np.float32)
        
        # Get input name from ONNX model
        input_name = self.model.get_inputs()[0].name
        
        # Run inference
        try:
            outputs = self.model.run(None, {input_name: X_processed})
        except Exception as e:
            logger.error(f"ONNX inference error: {str(e)}")
            raise
        
        # Extract probabilities based on output format
        if len(outputs) > 1:
            # Classification model with separate label and probability outputs
            probabilities = outputs[1]
            
            # Convert to numpy array if needed
            if not isinstance(probabilities, np.ndarray):
                probabilities = np.array(probabilities)
            
            # Handle different shapes
            if probabilities.ndim == 1:
                # Single probability per sample
                return probabilities
            elif probabilities.ndim == 2:
                if probabilities.shape[1] == 1:
                    # Single column of probabilities
                    return probabilities.flatten()
                elif probabilities.shape[1] >= 2:
                    # Multiple classes - return probability of positive class (index 1)
                    return probabilities[:, 1]
            
            return probabilities.flatten()
        
        else:
            # Single output
            predictions = outputs[0]
            
            if not isinstance(predictions, np.ndarray):
                predictions = np.array(predictions)
            
            return predictions.flatten()
        

    def predict_score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict scores (0-100).
        
        Args:
            X: Input features
            
        Returns:
            Array of scores from 0 to 100
        """
        
        probas = self.predict_proba(X)
        
        # Ensure probabilities are in valid range
        probas = np.clip(probas, 0, 1)
        
        return probas * 100
