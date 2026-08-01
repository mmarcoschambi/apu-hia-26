"""
test_write_safety.py — Tests de contrato y seguridad de escritura para optimización y promoción de combos
"""

import json
import sys
from pathlib import Path
import pytest
import shutil
import math
from unittest.mock import patch

# Añadir la raíz al path para poder importar desde scripts
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sync_combo_config import sync, SRC, DST


@pytest.fixture
def setup_test_combo():
    """Fixture para crear y limpiar archivos temporales de prueba."""
    test_combo_name = "combo_test_write_safety"
    src_file = SRC / f"{test_combo_name}_optimized.json"
    dst_file = DST / f"{test_combo_name}_config.json"
    bak_file = DST / f"{test_combo_name}_config.json.bak"

    # Limpiar antes
    for f in [src_file, dst_file, bak_file]:
        if f.exists():
            f.unlink()

    yield test_combo_name

    # Limpiar después
    for f in [src_file, dst_file, bak_file]:
        if f.exists():
            f.unlink()


def test_dry_run_does_not_write(setup_test_combo):
    """Test 2: Dry-run sin --promote no debe escribir en outputs."""
    name = setup_test_combo
    src_file = SRC / f"{name}_optimized.json"
    dst_file = DST / f"{name}_config.json"

    # Crear candidato válido
    candidate = {
        "name": name,
        "description": "Test combo desc",
        "optimized_at": "2026-07-16T12:00:00",
        "validation_passed": True,
        "optimization_score": 1.25,
        "screener": "minervini_trend",
        "pattern": "vcp",
        "tier1_exits": {"tp1_r": 1.5},
        "tier2_filters": {"min_adr": 2.0},
        "tier3_fixed": {"max_exposure_pct": 0.3},
        "validation": {
            "profit_factor": 1.8,
            "sharpe_ratio": 1.2,
            "total_trades": 25
        }
    }
    src_file.write_text(json.dumps(candidate))

    # Ejecutar sync en modo Dry-Run (promote=False)
    res = sync(name, promote=False)

    assert res is True
    assert not dst_file.exists(), "Dry-run no debería haber creado el archivo en outputs."


def test_promotion_success_with_metadata(setup_test_combo):
    """Test 3: La promoción exitosa escribe en outputs e inyecta metadatos obligatorios."""
    name = setup_test_combo
    src_file = SRC / f"{name}_optimized.json"
    dst_file = DST / f"{name}_config.json"

    candidate = {
        "name": name,
        "description": "Test combo desc",
        "optimized_at": "2026-07-16T12:00:00",
        "validation_passed": True,
        "optimization_score": 1.25,
        "screener": "minervini_trend",
        "pattern": "vcp",
        "tier1_exits": {"tp1_r": 1.5},
        "tier2_filters": {"min_adr": 2.0},
        "tier3_fixed": {"max_exposure_pct": 0.3},
        "oos_metrics": {
            "profit_factor": 1.8,
            "sharpe_ratio": 1.2,
            "trades": 160,
            "dsr": 0.5,
            "mdd_pct": -15.0
        },
        "params_json_source": "mocked_path"
    }
    src_file.write_text(json.dumps(candidate))

    # Ejecutar promoción
    with patch("src.validation.param_gate.assert_params_cleared", return_value={"gate_passed": True}):
        res = sync(name, promote=True)

    assert res is True
    assert dst_file.exists()

    # Validar metadatos inyectados
    promoted = json.loads(dst_file.read_text())
    assert "governance_hash" in promoted
    assert "promoted_at" in promoted
    assert promoted["approved_source"] == "sync_combo_config"


def test_block_when_validation_failed(setup_test_combo):
    """Test 4: Candidatos con validation_passed=False o sin clave son rechazados y no se promueven."""
    name = setup_test_combo
    src_file = SRC / f"{name}_optimized.json"
    dst_file = DST / f"{name}_config.json"

    # Caso validation_passed = False
    candidate = {
        "name": name,
        "validation_passed": False,
        "validation": {"profit_factor": 1.5}
    }
    src_file.write_text(json.dumps(candidate))

    res = sync(name, promote=True)
    assert res is False
    assert not dst_file.exists()


def test_hard_sanity_threshold_rejection(setup_test_combo):
    """Umbral de sanidad duro: se rechazan profit_factor anómalos (ej. 999.0 o infinitos)."""
    name = setup_test_combo
    src_file = SRC / f"{name}_optimized.json"
    dst_file = DST / f"{name}_config.json"

    # Caso profit_factor = 999.0 (anómalo)
    candidate = {
        "name": name,
        "validation_passed": True,
        "validation": {"profit_factor": 999.0}
    }
    src_file.write_text(json.dumps(candidate))

    res = sync(name, promote=True)
    assert res is False
    assert not dst_file.exists(), "Debería rechazar por superar el umbral duro de profit_factor."

    # Caso profit_factor = NaN/inf
    candidate = {
        "name": name,
        "validation_passed": True,
        "oos_metrics": {"profit_factor": float('inf'), "trades": 35, "dsr": 2.5, "mdd_pct": -5.0}
    }
    src_file.write_text(json.dumps(candidate))

    res = sync(name, promote=True)
    assert res is False
    assert not dst_file.exists()


def test_one_step_backup_and_atomic_replace(setup_test_combo):
    """Escritura atómica + backup de un paso: el archivo original se respalda en .bak antes de pisarse."""
    name = setup_test_combo
    src_file = SRC / f"{name}_optimized.json"
    dst_file = DST / f"{name}_config.json"
    bak_file = DST / f"{name}_config.json.bak"

    # 1. Crear un archivo previo en outputs y simular que ya estaba aprobado
    old_data = {"name": name, "approved": True, "version": "old"}
    dst_file.write_text(json.dumps(old_data))

    # 2. Crear el nuevo candidato optimizado válido
    candidate = {
        "name": name,
        "validation_passed": True,
        "oos_metrics": {"profit_factor": 2.1, "trades": 160, "dsr": 0.5, "mdd_pct": -15.0},
        "params_json_source": "mocked_path"
    }
    src_file.write_text(json.dumps(candidate))

    # 3. Promover
    with patch("src.validation.param_gate.assert_params_cleared", return_value={"gate_passed": True}):
        res = sync(name, promote=True)

    assert res is True
    assert dst_file.exists()
    assert bak_file.exists(), "El backup .bak de la versión previa no fue creado."

    # Verificar que el backup contiene los datos viejos
    backup_content = json.loads(bak_file.read_text())
    assert backup_content["version"] == "old"

    # Verificar que el nuevo contiene los datos actualizados
    new_content = json.loads(dst_file.read_text())
    assert "governance_hash" in new_content
    assert new_content["oos_metrics"]["profit_factor"] == 2.1
