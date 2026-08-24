import pandas as pd
import numpy as np
import json
import yaml
import shutil
from typing import Dict, Tuple, Optional, Any
from sklearn.model_selection import cross_validate, GroupKFold
from sklearn.preprocessing import StandardScaler, OrdinalEncoder
import matplotlib.pyplot as plt
import seaborn as sns

from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

from sklearn.ensemble import HistGradientBoostingRegressor
import onnx

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from datetime import datetime
from pathlib import Path
from soongo_data.utils.logging_utils import gen_logger

from sklearn.model_selection import GroupShuffleSplit

import optuna
import shap
optuna.logging.set_verbosity(optuna.logging.WARNING)

logger = gen_logger('Sell_Cost_Train - Model_Training')

GROUP_COLS = ['brand', 'model']


class SellCostModel:
    """Handles model training and evaluation."""

    def __init__(self, config: Dict):
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
        self.feature_importance = {}
        self.best_params = None

    # ------------------------------------------------------------------
    # DATA CLEANING
    # ------------------------------------------------------------------

    @staticmethod
    def clean_training_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Nettoyage du jeu d'entrainement avant split.
        """
        n0 = len(df)

        if 'vehicle_id' in df.columns:
            df = df.drop_duplicates(subset=['vehicle_id']).copy()
        else:
            df = df.copy()

        bad_segments = ['unknown', 'UNKNOWN', 'SCOOTER', 'TWO_WHEEL', 'TRUCK', 'BIKE']
        if 'segment' in df.columns:
            df = df[~df['segment'].isin(bad_segments)]

        if 'target' in df.columns:
            df = df[df['target'] >= 1000]

        df = df.reset_index(drop=True)

        logger.info(
            f"clean_training_data: {n0} -> {len(df)} lignes "
            f"({n0 - len(df)} lignes retirées : doublons vehicle_id, "
            f"segments hors périmètre, target aberrante)"
        )

        return df

    # ------------------------------------------------------------------
    # GROUP KEY BUILDER
    # ------------------------------------------------------------------

    @staticmethod
    def _build_group_key(df: pd.DataFrame, group_cols: list) -> pd.Series:
        """
        Construit une clé de groupe robuste à partir de group_cols.
        """
        available_cols = [c for c in group_cols if c in df.columns]
        missing_cols = [c for c in group_cols if c not in df.columns]
        if missing_cols:
            logger.warning(f"Group cols absentes du DataFrame, ignorées: {missing_cols}")

        group_df = df[available_cols].copy()

        for col in group_df.columns:
            if isinstance(group_df[col].dtype, pd.CategoricalDtype):
                group_df[col] = group_df[col].astype(object)
            group_df[col] = group_df[col].fillna('unknown').astype(str)

        return group_df.agg('|'.join, axis=1)

    # ------------------------------------------------------------------
    # MODEL FACTORY
    # ------------------------------------------------------------------

    def _get_model(self, params: Optional[Dict] = None) -> Any:
        """
        Build a model instance.
        Supports: hist_gradient_boosting, catboost, lightgbm, xgboost.
        """
        if params is not None:
            model_params = params
        else:
            model_params = self.config.get("model_params", {})

        if self.model_type == "catboost":
            from catboost import CatBoostRegressor
            # CatBoost gère les catégories nativement — on passe les indices
            cat_indices = []
            if self.feature_names:
                cat_indices = [
                    self.feature_names.index(f)
                    for f in self.categorical_features
                    if f in self.feature_names
                ]
            return CatBoostRegressor(
                cat_features=cat_indices if cat_indices else None,
                **model_params
            )

        if self.model_type == "lightgbm":
            from lightgbm import LGBMRegressor
            return LGBMRegressor(**model_params)

        if self.model_type == "xgboost":
            from xgboost import XGBRegressor
            return XGBRegressor(**model_params)

        # default: hist_gradient_boosting
        return HistGradientBoostingRegressor(**model_params)

    # ------------------------------------------------------------------
    # PREPROCESSING
    # ------------------------------------------------------------------

    def preprocess_features(
        self,
        df: pd.DataFrame,
        feature_list: list,
        fit: bool = True
    ) -> np.ndarray:
        """
        Preprocess features.
        """
        df = df.copy()

        if fit:
            self.categorical_features = df[feature_list].select_dtypes(
                include=['object', 'category']
            ).columns.tolist()
            self.numeric_features = [
                f for f in feature_list if f not in self.categorical_features
            ]

        # CatBoost gère les catégories nativement → pas d'encoding
        if self.model_type != "catboost":
            for col in self.categorical_features:
                if col in df.columns:
                    if fit:
                        self.label_encoders[col] = OrdinalEncoder(
                            handle_unknown='use_encoded_value',
                            unknown_value=-1
                        )
                        self.label_encoders[col].fit(df[[col]])
                    df[col] = self.label_encoders[col].transform(df[[col]])

        X = df[feature_list].values

        # CatBoost gère son propre scaling en interne → on skip StandardScaler
        if self.model_type != "catboost":
            if fit:
                X = self.scaler.fit_transform(X)
            else:
                X = self.scaler.transform(X)

        return X

    # ------------------------------------------------------------------
    # TRAIN / TEST SPLIT
    # ------------------------------------------------------------------

    def prepare_train_test_split(
        self,
        features_df: pd.DataFrame,
        target_df: pd.DataFrame,
        test_size: float = 0.3,
        random_state: int = 42
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:

        logger.info(f"target_df shape: {target_df.shape}")
        logger.info(f"features_df shape: {features_df.shape}")

        # feature_cols exclut uniquement vehicle_id (id technique).
        feature_cols = [
            col for col in features_df.columns
            if col not in ['vehicle_id']
        ]
        X = features_df[feature_cols]
        y = target_df['target']

        groups = self._build_group_key(features_df, feature_cols)

        n_unique_groups = groups.nunique()
        logger.info(f"Groupes de configurations véhicule uniques: {n_unique_groups}")

        gss = GroupShuffleSplit(
            n_splits=1,
            test_size=test_size,
            random_state=random_state
        )
        train_idx, test_idx = next(gss.split(X, y, groups=groups))

        X_train = X.iloc[train_idx]
        X_test  = X.iloc[test_idx]
        y_train = y.iloc[train_idx]
        y_test  = y.iloc[test_idx]

        # Conserve les groupes du train pour la CV interne (Optuna, model_fit)
        self._groups_train = groups.iloc[train_idx].reset_index(drop=True)

        logger.info(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
        logger.info(
            f"Groupes uniques — train: {groups.iloc[train_idx].nunique()}, "
            f"test: {groups.iloc[test_idx].nunique()}"
        )

        return X_train, X_test, y_train, y_test

    # ------------------------------------------------------------------
    # OPTUNA HYPERPARAMETER OPTIMIZATION
    # ------------------------------------------------------------------

    def _get_optuna_params(self, trial) -> Dict:
        """
        Retourne l'espace de recherche Optuna adapté au model_type.
        """
        if self.model_type == "catboost":
            return {
                "iterations":        trial.suggest_int("iterations", 300, 1000),
                "learning_rate":     trial.suggest_float("learning_rate", 0.005, 0.1, log=True),
                "depth":             trial.suggest_int("depth", 3, 8),
                "l2_leaf_reg":       trial.suggest_float("l2_leaf_reg", 1.0, 10.0, log=True),
                "subsample":         trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bylevel": trial.suggest_float("colsample_bylevel", 0.5, 1.0),
                "min_data_in_leaf":  trial.suggest_int("min_data_in_leaf", 5, 80),
                "random_seed":       self.random_state,
                "verbose":           0,
                "eval_metric":       "MAE",
            }

        if self.model_type == "lightgbm":
            return {
                "n_estimators":      trial.suggest_int("n_estimators", 300, 1000),
                "learning_rate":     trial.suggest_float("learning_rate", 0.005, 0.1, log=True),
                "max_depth":         trial.suggest_int("max_depth", 3, 8),
                "num_leaves":        trial.suggest_int("num_leaves", 20, 150),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
                "reg_alpha":         trial.suggest_float("reg_alpha", 0.0, 2.0),
                "reg_lambda":        trial.suggest_float("reg_lambda", 0.0, 2.0),
                "subsample":         trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "random_state":      self.random_state,
                "verbose":           -1,
            }

        if self.model_type == "xgboost":
            return {
                "n_estimators":     trial.suggest_int("n_estimators", 300, 1000),
                "learning_rate":    trial.suggest_float("learning_rate", 0.005, 0.1, log=True),
                "max_depth":        trial.suggest_int("max_depth", 3, 8),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 50),
                "gamma":            trial.suggest_float("gamma", 0.0, 2.0),
                "reg_alpha":        trial.suggest_float("reg_alpha", 0.0, 2.0),
                "reg_lambda":       trial.suggest_float("reg_lambda", 0.5, 5.0),
                "subsample":        trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "random_state":     self.random_state,
                "verbosity":        0,
            }

        # hist_gradient_boosting (default)
        return {
            "max_iter":          trial.suggest_int("max_iter", 200, 800),
            "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "max_depth":         trial.suggest_int("max_depth", 3, 10),
            "min_samples_leaf":  trial.suggest_int("min_samples_leaf", 5, 80),
            "l2_regularization": trial.suggest_float("l2_regularization", 0.1, 5.0, log=True),
            "max_features":      trial.suggest_float("max_features", 0.5, 1.0),
            "random_state":      self.random_state,
            "verbose":           0,
        }

    def optimize_hyperparams(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        n_trials: int = 100,
    ) -> Dict:
        """
        Run Optuna optimization using GroupShuffleSplit CV on training data.
        Avoids data leakage by respecting vehicle group structure.
        Adapte automatiquement l'espace de recherche au model_type.
        """
        logger.info(f"Starting Optuna optimization ({n_trials} trials) for model: {self.model_type}...")

        # Réutilise les groupes calculés dans prepare_train_test_split
        # (basés sur la signature complète des features, alignés sur
        # X_train par position)
        groups_train = self._groups_train.reset_index(drop=True)
        X_train_raw  = X_train.reset_index(drop=True)
        y_train      = y_train.reset_index(drop=True)

        feature_list = X_train_raw.columns.tolist()

        cat_features_detected = X_train_raw.select_dtypes(
            include=['object', 'category']
        ).columns.tolist()

        model_type = self.model_type

        def objective(trial):
            params = self._get_optuna_params(trial)

            gss_inner = GroupShuffleSplit(
                n_splits=3,
                test_size=0.25,
                random_state=self.random_state
            )

            mae_scores = []
            for train_idx, val_idx in gss_inner.split(X_train_raw, y_train, groups=groups_train):
                X_tr  = X_train_raw.iloc[train_idx].copy()
                X_val = X_train_raw.iloc[val_idx].copy()
                y_tr  = y_train.iloc[train_idx]
                y_val = y_train.iloc[val_idx]

                if model_type == "catboost":
                    from catboost import CatBoostRegressor, Pool
                    cat_indices = [feature_list.index(f) for f in cat_features_detected if f in feature_list]
                    train_pool = Pool(X_tr[feature_list], y_tr, cat_features=cat_indices)
                    val_pool   = Pool(X_val[feature_list], y_val, cat_features=cat_indices)
                    model = CatBoostRegressor(**params)
                    model.fit(train_pool, eval_set=val_pool, early_stopping_rounds=50)
                    y_pred = model.predict(X_val[feature_list].values)

                else:
                    # Encode catégories pour les autres modèles
                    for col in cat_features_detected:
                        enc = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
                        enc.fit(X_tr[[col]])
                        X_tr[col]  = enc.transform(X_tr[[col]])
                        X_val[col] = enc.transform(X_val[[col]])

                    scaler = StandardScaler()
                    X_tr_scaled  = scaler.fit_transform(X_tr[feature_list].values)
                    X_val_scaled = scaler.transform(X_val[feature_list].values)

                    if model_type == "lightgbm":
                        from lightgbm import LGBMRegressor
                        model = LGBMRegressor(**params)
                    elif model_type == "xgboost":
                        from xgboost import XGBRegressor
                        model = XGBRegressor(**params)
                    else:
                        model = HistGradientBoostingRegressor(**params)

                    model.fit(X_tr_scaled, y_tr)
                    y_pred = model.predict(X_val_scaled)

                mae_scores.append(mean_absolute_error(y_val, y_pred))

            return np.mean(mae_scores)

        study = optuna.create_study(
            direction="minimize",
            sampler=optuna.samplers.TPESampler(seed=self.random_state)
        )
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        self.best_params = study.best_params

        # Assure que les params système sont présents
        if self.model_type == "catboost":
            self.best_params["random_seed"] = self.random_state
            self.best_params["verbose"]     = 0
            self.best_params["eval_metric"] = "MAE"
        else:
            self.best_params["random_state"] = self.random_state
            self.best_params["verbose"]      = 0

        logger.info(f"Optuna best MAE (CV): {study.best_value:.2f}€")
        logger.info(f"Best params: {self.best_params}")

        self.results['optuna'] = {
            "best_cv_mae": study.best_value,
            "best_params": self.best_params,
            "n_trials":    n_trials,
            "model_type":  self.model_type,
        }

        return self.best_params

    # ------------------------------------------------------------------
    # MODEL FIT
    # ------------------------------------------------------------------

    def model_fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        feature_list: Optional[list] = None,
        model_params: Optional[Dict] = None,
    ) -> Dict[str, float]:

        logger.info(f"Starting model training [{self.model_type}]...")

        if feature_list is None:
            feature_list = X_train.columns.tolist()

        self.feature_names = feature_list
        X_train_processed = self.preprocess_features(X_train, feature_list, fit=True)
        effective_params   = model_params or self.best_params or None

        # Groupes alignés par position sur X_train (mêmes que le split principal)
        groups_train = self._groups_train.reset_index(drop=True)
        y_train_reset = y_train.reset_index(drop=True)
        gkf = GroupKFold(n_splits=5)

        # ── Cross-validation (group-aware) ────────────────────────────
        # CatBoost n'est pas clonable par sklearn → CV manuelle avec GroupKFold
        if self.model_type == "catboost":
            cv_mae, cv_rmse, cv_r2 = [], [], []

            for tr_idx, val_idx in gkf.split(X_train_processed, y_train_reset, groups=groups_train):
                X_tr,  X_val = X_train_processed[tr_idx], X_train_processed[val_idx]
                y_tr,  y_val = y_train_reset.iloc[tr_idx], y_train_reset.iloc[val_idx]

                fold_model = self._get_model(params=effective_params)
                fold_model.fit(X_tr, y_tr)
                y_pred = fold_model.predict(X_val)

                cv_mae.append(mean_absolute_error(y_val, y_pred))
                cv_rmse.append(np.sqrt(mean_squared_error(y_val, y_pred)))
                cv_r2.append(r2_score(y_val, y_pred))

            metrics = {
                "cv_rmse_mean": float(np.mean(cv_rmse)),
                "cv_rmse_std":  float(np.std(cv_rmse)),
                "cv_mae_mean":  float(np.mean(cv_mae)),
                "cv_mae_std":   float(np.std(cv_mae)),
                "cv_r2_mean":   float(np.mean(cv_r2)),
                "cv_r2_std":    float(np.std(cv_r2)),
            }

        else:
            # sklearn-compatible models → cross_validate group-aware
            cv_results = cross_validate(
                self._get_model(params=effective_params),
                X_train_processed,
                y_train_reset,
                groups=groups_train,
                cv=gkf,
                scoring={
                    "rmse": "neg_root_mean_squared_error",
                    "mae":  "neg_mean_absolute_error",
                    "r2":   "r2",
                },
                n_jobs=-1,
            )
            metrics = {
                "cv_rmse_mean": float(-cv_results["test_rmse"].mean()),
                "cv_rmse_std":  float(cv_results["test_rmse"].std()),
                "cv_mae_mean":  float(-cv_results["test_mae"].mean()),
                "cv_mae_std":   float(cv_results["test_mae"].std()),
                "cv_r2_mean":   float(cv_results["test_r2"].mean()),
                "cv_r2_std":    float(cv_results["test_r2"].std()),
            }

        # ── Entraîne le modèle final sur tout le train set ───────────────
        self.model = self._get_model(params=effective_params)
        self.model.fit(X_train_processed, y_train)

        self.metrics = metrics

        logger.info(f"CV MAE: {metrics['cv_mae_mean']:.2f}€ ± {metrics['cv_mae_std']:.2f}€")
        logger.info(f"CV R²:  {metrics['cv_r2_mean']:.4f} ± {metrics['cv_r2_std']:.4f}")
        logger.info("Training complete.")

        return metrics

    # ------------------------------------------------------------------
    # TRAIN MODEL (orchestrator)
    # ------------------------------------------------------------------

    def train_model(
        self,
        features: pd.DataFrame,
        target: pd.DataFrame
    ) -> Dict:

        X_train, X_test, y_train, y_test = self.prepare_train_test_split(
            features_df=features,
            target_df=target,
            test_size=self.config.get('test_size', 0.3),
            random_state=self.config.get('random_state', 42)
        )

        X_train = X_train.drop('vehicle_id', axis=1, errors='ignore')
        X_test  = X_test.drop('vehicle_id', axis=1, errors='ignore')

        # ── Optuna (si activé dans config) ──────────────────────────────
        use_optuna = self.config.get('use_optuna', False)
        n_trials   = self.config.get('optuna_n_trials', 100)

        if use_optuna:
            best_params = self.optimize_hyperparams(
                X_train, y_train, n_trials=n_trials
            )
        else:
            best_params = None

        # ── Fit ─────────────────────────────────────────────────────────
        train_metrics = self.model_fit(
            X_train, y_train,
            feature_list=X_train.columns.tolist(),
            model_params=best_params,
        )
        self.results['train_metrics'] = train_metrics

        # ── Evaluate ────────────────────────────────────────────────────
        test_metrics = self.evaluate(X_train, y_train, X_test, y_test)
        self.results['test_metrics'] = test_metrics

        logger.info(
            f"[RESULTS] train_R²={test_metrics['train_r2']:.4f} | "
            f"test_R²={test_metrics['test_r2']:.4f} | "
            f"MAE ratio={test_metrics['test_mae'] / test_metrics['train_mae']:.2f}x"
        )

        # ── Feature importance ──────────────────────────────────────────
        feature_importance = self.get_feature_importance()
        if not feature_importance.empty:
            self.results['feature_importance'] = feature_importance.to_dict('records')

        # ── Figures standard ────────────────────────────────────────────
        self.generate_evaluation_figures(X_test=X_test, y_test=y_test)

        # ── SHAP analysis ───────────────────────────────────────────────
        if self.config.get('use_shap', True):
            self.generate_shap_analysis(X_test=X_test, y_test=y_test)

        self.X_test = X_test
        self.y_test = y_test

        return self.results

    # ------------------------------------------------------------------
    # EVALUATE
    # ------------------------------------------------------------------

    def evaluate(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> Dict[str, float]:

        X_train_processed = self.preprocess_features(X_train, self.feature_names, fit=False)
        X_test_processed  = self.preprocess_features(X_test,  self.feature_names, fit=False)

        y_pred_train = self.model.predict(X_train_processed)
        y_pred_test  = self.model.predict(X_test_processed)

        metrics = {
            "train_mae":  float(mean_absolute_error(y_train, y_pred_train)),
            "test_mae":   float(mean_absolute_error(y_test,  y_pred_test)),
            "train_rmse": float(np.sqrt(mean_squared_error(y_train, y_pred_train))),
            "test_rmse":  float(np.sqrt(mean_squared_error(y_test,  y_pred_test))),
            "train_r2":   float(r2_score(y_train, y_pred_train)),
            "test_r2":    float(r2_score(y_test,  y_pred_test)),
        }

        return metrics

    # ------------------------------------------------------------------
    # FEATURE IMPORTANCE
    # ------------------------------------------------------------------

    def get_feature_importance(self) -> pd.DataFrame:
        if self.model is None:
            raise ValueError("Model not trained.")

        importance_values = None

        if self.model_type == "catboost":
            importance_values = self.model.get_feature_importance()
        elif hasattr(self.model, 'feature_importances_'):
            importance_values = self.model.feature_importances_

        if importance_values is not None:
            return pd.DataFrame({
                'feature':    self.feature_names,
                'importance': importance_values
            }).sort_values('importance', ascending=False)

        return pd.DataFrame()

    # ------------------------------------------------------------------
    # SHAP ANALYSIS
    # ------------------------------------------------------------------

    def generate_shap_analysis(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series,
    ):
        """
        SHAP analysis — identifie les features et plages de valeurs
        avec le plus d'erreurs de prédiction.
        """
        logger.info("Generating SHAP analysis...")

        output_dir  = Path(self.config["models_dir"]) / f"model_{datetime.now().strftime('%Y-%m-%d')}"
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        X_test_processed = self.preprocess_features(X_test, self.feature_names, fit=False)
        y_pred     = self.model.predict(X_test_processed)
        abs_errors = np.abs(y_test.values - y_pred)

        # ── SHAP values ──────────────────────────────────────────────────
        try:
            explainer   = shap.TreeExplainer(self.model)
            shap_values = explainer(X_test_processed)
        except Exception:
            logger.warning("TreeExplainer failed, falling back to KernelExplainer (slower)...")
            background  = shap.kmeans(X_test_processed, 50)
            explainer   = shap.KernelExplainer(self.model.predict, background)
            shap_values = explainer.shap_values(X_test_processed[:200])

        # ── Figure 6 : SHAP Summary ──────────────────────────────────────
        fig, ax = plt.subplots(figsize=(10, 8))
        shap.summary_plot(
            shap_values,
            X_test_processed,
            feature_names=self.feature_names,
            show=False,
            plot_size=None,
        )
        plt.title(
            "SHAP Summary — Feature Impact on Sell Cost Prediction",
            fontsize=13, fontweight="bold", pad=12
        )
        plt.tight_layout()
        plt.savefig(figures_dir / "06_shap_summary.png", dpi=300, bbox_inches="tight")
        plt.close()

        # ── Figure 7 : MAE par décile de feature ─────────────────────────
        X_test_orig   = X_test.copy().reset_index(drop=True)
        errors_series = pd.Series(abs_errors, name="abs_error")

        n_features = len(self.feature_names)
        ncols = 3
        nrows = int(np.ceil(n_features / ncols))

        fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4 * nrows))
        axes = axes.flatten()

        for i, feat in enumerate(self.feature_names):
            ax = axes[i]
            col_values = (
                X_test_orig[feat].reset_index(drop=True)
                if feat in X_test_orig.columns
                else pd.Series(X_test_processed[:, i])
            )
            try:
                buckets = pd.qcut(col_values, q=5, duplicates='drop')
                df_err  = pd.DataFrame({"bucket": buckets, "abs_error": errors_series})
                grouped = df_err.groupby("bucket", observed=True)["abs_error"].mean().reset_index()
                ax.bar(
                    range(len(grouped)),
                    grouped["abs_error"],
                    color=sns.color_palette("RdYlGn_r", len(grouped))
                )
                ax.set_xticks(range(len(grouped)))
                ax.set_xticklabels(
                    [str(b) for b in grouped["bucket"]],
                    rotation=30, ha="right", fontsize=7
                )
                ax.set_title(feat, fontsize=10, fontweight="bold")
                ax.set_ylabel("Mean |Error| (€)", fontsize=8)
            except Exception:
                ax.set_title(f"{feat} (skipped)", fontsize=9)
                ax.axis("off")

        for j in range(i + 1, len(axes)):
            axes[j].axis("off")

        fig.suptitle(
            "Mean Absolute Error by Feature Value Range",
            fontsize=14, fontweight="bold", y=1.01
        )
        plt.tight_layout()
        plt.savefig(figures_dir / "07_shap_error_by_feature.png", dpi=200, bbox_inches="tight")
        plt.close()

        # ── Figure 8 : Profil high-error vs low-error ────────────────────
        error_threshold_high = np.percentile(abs_errors, 80)
        error_threshold_low  = np.percentile(abs_errors, 20)
        high_error_mask = abs_errors >= error_threshold_high
        low_error_mask  = abs_errors <= error_threshold_low

        fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4 * nrows))
        axes = axes.flatten()

        for i, feat in enumerate(self.feature_names):
            ax = axes[i]
            col_values = (
                X_test_orig[feat].reset_index(drop=True)
                if feat in X_test_orig.columns
                else pd.Series(X_test_processed[:, i])
            )
            try:
                high_vals = col_values[high_error_mask]
                low_vals  = col_values[low_error_mask]

                if col_values.dtype == object or col_values.nunique() < 15:
                    high_counts = high_vals.value_counts(normalize=True).head(8)
                    low_counts  = low_vals.value_counts(normalize=True).reindex(high_counts.index).fillna(0)
                    x = np.arange(len(high_counts))
                    ax.bar(x - 0.2, high_counts.values, 0.4, label="High error (top 20%)", color="#e74c3c", alpha=0.8)
                    ax.bar(x + 0.2, low_counts.values,  0.4, label="Low error (bot 20%)",  color="#2ecc71", alpha=0.8)
                    ax.set_xticks(x)
                    ax.set_xticklabels(high_counts.index, rotation=30, ha="right", fontsize=7)
                    ax.set_ylabel("Frequency", fontsize=8)
                else:
                    high_vals.plot.kde(ax=ax, label="High error (top 20%)", color="#e74c3c", linewidth=2)
                    low_vals.plot.kde(ax=ax,  label="Low error (bot 20%)",  color="#2ecc71", linewidth=2)
                    ax.set_ylabel("Density", fontsize=8)

                ax.set_title(feat, fontsize=10, fontweight="bold")
                ax.legend(fontsize=7)
            except Exception:
                ax.set_title(f"{feat} (skipped)", fontsize=9)
                ax.axis("off")

        for j in range(i + 1, len(axes)):
            axes[j].axis("off")

        fig.suptitle(
            "Feature Distributions: High-Error vs Low-Error Samples",
            fontsize=14, fontweight="bold", y=1.01
        )
        plt.tight_layout()
        plt.savefig(figures_dir / "08_shap_high_error_profile.png", dpi=200, bbox_inches="tight")
        plt.close()

        # ── Log top SHAP features ─────────────────────────────────────────
        shap_array    = shap_values.values if hasattr(shap_values, 'values') else shap_values
        mean_abs_shap = np.abs(shap_array).mean(axis=0)
        shap_importance = pd.DataFrame({
            "feature":       self.feature_names,
            "mean_abs_shap": mean_abs_shap
        }).sort_values("mean_abs_shap", ascending=False)

        logger.info("Top SHAP features (impact on prediction):")
        for _, row in shap_importance.head(5).iterrows():
            logger.info(f"  {row['feature']}: {row['mean_abs_shap']:.2f}")

        self.results['shap_importance'] = shap_importance.to_dict('records')
        logger.info("SHAP analysis complete.")

    # ------------------------------------------------------------------
    # SAVE MODEL
    # ------------------------------------------------------------------

    def save_model(self, results: dict, config: dict):
        """
        Save model and preprocessors to disk.
        - CatBoost  → format natif .cbm  (ONNX ne supporte pas cat_features)
        - XGBoost   → ONNX via onnxmltools
        - Autres    → ONNX via skl2onnx
        """
        logger.info("Saving model artifacts...")

        model_path = Path(self.config['models_dir']) / f"model_{datetime.now().strftime('%Y-%m-%d')}"
        model_path.mkdir(parents=True, exist_ok=True)

        n_features  = len(self.feature_names)
        model_format = "cbm" if self.model_type == "catboost" else "onnx"

        # ── Export modèle ────────────────────────────────────────────────
        try:
            if self.model_type == "catboost":
                # CatBoost ne supporte pas ONNX avec cat_features
                # → format natif .cbm (chargeable avec CatBoostRegressor.load_model)
                self.model.save_model(str(model_path / "model.cbm"), format="cbm")
                logger.info("CatBoost model saved as model.cbm (native format)")

            elif self.model_type == "xgboost":
                from onnxmltools import convert_xgboost
                initial_type = [("float_input", FloatTensorType([None, n_features]))]
                onnx_model   = convert_xgboost(
                    self.model, initial_types=initial_type, target_opset=12
                )
                onnx.save_model(onnx_model, model_path / "model.onnx")

            else:
                initial_type = [("float_input", FloatTensorType([None, n_features]))]
                onnx_model   = convert_sklearn(
                    self.model, initial_types=initial_type, target_opset=12
                )
                onnx.save_model(onnx_model, model_path / "model.onnx")

        except Exception as e:
            logger.exception("Model export failed")
            raise RuntimeError(f"Model export failed: {e}")

        # ── Scaler (non utilisé pour CatBoost) ──────────────────────────
        if self.model_type != "catboost" and self.scaler is not None:
            if isinstance(self.scaler, StandardScaler):
                scaler_data = {
                    "scaler_type": "StandardScaler",
                    "mean":        self.scaler.mean_.tolist(),
                    "scale":       self.scaler.scale_.tolist(),
                    "var":         self.scaler.var_.tolist(),
                    "with_mean":   self.scaler.with_mean,
                    "with_std":    self.scaler.with_std,
                    "n_features":  int(self.scaler.n_features_in_),
                }
                with open(model_path / "scaler.json", "w") as f:
                    json.dump(scaler_data, f, indent=2)

        # ── Label encoders (non utilisés pour CatBoost) ─────────────────
        if self.model_type != "catboost" and self.label_encoders:
            encoders_data = {
                feat: {"classes": enc.categories_[0].tolist()}
                for feat, enc in self.label_encoders.items()
            }
            with open(model_path / "label_encoders.json", "w") as f:
                json.dump(encoders_data, f, indent=2)

        # ── Optuna best params ───────────────────────────────────────────
        if self.best_params is not None:
            with open(model_path / "optuna_best_params.json", "w") as f:
                json.dump(self.best_params, f, indent=2)

        # ── Clean helpers ────────────────────────────────────────────────
        def clean_dict(d):
            return {
                k: (None if isinstance(v, float) and (np.isnan(v) or np.isinf(v)) else v)
                for k, v in d.items()
            }

        metrics_clean       = clean_dict(self.metrics)
        median_values_clean = clean_dict(getattr(self, "median_values_", {}))

        # ── Metadata ─────────────────────────────────────────────────────
        metadata = {
            "model_type":           self.model_type,
            "format":               model_format,
            "version":              "1.0.0",
            "trained_at":           datetime.utcnow().isoformat(),
            "n_features":           n_features,
            "feature_names":        self.feature_names,
            "categorical_features": self.categorical_features,
            "numeric_features":     self.numeric_features,
            "metrics":              metrics_clean,
            "median_values":        median_values_clean,
            "optuna_used":          self.best_params is not None,
            "best_params":          self.best_params,
        }

        with open(model_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        with open(model_path / "training_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)

        with open(model_path / "config.yaml", "w") as f:
            yaml.dump(config, f)

        logger.info(f"Model saved to {model_path}")
        logger.info(f"Model successfully uploaded to S3 bucket {config['bucket_name']}")

        return Path(model_path)

    # ------------------------------------------------------------------
    # CLEANUP
    # ------------------------------------------------------------------

    def remove_model_folder_from_local(self):
        local_folder = Path(self.config['models_dir'])
        try:
            shutil.rmtree(local_folder)
        except Exception as e:
            logger.error(f"Failed to delete folder {local_folder}: {e}")

    # ------------------------------------------------------------------
    # EVALUATION FIGURES (standard)
    # ------------------------------------------------------------------

    def generate_evaluation_figures(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series,
    ):
        """Generate and save standard regression evaluation figures."""

        output_dir  = Path(self.config["models_dir"]) / f"model_{datetime.now().strftime('%Y-%m-%d')}"
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        X_test_processed = self.preprocess_features(X_test, self.feature_names, fit=False)
        y_pred     = self.model.predict(X_test_processed)
        residuals  = y_test - y_pred
        abs_errors = np.abs(residuals)

        sns.set_style("whitegrid")

        # 1. Predicted vs Actual
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.scatter(y_test, y_pred, alpha=0.5)
        ax.plot(
            [y_test.min(), y_test.max()],
            [y_test.min(), y_test.max()],
            linestyle="--", linewidth=2, color="black", label="Perfect prediction",
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