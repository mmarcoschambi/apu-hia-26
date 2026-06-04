import sqlite3
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import json

logger = logging.getLogger(__name__)

# Try to import SECTOR_MAP from sector_rotation
try:
    import sys
    import os
    sys.path.append(os.getcwd())
    from src.utils.sector_rotation import SECTOR_MAP, SECTOR_TO_ETF
    logger.info(f"Imported SECTOR_MAP ({len(SECTOR_MAP)}) and SECTOR_TO_ETF ({len(SECTOR_TO_ETF)})")
except ImportError:
    SECTOR_MAP = {}
    SECTOR_TO_ETF = {}
    logger.warning("Could not import sector rotation mappings")

class CandidateTracker:
    def __init__(self, db_path: str = "data/ticker_cache.db"):
        self.db_path = Path(db_path)
        self.setup_table()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def setup_table(self):
        conn = self.get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candidate_state (
                date            DATE    NOT NULL,
                ticker          TEXT    NOT NULL,

                -- Score y ranking
                rs_composite    REAL,
                rts_pct         REAL,
                score           REAL,
                rank_universe   INTEGER,

                -- Precio y estructura
                close           REAL,
                sma20           REAL,
                dist_sma20_pct  REAL,
                pivot_dist_pct  REAL,

                -- Breakout
                breakout_level  REAL,
                breakout_gap    REAL,
                near_breakout   INTEGER,

                -- Volumen
                rvol            REAL,

                -- MA Stack
                ma_stack        INTEGER,

                -- Sector / industria
                sector_etf      TEXT,
                sector          TEXT,
                industry        TEXT,
                theme_tags      TEXT,

                -- HTF
                htf_candidate   INTEGER DEFAULT 0,

                -- Estado del candidato
                in_watchlist    INTEGER DEFAULT 1,
                setup_age       INTEGER DEFAULT 0,
                status          TEXT,

                -- Trazabilidad
                computed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, ticker)
            )
        """)
        # Indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_candidate_date ON candidate_state(date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_candidate_ticker ON candidate_state(ticker)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_candidate_status ON candidate_state(status)")
        conn.commit()
        conn.close()

    def populate_day(self, date_str: str):
        """
        Puebla candidate_state para un dia usando pandas rolling sobre datos raw.
        NO depende de sma20/avg_volume_20/trend_aligned pre-calculados en ohlcv_cache
        porque el pipeline del VPS solo escribe OHLCV raw.
        """
        import pandas as pd
        import numpy as np

        logger.info(f"Poblando candidate_state para {date_str}...")
        conn = self.get_connection()

        # 1. Tickers activos ese dia segun daily_rs_rankings
        rs_df = pd.read_sql_query(
            "SELECT ticker, rs_composite FROM daily_rs_rankings WHERE date=?",
            conn, params=(date_str,)
        )
        if rs_df.empty:
            logger.warning(f"Sin datos en daily_rs_rankings para {date_str}")
            conn.close()
            return

        tickers = rs_df["ticker"].tolist()

        # 2. Triad rankings
        tri_df = pd.read_sql_query(
            "SELECT ticker, rts_pct, pivot_dist_pct FROM daily_triad_rankings WHERE date=?",
            conn, params=(date_str,)
        )

        # 3. Universe (sector/industry)
        uni_df = pd.read_sql_query(
            "SELECT ticker, sector, industry FROM universe WHERE ticker IN ({})".format(
                ",".join(["?"]*len(tickers))
            ), conn, params=tickers
        )

        # 4. OHLCV raw de los ultimos 250 dias para calcular rolling indicators
        lookback_start = (pd.Timestamp(date_str) - pd.Timedelta(days=300)).strftime("%Y-%m-%d")
        ohlcv_raw = pd.read_sql_query(
            """SELECT ticker, date, open, high, low, close, volume
               FROM ohlcv_cache
               WHERE ticker IN ({}) AND date >= ? AND date <= ?
               ORDER BY ticker, date""".format(",".join(["?"]*len(tickers))),
            conn, params=tickers + [lookback_start, date_str]
        )
        conn.close()

        if ohlcv_raw.empty:
            logger.warning(f"Sin datos OHLCV para {date_str}")
            return

        ohlcv_raw["date"] = pd.to_datetime(ohlcv_raw["date"], errors='coerce')
        ohlcv_raw = ohlcv_raw.dropna(subset=["date"])

        # 5. Calcular indicadores vectorizados con pivot (un rolling sobre el DataFrame completo)
        # Pivot: filas=date, columnas=ticker
        close_p = ohlcv_raw.pivot(index="date", columns="ticker", values="close").sort_index()
        high_p  = ohlcv_raw.pivot(index="date", columns="ticker", values="high").sort_index()
        vol_p   = ohlcv_raw.pivot(index="date", columns="ticker", values="volume").replace(0, np.nan).sort_index()

        sma20_p   = close_p.rolling(20, min_periods=10).mean()
        sma50_p   = close_p.rolling(50, min_periods=25).mean()
        sma200_p  = close_p.rolling(200, min_periods=80).mean()
        avg_v20_p = vol_p.rolling(20, min_periods=5).mean()
        bo_level_p = high_p.shift(1).rolling(20, min_periods=5).max()

        target_dt = pd.Timestamp(date_str)

        def get_row(df):
            if target_dt in df.index:
                return df.loc[target_dt]
            return pd.Series(dtype=float)

        close_row   = get_row(close_p)
        sma20_row   = get_row(sma20_p)
        sma50_row   = get_row(sma50_p)
        sma200_row  = get_row(sma200_p)
        avg_v20_row = get_row(avg_v20_p)
        bo_row      = get_row(bo_level_p)
        vol_row     = get_row(vol_p)

        derived = {}
        for ticker in tickers:
            if ticker not in close_row.index:
                continue
            cl   = close_row.get(ticker)
            s20  = sma20_row.get(ticker)
            s50  = sma50_row.get(ticker)
            s200 = sma200_row.get(ticker)
            avgv = avg_v20_row.get(ticker)
            bl   = bo_row.get(ticker)
            vol  = vol_row.get(ticker)
            if cl is None or np.isnan(cl):
                continue
            derived[ticker] = {
                "close":          float(cl),
                "sma20":          float(s20) if s20 and not np.isnan(s20) else None,
                "avg_vol20":      float(avgv) if avgv and not np.isnan(avgv) else None,
                "breakout_level": float(bl)  if bl  and not np.isnan(bl)  else None,
                "vol_today":      float(vol) if vol and not np.isnan(vol) else None,
                "trend_aligned":  int(bool(
                    cl > (s50 or 0) and (s50 or 0) > (s200 or 0)
                )),
            }

        # 5.5. Calcular HTF Candidate flag
        try:
            from src.screeners.htf_candidate import HTFCandidateScreener
            htf_screener = HTFCandidateScreener()
        except ImportError:
            htf_screener = None

        # 6. Merge y calcular campos derivados
        rs_df = rs_df.merge(tri_df, on="ticker", how="left")
        rs_df = rs_df.merge(uni_df, on="ticker", how="left")
        rs_df["rank_universe"] = rs_df["rs_composite"].rank(ascending=False, method="min").astype(int)

        rows = []
        for _, row in rs_df.iterrows():
            ticker = row["ticker"]
            d = derived.get(ticker)
            if d is None:
                continue

            cl  = d["close"]
            s20 = d["sma20"]
            avg_v = d["avg_vol20"]
            bl  = d["breakout_level"]

            dist_sma20  = ((cl - s20) / s20 * 100) if s20 else None
            bo_gap      = ((cl - bl)  / bl  * 100) if bl  else None
            near_bo     = int(bo_gap is not None and abs(bo_gap) < 3.0)
            rvol        = (d["vol_today"] / avg_v) if (avg_v and d.get("vol_today")) else None
            score = (0.6 * float(row["rs_composite"]) +
                     0.4 * float(row["rts_pct"] if pd.notna(row.get("rts_pct")) else row["rs_composite"]))

            htf_flag = 0
            if htf_screener:
                ticker_df = ohlcv_raw[ohlcv_raw["ticker"] == ticker]
                if not ticker_df.empty:
                    res = htf_screener.scan(ticker, ticker_df)
                    if res and res.passed:
                        htf_flag = 1

            rows.append((
                date_str, ticker,
                float(row["rs_composite"]),
                float(row["rts_pct"]) if pd.notna(row.get("rts_pct")) else None,
                score,
                int(row["rank_universe"]),
                cl, s20, dist_sma20,
                float(row["pivot_dist_pct"]) if pd.notna(row.get("pivot_dist_pct")) else None,
                bl, bo_gap, near_bo,
                float(rvol) if rvol else None,
                d["trend_aligned"],
                row.get("sector"), row.get("industry"),
                htf_flag,
                "BUILDING"
            ))

        # 7. Insertar en batch
        conn = self.get_connection()
        conn.executemany("""
            INSERT OR REPLACE INTO candidate_state (
                date, ticker, rs_composite, rts_pct, score,
                rank_universe, close, sma20, dist_sma20_pct,
                pivot_dist_pct, breakout_level, breakout_gap,
                near_breakout, rvol, ma_stack, sector, industry, htf_candidate, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

        logger.info(f"✅ {date_str}: {len(rows)} filas insertadas.")

        self._update_sector_etfs(date_str)
        self._update_setup_metrics(date_str)
        self._update_theme_tags(date_str)
        conn.close()

    def _update_theme_tags(self, date_str: str):
        """Actualiza theme_tags basado en THEME_MAP."""
        try:
            from src.data.theme_taxonomy import THEME_MAP
        except ImportError:
            return

        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get tickers for this date
        cursor.execute("SELECT ticker FROM candidate_state WHERE date = ?", (date_str,))
        tickers = [row[0] for row in cursor.fetchall()]
        
        updates = []
        for ticker in tickers:
            themes = THEME_MAP.get(ticker)
            if themes:
                updates.append((json.dumps(themes), date_str, ticker))
        
        if updates:
            cursor.executemany(
                "UPDATE candidate_state SET theme_tags = ? WHERE date = ? AND ticker = ?",
                updates
            )
            conn.commit()
        conn.close()

    def _update_sector_etfs(self, date_str: str):
        """Actualiza sector_etf basado en el SECTOR_MAP y SECTOR_TO_ETF."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get tickers and their sectors for this date
        cursor.execute("SELECT ticker, sector FROM candidate_state WHERE date = ?", (date_str,))
        rows = cursor.fetchall()
        logger.info(f"Updating {len(rows)} tickers for {date_str}")
        
        updates = []
        for ticker, sector in rows:
            etf = SECTOR_MAP.get(ticker)
            if not etf and sector:
                etf = SECTOR_TO_ETF.get(sector)
            
            if etf:
                updates.append((etf, date_str, ticker))
        
        if updates:
            logger.info(f"Found {len(updates)} sector updates for {date_str}")
            cursor.executemany(
                "UPDATE candidate_state SET sector_etf = ? WHERE date = ? AND ticker = ?",
                updates
            )
            conn.commit()
        else:
            logger.warning(f"No sector updates found for {date_str}")
        conn.close()

    def _update_setup_metrics(self, date_str: str):
        """Actualiza setup_age y status basado en lógica de transición."""
        conn = self.get_connection()
        
        # Get previous date
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM candidate_state WHERE date < ? ORDER BY date DESC LIMIT 1", (date_str,))
        prev_date_row = cursor.fetchone()
        
        if prev_date_row:
            prev_date = prev_date_row[0]
            # Update setup_age: age = prev_age + 1 if ticker was in previous day
            query_age = """
            UPDATE candidate_state
            SET setup_age = (
                SELECT COALESCE(prev.setup_age, 0) + 1
                FROM candidate_state prev
                WHERE prev.ticker = candidate_state.ticker
                  AND prev.date = ?
            )
            WHERE date = ?
              AND ticker IN (SELECT ticker FROM candidate_state WHERE date = ?)
            """
            conn.execute(query_age, (prev_date, date_str, prev_date))
        
        # Update status logic: BUILDING|NEAR|CONFIRMED|COOLED|DROPPED
        # NEAR: near_breakout = 1
        # CONFIRMED: close > breakout_level AND rvol > 1.2 (example)
        # BUILDING: otherwise
        
        query_status = """
        UPDATE candidate_state
        SET status = CASE 
            WHEN close > breakout_level AND rvol > 1.2 THEN 'CONFIRMED'
            WHEN near_breakout = 1 THEN 'NEAR'
            ELSE 'BUILDING'
        END
        WHERE date = ?
        """
        conn.execute(query_status, (date_str,))
        
        conn.commit()
        conn.close()

    def backfill(self, days: int = 90):
        """Puebla los últimos X días."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM daily_rs_rankings ORDER BY date DESC LIMIT ?", (days,))
        dates = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Process in chronological order for setup_age to work
        for date_str in reversed(dates):
            self.populate_day(date_str)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tracker = CandidateTracker()
    # Para probar un solo día
    # tracker.populate_day('2024-05-07')
    # O backfill
    tracker.backfill(10) # Probamos con 10 días primero
