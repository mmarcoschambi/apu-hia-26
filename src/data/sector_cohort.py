import sqlite3
import pandas as pd
from pathlib import Path
import logging
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SectorCohortManager:
    def __init__(self, db_path: str = "data/ticker_cache.db"):
        self.db_path = Path(db_path)
        self.setup_table()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def setup_table(self):
        conn = self.get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sector_cohort (
                date            DATE NOT NULL,
                sector_etf      TEXT NOT NULL,
                ticker_count    INTEGER,
                score_mean      REAL,
                score_mean_5d   REAL,
                score_delta_5d  REAL,
                near_breakout_n INTEGER,
                new_entrants    TEXT,
                dropped         TEXT,
                rank_today      INTEGER,
                rank_5d_ago     INTEGER,
                rank_delta      INTEGER,
                PRIMARY KEY (date, sector_etf)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cohort_date ON sector_cohort(date)")
        conn.commit()
        conn.close()

    def calculate_day(self, date_str: str):
        """Calcula métricas agregadas por sector para un día."""
        logger.info(f"Calculando sector_cohort para {date_str}...")
        
        conn = self.get_connection()
        
        # 1. Agregados básicos del día actual
        query_today = """
        SELECT 
            sector_etf,
            COUNT(*) as ticker_count,
            AVG(score) as score_mean,
            SUM(near_breakout) as near_breakout_n,
            GROUP_CONCAT(ticker) as tickers
        FROM candidate_state
        WHERE date = ? AND sector_etf IS NOT NULL
        GROUP BY sector_etf
        """
        df_today = pd.read_sql_query(query_today, conn, params=(date_str,))
        
        if df_today.empty:
            logger.warning(f"No hay datos en candidate_state para {date_str}")
            conn.close()
            return

        # 2. Obtener datos históricos para deltas (últimos 5 días de mercado)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM sector_cohort WHERE date < ? ORDER BY date DESC LIMIT 5", (date_str,))
        prev_dates = [row[0] for row in cursor.fetchall()]
        
        # 3. New entrants y dropped (comparado con el día anterior)
        if prev_dates:
            prev_date = prev_dates[0]
            query_prev = "SELECT sector_etf, GROUP_CONCAT(ticker) as tickers FROM candidate_state WHERE date = ? GROUP BY sector_etf"
            df_prev = pd.read_sql_query(query_prev, conn, params=(prev_date,))
            
            # Map tickers to sector
            prev_tickers = {row['sector_etf']: set(row['tickers'].split(',')) for _, row in df_prev.iterrows()}
            curr_tickers = {row['sector_etf']: set(row['tickers'].split(',')) for _, row in df_today.iterrows()}
            
            new_entrants = {}
            dropped = {}
            for etf in curr_tickers:
                prev = prev_tickers.get(etf, set())
                curr = curr_tickers[etf]
                new_entrants[etf] = list(curr - prev)
                dropped[etf] = list(prev - curr)
            
            # 4. Score mean 5d y delta
            # Obtenemos score_mean de los últimos 5 días
            placeholders = ','.join(['?'] * len(prev_dates))
            query_hist = f"SELECT sector_etf, AVG(score_mean) as score_mean_5d FROM sector_cohort WHERE date IN ({placeholders}) GROUP BY sector_etf"
            df_hist = pd.read_sql_query(query_hist, conn, params=prev_dates)
            
            df_today = df_today.merge(df_hist, on='sector_etf', how='left')
            df_today['score_delta_5d'] = df_today['score_mean'] - df_today['score_mean_5d'].fillna(df_today['score_mean'])
            
            # 5. Ranks
            df_today['rank_today'] = df_today['score_mean'].rank(ascending=False).astype(int)
            
            # Rank 5 days ago
            if len(prev_dates) >= 5:
                date_5d = prev_dates[-1]
                query_rank_5d = "SELECT sector_etf, rank_today as rank_5d_ago FROM sector_cohort WHERE date = ?"
                df_rank_5d = pd.read_sql_query(query_rank_5d, conn, params=(date_5d,))
                df_today = df_today.merge(df_rank_5d, on='sector_etf', how='left')
                df_today['rank_delta'] = df_today['rank_5d_ago'] - df_today['rank_today']
            else:
                df_today['rank_5d_ago'] = None
                df_today['rank_delta'] = 0
        else:
            df_today['score_mean_5d'] = df_today['score_mean']
            df_today['score_delta_5d'] = 0
            df_today['rank_today'] = df_today['score_mean'].rank(ascending=False).astype(int)
            df_today['rank_5d_ago'] = None
            df_today['rank_delta'] = 0
            new_entrants = {etf: [] for etf in df_today['sector_etf']}
            dropped = {etf: [] for etf in df_today['sector_etf']}

        # Prepare for insertion
        for _, row in df_today.iterrows():
            etf = row['sector_etf']
            conn.execute("""
                INSERT OR REPLACE INTO sector_cohort (
                    date, sector_etf, ticker_count, score_mean, score_mean_5d,
                    score_delta_5d, near_breakout_n, new_entrants, dropped,
                    rank_today, rank_5d_ago, rank_delta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str, etf, int(row['ticker_count']), row['score_mean'], row['score_mean_5d'],
                row['score_delta_5d'], int(row['near_breakout_n']),
                json.dumps(new_entrants.get(etf, [])),
                json.dumps(dropped.get(etf, [])),
                int(row['rank_today']), 
                int(row['rank_5d_ago']) if row['rank_5d_ago'] is not None else None,
                int(row['rank_delta'])
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"[OK] sector_cohort actualizado para {date_str}")

    def backfill(self, days: int = 90):
        """Puebla sector_cohort para los últimos X días."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM candidate_state ORDER BY date ASC")
        dates = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Usamos los últimos X días de los disponibles
        for date_str in dates[-days:]:
            self.calculate_day(date_str)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = SectorCohortManager()
    manager.backfill(10)
