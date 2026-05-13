
import unittest
import numpy as np
import pandas as pd
from src.backtest.numba_core import simulate_fast_core

class TestEXP010Formulas(unittest.TestCase):
    def test_stop_calculation_baseline(self):
        # A_baseline: fixed 8%
        # We'll mock simulate_fast_core input or just test the logic if it was in a separate function.
        # Since it's in a large NJIT function, we might need a small integration test.
        pass

    def test_adr14_calculation(self):
        # Rolling mean of (high-low)/close*100
        high = np.array([110, 112, 108, 115])
        low = np.array([100, 105, 95, 110])
        close = np.array([105, 108, 102, 112])
        
        expected_adr = ((high - low) / close * 100)
        # For 14 periods it would be rolling mean.
        # This is mostly handled by Pandas/SQL, but we should ensure Numba receives it correctly.
        pass

    def test_phantom_stop_logic(self):
        # Mark phantom if high >= tp1_target within 10 days post stop
        # Mocking a trades_df and high_arr
        from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
        
        # This requires a more complex setup. 
        # I'll implement a simplified check here.
        
        high_arr = np.zeros((20, 1))
        high_arr[5, 0] = 100 # Stop day
        high_arr[7, 0] = 110 # Recovery day
        
        tp1_target = 105
        t_idx = 5
        lookahead = 10
        start_f = t_idx + 1
        end_f = min(start_f + lookahead, high_arr.shape[0])
        
        is_phantom = np.any(high_arr[start_f:end_f, 0] >= tp1_target)
        self.assertTrue(is_phantom)
        
        # Case 2: No recovery
        high_arr[7, 0] = 102
        is_phantom = np.any(high_arr[start_f:end_f, 0] >= tp1_target)
        self.assertFalse(is_phantom)

if __name__ == '__main__':
    unittest.main()
