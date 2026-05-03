import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.pit_universe import PointInTimeUniverse

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
SP500_CSV = PROJECT_ROOT / "sp500" / "sp500" / "sp500.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "experiments"
START_DATE = "2025-01-01"
END_DATE = "2026-04-30"

ETFS = ["XLK", "XLE", "XLF", "XLV", "XLI", "XLY", "XLP", "XLB", "XLRE", "XLU", "XLC"]

GICS_TO_ETF = {
    "Information Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Energy": "XLE",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

# Ablation flag: False=baseline, True=apply ETF>SMA20 gate
USE_SECTOR_ETF_FILTER = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_ticker_to_etf_map():
    if not SP500_CSV.exists():
        logger.warning(f"SP500 CSV not found at {SP500_CSV}.")
        return {}
    df = pd.read_csv(SP500_CSV)
    ticker_to_gics = dict(zip(df["Symbol"], df["GICS Sector"]))
    return {t: GICS_TO_ETF[s] for t, s in ticker_to_gics.items() if s in GICS_TO_ETF}


def get_forward_returns(price_df, windows=[5, 10, 20]):
    return {w: price_df.shift(-w) / price_df - 1 for w in windows}


def compute_metrics(group_df, close_pivot, w):
    col = f"fwd_{w}d"
    data = group_df[group_df[col].notna()].copy()
    if data.empty:
        return None
    rets = data[col]
    gains = rets[rets > 0].sum()
    losses = abs(rets[rets < 0].sum())
    pf = gains / losses if losses > 0 else (99.9 if gains > 0 else 0.0)
    wr = (rets > 0).mean() * 100
    entry_prices = np.array([close_pivot.at[d, t] for d, t in zip(data["date"], data["ticker"])])
    stop_pcts = data["stop_dist"].values / entry_prices
    valid = stop_pcts > 0
    r_multi = rets.values[valid] / stop_pcts[valid]
    if len(r_multi) < 2 or r_multi.std() == 0:
        sharpe = 0.0
    else:
        sharpe = (r_multi.mean() / r_multi.std()) * np.sqrt(252 / w)
    return {
        "trades": len(data),
        "win_rate": round(float(wr), 2),
        "pf": round(float(pf), 3),
        "sharpe_r": round(float(sharpe), 3),
        "median_ret_pct": round(float(rets.median() * 100), 2),
        "mean_ret_pct": round(float(rets.mean() * 100), 2),
    }


def run_experiment():
    logger.info(f"Starting Sector Confirmed Filter — USE_SECTOR_ETF_FILTER={USE_SECTOR_ETF_FILTER}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    etf_start = (pd.to_datetime(START_DATE) - timedelta(days=100)).strftime("%Y-%m-%d")
    logger.info("Downloading ETF data...")
    etf_prices = yf.download(ETFS, start=etf_start, end="2026-05-02", progress=False)["Close"]
    if isinstance(etf_prices.columns, pd.MultiIndex):
        etf_prices.columns = etf_prices.columns.get_level_values(0)
    etf_sma20 = etf_prices.rolling(20).mean()

    pit = PointInTimeUniverse()
    ticker_to_etf = load_ticker_to_etf_map()
    conn = sqlite3.connect(DB_PATH)
    superset = pit.get_superset(START_DATE, END_DATE)
    logger.info(f"Superset: {len(superset)} tickers")

    buffer_start = (pd.to_datetime(START_DATE) - timedelta(days=60)).strftime("%Y-%m-%d")
    placeholders = ",".join(["?"] * len(superset))

    df_prices = pd.read_sql_query(
        f"SELECT ticker, date, close, dollar_volume, adr_pct_20 FROM ohlcv_cache"
        f" WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ? ORDER BY ticker, date",
        conn, params=superset + [buffer_start, END_DATE],
    )
    df_prices["date"] = pd.to_datetime(df_prices["date"], format="mixed").dt.normalize()
    df_prices["ticker"] = df_prices["ticker"].str.upper().str.strip()
    df_prices = df_prices.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"], keep="last")

    df_rs = pd.read_sql_query(
        "SELECT ticker, date, rs_composite FROM daily_rs_rankings WHERE date BETWEEN ? AND ?",
        conn, params=[START_DATE, END_DATE],
    )
    df_rs["date"] = pd.to_datetime(df_rs["date"], format="mixed").dt.normalize()
    df_rs["ticker"] = df_rs["ticker"].str.upper().str.strip()
    df_rs = df_rs.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"], keep="last")
    conn.close()

    close_pivot = df_prices.pivot(index="date", columns="ticker", values="close")
    dv_pivot = df_prices.pivot(index="date", columns="ticker", values="dollar_volume")
    adr_pivot = df_prices.pivot(index="date", columns="ticker", values="adr_pct_20")
    rs_pivot = df_rs.pivot(index="date", columns="ticker", values="rs_composite")

    rolling_max_20 = close_pivot.shift(1).rolling(20).max()
    is_breakout = close_pivot > rolling_max_20
    fwd_rets = get_forward_returns(close_pivot)
    stop_dist = adr_pivot * close_pivot / 100

    dates = pd.to_datetime(close_pivot.index, format="mixed")
    mask = pit.build_tradeable_mask(dates, list(close_pivot.columns))
    mask.index = close_pivot.index

    start_dt = pd.to_datetime(START_DATE)
    analysis_dates = close_pivot.index[close_pivot.index >= start_dt]
    signals = []

    logger.info(f"Scanning {len(analysis_dates)} trading days...")
    for date in analysis_dates:
        if date not in rs_pivot.index:
            continue
        rs_day = rs_pivot.loc[date]
        breakout_day = is_breakout.loc[date]
        dv_day = dv_pivot.loc[date]
        mask_day = mask.loc[date]
        valid = rs_day[(rs_day > 58) & breakout_day & (dv_day > 5_000_000) & mask_day].index
        for ticker in valid:
            etf = ticker_to_etf.get(ticker)
            if not etf or etf not in etf_prices.columns:
                continue
            try:
                etf_c = etf_prices.loc[date, etf]
                etf_s20 = etf_sma20.loc[date, etf]
            except KeyError:
                continue
            sector_confirmed = bool(etf_c > etf_s20)
            # Ablation gate
            if USE_SECTOR_ETF_FILTER and not sector_confirmed:
                continue
            signals.append({
                "date": date,
                "ticker": ticker,
                "sector_etf": etf,
                "sector_confirmed": sector_confirmed,
                "fwd_5d": fwd_rets[5].loc[date, ticker],
                "fwd_10d": fwd_rets[10].loc[date, ticker],
                "fwd_20d": fwd_rets[20].loc[date, ticker],
                "stop_dist": stop_dist.loc[date, ticker],
            })

    df_signals = pd.DataFrame(signals)
    n_conf = int(df_signals["sector_confirmed"].sum()) if not df_signals.empty else 0
    logger.info(f"Total signals: {len(df_signals)} | confirmed: {n_conf} | not: {len(df_signals)-n_conf}")

    if df_signals.empty:
        logger.warning("No signals found.")
        return

    results = {}
    for group_name, group_df in [
        ("sector_confirmed", df_signals[df_signals["sector_confirmed"]]),
        ("sector_not_confirmed", df_signals[~df_signals["sector_confirmed"]]),
        ("all_signals", df_signals),
    ]:
        group_results = {"count": len(group_df)}
        for w in [5, 10, 20]:
            group_results[f"metrics_{w}d"] = compute_metrics(group_df, close_pivot, w)
        results[group_name] = group_results

    df_signals["month"] = pd.to_datetime(df_signals["date"]).dt.to_period("M").astype(str)
    temporal_dist = df_signals.groupby(["month", "sector_confirmed"]).size().unstack(fill_value=0).to_dict()

    report = {
        "experiment": "Sector Confirmed Filter — ETF > SMA20 ablation",
        "hypothesis": "ETF > SMA20 as entry condition improves Sharpe(R) of combo_pure_momentum",
        "derived_from": "rotation_leaders_eval_20260502_223920 — late_entry/baseline > early_leader",
        "period": f"{START_DATE} to {END_DATE}",
        "use_sector_etf_filter": USE_SECTOR_ETF_FILTER,
        "summary": results,
        "temporal_distribution": temporal_dist,
        "config": {"rs_threshold": 58, "min_dollar_volume": 5_000_000, "breakout_window": 20},
        "gate_for_production": "delta Sharpe(R) >= +0.10 on BOTH 10d and 20d vs baseline",
        "timestamp": datetime.now().isoformat(),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    flag_suffix = "with_filter" if USE_SECTOR_ETF_FILTER else "baseline"
    out_path = OUTPUT_DIR / f"sector_confirmed_filter_eval_{flag_suffix}_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Report saved to {out_path}")

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"SECTOR CONFIRMED FILTER — USE_SECTOR_ETF_FILTER={USE_SECTOR_ETF_FILTER}")
    print(sep)
    for gn, res in results.items():
        print(f"\n  {gn.upper()} (n={res['count']})")
        for w in [5, 10, 20]:
            m = res.get(f"metrics_{w}d")
            if m:
                print(f"    {w:>2}d: WR={m['win_rate']:>5.1f}% | PF={m['pf']:.3f} | Sharpe(R)={m['sharpe_r']:+.3f}")
    print(f"\n{sep}")
    print("PROTOCOLO:")
    print("  1. flag=False  -> baseline Sharpe")
    print("  2. flag=True   -> filtered Sharpe")
    print("  3. delta >= +0.10 en 10d Y 20d -> GO -> feature flag en engine")
    print("  4. delta < +0.10               -> NO-GO -> hipotesis archivada")
    print(f"{sep}\n")


if __name__ == "__main__":
    run_experiment()
