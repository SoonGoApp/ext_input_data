import pandas as pd
import numpy as np
import json
import shutil
from pathlib import Path
import onnxruntime as ort
from sklearn.preprocessing import OrdinalEncoder, StandardScaler

from soongo_data.utils.logging_utils import gen_logger
from soongo_data.utils.aws import pull_folder_from_s3, s3_get_most_recent_folder


logger = gen_logger('Rent_Cost_Predict - Model_Predict')


class RentalCostPredictor:
    """Handles model loading and prediction for rental cost.
    Supports three model formats saved by the training pipeline:
      - "onnx"       (hist_gradient_boosting, xgboost, autres sklearn) -> ONNX + scaler + label encoders
      - "onnx_blend" (moyenne HGB + ExtraTrees + LightGBM)             -> un ONNX par membre (metadata.blend_members)
                                                                          + le même scaler / label encoders
      - "cbm"        (catboost)                                        -> format natif CatBoost, pas de scaler/encoders

    Le prétraitement reproduit EXACTEMENT celui du training :
      - catégories -> OrdinalEncoder du train (valeur inconnue -> 'unknown' si cette
        catégorie existe au train, sinon -1) ;
      - valeurs numériques manquantes / infinies -> médiane du TRAIN (metadata.median_values) ;
      - StandardScaler du train.
    La cible est reconvertie selon metadata.target_transform ('none', 'log', 'monthly_log').
    """

    def __init__(self, config):
        self.config = config
        self.model_type = None
        self.model_format = None
        self.model = None
        self.scaler = None
        self.label_encoders = {}
        self.feature_names = None
        self.categorical_features = []
        self.numeric_features = []
        self.metrics = {}
        self.results = {}
        self.median_values_ = {}
        self.target_transform = 'none'
        self.blend_members = []

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
    # ARTIFACT LOADING (dispatch by format)
    # ------------------------------------------------------------------

    def load_model_artifacts(self, path: str):
        """Load model and related artifacts from disk. Reads metadata first
        to know which format was used (onnx vs cbm) and dispatch accordingly.
        """
        model_path = Path(path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_path}")

        # ── METADATA (lu en premier pour connaître le format) ─────────────
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
        self.target_transform = metadata.get("target_transform", "none")

        if self.model_format == "cbm":
            self._load_catboost_model(model_path)
        elif self.model_format == "onnx_blend":
            self._load_onnx_blend(model_path, metadata.get("blend_members"))
        else:
            self._load_onnx_model(model_path)

    def _load_catboost_model(self, model_path: Path):
        """CatBoost natif : pas de scaler, pas de label encoders
        (CatBoost gère les catégories nativement)."""
        from catboost import CatBoostRegressor

        cbm_path = model_path / "model.cbm"
        if not cbm_path.exists():
            raise FileNotFoundError(f"CatBoost model not found: {cbm_path}")

        self.model = CatBoostRegressor()
        self.model.load_model(str(cbm_path), format="cbm")
        self.scaler = None
        self.label_encoders = None
        logger.info("CatBoost model loaded (native .cbm format)")

    def _load_onnx_model(self, model_path: Path):
        onnx_model_path = model_path / "model.onnx"
        if not onnx_model_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {onnx_model_path}")

        self.model = ort.InferenceSession(str(onnx_model_path))
        self._load_preprocessing(model_path)

    def _load_onnx_blend(self, model_path: Path, members_meta):
        """Blend : un fichier ONNX par membre, moyenne pondérée des prédictions.
        Le prétraitement (encoders, médianes, scaler) est commun à tous les membres."""
        if not members_meta:
            raise ValueError("metadata.blend_members manquant pour le format 'onnx_blend'")

        self.blend_members = []
        for member in members_meta:
            member_path = model_path / member["file"]
            if not member_path.exists():
                raise FileNotFoundError(f"Blend member not found: {member_path}")
            session = ort.InferenceSession(str(member_path))
            self.blend_members.append(
                (member["name"], session, float(member.get("weight", 1.0)))
            )
        self.model = self.blend_members
        self._load_preprocessing(model_path)
        logger.info(f"Blend loaded: {[name for name, _, _ in self.blend_members]}")

    def _load_preprocessing(self, model_path: Path):
        """Scaler et label encoders du train (communs aux formats ONNX et blend)."""
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
        else:
            self.scaler = None
            logger.error("No scaler found")

        # LOAD LABEL ENCODERS FROM JSON
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
            self.label_encoders = None
            logger.error("No label encoders found")

    def remove_model_folder_from_local(self):
        local_folder = Path(self.config['models_dir'])
        try:
            shutil.rmtree(local_folder)
        except Exception as e:
            logger.error(f"Failed to delete folder {local_folder}: {e}")

    # ------------------------------------------------------------------
    # PREPROCESS (ONNX path only — mêmes étapes que le training)
    # ------------------------------------------------------------------

    def preprocess_features(
        self,
        df: pd.DataFrame,
        feature_list: list,
    ) -> np.ndarray:
        df = df[feature_list].copy()
        median_values = getattr(self, 'median_values_', None) or {}
        categorical = [c for c in (self.categorical_features or []) if c in feature_list]
        numeric = [c for c in feature_list if c not in categorical]

        # ── Catégories : OrdinalEncoder du train ─────────────────────────
        for col in categorical:
            encoder = self.label_encoders[col]
            known = set(encoder.categories_[0].tolist()) if hasattr(encoder, 'categories_') else set()
            values = df[col].fillna('unknown').astype(str)
            # Catégorie jamais vue (ex. loueur rare/nouveau) -> 'unknown' si le train
            # l'a apprise (les loueurs rares y avaient été regroupés), sinon -1.
            if 'unknown' in known:
                values = values.where(values.isin(known), 'unknown')
            df[col] = np.asarray(encoder.transform(values.to_frame(col))).ravel()

        # ── Numériques : inf/NaN -> médiane du TRAIN ──────────────────────
        for col in numeric:
            series = pd.to_numeric(df[col], errors='coerce').astype(float)
            series = series.replace([np.inf, -np.inf], np.nan)
            if series.isna().any() and col not in median_values:
                logger.warning(f"No train median for '{col}', filling with 0")
            df[col] = series.fillna(median_values.get(col, 0.0))

        X = df[feature_list].values.astype(float)

        # Scale features (même scaler que le train)
        X = self.scaler.transform(X)

        return X

    # ------------------------------------------------------------------
    # TARGET TRANSFORM (inverse)
    # ------------------------------------------------------------------

    def _inverse_target(self, pred: np.ndarray, X: pd.DataFrame) -> np.ndarray:
        """Reconvertit la sortie du modèle en loyer (mêmes règles que le training)."""
        pred = np.asarray(pred, dtype=float)
        transform = getattr(self, 'target_transform', 'none') or 'none'

        if transform == 'none':
            result = pred
        elif transform == 'log':
            result = np.expm1(pred)
        elif transform == 'monthly_log':
            months = X['lease_months'].astype(float).clip(lower=1).values
            result = np.expm1(pred) * months
        else:
            raise ValueError(f"target_transform inconnu: {transform}")

        # un loyer ne peut pas être négatif
        return np.clip(result, 0, None)

    # ------------------------------------------------------------------
    # PREDICT (dispatch by format)
    # ------------------------------------------------------------------

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise ValueError("Model not loaded.")

        if self.model_format == "cbm":
            raw = self._predict_catboost(X)
        elif self.model_format == "onnx_blend":
            raw = self._predict_onnx_blend(X)
        else:
            raw = self._predict_onnx(X)
        return self._inverse_target(raw, X)

    def _predict_catboost(self, X: pd.DataFrame) -> np.ndarray:
        from catboost import Pool

        df = X.copy()
        # S'assure que les colonnes catégorielles sont bien en string
        # (comme au training) et que l'ordre des colonnes correspond
        # exactement à self.feature_names.
        df = df[self.feature_names]
        for col in self.categorical_features:
            if col in df.columns:
                df[col] = df[col].fillna('unknown').astype(str)

        cat_indices = [
            self.feature_names.index(c)
            for c in self.categorical_features
            if c in self.feature_names
        ]

        pool = Pool(df, cat_features=cat_indices)
        predictions = self.model.predict(pool)

        return np.asarray(predictions).flatten()

    def _predict_onnx(self, X: pd.DataFrame) -> np.ndarray:
        X_processed = self.preprocess_features(X, self.feature_names)
        X_processed = np.array(X_processed, dtype=np.float32)

        input_name = self.model.get_inputs()[0].name

        try:
            outputs = self.model.run(None, {input_name: X_processed})
        except Exception as e:
            logger.error(f"ONNX inference error: {str(e)}")
            raise

        return outputs[0].flatten()

    def _predict_onnx_blend(self, X: pd.DataFrame) -> np.ndarray:
        """Moyenne pondérée des prédictions de chaque membre (poids égaux par défaut,
        comme BlendRegressor à l'entraînement). Prétraitement calculé une seule fois."""
        X_processed = np.array(self.preprocess_features(X, self.feature_names), dtype=np.float32)

        predictions, weights = [], []
        for name, session, weight in self.blend_members:
            input_name = session.get_inputs()[0].name
            try:
                outputs = session.run(None, {input_name: X_processed})
            except Exception as e:
                logger.error(f"ONNX inference error (member {name}): {str(e)}")
                raise
            predictions.append(np.asarray(outputs[0], dtype=float).flatten())
            weights.append(weight)

        return np.average(np.vstack(predictions), axis=0, weights=weights)







# import pandas as pd
# import numpy as np
# import json
# import shutil
# from pathlib import Path
# import onnxruntime as ort
# from sklearn.preprocessing import OrdinalEncoder, StandardScaler

# from soongo_data.utils.logging_utils import gen_logger
# from soongo_data.utils.aws import pull_folder_from_s3, s3_get_most_recent_folder


# logger = gen_logger('Rent_Cost_Predict - Model_Predict')


# class RentalCostPredictor:
#     """Handles model loading and prediction for rental cost.
#     Supports two model formats saved by the training pipeline:
#       - "onnx" (hist_gradient_boosting, xgboost, autres sklearn) -> ONNX + scaler + label encoders
#       - "cbm"  (catboost)                                        -> format natif CatBoost, pas de scaler/encoders
#     """

#     def __init__(self, config):
#         self.config = config
#         self.model_type = None
#         self.model_format = None
#         self.model = None
#         self.scaler = None
#         self.label_encoders = {}
#         self.std_nb = 5
#         self.feature_names = None
#         self.categorical_features = []
#         self.numeric_features = []
#         self.metrics = {}
#         self.results = {}

#         self.model_local_path = self.load_model_from_s3()
#         self.load_model_artifacts(self.model_local_path)

#     # ------------------------------------------------------------------
#     # S3 LOADING
#     # ------------------------------------------------------------------

#     def load_model_from_s3(self):
#         last_model_name = s3_get_most_recent_folder(
#             bucket_name=self.config['bucket_name'],
#             prefix=self.config['model_folder']
#         )

#         models_dir = Path(self.config["models_dir"])
#         local_model_dir = models_dir / last_model_name

#         pull_folder_from_s3(
#             s3_prefix=f"{self.config['model_folder']}/{last_model_name}",
#             local_dir=str(local_model_dir),
#             bucket_name=self.config['bucket_name']
#         )
#         return local_model_dir

#     # ------------------------------------------------------------------
#     # ARTIFACT LOADING (dispatch by format)
#     # ------------------------------------------------------------------

#     def load_model_artifacts(self, path: str):
#         """Load model and related artifacts from disk. Reads metadata first
#         to know which format was used (onnx vs cbm) and dispatch accordingly.
#         """
#         model_path = Path(path)

#         if not model_path.exists():
#             raise FileNotFoundError(f"Model directory not found: {model_path}")

#         # ── METADATA (lu en premier pour connaître le format) ─────────────
#         metadata_path = model_path / "metadata.json"
#         if not metadata_path.exists():
#             raise FileNotFoundError(f"Metadata not found: {metadata_path}")

#         with open(metadata_path, "r") as f:
#             metadata = json.load(f)

#         self.model_type = metadata.get("model_type")
#         self.model_format = metadata.get("format", "onnx")
#         self.feature_names = metadata.get("feature_names")
#         self.categorical_features = metadata.get("categorical_features") or []
#         self.numeric_features = metadata.get("numeric_features") or []
#         self.metrics = metadata.get("metrics")
#         self.median_values_ = metadata.get("median_values")

#         if self.model_format == "cbm":
#             self._load_catboost_model(model_path)
#         else:
#             self._load_onnx_model(model_path)

#     def _load_catboost_model(self, model_path: Path):
#         """CatBoost natif : pas de scaler, pas de label encoders
#         (CatBoost gère les catégories nativement)."""
#         from catboost import CatBoostRegressor

#         cbm_path = model_path / "model.cbm"
#         if not cbm_path.exists():
#             raise FileNotFoundError(f"CatBoost model not found: {cbm_path}")

#         self.model = CatBoostRegressor()
#         self.model.load_model(str(cbm_path), format="cbm")
#         self.scaler = None
#         self.label_encoders = None
#         logger.info("CatBoost model loaded (native .cbm format)")

#     def _load_onnx_model(self, model_path: Path):
#         onnx_model_path = model_path / "model.onnx"
#         if not onnx_model_path.exists():
#             raise FileNotFoundError(f"ONNX model not found: {onnx_model_path}")

#         self.model = ort.InferenceSession(str(onnx_model_path))

#         # LOAD SCALER FROM JSON
#         scaler_json_path = model_path / "scaler.json"
#         if scaler_json_path.exists():
#             with open(scaler_json_path, "r") as f:
#                 scaler_data = json.load(f)

#             self.scaler = StandardScaler()
#             if scaler_data.get("mean") is not None:
#                 self.scaler.mean_ = np.array(scaler_data["mean"])
#             if scaler_data.get("var") is not None:
#                 self.scaler.var_ = np.array(scaler_data["var"])
#             if scaler_data.get("scale") is not None:
#                 self.scaler.scale_ = np.array(scaler_data["scale"])
#             self.scaler.n_features_in_ = scaler_data["n_features"]
#             self.scaler.with_mean = scaler_data.get("with_mean", True)
#             self.scaler.with_std = scaler_data.get("with_std", True)
#         else:
#             self.scaler = None
#             logger.error("No scaler found")

#         # LOAD LABEL ENCODERS FROM JSON
#         encoders_path = model_path / "label_encoders.json"
#         if encoders_path.exists():
#             with open(encoders_path, "r") as f:
#                 encoders_data = json.load(f)

#             self.label_encoders = {}
#             for feature_name, encoder_info in encoders_data.items():
#                 encoder = OrdinalEncoder(
#                     handle_unknown='use_encoded_value',
#                     unknown_value=-1
#                 )
#                 categories = np.array(encoder_info["classes"])
#                 encoder.fit(pd.DataFrame(categories, columns=[feature_name]))
#                 self.label_encoders[feature_name] = encoder
#         else:
#             self.label_encoders = None
#             logger.error("No label encoders found")

#     def remove_model_folder_from_local(self):
#         local_folder = Path(self.config['models_dir'])
#         try:
#             shutil.rmtree(local_folder)
#         except Exception as e:
#             logger.error(f"Failed to delete folder {local_folder}: {e}")

#     # ------------------------------------------------------------------
#     # PREPROCESS (ONNX path only — scaling + ordinal encoding)
#     # ------------------------------------------------------------------

#     def preprocess_features(
#         self,
#         df: pd.DataFrame,
#         feature_list: list,
#     ) -> np.ndarray:
#         df = df.copy()

#         categorical_features = df[feature_list].select_dtypes(
#             include=['object', 'category']
#         ).columns.tolist()

#         # Handle categorical features with OrdinalEncoder
#         for col in categorical_features:
#             if col in df.columns:
#                 df[col] = self.label_encoders[col].transform(df[[col]])

#         # Convert to matrix
#         X = df[feature_list].values.astype(float)

#         # Replace inf with NaN first
#         X = np.where(np.isinf(X), np.nan, X)

#         # Handle NaN values before scaling
#         col_means = np.nanmean(X, axis=0)
#         col_stds = np.nanstd(X, axis=0)

#         for i, col_idx in enumerate(feature_list):
#             col_mean = col_means[i]
#             col_std = col_stds[i]

#             # Clip extreme values (beyond 5 standard deviations)
#             if not np.isnan(col_std) and col_std > 0:
#                 lower_bound = col_mean - self.std_nb * col_std
#                 upper_bound = col_mean + self.std_nb * col_std
#                 X[:, i] = np.clip(X[:, i], lower_bound, upper_bound)

#         # Final check for any remaining NaN or inf
#         if np.any(~np.isfinite(X)):
#             logger.warning("Still found non-finite values after cleaning, replacing with 0")
#             X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

#         # Scale features
#         X = self.scaler.transform(X)

#         return X

#     # ------------------------------------------------------------------
#     # PREDICT (dispatch by format)
#     # ------------------------------------------------------------------

#     def predict(self, X: pd.DataFrame) -> np.ndarray:
#         if self.model is None:
#             raise ValueError("Model not loaded.")

#         if self.model_format == "cbm":
#             return self._predict_catboost(X)
#         return self._predict_onnx(X)

#     def _predict_catboost(self, X: pd.DataFrame) -> np.ndarray:
#         from catboost import Pool

#         df = X.copy()
#         # S'assure que les colonnes catégorielles sont bien en string
#         # (comme au training) et que l'ordre des colonnes correspond
#         # exactement à self.feature_names.
#         df = df[self.feature_names]
#         for col in self.categorical_features:
#             if col in df.columns:
#                 df[col] = df[col].fillna('unknown').astype(str)

#         cat_indices = [
#             self.feature_names.index(c)
#             for c in self.categorical_features
#             if c in self.feature_names
#         ]

#         pool = Pool(df, cat_features=cat_indices)
#         predictions = self.model.predict(pool)

#         return np.asarray(predictions).flatten()

#     def _predict_onnx(self, X: pd.DataFrame) -> np.ndarray:
#         X_processed = self.preprocess_features(X, self.feature_names)
#         X_processed = np.array(X_processed, dtype=np.float32)

#         input_name = self.model.get_inputs()[0].name

#         try:
#             outputs = self.model.run(None, {input_name: X_processed})
#         except Exception as e:
#             logger.error(f"ONNX inference error: {str(e)}")
#             raise

#         return outputs[0].flatten()