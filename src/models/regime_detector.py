import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import pandas as pd

class RegimeDetector:
    def __init__(self, n_regimes=3):
        self.n_regimes = n_regimes
        self.scaler = StandardScaler()
        self.kmeans = None
        self.regime_names = {
            0: "Normal",
            1: "Congested",
            2: "RES-Dominant"
        }

    def fit(self, df: pd.DataFrame) -> None:
        """Fit on historical data"""
        features = df[['res_penetration', 'net_import', 'price_volatility']].values
        scaled = self.scaler.fit_transform(features)
        self.kmeans = KMeans(n_clusters=self.n_regimes, random_state=42)
        self.kmeans.fit(scaled)

    def predict_regime(self, res_pct: float, net_import: float, volatility: float) -> str:
        """Return current regime"""
        state = np.array([[res_pct, net_import, volatility]])
        scaled = self.scaler.transform(state)
        regime_id = self.kmeans.predict(scaled)[0]
        return self.regime_names[regime_id]
