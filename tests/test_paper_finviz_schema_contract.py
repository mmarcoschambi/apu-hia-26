"""Schema contract tests for pre-market Finviz snapshots (issue #74).

Los snapshots productivos (outputs/paper_finviz/) perdieron la key
``avg_volume_20d`` silenciosamente: ``_build_watchlist_detail`` crasheaba por
ticker antes de escribirla y sus stubs de error no aportaban nada al merge de
enriquecido, asi que cada candidato conservaba el shape crudo del engine. El
gatillo live (#73) necesita esa key para calcular el RVOL real.

Capas cubiertas:
1. Contrato del productor: ``scan_signals`` debe emitir detalle completo sin
   stubs y con ``avg_volume_20d`` numerica > 0 para TODOS los candidatos.
2. Guard anti-drift: ``validate_snapshot()`` consume fixtures con el schema
   REAL de produccion y falla ruidosamente si ``avg_volume_20d`` desaparece.
3. Wiring en ``run_pre``: un snapshot driftedo debe exponer
   ``schema_contract_violations``.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.paper_finviz as pf  # noqa: E402, I001
from src.validation.snapshot_contract import validate_snapshot  # noqa: E402, I001

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DRIFTED_FIXTURE = FIXTURES_DIR / "paper_finviz_snapshot_drifted.json"
TRADE_DATE = "2026-08-21"


def _load_drifted_fixture() -> dict:
    """Fixture copiado del snapshot productivo 2026-08-21 (schema driftedo real)."""
    return json.loads(DRIFTED_FIXTURE.read_text(encoding="utf-8"))


def _raw_detail_template() -> dict:
    """Entrada cruda del engine (shape real de produccion, sin avg_volume_20d)."""
    return dict(_load_drifted_fixture()["watchlist_detail"]["KKR"])


def _fake_market_data(tickers: list[str]) -> dict[str, pd.DataFrame]:
    idx = pd.bdate_range(end=TRADE_DATE, periods=220)
    closes, highs, lows, vols, emas, sma20s, sma50s, rvols, adrs, dvols = (
        {} for _ in range(10)
    )
    for i, ticker in enumerate(tickers):
        close = pd.Series(100.0 + i * 10 + 0.05 * np.arange(len(idx)), index=idx)
        high = close * 1.01
        low = close * 0.99
        volume = pd.Series(2_000_000.0 + i * 50_000, index=idx)
        closes[ticker] = close
        highs[ticker] = high
        lows[ticker] = low
        vols[ticker] = volume
        emas[ticker] = close.ewm(span=10, adjust=False, min_periods=1).mean()
        sma20s[ticker] = close.rolling(20, min_periods=1).mean()
        sma50s[ticker] = close.rolling(50, min_periods=1).mean()
        rvols[ticker] = volume / volume.rolling(20, min_periods=1).mean()
        adrs[ticker] = pd.Series(3.5, index=idx)
        dvols[ticker] = close * volume
    return {
        "close": pd.DataFrame(closes),
        "high": pd.DataFrame(highs),
        "low": pd.DataFrame(lows),
        "volume": pd.DataFrame(vols),
        "ema_10": pd.DataFrame(emas),
        "sma_20": pd.DataFrame(sma20s),
        "sma_50": pd.DataFrame(sma50s),
        "rvol": pd.DataFrame(rvols),
        "adr_pct": pd.DataFrame(adrs),
        "dollar_volume": pd.DataFrame(dvols),
    }


class FakeEngine:
    """Espeja la superficie de atributos que paper_finviz consume del engine.

    Importante: NO define sma_100/sma_200 porque el engine real tampoco los
    tiene (ver comentario en vectorbt_engine_advanced.py).
    """

    max_dist_sma20 = 6.77

    def __init__(self, tickers: list[str]):
        data = _fake_market_data(tickers)
        for name, frame in data.items():
            setattr(self, name, frame)
        self.ticker_to_etf_map = {}
        self.etf_dist_matrix = None
        self.end_date = TRADE_DATE

    def run_backtest(self) -> dict:
        raw_template = _raw_detail_template()
        return {
            "rejected_tickers": [],
            "trades_df": pd.DataFrame(),
            "setups": [],
            "eligible_watchlist": {"KKR": 90.0, "PPL": 80.0},
            "watchlist_detail": {t: dict(raw_template) for t in ("KKR", "PPL")},
        }

    def cleanup(self) -> None:
        pass


@pytest.fixture
def producer_env(monkeypatch, tmp_path):
    """Mockea las dependencias externas de scan_signals dejando el builder real."""
    fake_engine = FakeEngine(["KKR", "PPL"])
    monkeypatch.setattr(pf, "AdvancedVectorBTEngine", lambda *a, **k: fake_engine)
    monkeypatch.setattr(pf, "load_combo_params", lambda *a, **k: {"tier2_filters": {}})
    monkeypatch.setattr(pf, "build_engine_kwargs", lambda *a, **k: {"risk_dollars": 500.0})
    monkeypatch.setattr(pf, "calculate_breadth_from_engine", lambda *a, **k: {})
    monkeypatch.setattr(pf, "DB_PATH", tmp_path / "ticker_cache.db")


# ---------------------------------------------------------------------------
# Capa 1: contrato del productor
# ---------------------------------------------------------------------------


def test_scan_signals_emits_avg_volume_20d_for_all_candidates(producer_env):
    out = pf.scan_signals("combo_pure_momentum", ["KKR", "PPL"], TRADE_DATE)

    wd = out["watchlist_detail"]
    assert set(wd) == {"KKR", "PPL"}, "todos los candidatos deben estar en el detalle"
    for ticker, detail in wd.items():
        value = detail.get("avg_volume_20d")
        assert isinstance(value, (int, float)) and not isinstance(value, bool), (
            f"{ticker}: 'avg_volume_20d' debe ser numerica, got {value!r}"
        )
        assert math.isfinite(float(value)) and value > 0, (
            f"{ticker}: 'avg_volume_20d' debe ser > 0, got {value!r}"
        )


def test_scan_signals_does_not_emit_error_stubs(producer_env):
    out = pf.scan_signals("combo_pure_momentum", ["KKR", "PPL"], TRADE_DATE)

    wd = out["watchlist_detail"]
    assert set(wd) == {"KKR", "PPL"}, "todos los candidatos deben estar en el detalle"
    for ticker, detail in wd.items():
        reasons = [str(r) for r in detail.get("reasons", [])]
        offenders = [r for r in reasons if r.startswith("No se pudo calcular")]
        assert not offenders, f"{ticker}: el builder devolvio stub de error: {offenders}"
        # El detalle enriquecido debe traer diagnosticos completos, no solo score.
        assert "price" in detail, f"{ticker}: falta diagnostico de precio"


# ---------------------------------------------------------------------------
# Capa 2: guard anti-drift sobre schema real
# ---------------------------------------------------------------------------


def test_validator_flags_real_drifted_snapshot():
    violations = validate_snapshot(_load_drifted_fixture())

    assert violations, "el snapshot driftedo real debe producir violaciones"
    assert any("KKR" in v and "avg_volume_20d" in v for v in violations), violations


def test_validator_accepts_complete_candidate():
    snap = _load_drifted_fixture()
    snap["watchlist_detail"]["KKR"]["avg_volume_20d"] = 2_500_000

    assert validate_snapshot(snap) == []


def test_validator_rejects_non_positive_avg_volume():
    snap = _load_drifted_fixture()

    for bad_value in (0, -1.0, float("nan"), "2500000"):
        snap["watchlist_detail"]["KKR"]["avg_volume_20d"] = bad_value
        violations = validate_snapshot(snap)
        assert any("avg_volume_20d" in v for v in violations), (
            f"valor invalido no detectado: {bad_value!r}"
        )


# ---------------------------------------------------------------------------
# Capa 3: wiring del guard en run_pre
# ---------------------------------------------------------------------------


class _FinvizResult:
    ok = True
    tickers = ["KKR"]


@pytest.fixture
def run_pre_deps(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pf, "fetch_finviz_universe", lambda *a, **k: _FinvizResult()
    )
    monkeypatch.setattr(pf, "load_production_config", lambda: {})
    monkeypatch.setattr(pf, "pre_warm_cache", lambda *a, **k: None)
    monkeypatch.setattr(pf, "_get_latest_ohlcv_date", lambda *a, **k: TRADE_DATE)

    fake_db = tmp_path / "ticker_cache.db"
    fake_db.write_bytes(b"placeholder")
    monkeypatch.setattr(pf, "DB_PATH", fake_db)

    monkeypatch.setattr(pf, "get_market_context_live", lambda *a, **k: {})
    monkeypatch.setattr(
        pf, "apply_regime_override", lambda *a, **k: {"effective_regime_ok": True}
    )
    monkeypatch.setattr(pf, "load_combo_params", lambda *a, **k: {"tier2_filters": {}})
    monkeypatch.setattr(pf, "shared_calculate_quality", lambda detail: ("ok", []))
    monkeypatch.setattr("src.utils.terminal_gui._build_hot_sectors", lambda *a, **k: [])
    monkeypatch.setattr(pf, "_build_e25_summary", lambda *a, **k: {})
    monkeypatch.setattr(pf, "_build_nearest_flow", lambda *a, **k: {})
    monkeypatch.setattr(pf, "_build_sector_flow", lambda *a, **k: {})
    monkeypatch.setattr(pf, "print_terminal_brief", lambda *a, **k: None)
    monkeypatch.setattr(pf, "OUT_DIR", tmp_path)
    return tmp_path


def _install_scan_signals_mock(monkeypatch, details: dict):
    def fake_scan_signals(combo_name, universe, data_as_of, rs_min_pct=0.0):
        return {
            "signals": [],
            "watchlist": {t: d.get("score", 0) for t, d in details.items()},
            "watchlist_detail": dict(details),
            "breadth": None,
        }

    monkeypatch.setattr(pf, "scan_signals", fake_scan_signals)


def test_run_pre_flags_drifted_snapshot(run_pre_deps, monkeypatch):
    details = {"KKR": _raw_detail_template()}  # schema real driftedo, sin avg_volume_20d
    _install_scan_signals_mock(monkeypatch, details)

    snap = pf.run_pre(TRADE_DATE, 100.0)

    violations = snap.get("schema_contract_violations")
    assert violations, "run_pre debe incrustar violaciones cuando hay drift"
    assert any("KKR" in v and "avg_volume_20d" in v for v in violations), violations


def test_run_pre_clean_when_contract_holds(run_pre_deps, monkeypatch):
    details = {"KKR": _raw_detail_template()}
    details["KKR"]["avg_volume_20d"] = 2_500_000
    _install_scan_signals_mock(monkeypatch, details)

    snap = pf.run_pre(TRADE_DATE, 100.0)

    assert "schema_contract_violations" not in snap
