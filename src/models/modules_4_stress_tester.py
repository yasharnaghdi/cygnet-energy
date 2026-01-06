"""
Module 4: Stress Tester
Counterfactual scenario engine: perturb system state and observe impact.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class StressScenario:
    """Represents a counterfactual scenario"""
    name: str
    description: str
    perturbations: Dict[str, float]
    regime_id: Optional[int] = None


class StressTester:
    """Virtual stress testing engine."""
    
    def __init__(self, regime_models):
        """
        Args:
            regime_models: RegimeModelEnsemble instance (fitted)
        """
        self.regime_models = regime_models
        self.feature_names = regime_models.feature_names
    
    def stress_single_feature(
        self,
        regime_id: int,
        base_state: Dict[str, float],
        feature: str,
        delta: float
    ) -> Dict:
        """Stress one feature, hold everything else constant."""
        
        X_base = pd.DataFrame([base_state])
        y_base = self.regime_models.predict(regime_id, X_base)[0]
        
        X_shocked = X_base.copy()
        X_shocked[feature] += delta
        y_shocked = self.regime_models.predict(regime_id, X_shocked)[0]
        
        delta_pred = y_shocked - y_base
        pct_change = (delta_pred / abs(y_base)) * 100 if y_base != 0 else 0
        elasticity = (pct_change / 100) / (delta / base_state[feature]) if base_state[feature] != 0 else 0
        
        return {
            'scenario': f"{feature}_{delta:+.1f}",
            'regime_id': regime_id,
            'regime_name': f"Regime_{regime_id}",
            'baseline_pred': float(y_base),
            'shocked_pred': float(y_shocked),
            'delta_pred': float(delta_pred),
            'pct_change': float(pct_change),
            'elasticity': float(elasticity),
            'feature_shocked': feature,
            'perturbation_size': float(delta),
            'base_state': base_state.copy(),
            'shocked_state': X_shocked.iloc[0].to_dict()
        }
    
    def stress_combined(
        self,
        regime_id: int,
        base_state: Dict[str, float],
        perturbations: Dict[str, float]
    ) -> Dict:
        """Stress multiple features simultaneously."""
        
        X_base = pd.DataFrame([base_state])
        y_base = self.regime_models.predict(regime_id, X_base)[0]
        
        X_shocked = X_base.copy()
        for feature, delta in perturbations.items():
            X_shocked[feature] += delta
        
        y_shocked = self.regime_models.predict(regime_id, X_shocked)[0]
        
        delta_pred = y_shocked - y_base
        pct_change = (delta_pred / abs(y_base)) * 100 if y_base != 0 else 0
        
        individual_effects = {}
        model = self.regime_models.models[regime_id]
        for feature, delta in perturbations.items():
            coef = model.coef.get(feature, 0)
            individual_effects[feature] = {
                'coefficient': float(coef),
                'contribution': float(coef * delta),
                'pct_of_total': float((coef * delta / delta_pred * 100) if delta_pred != 0 else 0)
            }
        
        return {
            'scenario': 'Combined Shock',
            'regime_id': regime_id,
            'regime_name': f"Regime_{regime_id}",
            'baseline_pred': float(y_base),
            'shocked_pred': float(y_shocked),
            'delta_pred': float(delta_pred),
            'pct_change': float(pct_change),
            'perturbations': perturbations,
            'individual_effects': individual_effects,
            'base_state': base_state.copy(),
            'shocked_state': X_shocked.iloc[0].to_dict()
        }
    
    def sensitivity_curve(
        self,
        regime_id: int,
        base_state: Dict[str, float],
        feature: str,
        delta_range: Tuple[float, float],
        n_points: int = 10
    ) -> pd.DataFrame:
        """Sweep feature over range, plot sensitivity curve."""
        
        results = []
        
        X_base = pd.DataFrame([base_state])
        y_base = self.regime_models.predict(regime_id, X_base)[0]
        
        deltas = np.linspace(delta_range[0], delta_range[1], n_points)
        
        for delta in deltas:
            X_shocked = X_base.copy()
            X_shocked[feature] += delta
            y_shocked = self.regime_models.predict(regime_id, X_shocked)[0]
            
            delta_pred = y_shocked - y_base
            feature_value = base_state[feature] + delta
            
            results.append({
                'feature_value': feature_value,
                'perturbation': delta,
                'predicted_output': y_shocked,
                'delta_pred': delta_pred,
                'baseline': y_base,
                'pct_change': (delta_pred / abs(y_base) * 100) if y_base != 0 else 0
            })
        
        return pd.DataFrame(results)
    
    def regime_comparison(
        self,
        base_state: Dict[str, float],
        feature: str,
        delta: float
    ) -> pd.DataFrame:
        """Apply same shock across all regimes, compare outcomes."""
        
        results = []
        
        for regime_id in sorted(self.regime_models.models.keys()):
            outcome = self.stress_single_feature(
                regime_id, base_state, feature, delta
            )
            results.append(outcome)
        
        return pd.DataFrame(results)
    
    def scenario_library(self) -> Dict[str, StressScenario]:
        """Pre-defined realistic scenarios."""
        
        return {
            'renewable_surge': StressScenario(
                name='Renewable Surge',
                description='RES penetration increases 15%',
                perturbations={'res_penetration': +15}
            ),
            'congestion_shock': StressScenario(
                name='Congestion Crisis',
                description='Interconnect saturation rises 30%',
                perturbations={'interconnect_saturation': +30}
            ),
            'import_crisis': StressScenario(
                name='Import Dependency',
                description='Net imports surge 500 MW',
                perturbations={'net_import': +500}
            ),
            'volatility_spike': StressScenario(
                name='Volatility Spike',
                description='Price volatility increases 50%',
                perturbations={'price_volatility': +50}
            ),
            'perfect_storm': StressScenario(
                name='Perfect Storm',
                description='RES drops, import demand rises',
                perturbations={
                    'res_penetration': -10,
                    'net_import': +400,
                    'price_volatility': +30
                }
            )
        }
    
    def run_scenario(
        self,
        scenario: StressScenario,
        base_state: Dict[str, float],
        regime_id: Optional[int] = None
    ) -> Dict:
        """Execute a pre-defined scenario."""
        
        if regime_id is not None:
            return self.stress_combined(regime_id, base_state, scenario.perturbations)
        
        results = {}
        for rid in sorted(self.regime_models.models.keys()):
            results[rid] = self.stress_combined(rid, base_state, scenario.perturbations)
        
        return results
    
    def narrative(self, outcome: Dict) -> str:
        """Convert numerical outcome into human-readable narrative."""
        
        regime = outcome['regime_name']
        delta_pred = outcome['delta_pred']
        pct_change = outcome['pct_change']
        
        magnitude = abs(delta_pred)
        
        narrative = (
            f"Under {regime}, stress leads to €{magnitude:.2f}/MWh change "
            f"({pct_change:+.1f}%). "
        )
        
        if 'individual_effects' in outcome:
            narrative += "Key drivers: "
            effects = outcome['individual_effects']
            sorted_effects = sorted(
                effects.items(),
                key=lambda x: abs(x[1]['contribution']),
                reverse=True
            )[:2]
            
            for feat, effect in sorted_effects:
                contrib = effect['contribution']
                direction = "+" if contrib > 0 else ""
                narrative += f"{feat} ({direction}€{contrib:.2f}), "
            
            narrative = narrative.rstrip(", ") + "."
        
        return narrative
