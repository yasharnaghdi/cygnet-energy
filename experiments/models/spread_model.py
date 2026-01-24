from sklearn.linear_model import LinearRegression
import pandas as pd
import numpy as np
class SpreadModel:
    """FR-DE price spread under regime"""

    def __init__(self):
        self.models = {} # regime -> fitted model

    def fit_regime_models(self, df: pd.DataFrame, regime_col: str) -> None:
        """Train seperate model per regime"""

        for regime in df[regime_col].unique():
            regime_data = df[df[regime_col] == regime]

            X = regime_data[['net_flow_fr_de', 'res_asymmetry', 'congestion_score']]
            y = regime_data['spread_fr_de']     # p_FR - # p_DR


            model = LinearRegression()
            model.fit(X, y)
            self.models[regime] = {
                'model' : model,
                'coef' : dict(zip(['flow', 'res_asym','cong'], model.coef_))
            }
    def stress_test(self, regime: str, base_x: dict, shock: dict) -> dict:
        """Counterfactual: what if res_asymmetry += 15%? """

        model = self.models[regime]['model']
        X_base = np.array([base_x['flow'], base_x['res_asym'], base_x['cong']])
        p_base = model.predict([X_base])[0]

        X_shocked = X_base.copy()
        X_shocked[shock['feature_idx']] += shock['delta']
        p_shocked = model.predict([X_shocked])[0]

        return {
            'baseline_spread': p_base,
            'shocked_spread': p_shocked,
            'delta': p_shocked - p_base,
            'pct_change': (p_shocked - p_base) / abs(p_base) * 100
        }
