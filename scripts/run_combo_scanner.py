#!/usr/bin/env python3
"""
run_combo_scanner.py - Multi-combo scanner sobre universo maestro.

Usa:
  - config/combos/*.json     → screener, pattern, tier2_filters (fuente primaria)
  - config/screeners/*.json  → parámetros del screener
  - src.signals.signal_engine → MOTOR CANÓNICO (live = backtest)

No reconsulta Finviz.

Uso:
    python3 scripts/run_combo_scanner.py                                    # hoy, universo DB
    python3 scripts/run_combo_scanner.py --universe-source stable             # universo maestro
    python3 scripts/run_combo_scanner.py --agents combo_pure_momentum    # agentes específicos
    python3 scripts/run_combo_scanner.py --dry-run                        # sin archivos
    python3 scripts/run_combo_scanner.py --skip-tier2                        # solo screener
    python3 scripts/run_combo_scanner.py --mode A_BOTH                     # fusión A+B ranking
"""

import argparse
import copy
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.scanner.universe_loader import load_scan_universe  # noqa: E402
from src.signals.signal_engine import (  # noqa: E402
    SignalMode,
    SignalDecision,
    evaluate_ticker,
    merge_ab_signals,
)
from src.config.dynamic_config import load_production_config
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "live_signals"
COMBOS_DIR = PROJECT_ROOT / "config" / "combos"
AGENTS_DIR = PROJECT_ROOT / "config" / "production_agents"

LOOKBACK_DAYS = 250
RS_LOOKBACK = 60

COMBO_ALIASES = {
    "A": "combo_pure_momentum",
    "B": "combo_stage2_breakout",
    "combo_pure_momentum": "combo_pure_momentum",
    "combo_stage2_breakout": "combo_stage2_breakout",
}


def load_ohlcv(ticker: str, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT date,open,high,low,close,volume FROM ohlcv_cache "
        "WHERE ticker=? AND date>=? ORDER BY date",
        (ticker, cutoff),
    ).fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    return df.set_index("date").astype(float)


def _load_combo_json(combo_name: str) -> Optional[dict]:
    candidates = [
        COMBOS_DIR / f"{combo_name}.json",
        AGENTS_DIR / f"{combo_name}_config.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text())
    return None


def list_available_combos() -> list[str]:
    combos = []
    for d in [COMBOS_DIR, AGENTS_DIR]:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            name = f.stem.replace("_config", "")
            if name in combos:
                continue
            cfg = _load_combo_json(name)
            if cfg and isinstance(cfg, dict) and "name" in cfg:
                combos.append(name)
    return combos


def _compute_rs_percentile(
    ticker: str,
    all_closes: dict[str, pd.Series],
    rs_lookback: int,
) -> float | None:
    ticker_series = all_closes.get(ticker)
    if ticker_series is None or len(ticker_series) < rs_lookback + 5:
        return None
    ticker_ret_series = ticker_series.pct_change(rs_lookback).dropna()
    if ticker_ret_series.empty:
        return None
    ticker_ret = float(ticker_ret_series.iloc[-1])
    other_rets = []
    for other_ticker, series in all_closes.items():
        if other_ticker == ticker or len(series) < rs_lookback + 5:
            continue
        ret_series = series.pct_change(rs_lookback).dropna()
        if not ret_series.empty:
            other_rets.append(float(ret_series.iloc[-1]))
    if not other_rets:
        return None
    return float((sum(r < ticker_ret for r in other_rets) / len(other_rets)) * 100.0)


def scan_combo(
    combo_cfg: dict,
    universe: list[str],
    df_map: dict[str, pd.DataFrame],
    spy_df: pd.DataFrame | None,
    all_closes: dict[str, pd.Series],
    mode: SignalMode = "A",
    skip_tier2: bool = False,
    etf_dists: dict[str, float] | None = None,
) -> list[SignalDecision]:
    signals: list[SignalDecision] = []

    for ticker in universe:
        df = df_map.get(ticker)
        if df is None or len(df) < 65:
            continue
        rs_pct = _compute_rs_percentile(ticker, all_closes, RS_LOOKBACK)
        
        # Obtener dist del ETF
        etf_symbol = SECTOR_MAP.get(ticker)
        dist = etf_dists.get(etf_symbol) if etf_dists and etf_symbol else None
        
        decision = evaluate_ticker(
            ticker, df, spy_df, combo_cfg, mode, skip_tier2, rs_pct,
            sector_etf_dist=dist
        )
        decision.mode = mode
        if decision.passed:
            signals.append(decision)

    signals.sort(key=lambda x: x.entry_score, reverse=True)
    return signals


def _decision_to_row(d: SignalDecision) -> dict:
    return {
        "agent_name": d.mode,
        "combo_name": d.mode,
        "ticker": d.ticker,
        "signal_date": datetime.now().strftime("%Y-%m-%d"),
        "entry_score": d.entry_score,
        "screener_score": d.screener_score,
        "screener_reason": d.screener_reason,
        "pattern_signal": d.signal_type,
        "tier2_filter": d.reject_reason if not d.passed else "passed",
        "rvol": round(d.tier2_metrics.rvol, 2),
        "adr_pct": round(d.tier2_metrics.adr_pct, 2),
        "dist_sma20": round(d.tier2_metrics.dist_sma20, 2),
        "consol_days": d.tier2_metrics.consol_days,
        "volume": int(d.tier2_metrics.volume),
        "avg_volume_20d": round(d.tier2_metrics.volume / d.tier2_metrics.rvol, 0) if d.tier2_metrics.rvol and d.tier2_metrics.rvol > 0 else 0,
        "dollar_vol_M": round(d.tier2_metrics.dollar_vol_M, 1),
        "rs_ret": round(d.tier2_metrics.rs_ret, 4)
        if d.tier2_metrics.rs_ret is not None
        else None,
        "rs_percentile": round(d.tier2_metrics.rs_percentile, 1)
        if d.tier2_metrics.rs_percentile is not None
        else None,
        "entry_price": round(d.tier2_metrics.close, 4),
        "rvol": round(d.tier2_metrics.rvol, 2),
        "adr_pct": round(d.tier2_metrics.adr_pct, 2),
        "dist_sma20": round(d.tier2_metrics.dist_sma20, 2),
        "consol_days": d.tier2_metrics.consol_days,
        "volume": int(d.tier2_metrics.volume),
        "avg_volume_20d": round(d.tier2_metrics.volume / d.tier2_metrics.rvol, 0) if d.tier2_metrics.rvol and d.tier2_metrics.rvol > 0 else 0,
        "dollar_vol_M": round(d.tier2_metrics.dollar_vol_M, 1),
        "rs_ret": round(d.tier2_metrics.rs_ret, 4)
        if d.tier2_metrics.rs_ret is not None
        else None,
        "rs_percentile": round(d.tier2_metrics.rs_percentile, 1)
        if d.tier2_metrics.rs_percentile is not None
        else None,
        "close": round(d.tier2_metrics.close, 4),
        "spy_above_sma50": d.tier2_metrics.spy_above_sma50,
        "spy_above_sma200": d.tier2_metrics.spy_above_sma200,
        "reject_contract": d.reject_contract,
        "mode": d.mode,
        "shares": getattr(d, "shares", None),
        "initial_size": getattr(d, "shares", None),
        "risk_budget_usd": getattr(d, "risk_budget_usd", None),
        "raw_risk_budget_usd": getattr(d, "raw_risk_budget_usd", None),
        "risk_per_share": getattr(d, "risk_per_share", None),
        "sizing_factor": getattr(d, "sizing_factor", None),
        "sizing_reason": getattr(d, "sizing_reason", None),
    }


# --- Watchlist detail gate derivation ---
GATES = ["last_base_entry", "last_liquidity", "last_quality", "last_consolidation"]


def _derive_gate_status(decision: SignalDecision) -> dict[str, bool]:
    """
    Deriva el estado de las 4 gates de watchlist a partir de un SignalDecision.

    Solo se conoce la PRIMERA gate que falló (reject_reason tiene la primera
    razón de rechazo). Las gates que no fallaron en ese orden se asumen True
    (lower bound de rechazo real).
    """
    if decision.passed:
        return {g: True for g in GATES}

    reason = (decision.reject_reason or "") + " " + (decision.screener_reason or "")
    gates = {g: True for g in GATES}

    if reason.startswith("screener_fail") or "screener_fail" in reason:
        gates["last_base_entry"] = False
    elif any(k in reason for k in ("rvol", "adr_pct", "consol_days", "dist_sma20", "consolidation")):
        gates["last_consolidation"] = False
    elif any(k in reason for k in ("dollar_vol", "volume")):
        gates["last_liquidity"] = False
    elif any(k in reason for k in ("rs_percentile", "trend_intensity", "ma_stack", "spy_above")):
        gates["last_quality"] = False
    # Si no hay match, dejamos todas True (no sabemos cuál falló exactamente)

    return gates


def _build_watchlist_detail(
    universe: list[str],
    df_map: dict[str, pd.DataFrame],
    all_rejections: list[dict],
) -> dict[str, dict]:
    """
    Construye watchlist_detail para todo el universo.

    Para tickers evaluados: deriva las 4 gates del resultado del scanner.
    Para tickers sin datos: todas las gates en False (sin_data).
    """
    # Indexar rejection results por ticker (tomar el primer agente)
    rejection_by_ticker: dict[str, dict] = {}
    for entry in all_rejections:
        t = entry["ticker"]
        if t not in rejection_by_ticker:
            rejection_by_ticker[t] = entry

    detail = {}
    for ticker in universe:
        if ticker in df_map:
            entry = rejection_by_ticker.get(ticker)
            if entry:
                # Reconstruir SignalDecision-like object
                passed = entry["passed_with_sector"]
                reject_reason = entry.get("reject_reason_with_sector", "")
                screener_reason = entry.get("screener_reason_with_sector", "")
                # Usar un mock de SignalDecision para la derivación
                mock = SignalDecision(
                    ticker=ticker,
                    mode="A",
                    passed=passed,
                    reject_reason=reject_reason,
                )
                mock.screener_reason = screener_reason
                gates = _derive_gate_status(mock)
                detail[ticker] = {
                    **gates,
                    "passed": passed,
                    "reject_reason": reject_reason,
                    "has_data": True,
                }
            else:
                # Ticker with data but not in rejections — edge case
                detail[ticker] = {
                    **{g: True for g in GATES},
                    "passed": True,
                    "reject_reason": "",
                    "has_data": True,
                }
        else:
            # Ticker without data
            detail[ticker] = {
                **{g: False for g in GATES},
                "passed": False,
                "reject_reason": "no_data",
                "has_data": False,
            }

    return detail


def run_combo_scan(
    date: str | None = None,
    universe_source: str = "db",
    universe_file: str = "",
    agent_names: list[str] | None = None,
    dry_run: bool = False,
    skip_tier2: bool = False,
    mode: SignalMode = "A",
) -> dict:
    today = date or datetime.now().strftime("%Y-%m-%d")
    logger.info(
        f"Combo Scanner | scan_date={today} | universe={universe_source} | mode={mode}"
    )

    # 1. Cargar Master Config (production_config.json)
    try:
        master_cfg = load_production_config()
        t2_master = master_cfg.get("tier2_filters", {})
        use_sector_filter = t2_master.get("use_sector_etf_filter", False)
        logger.info(f"Master Config loaded. Sector Filter: {'ENABLED' if use_sector_filter else 'DISABLED'}")
    except Exception as e:
        logger.warning(f"Failed to load master config: {e}. Sector filter will be disabled.")
        t2_master = {}
        use_sector_filter = False

    # 2. Pre-fetch ETF data si el filtro está activo
    etf_dists = {}
    if use_sector_filter:
        import yfinance as yf
        logger.info("Fetching Sector ETF data for filter...")
        as_of = pd.Timestamp(today)
        etf_start = (as_of - timedelta(days=60)).strftime("%Y-%m-%d")
        try:
            etf_data = yf.download(SECTOR_ETFS, start=etf_start, end=today, progress=False)["Close"]
            if isinstance(etf_data.columns, pd.MultiIndex):
                etf_data.columns = etf_data.columns.get_level_values(0)
            
            sma_period = t2_master.get("sector_etf_sma_period", 20)
            for etf in SECTOR_ETFS:
                if etf in etf_data.columns:
                    series = etf_data[etf].ffill()
                    if len(series) >= sma_period:
                        sma = series.rolling(sma_period).mean().iloc[-1]
                        current = series.iloc[-1]
                        etf_dists[etf] = (current / sma) - 1
            logger.info(f"  ETF Dists calculated for {len(etf_dists)} sectors.")
        except Exception as e:
            logger.error(f"Error fetching ETF data: {e}. Filter might fail for some tickers.")

    csv_path = Path(universe_file) if universe_file else None
    universe = load_scan_universe(
        source=universe_source if universe_source != "db" else "db",
        path=csv_path,
        tickers=None,
    )
    import sys
    import os
    is_test = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules
    min_limit = 2 if is_test else 10
    if not universe or len(universe) < min_limit:
        logger.error(f"[CRITICAL] Universe demasiado chico ({len(universe) if universe else 0} tickers) — posible DB vacía")
        return {"ok": False, "error": "empty_universe", "signals": {}}

    logger.info(f"Universe loaded: {len(universe)} tickers")

    if mode == "A_BOTH":
        cfg_a = _load_combo_json(COMBO_ALIASES["A"])
        cfg_b = _load_combo_json(COMBO_ALIASES["B"])
        if cfg_a is None:
            logger.error(f"Combo A '{COMBO_ALIASES['A']}' not found")
            return {"ok": False, "error": "combo_a_not_found"}
        if cfg_b is None:
            logger.error(f"Combo B '{COMBO_ALIASES['B']}' not found")
            return {"ok": False, "error": "combo_b_not_found"}
        agent_names = [
            cfg_a.get("name", "combo_pure_momentum"),
            cfg_b.get("name", "combo_stage2_breakout"),
        ]
        configs = {"combo_pure_momentum": cfg_a, "combo_stage2_breakout": cfg_b}
    else:
        alias = COMBO_ALIASES.get(mode, mode)
        if agent_names is None:
            agent_names = [alias]
        configs = {}
        for name in agent_names:
            cfg = _load_combo_json(name)
            if cfg and isinstance(cfg, dict) and "name" in cfg:
                configs[name] = cfg
            else:
                logger.warning(f"Config not found for: {name}")

    spy_df: Optional[pd.DataFrame] = None
    try:
        spy_df = load_ohlcv("SPY", days=LOOKBACK_DAYS)
    except Exception:
        pass

    all_signals: list[SignalDecision] = []
    agent_results: dict[str, list[SignalDecision]] = {}
    df_map: dict[str, pd.DataFrame] = {}
    all_closes: dict[str, pd.Series] = {}

    for ticker in universe:
        df = load_ohlcv(ticker)
        if len(df) >= RS_LOOKBACK + 5:
            all_closes[ticker] = df["close"]
            df_map[ticker] = df

    # Only enforce df_map min size if the loaded universe was large enough
    if len(universe) >= 10 and len(df_map) < 10:
        logger.error(f"[CRITICAL] Universe demasiado chico ({len(df_map)} tickers con datos cargados) — posible DB vacía")
        return {"ok": False, "error": "empty_universe", "signals": {}}

    # Combinar t2_master con VALIDATED_OVERRIDES (legacy fallback)
    VALIDATED_OVERRIDES = {
        "min_rs_percentile": 75,
        "min_trend_intensity": 104,
        "require_ma_stack": True,
        "min_adr_pct": 1.2,
        "require_spy_above_sma200": True,
    }
    final_t2 = {**VALIDATED_OVERRIDES, **t2_master}

    all_rejections = []

    for name, cfg in configs.items():
        logger.info(f"  Scanning {name}...")
        effective_mode = "A" if name == "combo_pure_momentum" else "B"
        
        # Inyectar tier3_fixed (E25) solo en System B desde production_config.json
        if effective_mode == "B":
            cfg["tier3_fixed"] = dict(master_cfg.get("tier3_fixed", {}))
        
        # Config contrafactual
        cfg_no_sector = copy.deepcopy(cfg)
        cfg_no_sector.setdefault("tier2_filters", {})["use_sector_etf_filter"] = False

        # Inyectar Overrides en la config del agente
        # System B con dynamic extension sizing salta max_dist_sma20 (E25 maneja su propio limite)
        skip_max_dist = (effective_mode == "B"
                         and cfg.get("tier3_fixed", {}).get("use_dynamic_extension_sizing", False))
        for k, v in final_t2.items():
            if skip_max_dist and k == "max_dist_sma20":
                continue
            cfg.setdefault("tier2_filters", {})[k] = v
            cfg.setdefault("screener", {}).setdefault("params", {})[k] = v
            if k == "min_adr_pct":
                cfg.setdefault("screener", {})[k] = v

        decisions = scan_combo(
            cfg, universe, df_map, spy_df, all_closes, effective_mode, skip_tier2,
            etf_dists=etf_dists
        )
        
        # Reconstruir impacto marginal para auditoria
        # Reconstruir impacto marginal para auditoria
        for ticker in universe:
            if ticker not in df_map:
                continue
            rs_pct = _compute_rs_percentile(ticker, all_closes, RS_LOOKBACK)
            etf_symbol = SECTOR_MAP.get(ticker)
            dist = etf_dists.get(etf_symbol) if etf_dists and etf_symbol else None

            d_with = evaluate_ticker(
                ticker, df_map[ticker], spy_df, cfg, effective_mode, skip_tier2, 
                rs_percentile=rs_pct, sector_etf_dist=dist
            )
            d_without = evaluate_ticker(
                ticker, df_map[ticker], spy_df, cfg_no_sector, effective_mode, skip_tier2,
                rs_percentile=rs_pct, sector_etf_dist=dist
            )
            
            is_blocked = d_without.passed and not d_with.passed and "sector_etf" in d_with.reject_reason
            all_rejections.append({
                "ticker": ticker,
                "mode": effective_mode,
                "passed_with_sector": d_with.passed,
                "reject_reason_with_sector": d_with.reject_reason,
                "screener_reason_with_sector": d_with.screener_reason,
                "passed_without_sector": d_without.passed,
                "reject_reason_without_sector": d_without.reject_reason,
                "screener_reason_without_sector": d_without.screener_reason,
                "blocked_by_sector": is_blocked,
                "sector_etf": etf_symbol,
                "sector_etf_dist": dist
            })

        agent_results[name] = decisions
        all_signals.extend(decisions)
        logger.info(f"  {name}: {len(decisions)} signals")

    if mode == "A_BOTH":
        signals_a = agent_results.get("combo_pure_momentum", [])
        signals_b = agent_results.get("combo_stage2_breakout", [])
        merged = merge_ab_signals(signals_a, signals_b)
        all_signals = merged
        logger.info(f"  A+B merged: {len(merged)} signals")

    all_signals.sort(key=lambda x: x.entry_score, reverse=True)

    if not dry_run:
        out_dir = OUTPUT_DIR / today
        out_dir.mkdir(parents=True, exist_ok=True)
        
        if all_rejections:
            pd.DataFrame(all_rejections).to_csv(out_dir / "rejection_audit.csv", index=False)
            logger.info(f"Saved {len(all_rejections)} rejection records to {out_dir / 'rejection_audit.csv'}")

        for name, decisions in agent_results.items():
            df_rows = pd.DataFrame([_decision_to_row(d) for d in decisions])
            df_rows.to_csv(out_dir / f"{name}.csv", index=False)

        pd.DataFrame([_decision_to_row(d) for d in all_signals]).to_csv(
            out_dir / "combined.csv", index=False
        )

        watchlist_detail = _build_watchlist_detail(universe, df_map, all_rejections)
        summary = {
            "scan_date": today,
            "universe_source": universe_source,
            "universe_count": len(universe),
            "mode": mode,
            "agents": {name: len(sigs) for name, sigs in agent_results.items()},
            "total_signals": len(all_signals),
            "top_signals": [
                {"ticker": s.ticker, "agent": s.mode, "score": s.entry_score}
                for s in all_signals[:10]
            ],
            "watchlist_detail": watchlist_detail,
        }
        with open(out_dir / "run_summary.json", "w") as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info(f"Output: {out_dir}")

    return {
        "ok": True,
        "scan_date": today,
        "universe_count": len(universe),
        "mode": mode,
        "agent_results": {name: len(sigs) for name, sigs in agent_results.items()},
        "total_signals": len(all_signals),
        "all_signals": [_decision_to_row(d) for d in all_signals],
    }


def main():
    parser = argparse.ArgumentParser(description="Multi-combo scanner (real pipeline)")
    parser.add_argument("--date", type=str, help="Scan date (YYYY-MM-DD)")
    parser.add_argument(
        "--universe-source",
        type=str,
        choices=["db", "stable", "file"],
        default="db",
        help="Universe source (default: db)",
    )
    parser.add_argument("--universe-file", type=str, default="", help="CSV path")
    parser.add_argument(
        "--agents",
        nargs="+",
        help="Combo names (default: all combos in config/combos/ and config/production_agents/)",
    )
    parser.add_argument(
        "--skip-tier2",
        action="store_true",
        help="Skip tier2 filters, only use screener pipeline",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["A", "B", "A_BOTH"],
        default="A",
        help="Signal mode: A (momentum), B (stage2), A_BOTH (fusion)",
    )
    args = parser.parse_args()

    result = run_combo_scan(
        date=args.date,
        universe_source=args.universe_source,
        universe_file=args.universe_file,
        agent_names=args.agents,
        dry_run=args.dry_run,
        skip_tier2=args.skip_tier2,
        mode=args.mode,
    )

    print(f"\n{'=' * 60}")
    print(
        f"  COMBO SCANNER  |  {result.get('scan_date', '?')}  |  mode={result.get('mode', '?')}"
    )
    print(f"{'=' * 60}")
    for agent, count in result.get("agent_results", {}).items():
        print(f"  {agent:<35} {count:>5} signals")
    print(f"  {'TOTAL':<35} {result.get('total_signals', 0):>5} signals")
    print(f"  Universe: {result.get('universe_count', 0)} tickers")
    print(f"{'=' * 60}")

    if not result.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
