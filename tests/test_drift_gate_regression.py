#!/usr/bin/env python3
"""
test_drift_gate_regression.py

Test de regresión: el drift gate debe calcularse por COBERTURA del universo de
referencia, NO por Jaccard distance clásica.

Contexto: el bug original usaba Jaccard distance, que falla catastróficamente
cuando los conjuntos tienen tamaños dispares (ref=200 vs live=600+).
Con Jaccard, un drift sano daba 70%+ y bloqueaba todo en falso.

Fix: el drift se calcula como 100 - live_coverage_pct, donde live_coverage_pct
es el % del universo de referencia (top-200) que está presente en el live.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from src.paper.universe_drift_audit import run_drift_audit


def test_drift_gate_uses_coverage_not_jaccard(tmp_path: Path):
    """
    Escenario:
      - DB de Referencia: 200 tickers (TICKER1..TICKER200)
      - Live (Finviz):    600 tickers (TICKER1..TICKER180 + EXTRA1..EXTRA420)
      - Intersección:     180 de los 200 de referencia están en Live.

    Con cobertura:  coverage = 180/200 = 90% → drift = 10% → GATE PASA
    Con Jaccard:    J = 180/(200+600-180) = 180/620 = 29% → drift = 71% → GATE BLOQUEA

    El test pasa si el gate usa cobertura. Si alguien revierte a Jaccard, falla.
    """
    db_path = tmp_path / "mock_cache.db"

    # ── 1. Poblar DB con 200 tickers de referencia ───────────────────────────
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE ohlcv_cache (
            ticker TEXT, date TEXT, open REAL, high REAL,
            low REAL, close REAL, volume INTEGER
        )
        """
    )
    for i in range(1, 201):
        conn.execute(
            "INSERT INTO ohlcv_cache (ticker, date, open, high, low, close, volume) "
            "VALUES (?, ?, 10, 11, 9, 10, 1000)",
            (f"TICKER{i}", today),
        )
    conn.commit()
    conn.close()

    # ── 2. Live set: 180 de referencia + 420 extras = 600 ────────────────────
    live_tickers = [f"TICKER{i}" for i in range(1, 181)]
    live_tickers.extend([f"EXTRA{i}" for i in range(1, 421)])

    # ── 3. Ejecutar auditoría con umbral 15% ─────────────────────────────────
    result = run_drift_audit(
        live_tickers=live_tickers,
        db_path=db_path,
        max_divergence_pct=15.0,
        reference_limit=200,
    )

    # ── 4. Aseveraciones ─────────────────────────────────────────────────────
    # Tamaños de conjuntos
    assert result.ref_size == 200, f"Esperado ref=200, obtenido {result.ref_size}"
    assert result.live_size == 600, f"Esperado live=600, obtenido {result.live_size}"
    assert result.intersection == 180, (
        f"Esperado intersección=180, obtenido {result.intersection}"
    )

    # Cobertura real: 180/200 = 90%
    assert result.live_coverage_pct == 90.0, (
        f"live_coverage_pct debería ser 90.0%, "
        f"obtenido {result.live_coverage_pct}%"
    )

    # Si alguien cambia divergence_pct por cobertura, este assert ataja
    # (divergence_pct sigue siendo Jaccard = 70.97% en este escenario)
    assert result.divergence_pct == pytest.approx(70.97, abs=0.1), (
        f"divergence_pct (Jaccard) debería ser ~70.97%, "
        f"obtenido {result.divergence_pct}%"
    )

    # El gate usa drift = 100 - coverage = 10%, debe pasar
    assert result.gate_passed is True, (
        f"gate_passed debería ser True (drift=10% <= 15%), "
        f"obtenido gate_passed={result.gate_passed}"
    )
    assert result.block_reason is None, (
        f"block_reason debería ser None si el gate pasa, "
        f"obtenido '{result.block_reason}'"
    )
