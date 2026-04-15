import pandas as pd
import numpy as np
import json
import yaml
import shutil
from typing import Dict, Tuple, Optional, Any
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, OrdinalEncoder
import matplotlib.pyplot as plt
import seaborn as sns

from skl2onnx import convert_sklearn
from onnxmltools import convert_xgboost
from skl2onnx.common.data_types import FloatTensorType


from sklearn.ensemble import HistGradientBoostingRegressor
import onnx

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from datetime import datetime
from pathlib import Path
from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.aws import push_folder_to_s3


logger = gen_logger('Rent_Cost_Train - Model_Training')


class RentCostModel:
    """Handles model training and evaluation."""
    
    def __init__(self, config: Dict):
        """
        Initialize the model.
        
        Args:
            model_type: Type of model ('hist_gradient_boosting', 'XGBoost'...)
        """
        self.config = config
        self.model_type = self.config.get('model_type', 'hist_gradient_boosting')
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.feature_names = None
        self.categorical_features = []
        self.numeric_features = []
        self.metrics = {}
        self.results = {}

        self.test_size = config.get('test_size', 0.3)
        self.random_state = config.get('random_state', 42)
        self.performance_metrics = {}


    def _get_model(self) -> Any:
        """Get the appropriate model based on model_type."""
        model_params = self.config.get("model_params", {})
        models = {
            'hist_gradient_boosting': HistGradientBoostingRegressor(
                **model_params
            )
        }
        return models.get(self.model_type, models['hist_gradient_boosting'])


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
                
        # Scale features
        if fit:
            X = self.scaler.fit_transform(X)
        else:
            X = self.scaler.transform(X)
        
        return X


    def prepare_train_test_split(
        self,
        features_df: pd.DataFrame,
        target_df: pd.DataFrame,
        test_size: float = 0.3,
        random_state: int = 42
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:

        logger.info(f"target_df shape: {target_df.shape}" )
        logger.info(f"features_df shape: {features_df.shape}" )
        
        # Remove vehicle_id from features
        feature_cols = [col for col in features_df.columns if col != 'vehicle_id']

        X = features_df[feature_cols]
        y = target_df['target']

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        
        logger.info(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
        
        return X_train, X_test, y_train, y_test


    def model_fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        feature_list: Optional[list] = None
    ) -> Dict[str, float]:

        logger.info("Starting model training...")

        if feature_list is None:
            feature_list = X_train.columns.tolist()

        self.feature_names = feature_list

        # Preprocess features
        X_train_processed = self.preprocess_features(
            X_train, feature_list, fit=True
        )

        # Initialize model
        base_model = self._get_model()

        # Cross-validation on training set (REGRESSION METRICS)
        cv_rmse = cross_val_score(
            base_model,
            X_train_processed,
            y_train,
            cv=5,
            scoring="neg_root_mean_squared_error",
            n_jobs=-1
        )

        cv_mae = cross_val_score(
            base_model,
            X_train_processed,
            y_train,
            cv=5,
            scoring="neg_mean_absolute_error",
            n_jobs=-1
        )

        cv_r2 = cross_val_score(
            base_model,
            X_train_processed,
            y_train,
            cv=5,
            scoring="r2",
            n_jobs=-1
        )

        metrics = {
            "cv_rmse_mean": -cv_rmse.mean(),
            "cv_rmse_std": cv_rmse.std(),
            "cv_mae_mean": -cv_mae.mean(),
            "cv_mae_std": cv_mae.std(),
            "cv_r2_mean": cv_r2.mean(),
            "cv_r2_std": cv_r2.std()
        }

        # Train final model on full training set
        self.model = self._get_model()
        self.model.fit(X_train_processed, y_train)

        self.metrics = metrics

        logger.info("Training complete.")

        return metrics


    def train_model(
        self,
        features: pd.DataFrame, 
        target: pd.DataFrame
    ) -> Tuple[Any, Any]:

        # Select features
        feature_list = features.columns

        # Prepare data
        feature_cols = [col for col in features.columns if col not in ['vehicle_id', 'id']]
        feature_cols = [col for col in feature_cols if col in feature_list]

        X_train, X_test, y_train, y_test = self.prepare_train_test_split(
            features_df=features,
            target_df=target,
            test_size=self.config.get('test_size', 0.3),
            random_state=self.config.get('random_state', 42)
        )

        # Remove vehicle_id from features
        X_train = X_train.drop('vehicle_id', axis=1, errors='ignore')
        X_test = X_test.drop('vehicle_id', axis=1, errors='ignore')
        
        train_metrics = self.model_fit(
            X_train, y_train,
            feature_list=X_train.columns.tolist()
        )

        self.results['train_metrics'] = train_metrics

        # Evaluate on test set
        test_metrics = self.evaluate(X_train, y_train, X_test, y_test)
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
    

    def evaluate(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> Dict[str, float]:
        # Preprocess features (NO fitting here)
        X_train_processed = self.preprocess_features(
            X_train, self.feature_names, fit=False
        )
        X_test_processed = self.preprocess_features(
            X_test, self.feature_names, fit=False
        )

        # Predictions
        y_pred_train = self.model.predict(X_train_processed)
        y_pred_test = self.model.predict(X_test_processed)

        # Metrics
        metrics = {
            "train_mae": float(mean_absolute_error(y_train, y_pred_train)),
            "test_mae": float(mean_absolute_error(y_test, y_pred_test)),
            "train_rmse": float(np.sqrt(mean_squared_error(y_train, y_pred_train))),
            "test_rmse": float(np.sqrt(mean_squared_error(y_test, y_pred_test))),
            "train_r2": float(r2_score(y_train, y_pred_train)),
            "test_r2": float(r2_score(y_test, y_pred_test)),
        }

        return metrics
    

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
            return pd.DataFrame()
    
    
    def save_model(self, results: dict, config: dict):
        """
        Save model and preprocessors to disk using ONNX format.
        Supports XGBoost and sklearn models.
        """

        logger.info("Saving model artifacts...")

        model_path = Path(self.config['models_dir']) / f'model_{datetime.now().strftime('%Y-%m-%d')}'

        model_path.mkdir(parents=True, exist_ok=True)

        # ONNX MODEL EXPORT
        try:
            n_features = len(self.feature_names)
            initial_type = [("float_input", FloatTensorType([None, n_features]))]

            if self.model_type == "xgboost":
                onnx_model = convert_xgboost(
                    self.model,
                    initial_types=initial_type,
                    target_opset=12
                )
            else:
                onnx_model = convert_sklearn(
                    self.model,
                    initial_types=initial_type,
                    target_opset=12
                )

            onnx.save_model(onnx_model, model_path / "model.onnx")

        except Exception as e:
            logger.exception("ONNX conversion failed")
            raise RuntimeError(f"ONNX conversion failed: {e}")

        # SAVE SCALER
        if self.scaler is not None:
            if isinstance(self.scaler, StandardScaler):
                scaler_data = {
                    "scaler_type": "StandardScaler",
                    "mean": self.scaler.mean_.tolist(),
                    "scale": self.scaler.scale_.tolist(),
                    "var": self.scaler.var_.tolist(),
                    "with_mean": self.scaler.with_mean,
                    "with_std": self.scaler.with_std,
                    "n_features": int(self.scaler.n_features_in_),
                }

                with open(model_path / "scaler.json", "w") as f:
                    json.dump(scaler_data, f, indent=2)

            else:
                logger.error(f"Unsupported scaler type: {type(self.scaler)}")

        # SAVE LABEL ENCODERS AS JSON
        if self.label_encoders is not None:
            encoders_data = {}
            for feature_name, encoder in self.label_encoders.items():
                encoders_data[feature_name] = {
                    "classes": encoder.categories_[0].tolist(),
                }
            
            with open(model_path / "label_encoders.json", "w") as f:
                json.dump(encoders_data, f, indent=2)

        # CLEAN MEDIAN VALUES
        median_values_clean = {}
        for k, v in getattr(self, "median_values_", {}).items():
            if isinstance(v, (float, int)):
                median_values_clean[k] = None if np.isnan(v) or np.isinf(v) else float(v)
            else:
                median_values_clean[k] = v

        # CLEAN METRICS
        metrics_clean = {}
        for k, v in self.metrics.items():
            if isinstance(v, (float, int)):
                metrics_clean[k] = None if np.isnan(v) or np.isinf(v) else float(v)
            else:
                metrics_clean[k] = v

        # SAVE METADATA
        metadata = {
            "model_type": self.model_type,
            "format": "onnx",
            "version": "1.0.0",
            "trained_at": datetime.utcnow().isoformat(),
            "n_features": n_features,
            "feature_names": self.feature_names,
            "categorical_features": self.categorical_features,
            "numeric_features": self.numeric_features,
            "metrics": metrics_clean,
            "median_values": median_values_clean,
        }

        with open(model_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        # SAVE TRAINING RESULTS
        with open(model_path / "training_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)

        # SAVE CONFIG
        with open(model_path / "config.yaml", "w") as f:
            yaml.dump(config, f)

        logger.info(f"Model successfully uploaded to S3 bucket {config['bucket_name']}")

        return Path(model_path)


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
        Generate and save regression evaluation figures.
        """

        output_dir = Path(self.config["models_dir"]) / f"model_{datetime.now().strftime('%Y-%m-%d')}"
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        # PREPROCESS TEST FEATURES (THIS WAS MISSING)
        X_test_processed = self.preprocess_features(
            X_test,
            self.feature_names,
            fit=False
        )

        # PREDICTIONS 
        y_pred = self.model.predict(X_test_processed)

        residuals = y_test - y_pred
        abs_errors = np.abs(residuals)

        sns.set_style("whitegrid")
        plt.rcParams["figure.figsize"] = (12, 8)

        # 1. Predicted vs Actual
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.scatter(y_test, y_pred, alpha=0.5)
        ax.plot(
            [y_test.min(), y_test.max()],
            [y_test.min(), y_test.max()],
            linestyle="--",
            linewidth=2,
            color="black",
            label="Perfect prediction",
        )
        ax.set_xlabel("Actual Values", fontsize=12, fontweight="bold")
        ax.set_ylabel("Predicted Values", fontsize=12, fontweight="bold")
        ax.set_title("Predicted vs Actual Values", fontsize=14, fontweight="bold")
        ax.legend()
        plt.tight_layout()
        plt.savefig(figures_dir / "01_predicted_vs_actual.png", dpi=300)
        plt.close()

        # 2. Residuals vs Predicted
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(y_pred, residuals, alpha=0.5)
        ax.axhline(0, linestyle="--", linewidth=2, color="red")
        ax.set_xlabel("Predicted Values", fontsize=12, fontweight="bold")
        ax.set_ylabel("Residuals", fontsize=12, fontweight="bold")
        ax.set_title("Residuals vs Predicted Values", fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.savefig(figures_dir / "02_residuals_vs_predicted.png", dpi=300)
        plt.close()

        # 3. Residual Distribution
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.histplot(residuals, bins=50, kde=True, ax=ax)
        ax.set_title("Residual Distribution", fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.savefig(figures_dir / "03_residual_distribution.png", dpi=300)
        plt.close()

        # 4. Absolute Error Distribution
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.histplot(abs_errors, bins=50, kde=True, ax=ax)
        ax.set_title("Absolute Error Distribution", fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.savefig(figures_dir / "04_absolute_error_distribution.png", dpi=300)
        plt.close()

        # 5. Feature Importance
        feature_importance = self.get_feature_importance()
        if feature_importance is not None and not feature_importance.empty:
            fig, ax = plt.subplots(figsize=(10, 8))
            top_features = feature_importance.head(15)
            ax.barh(top_features["feature"], top_features["importance"])
            ax.set_title("Top 15 Most Important Features", fontsize=14, fontweight="bold")
            ax.invert_yaxis()
            plt.tight_layout()
            plt.savefig(figures_dir / "05_feature_importance.png", dpi=300)
            plt.close()