#!/usr/bin/env python3
"""
Populate Custom Ticker List
============================
Descarga data histórica para una lista específica de tickers.

Usage:
    python3 populate_custom_list.py
    python3 populate_custom_list.py --start-date 2020-01-01 --end-date 2024-12-31
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yfinance as yf
from src.data.ticker_cache import TickerCache
import pandas as pd
from datetime import datetime
import time
import argparse

# Tu lista de tickers
TICKER_LIST = """NVDA, AAPL, MSFT, AMZN, GOOGL, GOOG, META, AVGO, TSLA, BRK.B, LLY, WMT, JPM, V, ORCL, XOM, MA, JNJ, PLTR, BAC, COST, ABBV, MU, NFLX, HD, GE, PG, AMD, CVX, UNH, KO, WFC, MS, CSCO, CAT, IBM, GS, MRK, LRCX, AXP, PM, RTX, CRM, AMAT, TMO, TMUS, ABT, APP, MCD, INTC, C, ISRG, LIN, DIS, PEP, QCOM, KLAC, BA, INTU, SCHW, UBER, BKNG, AMGN, TJX, TXN, ACN, APH, VZ, T, GEV, DHR, BLK, NEE, SPGI, COF, ANET, GILD, LOW, NOW, ADI, PFE, BSX, SYK, ADBE, UNP, DE, PANW, HON, WELL, PGR, ETN, LMT, MDT, CEG, BX, CB, COP, PLD, KKR, NEM, CRWD, VRTX, PH, BMY, HCA, ADP, HOOD, CMCSA, CVS, SBUX, MCK, SNPS, NKE, MO, SO, GD, MCO, CME, ICE, DASH, UPS, MMC, DUK, CDNS, WM, NOC, MAR, CRH, HWM, MMM, SHW, USB, PNC, RCL, TT, APO, ABNB, REGN, BK, ELV, FCX, EMR, DELL, ORLY, AMT, EQIX, TDG, CTAS, GM, ECL, CMI, MNST, AON, CI, ITW, WMB, FDX, GLW, WBD, MDLZ, HLT, WDC, TEL, AJG, JCI, SLB, STX, RSG, CL, CSX, CVNA, COR, COIN, TFC, NSC, MSI, PWR, TRV, LHX, AEP, PCAR, ROST, NXPI, KMI, SPG, URI, FTNT, APD, ADSK, SRE, BDX, PSX, AFL, IDXX, EOG, AZO, F, VLO, VST, NDAQ, ZTS, ALL, SNDK, WDAY, DLR, PYPL, O, CMG, MPC, MET, EA, AXON, D, EW, BKR, CBRE, GWW, PSA, AME, FAST, CAH, TGT, CARR, DAL, AMP, ROP, CTVA, TTWO, ROK, MPWR, DHI, OKE, DDOG, XEL, MSCI, EXC, YUM, XYZ, FANG, OXY, CCL, A, ETR, PRU, IQV, VMC, CTSH, EBAY, EL, PAYX, GRMN, AIG, MCHP, MLM, LVS, GEHC, FICO, PEG, ARES, CPRT, WAB, HSY, HIG, UAL, TRGP, KDP, KR, FISV, NUE, STT, RMD, CCI, EXPE, ODFL, ED, FIX, KEYS, SYY, VTR, OTIS, PCG, FIS, ACGL, WEC, TER, XYL, LYV, IR, HUM, RJF, FITB, MTB, KMB, KVUE, EQT, WTW, DG, IBKR, VRSK, SYF, MTD, ADM, VICI, HPE, ULTA, EXR, LEN, ROL, EME, HBAN, NRG, EFX, KHC, DOV, NTRS, BRO, BIIB, TPR, HAL, CBOE, CHTR, TSCO, AEE, ATO, DTE, IRM, DLTR, DXCM, BR, WRB, CFG, FE, TDY, PHM, FSLR, STZ, PPL, VLTO, ES, CINF, AVB, LDOS, STE, ON, RF, HUBB, AWK, OMC, CSGP, CNP, STLD, EXE, JBL, PPG, LULU, GIS, WSM, WAT, EIX, TROW, DRI, CPAY, VRSN, LUV, KEY, EQR, CNC, IP, SW, DVN, RL, L, TPL, CMS, EXPD, INCY, LH, NTAP, NVR, CHD, TSN, PTC, PODD, CHRW, AMCR, NI, PFG, WST, PKG, HPQ, JBHT, DGX, BG, SBAC, TYL, TRMB, APTV"""


def populate_ticker(ticker: str, start_date: str, end_date: str, cache: TickerCache) -> bool:
    """Descarga y guarda data para un ticker."""
    try:
        print(f"   📥 Downloading {ticker}...", end=" ", flush=True)
        
        # Download from yfinance
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if df is None or len(df) == 0:
            print(f"❌ No data")
            return False
        
        # Normalize column names
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
        df.columns = df.columns.str.capitalize()
        
        # Reset index (date)
        df = df.reset_index()
        df.columns = [col.lower() for col in df.columns]
        
        # Convert date to string format for SQLite
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # Clean data: remove NaN/inf
        df = df.replace([float('inf'), float('-inf')], None)
        df = df.where(pd.notna(df), None)
        
        # Store in cache
        for _, row in df.iterrows():
            try:
                cache.conn.execute(
                    """INSERT OR REPLACE INTO ohlcv_cache 
                       (ticker, date, open, high, low, close, volume)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ticker, 
                        str(row['date']), 
                        float(row['open']) if row['open'] is not None else None,
                        float(row['high']) if row['high'] is not None else None,
                        float(row['low']) if row['low'] is not None else None,
                        float(row['close']) if row['close'] is not None else None,
                        int(row['volume']) if row['volume'] is not None else 0
                    )
                )
            except Exception as e:
                # Skip problematic rows
                continue
        
        cache.conn.commit()
        print(f"✅ {len(df)} days")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:50]}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Populate custom ticker list')
    parser.add_argument('--start-date', default='2020-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2024-12-31', help='End date (YYYY-MM-DD)')
    parser.add_argument('--batch-size', type=int, default=10, help='Commit every N tickers')
    parser.add_argument('--skip-existing', action='store_true', help='Skip tickers already in DB')
    args = parser.parse_args()
    
    # Parse ticker list
    tickers = [t.strip() for t in TICKER_LIST.split(',')]
    tickers = sorted(set(tickers))  # Remove duplicates
    
    print(f"🏎️ POPULATE CUSTOM TICKER LIST")
    print(f"="*60)
    print(f"📊 Total tickers: {len(tickers)}")
    print(f"📅 Period: {args.start_date} → {args.end_date}")
    print(f"=" * 60)
    
    cache = TickerCache()
    
    # Check existing
    if args.skip_existing:
        query = 'SELECT DISTINCT ticker FROM ohlcv_cache'
        existing = set([row[0] for row in cache.conn.execute(query).fetchall()])
        to_download = [t for t in tickers if t not in existing]
        print(f"✅ Already in DB: {len(tickers) - len(to_download)}")
        print(f"📥 To download: {len(to_download)}")
        tickers = to_download
    
    if not tickers:
        print(f"\n✅ All tickers already in DB!")
        return
    
    # Download
    print(f"\n🚀 Starting download...\n")
    start_time = time.time()
    success = 0
    failed = []
    
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] ", end="")
        
        if populate_ticker(ticker, args.start_date, args.end_date, cache):
            success += 1
        else:
            failed.append(ticker)
        
        # Rate limiting (yfinance free tier)
        if i % args.batch_size == 0:
            print(f"\n⏸️  Batch {i}/{len(tickers)} completed. Sleeping 2s...\n")
            time.sleep(2)
        else:
            time.sleep(0.5)  # Small delay between requests
    
    elapsed = time.time() - start_time
    
    # Summary
    print(f"\n{'='*60}")
    print(f"✅ COMPLETED!")
    print(f"{'='*60}")
    print(f"   Success: {success}/{len(tickers)} ({success/len(tickers)*100:.1f}%)")
    print(f"   Failed: {len(failed)}")
    print(f"   Time: {elapsed/60:.1f} minutes")
    
    if failed:
        print(f"\n❌ Failed tickers:")
        for t in failed[:20]:
            print(f"   {t}")
        if len(failed) > 20:
            print(f"   ... and {len(failed)-20} more")
        
        # Save failed list
        with open('failed_tickers.txt', 'w') as f:
            f.write('\n'.join(failed))
        print(f"\n💾 Full list saved to: failed_tickers.txt")
    
    # Verify final count
    query = "SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache"
    total_in_db = cache.conn.execute(query).fetchone()[0]
    print(f"\n📊 Total tickers in DB now: {total_in_db}")
    
    print(f"\n🏎️ Ready for Bugatti EVO with fold-size={min(total_in_db-10, 300)}!")


if __name__ == '__main__':
    main()
