import pandas as pd
import numpy as np
import json
import yaml
import shutil
from typing import Dict, Tuple, Optional, Any
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, OrdinalEncoder
from sklearn.ensemble import RandomForestClassifier
import matplotlib.pyplot as plt
import seaborn as sns

import numpy as np
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx

from sklearn.metrics import (
    roc_auc_score, classification_report, confusion_matrix, 
    average_precision_score, roc_curve, auc
)

from datetime import datetime
from pathlib import Path
from soongo_data.utils.aws import push_folder_to_s3
from soongo_data.utils.logging_utils import gen_logger


logger = gen_logger('Elec_Eligibility_Training - Model_Training')


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
        self.threshold = 0.55
        self.std_nb = 5
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.feature_names = None
        self.categorical_features = []
        self.numeric_features = []
        self.metrics = {}
        self.results = {}
        
        
    def _get_model(self) -> Any:
        """Get the appropriate model based on model_type."""
        model_params = self.config.get("model_params", {})
        models = {
            'random_forest': RandomForestClassifier(
                 **model_params
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
                    self.label_encoders[col] = OrdinalEncoder(
                        handle_unknown='use_encoded_value',
                        unknown_value=-1
                    )
                    self.label_encoders[col].fit(df[[col]])
                    df[col] = self.label_encoders[col].transform(df[[col]])
                else:
                    df[col] = self.label_encoders[col].transform(df[[col]])
        
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
                lower_bound = col_mean - self.std_nb * col_std
                upper_bound = col_mean + self.std_nb * col_std
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
        
        self.metrics = metrics
        
        logger.info(f"Training complete.")
        
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
    ) -> Dict[str, Any]:
        logger.info("Evaluating model...")
        
        # Get predictions
        y_pred_proba = self.predict_proba(X_test)
        y_pred = (y_pred_proba >= self.threshold).astype(int)
        
        # Calculate metrics
        metrics = {
            'test_auc': roc_auc_score(y_test, y_pred_proba),
            'test_average_precision': average_precision_score(y_test, y_pred_proba),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'classification_report': classification_report(y_test, y_pred, output_dict=True)
        }
        
        return metrics
    

    def save_model(self, path: str, results: dict, config: dict):
        """Save model and preprocessors to disk using ONNX format (secure)."""

        model_path = Path(path)
        model_path.mkdir(parents=True, exist_ok=True)
        
        # ============== CONVERT MODEL TO ONNX ==============
        try:
            # Determine input type based on features
            n_features = len(self.feature_names)
            initial_type = [('float_input', FloatTensorType([None, n_features]))]
            
            # Convert sklearn model to ONNX
            onnx_model = convert_sklearn(
                self.model,
                initial_types=initial_type,
                target_opset=12,  # Use a stable opset version
                options={
                    'zipmap': False  # Disable zipmap for cleaner output
                }
            )
            
            # Save ONNX model
            onnx.save_model(onnx_model, str(model_path / "model.onnx"))
            logger.info("Model saved to model.onnx")
            
        except Exception as e:
            logger.error(f"Error converting model to ONNX: {str(e)}")
            raise
        
        # ============== SAVE SCALER AS JSON ==============
        if self.scaler is not None:
            scaler_data = {"scaler_type": type(self.scaler).__name__}
            
            if isinstance(self.scaler, StandardScaler):
                scaler_data.update({
                    "mean": self.scaler.mean_.tolist() if hasattr(self.scaler, 'mean_') else None,
                    "var": self.scaler.var_.tolist() if hasattr(self.scaler, 'var_') else None,
                    "scale": self.scaler.scale_.tolist() if hasattr(self.scaler, 'scale_') else None,
                    "n_features": int(self.scaler.n_features_in_),
                    "with_mean": self.scaler.with_mean,
                    "with_std": self.scaler.with_std,
                })
            else:
                logger.warning(f"Unsupported scaler type: {type(self.scaler)}")
                scaler_data = None
            
            if scaler_data:
                with open(model_path / "scaler.json", "w") as f:
                    json.dump(scaler_data, f, indent=2)
                logger.info("Scaler saved to scaler.json")
        
        # ============== SAVE LABEL ENCODERS AS JSON ==============
        if self.label_encoders is not None:
            encoders_data = {}
            for feature_name, encoder in self.label_encoders.items():
                encoders_data[feature_name] = {
                    "classes": encoder.categories_[0].tolist(),
                }
            
            with open(model_path / "label_encoders.json", "w") as f:
                json.dump(encoders_data, f, indent=2)
            logger.info("Label encoders saved to label_encoders.json")
        
        # ============== CLEAN MEDIAN VALUES ==============
        median_values_clean = {}
        for key, value in getattr(self, "median_values_", {}).items():
            if isinstance(value, float):
                if np.isnan(value) or np.isinf(value):
                    median_values_clean[key] = None
                else:
                    median_values_clean[key] = float(value)
            else:
                median_values_clean[key] = value
        
        # ============== CLEAN METRICS ==============
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
        
        # ============== SAVE METADATA ==============
        metadata = {
            "model_type": self.model_type,
            "feature_names": self.feature_names,
            "categorical_features": self.categorical_features,
            "numeric_features": self.numeric_features,
            "metrics": metrics_clean,
            "median_values": median_values_clean,
            "trained_at": datetime.now().isoformat(),
            "version": "1.0.0",
            "format": "onnx",
            "n_features": n_features,
        }
        
        with open(model_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Metadata saved to {model_path}/metadata.json")
        
        # ============== SAVE RESULTS ==============
        results_path = model_path / 'training_results.json'
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Training results saved to {results_path}")
        
        # ============== SAVE CONFIG ==============
        config_path = model_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        logger.info(f"Configuration saved to {config_path}")
        
        # ============== UPLOAD TO S3 ==============
        push_folder_to_s3(
            local_dir=model_path,
            s3_prefix=str(model_path),
            bucket_name=config["bucket_name"]
        )

        self.remove_model_folder_from_local()
        
        logger.info(f"Model uploaded to {config['bucket_name']}")
    


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
        
        test_metrics = self.evaluate(X_test, y_test)
        self.results['test_metrics'] = test_metrics
        
        # Feature importance
        feature_importance = self.get_feature_importance()
        if not feature_importance.empty:
            self.results['feature_importance'] = feature_importance.to_dict('records')
        

        self.generate_evaluation_figures(
            X_test=X_test,
            y_test=y_test
        )

        # Store test data for figure generation
        self.X_test = X_test
        self.y_test = y_test
        
        return self.results
    


    def remove_model_folder_from_local(self):
        local_folder = Path(self.config['models_dir'])
        try:
            shutil.rmtree(local_folder)
        except Exception as e:
            logger.error(f"Failed to delete folder {local_folder}: {e}")



    def generate_evaluation_figures(
        self, 
        X_test: pd.DataFrame, 
        y_test: pd.Series,
    ):
        """
        Generate and save evaluation figures.
        
        Args:
            X_test: Test features
            y_test: Test target
            output_dir: Directory to save figures
        """
        output_dir = Path(self.config['models_dir']) / f'model_{datetime.now().strftime('%Y-%m-%d')}'
        figures_dir = output_dir / 'figures'
        figures_dir.mkdir(parents=True, exist_ok=True)
        
        # Get predictions
        y_pred_proba = self.predict_proba(X_test)
        y_pred = (y_pred_proba >= self.threshold).astype(int)
        
        # Set style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (12, 8)
        
        # 1. Confusion Matrix
        fig, ax = plt.subplots(figsize=(8, 6))
        cm = confusion_matrix(y_test, y_pred)
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax, 
                   xticklabels=['Non-Eligible', 'Eligible'],
                   yticklabels=['Non-Eligible', 'Eligible'])
        ax.set_ylabel('True Label', fontsize=12, fontweight='bold')
        ax.set_xlabel('Predicted Label', fontsize=12, fontweight='bold')
        ax.set_title('Confusion Matrix - Electrification Eligibility', 
                    fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(figures_dir / '01_confusion_matrix.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. ROC Curve
        fig, ax = plt.subplots(figsize=(10, 8))
        fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
        roc_auc = auc(fpr, tpr)
        
        ax.plot(fpr, tpr, color='darkorange', lw=2.5, 
               label=f'ROC curve (AUC = {roc_auc:.4f})')
        ax.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random Classifier')
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('False Positive Rate', fontsize=12, fontweight='bold')
        ax.set_ylabel('True Positive Rate', fontsize=12, fontweight='bold')
        ax.set_title('ROC Curve - Electrification Eligibility Model', 
                    fontsize=14, fontweight='bold')
        ax.legend(loc="lower right", fontsize=11)
        ax.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(figures_dir / '02_roc_curve.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. Feature Importance (Top 15)
        feature_importance = self.get_feature_importance()
        if not feature_importance.empty:
            fig, ax = plt.subplots(figsize=(10, 8))
            top_features = feature_importance.head(15)
            
            ax.barh(range(len(top_features)), top_features['importance'], color='steelblue')
            ax.set_yticks(range(len(top_features)))
            ax.set_yticklabels(top_features['feature'])
            ax.set_xlabel('Importance Score', fontsize=12, fontweight='bold')
            ax.set_title('Top 15 Most Important Features', fontsize=14, fontweight='bold')
            ax.invert_yaxis()
            ax.grid(axis='x', alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(figures_dir / '05_feature_importance.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # 4. Classification Report (Text as Image)
        report = classification_report(y_test, y_pred, 
                                      target_names=['Non-Eligible', 'Eligible'])
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('tight')
        ax.axis('off')
        ax.text(0.5, 0.5, report, transform=ax.transAxes, 
               fontsize=11, verticalalignment='center', horizontalalignment='center',
               family='monospace',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        ax.set_title('Classification Report', fontsize=14, fontweight='bold', pad=20)
        
        plt.tight_layout()
        plt.savefig(figures_dir / '06_classification_report.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"\n✓ All figures saved to: {figures_dir}")

