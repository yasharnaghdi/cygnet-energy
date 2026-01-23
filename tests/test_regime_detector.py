import pandas as pd

from src.models.modules_2_regime_detector import RegimeDetector


def test_regime_detector_fit_and_predict():
    df = pd.DataFrame(
        {
            "res_penetration": [10, 20, 30, 60, 70, 80],
            "net_import": [400, 200, -100, -300, -500, -600],
            "price_volatility": [5, 6, 7, 3, 2, 4],
        }
    )

    detector = RegimeDetector(n_regimes=2)
    metrics = detector.fit(df)

    assert metrics["n_regimes"] == 2
    result = detector.predict_regime(50, -200, 4)

    assert "regime_id" in result
    assert "regime_name" in result
    assert 0 <= result["confidence"] <= 1

    labeled = detector.analyze_df(df)
    assert "regime_id" in labeled.columns
    assert "regime_name" in labeled.columns
    assert "regime_confidence" in labeled.columns
