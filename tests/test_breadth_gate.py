import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

class TestBreadthGate(unittest.TestCase):

    @patch("src.backtest.vectorbt_engine_advanced.sqlite3.connect")
    def test_breadth_gate_no_selection_bias_and_warmup(self, mock_connect):
        # 1. Crear entries mockeadas de simulación (2 tickers, 3 días)
        dates = pd.to_datetime(["2019-01-01", "2019-01-02", "2019-01-03"])
        entries = pd.DataFrame(True, index=dates, columns=["T1", "T2"])

        # 2. Mockear la consulta SQL.
        # Debe incluir datos de calentamiento de 2018 y tickers adicionales (T3, T4) para validar sin sesgo.
        sql_data = pd.DataFrame([
            # Datos de calentamiento (2018)
            {"ticker": "T1", "date": "2018-12-30", "close": 100.0, "high": 105.0, "low": 95.0},
            {"ticker": "T2", "date": "2018-12-30", "close": 100.0, "high": 105.0, "low": 95.0},
            {"ticker": "T3", "date": "2018-12-30", "close": 100.0, "high": 105.0, "low": 95.0},
            {"ticker": "T4", "date": "2018-12-30", "close": 100.0, "high": 105.0, "low": 95.0},
            
            # Datos de simulación (2019)
            {"ticker": "T1", "date": "2019-01-01", "close": 101.0, "high": 106.0, "low": 96.0},
            {"ticker": "T2", "date": "2019-01-01", "close": 99.0, "high": 104.0, "low": 94.0},
            {"ticker": "T3", "date": "2019-01-01", "close": 101.0, "high": 106.0, "low": 96.0},
            {"ticker": "T4", "date": "2019-01-01", "close": 101.0, "high": 106.0, "low": 96.0},
            
            {"ticker": "T1", "date": "2019-01-02", "close": 102.0, "high": 107.0, "low": 97.0},
            {"ticker": "T2", "date": "2019-01-02", "close": 98.0, "high": 103.0, "low": 93.0},
            {"ticker": "T3", "date": "2019-01-02", "close": 102.0, "high": 107.0, "low": 97.0},
            {"ticker": "T4", "date": "2019-01-02", "close": 102.0, "high": 107.0, "low": 97.0},
            
            {"ticker": "T1", "date": "2019-01-03", "close": 103.0, "high": 108.0, "low": 98.0},
            {"ticker": "T2", "date": "2019-01-03", "close": 97.0, "high": 102.0, "low": 92.0},
            {"ticker": "T3", "date": "2019-01-03", "close": 103.0, "high": 108.0, "low": 98.0},
            {"ticker": "T4", "date": "2019-01-03", "close": 103.0, "high": 108.0, "low": 98.0},
        ])

        with patch("pandas.read_sql_query", return_value=sql_data) as mock_read_sql:
            engine = AdvancedVectorBTEngine(
                universe=["T1", "T2"],
                start_date="2019-01-01",
                end_date="2019-01-03",
                use_breadth_filter=True,
                breadth_filter_mode="nh_nl",
                breadth_filter_threshold=0.5,
            )
            mask = engine._build_breadth_mask(entries)
            
            # Aserción 1: Sin sesgo de selección en SQL
            sql_query = mock_read_sql.call_args[0][0]
            self.assertNotIn("ticker IN", sql_query, "La consulta SQL tiene sesgo de selección (filtra por ticker)")

            # Aserción 2: Warm-up exitoso (datos de 2018 considerados en el primer día del backtest)
            # En 2019-01-01:
            # - T1: close=101 >= high_shift1(105) -> False (0)
            # - T2: close=99 >= high_shift1(105) -> False (0)
            # - T3: close=101 >= high_shift1(105) -> False (0)
            # - T4: close=101 >= high_shift1(105) -> False (0)
            # Para nuevos mínimos:
            # - T1: close=101 <= low_shift1(95) -> False (0)
            # - T2: close=99 <= low_shift1(95) -> False (0)
            # - T3: close=101 <= low_shift1(95) -> False (0)
            # - T4: close=101 <= low_shift1(95) -> False (0)
            # Como ambos son 0, ratio = 0.0.
            #
            # En 2019-01-02:
            # - T1: close=102 >= high_shift1(106) -> False
            # - T2: close=98 <= low_shift1(94) -> False
            # - T3: close=102 >= high_shift1(106) -> False
            # - T4: close=102 >= high_shift1(106) -> False
            #
            # Modifiquemos un dato de simulación para que dé un ratio válido (ej: Nuevos Máximos >= 0.5)
            # Para asegurar que la aserción de warm-up sea robusta, lo ideal es verificar que el ratio no sea NaN.
            # En el engine viejo, la serie ratio tendrá NaN el primer día.
            # En el engine nuevo, ratio será una serie numérica limpia (ej: 0.0 o 0.75) y no NaN.
            self.assertIsNotNone(engine.breadth_metric_series, "La serie de métricas de breadth no se generó")
            self.assertFalse(np.isnan(engine.breadth_metric_series.loc["2019-01-01"]), "El primer día es NaN (fallo de warm-up)")

if __name__ == "__main__":
    unittest.main()
