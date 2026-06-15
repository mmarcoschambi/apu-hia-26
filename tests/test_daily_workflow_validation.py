import os
import sys
from pathlib import Path
import json
import pytest

# Add project root to sys.path to find daily_workflow module
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

from daily_workflow import DailyWorkflow

def test_daily_workflow_validate_subcommand(monkeypatch, tmp_path):
    """
    Verifica que la rutina run_validation se ejecute sin errores y cree los reportes correctos.
    """
    # Crear un directorio temporal para outputs
    output_dir = tmp_path / "outputs" / "backtests"
    output_dir.mkdir(parents=True)
    
    # Crear una configuracion de produccion ficticia
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    prod_config_file = config_dir / "production_config.json"
    
    mock_config = {
        "tier2_filters": {
            "max_dist_sma20": 8.94,
            "min_rvol": 0.91,
            "min_adr": 1.97
        },
        "tier1_strategy": {
            "tp1_r": 1.25,
            "tp2_r": 3.0
        },
        "tier3_fixed": {
            "use_dynamic_extension_sizing": True,
            "dynamic_extension_sizing": {
                "version": "v2_atlas_informed"
            }
        }
    }
    
    prod_config_file.write_text(json.dumps(mock_config))
    
    # Mockear paths
    monkeypatch.setattr("daily_workflow.Path", lambda *args: tmp_path / Path(*args) if args else tmp_path)
    
    # Mockear el modulo vectorbt / stress testing para no ejecutar simulaciones reales lentas
    from src.validation.stress_testing import StressTestResult
    
    class MockStressTestSuite:
        def __init__(self, engine_class):
            pass
        def run_full_stress_test(self, params, universe, test_dates, verbose):
            # Devolver resultado real de la dataclass
            return StressTestResult(
                all_passed=True,
                baseline_return=10.0,
                cost_stress_passed=True,
                liquidity_stress_passed=True,
                gap_risk_passed=True,
                capacity_passed=True,
                correlation_stress_passed=True,
                worst_case_passed=True,
                impact_2x_costs=0.0,
                impact_3x_costs=0.0,
                impact_5x_costs=0.0,
                impact_wider_spreads=0.0,
                impact_extreme_spreads=0.0,
                impact_gap_1pct=0.0,
                impact_gap_2pct=0.0,
                avg_position_size_dollars=1000.0,
                max_position_size_dollars=2000.0,
                min_liquidity_dollar_volume=5000000.0,
                impact_high_correlation=-2.0,
                impact_worst_case=-5.0,
                scenario_details={},
                failure_reasons=[]
            )
            
    monkeypatch.setattr("src.validation.stress_testing.StressTestSuite", MockStressTestSuite)
    
    # Mockear AdvancedVectorBTEngine para evitar carga de datos real
    class MockAdvancedVectorBTEngine:
        def __init__(self, **kwargs):
            pass
        def load_data(self):
            pass
        def run_backtest(self):
            return {
                "equity": [1000.0] * 40,  # Suficiente longitud para calcular robustez
                "trades": [],
                "sharpe_ratio": 1.5,
                "max_drawdown": -5.0,
                "win_rate": 60.0,
                "profit_factor": 2.0
            }
            
    monkeypatch.setattr("src.backtest.vectorbt_engine_advanced.AdvancedVectorBTEngine", MockAdvancedVectorBTEngine)
    
    # Inicializar workflow
    workflow = DailyWorkflow()
    # Forzar watchlist ficticia
    workflow.watchlist = ["AAPL"]
    
    # Ejecutar validacion
    workflow.run_validation()
    
    # Verificar que se crearon los archivos
    stress_report_path = output_dir / "daily_workflow_stress_report.json"
    robustness_report_path = output_dir / "daily_workflow_robustness_report.json"
    
    assert stress_report_path.exists(), "El reporte de stress test deberia haber sido creado"
    assert robustness_report_path.exists(), "El reporte de robustez deberia haber sido creado"
    
    # Leer y validar contenido
    with open(stress_report_path, "r") as f:
        data = json.load(f)
        assert data["all_passed"] is True
        
    with open(robustness_report_path, "r") as f:
        data = json.load(f)
        assert "risk_adjusted" in data
        assert data["probability_of_loss"] >= 0.0
