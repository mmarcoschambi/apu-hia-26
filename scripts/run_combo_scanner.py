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
    }


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
    if not universe:
        logger.error("No tickers in universe")
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

    for name, cfg in configs.items():
        logger.info(f"  Scanning {name}...")
        effective_mode = "A" if name == "combo_pure_momentum" else "B"
        decisions = scan_combo(
            cfg, universe, df_map, spy_df, all_closes, effective_mode, skip_tier2
        )
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

    if not dry_run and all_signals:
        out_dir = OUTPUT_DIR / today
        out_dir.mkdir(parents=True, exist_ok=True)

        for name, decisions in agent_results.items():
            if decisions:
                df_rows = pd.DataFrame([_decision_to_row(d) for d in decisions])
                df_rows.to_csv(out_dir / f"{name}.csv", index=False)

        if mode == "A_BOTH":
            pd.DataFrame([_decision_to_row(d) for d in all_signals]).to_csv(
                out_dir / "combined.csv", index=False
            )
            pd.DataFrame(
                [
                    _decision_to_row(d)
                    for d in agent_results.get("combo_pure_momentum", [])
                ]
            ).to_csv(out_dir / "combo_pure_momentum.csv", index=False)
            pd.DataFrame(
                [
                    _decision_to_row(d)
                    for d in agent_results.get("combo_stage2_breakout", [])
                ]
            ).to_csv(out_dir / "combo_stage2_breakout.csv", index=False)
        else:
            if all_signals:
                pd.DataFrame([_decision_to_row(d) for d in all_signals]).to_csv(
                    out_dir / "combined.csv", index=False
                )

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
