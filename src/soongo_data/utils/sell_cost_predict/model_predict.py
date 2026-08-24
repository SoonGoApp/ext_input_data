import json
import shutil
from pathlib import Path
from typing import Optional

import numpy as np
import onnxruntime as ort
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder, StandardScaler

from soongo_data.utils.aws import pull_folder_from_s3, s3_get_most_recent_folder
from soongo_data.utils.logging_utils import gen_logger

logger = gen_logger('Sell_Cost_Predict - Model_Predict')


class SellCostPredictor:
    def __init__(self, config):
        self.config = config
        self.model_type: Optional[str] = None
        self.model_format: Optional[str] = None 
        self.model = None
        self.scaler: Optional[StandardScaler] = None
        self.label_encoders = {}
        self.std_nb = 5  # largeur du clipping de securite, en unites de std du TRAINING
        self.feature_names = None
        self.categorical_features = []
        self.numeric_features = []
        self.metrics = {}
        self.median_values_ = {}

        self.model_local_path = self.load_model_from_s3()
        self.load_model_artifacts(self.model_local_path)

    # ------------------------------------------------------------------
    # S3 LOADING
    # ------------------------------------------------------------------

    def load_model_from_s3(self):
        last_model_name = s3_get_most_recent_folder(
            bucket_name=self.config['bucket_name'],
            prefix=self.config['model_folder']
        )

        models_dir = Path(self.config["models_dir"])
        local_model_dir = models_dir / last_model_name

        pull_folder_from_s3(
            s3_prefix=f"{self.config['model_folder']}/{last_model_name}",
            local_dir=str(local_model_dir),
            bucket_name=self.config['bucket_name']
        )
        return local_model_dir

    # ------------------------------------------------------------------
    # LOAD ARTIFACTS
    # ------------------------------------------------------------------

    def load_model_artifacts(self, path: str):
        """Charge le modele + preprocesseurs, en miroir de SellCostModel.save_model."""

        model_path = Path(path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_path}")

        # ── METADATA ──
        metadata_path = model_path / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found: {metadata_path}")

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        self.model_type = metadata.get("model_type")
        self.model_format = metadata.get("format", "onnx")
        self.feature_names = metadata.get("feature_names")
        self.categorical_features = metadata.get("categorical_features") or []
        self.numeric_features = metadata.get("numeric_features") or []
        self.metrics = metadata.get("metrics")
        self.median_values_ = metadata.get("median_values") or {}

        if not self.feature_names:
            raise ValueError("metadata.json ne contient pas 'feature_names'")

        # ── MODELE ──────────────────────────────────────────────────────
        if self.model_format == "cbm":
            from catboost import CatBoostRegressor
            cbm_path = model_path / "model.cbm"
            if not cbm_path.exists():
                raise FileNotFoundError(f"CatBoost model not found: {cbm_path}")
            self.model = CatBoostRegressor()
            self.model.load_model(str(cbm_path), format="cbm")
        else:
            onnx_model_path = model_path / "model.onnx"
            if not onnx_model_path.exists():
                raise FileNotFoundError(f"ONNX model not found: {onnx_model_path}")
            self.model = ort.InferenceSession(str(onnx_model_path))

        # ── SCALER (absent pour catboost) ─────────────────────────────
        scaler_json_path = model_path / "scaler.json"
        if scaler_json_path.exists():
            with open(scaler_json_path, "r") as f:
                scaler_data = json.load(f)

            self.scaler = StandardScaler()
            self.scaler.mean_ = np.array(scaler_data["mean"])
            self.scaler.var_ = np.array(scaler_data["var"])
            self.scaler.scale_ = np.array(scaler_data["scale"])
            self.scaler.n_features_in_ = scaler_data["n_features"]
            self.scaler.with_mean = scaler_data.get("with_mean", True)
            self.scaler.with_std = scaler_data.get("with_std", True)
        else:
            self.scaler = None
            if self.model_format != "cbm":
                logger.error("No scaler found")

        # ── LABEL ENCODERS (absents pour catboost) ─────────────────────
        encoders_path = model_path / "label_encoders.json"
        if encoders_path.exists():
            with open(encoders_path, "r") as f:
                encoders_data = json.load(f)

            self.label_encoders = {}
            for feature_name, encoder_info in encoders_data.items():
                encoder = OrdinalEncoder(
                    handle_unknown='use_encoded_value',
                    unknown_value=-1
                )
                categories = np.array(encoder_info["classes"])
                encoder.fit(pd.DataFrame(categories, columns=[feature_name]))
                self.label_encoders[feature_name] = encoder
        else:
            self.label_encoders = {}
            if self.model_format != "cbm":
                logger.error("No label encoders found")

        logger.info(
            f"Model loaded: type={self.model_type} format={self.model_format} "
            f"n_features={len(self.feature_names)}"
        )

    def remove_model_folder_from_local(self):
        local_folder = Path(self.config['models_dir'])
        try:
            shutil.rmtree(local_folder)
        except Exception as e:
            logger.error(f"Failed to delete folder {local_folder}: {e}")

    # ------------------------------------------------------------------
    # PREPROCESSING 
    # ------------------------------------------------------------------

    def preprocess_features(self, df: pd.DataFrame, feature_list: list):
        df = df.copy()

        missing_cols = [c for c in feature_list if c not in df.columns]
        if missing_cols:
            raise ValueError(
                f"Colonnes manquantes dans les donnees de prediction: {missing_cols} "
                f"(attendues par le modele entraine: {feature_list})"
            )

        # ── CatBoost : pas d'encoding, pas de scaling (comme au training) ──
        if self.model_type == "catboost":
            return df[feature_list]

        # ── Autres modeles : OrdinalEncoder ────
        for col in self.categorical_features:
            if col in df.columns:
                if col not in self.label_encoders:
                    raise ValueError(f"Pas de label encoder charge pour '{col}'")
                df[col] = self.label_encoders[col].transform(df[[col]])

        X = df[feature_list].values.astype(float)

        X = np.where(np.isinf(X), np.nan, X)
        nan_mask = ~np.isfinite(X)
        if nan_mask.any() and self.scaler is not None:
            for i in range(X.shape[1]):
                if nan_mask[:, i].any():
                    X[nan_mask[:, i], i] = self.scaler.mean_[i]

        if self.scaler is not None:
            lower = self.scaler.mean_ - self.std_nb * self.scaler.scale_
            upper = self.scaler.mean_ + self.std_nb * self.scaler.scale_
            X = np.clip(X, lower, upper)

            X = self.scaler.transform(X)
        else:
            logger.warning("No scaler available - features used unscaled")

        if np.any(~np.isfinite(X)):
            logger.warning("Non-finite values remaining after cleaning, replacing with 0")
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        return X

    # ------------------------------------------------------------------
    # PREDICT
    # ------------------------------------------------------------------

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predit le cout de reprise.

        Args:
            X: features d'entree (memes colonnes que feature_names, sans
               vehicle_id)

        Returns:
            Array des predictions
        """
        if self.model is None:
            raise ValueError("Model not loaded.")

        X_processed = self.preprocess_features(X, self.feature_names)

        if self.model_type == "catboost":
            from catboost import Pool
            cat_indices = [
                self.feature_names.index(c)
                for c in self.categorical_features
                if c in self.feature_names
            ]
            pool = Pool(X_processed, cat_features=cat_indices)
            preds = self.model.predict(pool)
            return np.asarray(preds).flatten()

        # ONNX (hist_gradient_boosting, lightgbm, xgboost)
        X_processed = np.array(X_processed, dtype=np.float32)
        input_name = self.model.get_inputs()[0].name

        try:
            outputs = self.model.run(None, {input_name: X_processed})
        except Exception as e:
            logger.error(f"ONNX inference error: {str(e)}")
            raise

        return outputs[0].flatten()