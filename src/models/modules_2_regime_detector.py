"""
Module 2: Regime Detector
Clusters hours into 3-4 operating modes (Normal, Stressed, RES-Dominant, etc.)
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from typing import Dict, List, Optional
import pickle
from pathlib import Path
import psycopg2


class RegimeDetector:
    """
    Unsupervised regime detection via clustering.
    
    Regimes (typical output):
    - 0: "Normal" - balanced supply/demand, low volatility
    - 1: "Stressed" - high import need, tight capacity
    - 2: "RES-Dominant" - high renewable penetration, low imports
    """
    
    REGIME_NAMES = {
        0: "Normal",
        1: "Stressed",
        2: "RES-Dominant"
    }
    
    def __init__(self, n_regimes: int = 3, random_state: int = 42):
        self.n_regimes = n_regimes
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.kmeans = None
        self.centroids = None
        self.feature_names = ['res_penetration', 'net_import', 'price_volatility']
    
    def fit(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Fit regime detector on historical state variables.
        
        Returns:
            Metrics dict: {silhouette_score, inertia, n_samples}
        """
        
        features = df[self.feature_names].values
        mask = ~np.isnan(features).any(axis=1)
        features = features[mask]
        
        if len(features) < self.n_regimes:
            raise ValueError(f"Need at least {self.n_regimes} samples")
        
        features_scaled = self.scaler.fit_transform(features)
        
        self.kmeans = KMeans(
            n_clusters=self.n_regimes,
            random_state=self.random_state,
            n_init=10
        )
        self.kmeans.fit(features_scaled)
        self.centroids = self.scaler.inverse_transform(self.kmeans.cluster_centers_)
        
        sil_score = silhouette_score(features_scaled, self.kmeans.labels_)
        inertia = self.kmeans.inertia_
        
        return {
            'silhouette_score': sil_score,
            'inertia': inertia,
            'n_samples': len(features),
            'n_regimes': self.n_regimes
        }
    
    def predict_regime(
        self,
        res_penetration: float,
        net_import: float,
        price_volatility: float
    ) -> Dict[str, object]:
        """
        Predict regime for a single system state.
        
        Returns:
            Dict with regime_id, regime_name, confidence, state_vector
        """
        
        if self.kmeans is None:
            raise ValueError("Model not fitted. Call fit() first.")
        
        state = np.array([[res_penetration, net_import, price_volatility]])
        state_scaled = self.scaler.transform(state)
        
        regime_id = self.kmeans.predict(state_scaled)[0]
        
        distances = np.linalg.norm(state_scaled - self.kmeans.cluster_centers_, axis=1)
        sorted_dist = np.sort(distances)
        confidence = 1.0 - (sorted_dist[0] / (sorted_dist[1] + 1e-6))
        
        return {
            'regime_id': int(regime_id),
            'regime_name': self.REGIME_NAMES.get(regime_id, f"Regime_{regime_id}"),
            'confidence': float(confidence),
            'state_vector': [res_penetration, net_import, price_volatility]
        }
    
    def regime_profile(self, regime_id: int) -> Dict[str, float]:
        """Return centroid profile of a regime."""
        
        if self.centroids is None:
            raise ValueError("Model not fitted.")
        
        if regime_id >= len(self.centroids):
            raise ValueError(f"Regime {regime_id} not found")
        
        centroid = self.centroids[regime_id]
        
        return {
            'regime_id': regime_id,
            'regime_name': self.REGIME_NAMES[regime_id],
            'res_penetration': float(centroid[0]),
            'net_import': float(centroid[1]),
            'price_volatility': float(centroid[2])
        }
    
    def analyze_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Assign regimes to all rows in DataFrame."""
        
        results = []
        for _, row in df.iterrows():
            pred = self.predict_regime(
                row['res_penetration'],
                row['net_import'],
                row['price_volatility']
            )
            results.append({
                'regime_id': pred['regime_id'],
                'regime_name': pred['regime_name'],
                'regime_confidence': pred['confidence']
            })
        
        result_df = pd.concat([df, pd.DataFrame(results)], axis=1)
        return result_df
    
    def save(self, filepath: str) -> None:
        """Serialize model to disk"""
        model_dict = {
            'scaler': self.scaler,
            'kmeans': self.kmeans,
            'centroids': self.centroids,
            'n_regimes': self.n_regimes,
            'feature_names': self.feature_names,
            'regime_names': self.REGIME_NAMES
        }
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump(model_dict, f)
    
    def load(self, filepath: str) -> None:
        """Deserialize model from disk"""
        with open(filepath, 'rb') as f:
            model_dict = pickle.load(f)
        self.scaler = model_dict['scaler']
        self.kmeans = model_dict['kmeans']
        self.centroids = model_dict['centroids']
        self.n_regimes = model_dict['n_regimes']
        self.feature_names = model_dict['feature_names']
    
    def save_to_db(
        self,
        df: pd.DataFrame,
        conn: psycopg2.extensions.connection,
        table_name: str = 'regime_states'
    ) -> int:
        """Update regime_states table with regime assignments."""
        
        cursor = conn.cursor()
        updated = 0
        
        for _, row in df.iterrows():
            cursor.execute(f"""
                UPDATE {table_name}
                SET regime_id = %s,
                    regime_name = %s,
                    regime_confidence = %s
                WHERE time = %s
                  AND zone = %s
            """, (
                row['regime_id'],
                row['regime_name'],
                float(row['regime_confidence']),
                row['time'],
                row['zone']
            ))
            updated += cursor.rowcount
        
        conn.commit()
        cursor.close()
        
        return updated
