import sys, pickle, argparse, logging, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.indicators.pattern_detection import PatternDetectionEngine

logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CACHE_DIR = PROJECT_ROOT / "data" / "cache"
OUTPUT_DIR = PROJECT_ROOT / "data"
PATTERN_CACHE_FILE = OUTPUT_DIR / "pattern_cache.pkl"
PATTERN_MATRIX_FILE = OUTPUT_DIR / "pattern_matrix.pkl"
PROGRESS_FILE = OUTPUT_DIR / ".pattern_progress.pkl"
TICKER_FILE = PROJECT_ROOT / "top_500_momentum_tickers.txt"

TEST_SUBSET = [
    "AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","AMD","AVGO","ORCL",
    "CRM","PANW","SNPS","KLAC","LRCX","AMAT","TXN","QCOM","MU","MRVL",
    "DECK","CROX","ONON","LULU","NKE","ELF","CELH","MNST","COST","WMT",
    "AXON","TMDX","IRTC","PODD","DXCM","ISRG","SYK","EW","NTRA","RXRX",
    "ENPH","FSLR","NEE","VST","CEG","NRG","ETN","PWR","HUBB","GNRC"
]

def load_ticker_list(full=False):
    if not full:
        print(f"[INFO] Modo TEST: {len(TEST_SUBSET)} tickers")
        return TEST_SUBSET
    if not TICKER_FILE.exists():
        return TEST_SUBSET
    tickers = []
    with open(TICKER_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                tickers.append(line.upper())
    print(f"[INFO] Modo FULL: {len(tickers)} tickers")
    return tickers

def load_ohlcv(ticker, start_date, end_date):
    pkl = CACHE_DIR / f"{ticker}.pkl"
    if not pkl.exists():
        return None
    try:
        with open(pkl, "rb") as f:
            df = pickle.load(f)
        df.columns = [c.lower() for c in df.columns]
        if not {"open","high","low","close","volume"}.issubset(df.columns):
            return None
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df = df.loc[(df.index >= start_date) & (df.index <= end_date)].copy()
        return df if len(df) >= 100 else None
    except Exception:
        return None

def compute_patterns_for_ticker(ticker, df, step_days=5):
    results = {}
    min_history = 150
    dates = df.index
    if len(dates) < min_history:
        return results
    calc_set = set(range(min_history, len(dates), step_days))
    calc_set.add(len(dates) - 1)
    last = {"pattern_type": "NONE", "confidence": 0.0,
            "entry_price": None, "stop_loss": None, "pivot_price": None}
    for i, date in enumerate(dates):
        if i < min_history:
            results[date] = last.copy()
            continue
        if i in calc_set:
            hist = df.iloc[max(0, i-199): i+1]
            try:
                engine = PatternDetectionEngine(ticker, hist, lookback=200)
                patterns = engine.scan_all_patterns()
                if patterns:
                    best = patterns[0]
                    last = {
                        "pattern_type": best.pattern_type.value,
                        "confidence": round(best.confidence, 4),
                        "entry_price": best.entry_price,
                        "stop_loss": best.stop_loss,
                        "pivot_price": best.pivot_price,
                    }
                else:
                    last = {"pattern_type": "NONE", "confidence": 0.0,
                            "entry_price": None, "stop_loss": None, "pivot_price": None}
            except Exception:
                pass
        results[date] = last.copy()
    return results

def build_confidence_matrix(cache, tickers, start_date, end_date):
    dates = pd.date_range(start_date, end_date, freq="B")
    data, type_data = {}, {}
    for ticker in tickers:
        if ticker not in cache or not cache[ticker]:
            data[ticker] = pd.Series(0.0, index=dates)
            type_data[ticker] = pd.Series("NONE", index=dates)
            continue
        raw = cache[ticker]
        conf = pd.Series({d: v["confidence"] for d, v in raw.items()})
        ptype = pd.Series({d: v["pattern_type"] for d, v in raw.items()})
        conf.index = pd.to_datetime(conf.index)
        ptype.index = pd.to_datetime(ptype.index)
        data[ticker] = conf.reindex(dates, method="ffill").fillna(0.0)
        type_data[ticker] = ptype.reindex(dates, method="ffill").fillna("NONE")
    return {"confidence": pd.DataFrame(data, index=dates),
            "pattern_type": pd.DataFrame(type_data, index=dates)}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--full", action="store_true")
    p.add_argument("--tickers", nargs="+")
    p.add_argument("--tickers-file", help="Archivo con un ticker por linea")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    p.add_argument("--step", type=int, default=5)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--merge", action="store_true",
                   help="Mergear con cache existente en vez de sobreescribir")
    p.add_argument("--no-matrix", action="store_true")
    args = p.parse_args()

    # Determinar tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    elif args.tickers_file:
        with open(args.tickers_file) as f:
            tickers = [l.strip().upper() for l in f if l.strip() and not l.startswith("#")]
        print(f"[INFO] Tickers desde archivo: {len(tickers)}")
    else:
        tickers = load_ticker_list(full=args.full)

    print(f"\n{'='*55}")
    print(f"  PRECOMPUTE PATTERN CACHE")
    print(f"  Tickers : {len(tickers)} | Periodo: {args.start} -> {args.end}")
    print(f"  Step    : cada {args.step} dias | Merge: {args.merge}")
    print(f"{'='*55}\n")

    # Cargar cache base (merge o resume)
    cache = {}
    if args.merge and PATTERN_CACHE_FILE.exists():
        with open(PATTERN_CACHE_FILE, "rb") as f:
            cache = pickle.load(f)
        print(f"[MERGE] Cache existente: {len(cache)} tickers\n")
    elif args.resume and PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "rb") as f:
            cache = pickle.load(f)
        print(f"[RESUME] {len(cache)} tickers ya procesados\n")

    pending = [t for t in tickers if t not in cache]
    print(f"[INFO] Por procesar: {len(pending)} tickers\n")
    stats = {"loaded": 0, "no_data": 0, "error": 0, "with_patterns": 0}

    for ticker in tqdm(pending, desc="Patrones", unit="ticker"):
        try:
            df = load_ohlcv(ticker, args.start, args.end)
            if df is None:
                stats["no_data"] += 1
                cache[ticker] = {}
                continue
            stats["loaded"] += 1
            results = compute_patterns_for_ticker(ticker, df, step_days=args.step)
            if any(v["confidence"] > 0 for v in results.values()):
                stats["with_patterns"] += 1
            cache[ticker] = results
            if stats["loaded"] % 10 == 0:
                with open(PROGRESS_FILE, "wb") as f:
                    pickle.dump(cache, f, protocol=4)
        except Exception as e:
            logger.warning(f"Error {ticker}: {e}")
            stats["error"] += 1
            cache[ticker] = {}

    with open(PATTERN_CACHE_FILE, "wb") as f:
        pickle.dump(cache, f, protocol=4)
    print(f"\n[OK] Cache guardado: {PATTERN_CACHE_FILE} ({len(cache)} tickers total)")

    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()

    if not args.no_matrix:
        all_tickers = sorted(cache.keys())
        print(f"[INFO] Construyendo matrix ({len(all_tickers)} tickers)...")
        matrix = build_confidence_matrix(cache, all_tickers, args.start, args.end)
        with open(PATTERN_MATRIX_FILE, "wb") as f:
            pickle.dump(matrix, f, protocol=4)
        conf_df = matrix["confidence"]
        mean_conf = conf_df[conf_df > 0].mean().mean()
        pct_nonzero = (conf_df > 0).mean().mean() * 100
        print(f"[OK] Matrix: {conf_df.shape} | Conf media: {mean_conf:.3f} | Cobertura: {pct_nonzero:.1f}%")

    print(f"\n{'='*55}")
    print(f"  Procesados   : {len(tickers)}")
    print(f"  Con datos    : {stats['loaded']}")
    print(f"  Sin datos    : {stats['no_data']}")
    print(f"  Con errores  : {stats['error']}")
    if stats['loaded'] > 0:
        pct = stats['with_patterns'] / stats['loaded'] * 100
        print(f"  Con patrones : {stats['with_patterns']} ({pct:.1f}%)")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    main()
