"""
Module 3: Regime Models
Fits separate linear behavior models per regime.
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score, mean_absolute_error
from typing import Dict, List, Optional
import pickle
from pathlib import Path
import psycopg2


class RegimeModel:
    """Per-regime behavior model (linear)."""

    def __init__(self, regime_id: int, regime_name: str):
        self.regime_id = regime_id
        self.regime_name = regime_name
        self.model = None
        self.feature_names = None
        self.coef = {}
        self.intercept = None
        self.metrics = {}

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_names: List[str],
        alpha: float = 1.0
    ) -> Dict[str, float]:
        """Fit linear model for this regime."""

        self.feature_names = feature_names
        self.model = Ridge(alpha=alpha, random_state=42)
        self.model.fit(X, y)

        self.intercept = self.model.intercept_
        self.coef = dict(zip(feature_names, self.model.coef_))

        y_pred = self.model.predict(X)

        self.metrics = {
            'r2': float(r2_score(y, y_pred)),
            'mae': float(mean_absolute_error(y, y_pred)),
            'rmse': float(np.sqrt(np.mean((y - y_pred) ** 2))),
            'n_samples': len(y),
            'intercept': float(self.intercept)
        }

        return self.metrics

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict target under this regime"""
        if self.model is None:
            raise ValueError("Model not fitted")
        return self.model.predict(X)

    def summary(self) -> str:
        """Human-readable model summary"""

        summary = f"\n{'='*60}\n"
        summary += f"Regime {self.regime_id}: {self.regime_name}\n"
        summary += f"{'='*60}\n"
        summary += f"Intercept: {self.intercept:.4f}\n"
        summary += f"\nCoefficients:\n"

        for feat, coef in sorted(self.coef.items(), key=lambda x: abs(x[1]), reverse=True):
            summary += f"  {feat:.<30} {coef:>8.4f}\n"

        summary += f"\nMetrics:\n"
        summary += f"  R² Score:  {self.metrics.get('r2', 0):.4f}\n"
        summary += f"  MAE:       {self.metrics.get('mae', 0):.4f}\n"
        summary += f"  RMSE:      {self.metrics.get('rmse', 0):.4f}\n"
        summary += f"  N Samples: {self.metrics.get('n_samples', 0)}\n"

        return summary


class RegimeModelEnsemble:
    """Container for multiple regime-specific models."""

    def __init__(self, n_regimes: int = 3):
        self.n_regimes = n_regimes
        self.models = {}
        self.feature_names = None
        self.target_name = None

    def fit_all(
        self,
        df: pd.DataFrame,
        regime_col: str,
        target_col: str,
        feature_cols: List[str],
        alpha: float = 1.0
    ) -> Dict:
        """Train separate model for each regime."""

        self.feature_names = feature_cols
        self.target_name = target_col

        summary = {}

        for regime_id in range(self.n_regimes):
            regime_data = df[df[regime_col] == regime_id].copy()

            if len(regime_data) < 10:
                print(f"⚠️  Regime {regime_id}: only {len(regime_data)} samples, skipping")
                continue

            X = regime_data[feature_cols].fillna(0).values
            y = regime_data[target_col].fillna(0).values

            model = RegimeModel(regime_id, f"Regime_{regime_id}")
            metrics = model.fit(
                pd.DataFrame(X, columns=feature_cols),
                pd.Series(y),
                feature_cols,
                alpha=alpha
            )

            self.models[regime_id] = model
            summary[regime_id] = metrics

            print(f"✓ Regime {regime_id}: R²={metrics['r2']:.3f}, MAE={metrics['mae']:.3f}")

        return summary

    def predict(self, regime_id: int, X: pd.DataFrame) -> np.ndarray:
        """Predict using regime-specific model"""
        if regime_id not in self.models:
            raise ValueError(f"No model for regime {regime_id}")
        return self.models[regime_id].predict(X)

    def coefficient_comparison(self) -> pd.DataFrame:
        """Compare coefficients across regimes."""

        data = {}

        for regime_id, model in self.models.items():
            data[f"Regime_{regime_id}"] = model.coef

        df = pd.DataFrame(data).fillna(0)
        return df

    def save(self, dirpath: str) -> None:
        """Save all models to directory"""
        dirpath = Path(dirpath)
        dirpath.mkdir(parents=True, exist_ok=True)

        for regime_id, model in self.models.items():
            filepath = dirpath / f"regime_{regime_id}.pkl"
            with open(filepath, 'wb') as f:
                pickle.dump(model, f)

        metadata = {
            'feature_names': self.feature_names,
            'target_name': self.target_name,
            'n_regimes': self.n_regimes
        }
        with open(dirpath / 'metadata.pkl', 'wb') as f:
            pickle.dump(metadata, f)

    def load(self, dirpath: str) -> None:
        """Load all models from directory"""
        dirpath = Path(dirpath)

        with open(dirpath / 'metadata.pkl', 'rb') as f:
            metadata = pickle.load(f)

        self.feature_names = metadata['feature_names']
        self.target_name = metadata['target_name']
        self.n_regimes = metadata['n_regimes']

        for regime_id in range(self.n_regimes):
            filepath = dirpath / f"regime_{regime_id}.pkl"
            if filepath.exists():
                with open(filepath, 'rb') as f:
                    self.models[regime_id] = pickle.load(f)

    def print_summary(self) -> None:
        """Print summary of all regime models"""

        print("\n" + "="*70)
        print("REGIME MODEL ENSEMBLE SUMMARY")
        print("="*70)

        for regime_id in sorted(self.models.keys()):
            print(self.models[regime_id].summary())
