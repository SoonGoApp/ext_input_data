
import pandas as pd
import numpy as np
import joblib
import json
import yaml
import shutil
from typing import Dict, Tuple, Optional, Any
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from sklearn.metrics import (
    roc_auc_score, precision_recall_curve, classification_report,
    confusion_matrix, average_precision_score, roc_curve, auc
)

from datetime import datetime
from pathlib import Path
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.aws import push_folder_to_s3


logger = gen_logger('Model_Training')


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
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.feature_names = None
        self.categorical_features = []
        self.numeric_features = []
        self.metrics = {}
        self.results = {}
        
        
    def _get_model(self) -> Any:
        """Get the appropriate model based on model_type."""
        models = {
            'random_forest': RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                min_samples_split=20,
                min_samples_leaf=10,
                class_weight='balanced',
                random_state=42,
                n_jobs=-1
            ),
            'gradient_boosting': GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                min_samples_split=20,
                min_samples_leaf=10,
                random_state=42
            ),
            'logistic': LogisticRegression(
                class_weight='balanced',
                random_state=42,
                max_iter=1000
            ),
            'xgboost': XGBClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                min_child_weight=10,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=1,
                random_state=42,
                n_jobs=-1,
                eval_metric='logloss'
            )
        }
        return models.get(self.model_type, models['random_forest'])
    
    def preprocess_features(
        self, 
        df: pd.DataFrame, 
        feature_list: list,
        fit: bool = True
    ) -> np.ndarray:
        df = df.copy()
        
        # Separate numeric and categorical features
        if fit:
            self.categorical_features = df[feature_list].select_dtypes(
                include=['object', 'category']
            ).columns.tolist()
            self.numeric_features = [
                f for f in feature_list if f not in self.categorical_features
            ]
        
        # Handle categorical features
        for col in self.categorical_features:
            if col in df.columns:
                if fit:
                    self.label_encoders[col] = LabelEncoder()
                    # Fill NaN with MISSING before encoding
                    filled_col = df[col].astype(str).fillna('MISSING')
                    self.label_encoders[col].fit(filled_col)
                    df[col] = self.label_encoders[col].transform(filled_col)
                else:
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
                if fit:
                    median_val = df[col].median()
                    self.median_values_ = getattr(self, 'median_values_', {})
                    self.median_values_[col] = median_val
                    df[col] = df[col].fillna(median_val)
                else:
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
        if fit:
            X = self.scaler.fit_transform(X)
        else:
            X = self.scaler.transform(X)
        
        return X
    


    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        feature_list: Optional[list] = None
    ) -> Dict[str, float]:
        logger.info("Starting model training...")
        
        if feature_list is None:
            feature_list = X_train.columns.tolist()
        
        self.feature_names = feature_list
        
        # Preprocess features
        X_train_processed = self.preprocess_features(X_train, feature_list, fit=True)
        
        # Initialize model
        base_model = self._get_model()
        
        # Cross-validation on training set
        logger.info("Performing 5-fold cross-validation...")
        cv_auc_scores = cross_val_score(
            base_model, X_train_processed, y_train, 
            cv=5, scoring='roc_auc', n_jobs=-1
        )
        
        cv_ap_scores = cross_val_score(
            base_model, X_train_processed, y_train, 
            cv=5, scoring='average_precision', n_jobs=-1
        )

        metrics = {
            'cv_auc_mean': cv_auc_scores.mean(),
            'cv_auc_std': cv_auc_scores.std(),
            'cv_ap_mean': cv_ap_scores.mean(),
            'cv_ap_std': cv_ap_scores.std()
        }
        
        logger.info(f"CV AUC: {metrics['cv_auc_mean']:.4f} (+/- {metrics['cv_auc_std']:.4f})")
        logger.info(f"CV AP: {metrics['cv_ap_mean']:.4f} (+/- {metrics['cv_ap_std']:.4f})")
        
        # Train final model on full training set
        logger.info("Training final model on full training set...")
        self.model = self._get_model()
        self.model.fit(X_train_processed, y_train)
        
        # Calculate training metrics
        train_pred = self.model.predict_proba(X_train_processed)[:, 1]
        train_auc = roc_auc_score(y_train, train_pred)
        train_ap = average_precision_score(y_train, train_pred)
        
        metrics['train_auc'] = train_auc
        metrics['train_average_precision'] = train_ap
        
        # Validation metrics if provided
        if X_val is not None and y_val is not None:
            X_val_processed = self.preprocess_features(X_val, feature_list, fit=False)
            val_pred = self.model.predict_proba(X_val_processed)[:, 1]
            val_auc = roc_auc_score(y_val, val_pred)
            val_ap = average_precision_score(y_val, val_pred)
            
            metrics['val_auc'] = val_auc
            metrics['val_average_precision'] = val_ap
            
            logger.info(f"Validation AUC: {val_auc:.4f}, AP: {val_ap:.4f}")
        
        self.metrics = metrics
        
        logger.info(f"Training complete. Train AUC: {train_auc:.4f}")
        
        return metrics
    

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
        
        X_processed = self.preprocess_features(X, self.feature_names, fit=False)
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
    
    def get_feature_importance(self) -> pd.DataFrame:
        """
        Get feature importance scores.
        
        Returns:
            DataFrame with features and their importance scores
        """
        if self.model is None:
            raise ValueError("Model not trained.")
        
        if hasattr(self.model, 'feature_importances_'):
            importance = pd.DataFrame({
                'feature': self.feature_names,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            return importance
        else:
            logger.warning("Model does not support feature importance.")
            return pd.DataFrame()
    
    def evaluate(
        self, 
        X_test: pd.DataFrame, 
        y_test: pd.Series,
        threshold: float = 0.50
    ) -> Dict[str, Any]:
        logger.info("Evaluating model...")
        
        # Get predictions
        y_pred_proba = self.predict_proba(X_test)
        y_pred = (y_pred_proba >= threshold).astype(int)
        
        # Calculate metrics
        metrics = {
            'test_auc': roc_auc_score(y_test, y_pred_proba),
            'test_average_precision': average_precision_score(y_test, y_pred_proba),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'classification_report': classification_report(y_test, y_pred, output_dict=True)
        }
        
        logger.info(f"Test AUC: {metrics['test_auc']:.4f}")
        logger.info(f"Test AP: {metrics['test_average_precision']:.4f}")
        
        return metrics
    


    def save_model(self, path: str, results: dict, config: dict):

        """Save model and preprocessors to disk (secure format)."""

        model_path = Path(path)
        model_path.mkdir(parents=True, exist_ok=True)

        joblib.dump(self.model, model_path / "model.joblib")
        joblib.dump(self.scaler, model_path / "scaler.joblib")
        joblib.dump(self.label_encoders, model_path / "label_encoders.joblib")

        median_values_clean = {}
        for key, value in getattr(self, "median_values_", {}).items():
            if isinstance(value, float):
                if np.isnan(value) or np.isinf(value):
                    median_values_clean[key] = None
                else:
                    median_values_clean[key] = float(value)
            else:
                median_values_clean[key] = value

        metrics_clean = {}
        for key, value in self.metrics.items():
            if isinstance(value, float):
                if np.isnan(value) or np.isinf(value):
                    metrics_clean[key] = None
                else:
                    metrics_clean[key] = float(value)
            elif isinstance(value, (dict, list)):
                metrics_clean[key] = value
            else:
                metrics_clean[key] = value

        metadata = {
            "model_type": self.model_type,
            "feature_names": self.feature_names,
            "categorical_features": self.categorical_features,
            "numeric_features": self.numeric_features,
            "metrics": metrics_clean,
            "median_values": median_values_clean,
            "trained_at": datetime.now().isoformat(),
        }

        with open(model_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Model saved to {model_path}")


        # Save results
        results_path = model_path / 'training_results.json'
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Training results saved to {results_path}")
        
        # Save config used
        config_path = model_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        logger.info(f"Configuration saved to {config_path}")

        push_folder_to_s3(
            local_dir=model_path,
            s3_prefix=model_path,
            bucket_name=config["bucket_name"]
        )

        self.remove_model_folder_from_local()

        logger.info(f"Model uploaded to {config["bucket_name"]}")
    


    def prepare_train_test_split(
        self,
        features_df: pd.DataFrame,
        target_df: pd.DataFrame,
        test_size: float = 0.3,
        random_state: int = 42
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:

        logger.info(f"target_df shape: {target_df.shape}" )
        logger.info(f"features_df shape: {features_df.shape}" )
        # Merge features and target
        data = features_df.merge(target_df, on='vehicle_id', how='inner')
        
        # Remove vehicle_id from features
        feature_cols = [col for col in features_df.columns if col != 'vehicle_id']
        X = data[feature_cols]
        y = data['target']
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )
        
        logger.info(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
        logger.info(f"Train target distribution: {y_train.value_counts().to_dict()}")
        logger.info(f"Test target distribution: {y_test.value_counts().to_dict()}")
        
        return X_train, X_test, y_train, y_test


    def train_model(
            self, 
            features: pd.DataFrame, 
            target: pd.DataFrame
        ):

        logger.info("\n" + "="*60)
        logger.info("STEP 5: MODEL TRAINING")
        logger.info("="*60)
        
        # Select features
        feature_list = features.columns
        logger.info(f"Using {len(feature_list)} features")
        
        # Prepare data
        feature_cols = [col for col in features.columns if col not in ['vehicle_id', 'id']]
        feature_cols = [col for col in feature_cols if col in feature_list]
        
        # Merge features and target
        data = features[['vehicle_id'] + feature_cols].merge(target, on='vehicle_id', how='inner')
        
        logger.info(f"Total samples: {len(data)}")
        logger.info(f"Target distribution:\n{data['target'].value_counts().to_dict()}")
        
        # Prepare train/test split
        X = data[feature_cols]
        y = data['target']
        
        X_train, X_test, y_train, y_test = self.prepare_train_test_split(
            features_df=pd.concat([pd.DataFrame({'vehicle_id': data['vehicle_id']}), X], axis=1),
            target_df=target,
            test_size=self.config.get('test_size', 0.3),
            random_state=self.config.get('random_state', 42)
        )
        
        # Remove vehicle_id from features
        X_train = X_train.drop('vehicle_id', axis=1, errors='ignore')
        X_test = X_test.drop('vehicle_id', axis=1, errors='ignore')
        
        train_metrics = self.train(
            X_train, y_train,
            X_test, y_test,
            feature_list=X_train.columns.tolist()
        )
        
        self.results['train_metrics'] = train_metrics
        
        # Evaluate on test set
        logger.info("\n" + "="*60)
        logger.info("STEP 6: MODEL EVALUATION")
        logger.info("="*60)
        
        test_metrics = self.evaluate(X_test, y_test)
        self.results['test_metrics'] = test_metrics
        
        # Feature importance
        feature_importance = self.get_feature_importance()
        if not feature_importance.empty:
            logger.info("\nTop 10 Most Important Features:")
            logger.info(feature_importance.head(10).to_string())
            self.results['feature_importance'] = feature_importance.to_dict('records')
        
        # Store test data for figure generation
        self.X_test = X_test
        self.y_test = y_test
        
        return self.results
    

    def remove_model_folder_from_local(self):
        local_folder = Path(self.config['models_dir'])
        try:
            shutil.rmtree(local_folder)
        except Exception as e:
            print(f"Failed to delete folder {local_folder}: {e}")