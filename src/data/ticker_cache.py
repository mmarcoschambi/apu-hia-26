import sqlite3
import threading
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import logging
from config.settings import DATA_SOURCE, OPENBB_PROVIDER

logger = logging.getLogger(__name__)


class TickerCache:
    def __init__(self, db_path=None):
        if db_path is None:
            # Default to data directory in project root
            base_dir = Path(__file__).resolve().parent.parent.parent
            data_dir = base_dir / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = data_dir / "ticker_cache.db"

        self.db_path = db_path
        self.lock = threading.Lock()

        # Add timeout and other optimizations to reduce lock contention
        self.conn = sqlite3.connect(
            str(db_path),
            check_same_thread=False,
            timeout=60.0,  # Increased timeout for safety
            isolation_level="DEFERRED",
        )
        # Enable WAL mode for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe
        # PERF: aumentar cache de páginas en memoria (4MB → 64MB)
        self.conn.execute("PRAGMA cache_size = -65536")
        # PERF: guardar tmp en memoria (evita I/O en operaciones temporales)
        self.conn.execute("PRAGMA temp_store = MEMORY")

        self.cache_dir = Path(db_path).parent / "cache"
        self.cache_dir.mkdir(exist_ok=True)

        self.setup_database()

    def setup_database(self):
        """Crea tablas si no existen"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS universe (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                exchange TEXT,
                sector TEXT,
                industry TEXT,
                last_updated DATE
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_cache (
                ticker TEXT,
                date DATE,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                dollar_volume REAL,
                rolling_dollar_vol_20 REAL,
                sma20 REAL,
                sma50 REAL,
                sma100 REAL,
                sma200 REAL,
                adr_pct_20 REAL,
                PRIMARY KEY (ticker, date)
            )
        """)

        # Migración automática para bases de datos existentes
        cursor = self.conn.execute("PRAGMA table_info(ohlcv_cache)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        
        for col in ["sma20", "sma50", "sma100", "sma200", "adr_pct_20"]:
            if col not in existing_cols:
                logger.info(f"Migrating ticker_cache.db: adding column {col} to ohlcv_cache")
                try:
                    self.conn.execute(f"ALTER TABLE ohlcv_cache ADD COLUMN {col} REAL")
                except Exception as e:
                    logger.warning(f"Failed to add column {col}: {e}")


        # Nueva tabla para guardar el Top 500 de cada mes y no recalcularlo
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS monthly_universe_cache (
                year_month TEXT PRIMARY KEY,  -- Formato 'YYYY-MM'
                tickers TEXT,                 -- JSON list
                created_at DATE
            )
        """)

        # Tabla para histórico de Earnings
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS earnings_cache (
                ticker TEXT,
                report_date DATE,
                eps_estimate REAL,
                eps_actual REAL,
                revenue REAL,
                surprise_pct REAL,
                PRIMARY KEY (ticker, report_date)
            )
        """)
        self.conn.commit()

    def save_earnings(self, ticker, earnings_df):
        """
        Guarda histórico de earnings en la base de datos.
        Esperamos un DataFrame con columnas estandarizadas.
        """
        if earnings_df is None or earnings_df.empty:
            return 0

        count = 0
        for _, row in earnings_df.iterrows():
            try:
                # Extraer y limpiar datos
                report_date = row.get("report_date")
                if isinstance(report_date, pd.Timestamp):
                    report_date = report_date.strftime("%Y-%m-%d")

                # Insertar
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO earnings_cache 
                    (ticker, report_date, eps_estimate, eps_actual, revenue, surprise_pct)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        ticker,
                        report_date,
                        row.get("eps_estimate"),
                        row.get("eps_actual"),
                        row.get("revenue"),
                        row.get("surprise_pct"),
                    ),
                )
                count += 1
            except Exception as e:
                logger.debug(f"Error inserting earnings for {ticker}: {e}")

        self.conn.commit()
        return count

    def get_earnings_history(self, ticker):
        """Recupera histórico de earnings desde cache"""
        cursor = self.conn.execute(
            """
            SELECT report_date, eps_estimate, eps_actual, revenue, surprise_pct
            FROM earnings_cache
            WHERE ticker = ?
            ORDER BY report_date DESC
        """,
            (ticker,),
        )

        rows = cursor.fetchall()
        if rows:
            df = pd.DataFrame(
                rows,
                columns=[
                    "report_date",
                    "eps_estimate",
                    "eps_actual",
                    "revenue",
                    "surprise_pct",
                ],
            )
            df["report_date"] = pd.to_datetime(df["report_date"])
            return df
        return None

    def update_universe(self, force=False):
        """
        Actualiza lista de tickers (correr 1 vez por semana)
        """
        cursor = self.conn.execute("SELECT last_updated FROM universe LIMIT 1")
        row = cursor.fetchone()

        # Si la última actualización fue hace menos de 7 días, skip
        if row and not force:
            try:
                last_update = datetime.strptime(row[0], "%Y-%m-%d")
                if (datetime.now() - last_update).days < 7:
                    logger.info("Universe cache is fresh")
                    return
            except (ValueError, TypeError):
                pass

        logger.info("Updating universe...")

        all_tickers = set()

        # Try yahoo_fin first
        try:
            from yahoo_fin import stock_info as si

            all_tickers.update(si.tickers_nasdaq())
            all_tickers.update(si.tickers_sp500())
            all_tickers.update(si.tickers_dow())
            logger.info(f"Fetched {len(all_tickers)} tickers from yahoo_fin")
        except Exception as e:
            logger.warning(
                f"Error fetching tickers from yahoo_fin: {e}. Trying fallback..."
            )

            # Fallback to Wikipedia (more reliable)
            try:
                import requests

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }

                # S&P 500
                url_sp500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
                r_sp500 = requests.get(url_sp500, headers=headers)
                sp500 = pd.read_html(r_sp500.text)[0]
                all_tickers.update(sp500["Symbol"].tolist())

                # Nasdaq 100
                url_ndx = "https://en.wikipedia.org/wiki/Nasdaq-100"
                r_ndx = requests.get(url_ndx, headers=headers)
                # Table index might vary, try to find it
                tables = pd.read_html(r_ndx.text)
                for table in tables:
                    if "Ticker" in table.columns:
                        all_tickers.update(table["Ticker"].tolist())
                        break

                logger.info(
                    f"Fetched {len(all_tickers)} tickers from Wikipedia fallback"
                )
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return

        # Guardar en DB
        count = 0
        for ticker in all_tickers:
            if not ticker or not isinstance(ticker, str):
                continue
            # Clean ticker
            ticker = ticker.replace(".", "-")
            try:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO universe (ticker, last_updated)
                    VALUES (?, ?)
                """,
                    (ticker, datetime.now().strftime("%Y-%m-%d")),
                )
                count += 1
            except Exception as e:
                logger.debug(f"Error inserting ticker {ticker}: {e}")

        self.conn.commit()
        logger.info(
            f"Universe updated: {len(all_tickers)} tickers total. Added {count} new entries."
        )

    def add_tickers(self, tickers):
        """
        Agrega una lista de tickers a la base de datos si no existen.
        Opcionalmente descarga su información básica.
        """
        if isinstance(tickers, str):
            tickers = [tickers]

        count = 0
        new_tickers = []

        for ticker in tickers:
            if not ticker or not isinstance(ticker, str):
                continue

            ticker = ticker.strip().upper().replace(".", "-")

            # Check if exists
            cursor = self.conn.execute(
                "SELECT 1 FROM universe WHERE ticker = ?", (ticker,)
            )
            if not cursor.fetchone():
                try:
                    self.conn.execute(
                        """
                        INSERT OR IGNORE INTO universe (ticker, last_updated)
                        VALUES (?, ?)
                    """,
                        (ticker, datetime.now().strftime("%Y-%m-%d")),
                    )
                    new_tickers.append(ticker)
                    count += 1
                except Exception as e:
                    logger.debug(f"Error inserting ticker {ticker}: {e}")

        self.conn.commit()

        if count > 0:
            logger.info(f"Added {count} new tickers to universe: {new_tickers}")

        return count

    def update_ticker_info(self, ticker):
        """Actualiza info detallada de un ticker específico"""
        try:
            info = yf.Ticker(ticker).info
            self.conn.execute(
                """
                UPDATE universe 
                SET name = ?, exchange = ?, sector = ?, industry = ?, last_updated = ?
                WHERE ticker = ?
            """,
                (
                    info.get("longName", ""),
                    info.get("exchange", ""),
                    info.get("sector", ""),
                    info.get("industry", ""),
                    datetime.now().strftime("%Y-%m-%d"),
                    ticker,
                ),
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating info for {ticker}: {e}")
            return False

    def get_active_tickers(
        self,
        filters=None,
        sort_by="alphabetical",
        limit=None,
        date_filter=None,
        min_price=5.0,
        min_rolling_dollar_vol=15000000,
    ):
        """
        Obtiene tickers que cumplen filtros

        Args:
            filters: dict con filtros (sector, exchange, etc)
            sort_by: 'alphabetical', 'liquidity', or 'random'
            limit: número máximo de tickers a retornar
            date_filter: fecha específica para filtrar por liquidez (por ejemplo, '2024-01-18')
            min_price: precio mínimo para considerar liquidez
            min_rolling_dollar_vol: volumen en dólares mínimo para considerar liquidez
        """
        if sort_by == "liquidity":
            # Get tickers with volume data and sort by rolling dollar volume for a specific date
            if date_filter:
                # Filtrar tickers líquidos para una fecha específica
                query = """
                    SELECT o.ticker
                    FROM ohlcv_cache o
                    JOIN universe u ON o.ticker = u.ticker
                    WHERE o.date = ? AND o.close >= ? AND o.rolling_dollar_vol_20 >= ?
                """
                params = [date_filter, min_price, min_rolling_dollar_vol]
            else:
                # Original approach: Get tickers with volume data and sort by average dollar volume
                query = """
                    SELECT o.ticker, AVG(o.close * o.volume) as avg_dollar_vol
                    FROM ohlcv_cache o
                    JOIN universe u ON o.ticker = u.ticker
                    WHERE 1=1
                """
                params = []

            if filters and not date_filter:
                if "sector" in filters:
                    query += " AND u.sector = ?"
                    params.append(filters["sector"])
                if "exchange" in filters:
                    if isinstance(filters["exchange"], (list, tuple)):
                        placeholders = ",".join(["?" for _ in filters["exchange"]])
                        query += f" AND u.exchange IN ({placeholders})"
                        params.extend(filters["exchange"])
                    else:
                        query += " AND u.exchange = ?"
                        params.append(filters["exchange"])

            if date_filter:
                # Si estamos filtrando por fecha, no necesitamos GROUP BY ni HAVING
                if filters:
                    if "sector" in filters:
                        query += " AND u.sector = ?"
                        params.append(filters["sector"])
                    if "exchange" in filters:
                        if isinstance(filters["exchange"], (list, tuple)):
                            placeholders = ",".join(["?" for _ in filters["exchange"]])
                            query += f" AND u.exchange IN ({placeholders})"
                            params.extend(filters["exchange"])
                        else:
                            query += " AND u.exchange = ?"
                            params.append(filters["exchange"])
            else:
                query += " GROUP BY o.ticker HAVING COUNT(*) >= 20 ORDER BY avg_dollar_vol DESC"

            if limit and not date_filter:
                query += f" LIMIT {limit}"
            elif limit and date_filter:
                query += f" ORDER BY o.rolling_dollar_vol_20 DESC LIMIT {limit}"

            cursor = self.conn.execute(query, params)
            return [row[0] for row in cursor.fetchall()]

    def get_cached_month_universe(self, year_month):
        """Recupera el universo guardado para un mes específico (YYYY-MM)"""
        try:
            import json

            cursor = self.conn.execute(
                "SELECT tickers FROM monthly_universe_cache WHERE year_month = ?",
                (year_month,),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.error(f"Error reading monthly cache: {e}")
        return None

    def save_cached_month_universe(self, year_month, tickers):
        """Guarda el universo de un mes para uso futuro"""
        try:
            import json

            self.conn.execute(
                "INSERT OR REPLACE INTO monthly_universe_cache (year_month, tickers, created_at) VALUES (?, ?, ?)",
                (
                    year_month,
                    json.dumps(tickers),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving monthly cache: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # PERF TAREA 1.2: Batch query — carga N tickers en 1 sola query SQL
    # ──────────────────────────────────────────────────────────────────────────
    def get_ohlcv_batch(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        offline: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        """
        Carga datos OHLCV de múltiples tickers en UNA sola query SQL.
        Reemplaza el patrón de 800 queries separadas (una por ticker) con
        un único SELECT ... WHERE ticker IN (...), eliminando lock contention
        y el overhead de 800 roundtrips a SQLite.

        Estrategia de 2 capas:
          1. Parquet / Pickle  → los que están en disco se cargan sin tocar SQLite
          2. SQLite batch      → el resto en una sola query

        Returns: dict {ticker: DataFrame} con índice DatetimeIndex y
                 columnas Open/High/Low/Close/Volume (+ métricas precalculadas).
        """
        if isinstance(start_date, datetime):
            start_date = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, datetime):
            end_date = end_date.strftime("%Y-%m-%d")

        result: Dict[str, pd.DataFrame] = {}
        missing_from_disk: List[str] = []

        # ── Capa 1: Parquet (nuevo) o Pickle (legado) ──────────────────────
        for ticker in tickers:
            parquet_path = self.cache_dir / f"{ticker}.parquet"
            pkl_path = self.cache_dir / f"{ticker}.pkl"

            df_disk = None
            try:
                if parquet_path.exists():
                    df_disk = pd.read_parquet(parquet_path)
                elif pkl_path.exists():
                    import pickle

                    with open(pkl_path, "rb") as f:
                        df_disk = pickle.load(f)
            except Exception as e:
                logger.debug(f"Disk cache read error for {ticker}: {e}")

            if df_disk is not None:
                mask = (df_disk.index >= start_date) & (df_disk.index <= end_date)
                df_filtered = df_disk.loc[mask].copy()
                if not df_filtered.empty:
                    last_date = df_filtered.index[-1].date()
                    req_end = pd.to_datetime(end_date).date()
                    yesterday = (datetime.now() - timedelta(days=1)).date()
                    if offline or last_date >= req_end or last_date >= yesterday:
                        result[ticker] = df_filtered
                        continue

            missing_from_disk.append(ticker)

        if not missing_from_disk:
            return result

        # ── Capa 2: SQLite — 1 sola query para todos los tickers restantes ─
        placeholders = ",".join(["?"] * len(missing_from_disk))
        query = f"""
            SELECT ticker, date, open, high, low, close, volume,
                   dollar_volume, rolling_dollar_vol_20,
                   sma20, sma50, sma100, sma200, adr_pct_20
            FROM ohlcv_cache
            WHERE ticker IN ({placeholders})
              AND date BETWEEN ? AND ?
            ORDER BY ticker, date
        """
        params = missing_from_disk + [start_date, end_date]

        try:
            with self.lock:
                df_all = pd.read_sql_query(query, self.conn, params=params)
        except Exception as e:
            logger.error(f"Batch query error: {e}")
            df_all = pd.DataFrame()

        if df_all.empty:
            return result

        df_all["date"] = pd.to_datetime(df_all["date"], format="mixed")

        for ticker, grp in df_all.groupby("ticker"):
            grp = grp.drop(columns="ticker").set_index("date")
            grp.rename(
                columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                },
                inplace=True,
            )
            result[ticker] = grp

        logger.debug(
            f"Batch load: {len(result)}/{len(tickers)} tickers "
            f"({len(result) - len(missing_from_disk)} from disk, "
            f"{len(df_all['ticker'].unique()) if not df_all.empty else 0} from SQLite)"
        )
        return result

    def get_ohlcv(self, ticker, start_date, end_date, offline=False):
        """
        Obtiene datos OHLCV con todas las métricas calculadas, usa cache o descarga.
        Prioriza archivos Parquet > Pickle > SQLite por velocidad.
        """
        if isinstance(start_date, datetime):
            start_date = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, datetime):
            end_date = end_date.strftime("%Y-%m-%d")

        # ── NIVEL 1: FAST CACHE — Parquet (nuevo) o Pickle (legado) ─────────
        parquet_path = self.cache_dir / f"{ticker}.parquet"
        pkl_path = self.cache_dir / f"{ticker}.pkl"

        for cache_path, reader in [
            (parquet_path, lambda p: pd.read_parquet(p)),
            (pkl_path, lambda p: __import__("pickle").loads(open(p, "rb").read())),
        ]:
            if not cache_path.exists():
                continue
            try:
                df = reader(cache_path)
                mask = (df.index >= start_date) & (df.index <= end_date)
                df_filtered = df.loc[mask].copy()
                if not df_filtered.empty:
                    last_date = df_filtered.index[-1].date()
                    req_end = pd.to_datetime(end_date).date()
                    yesterday = (datetime.now() - timedelta(days=1)).date()
                    if offline or last_date >= req_end or last_date >= yesterday:
                        return df_filtered
            except Exception as e:
                logger.debug(
                    f"Cache read error ({cache_path.suffix}) for {ticker}: {e}"
                )

        # ── NIVEL 2: BASE CACHE (SQLITE) ─────────────────────────────────────
        try:
            with self.lock:
                cursor = self.conn.execute(
                    """
                    SELECT date, open, high, low, close, volume,
                           dollar_volume, rolling_dollar_vol_20,
                           sma20, sma50, sma100, sma200, adr_pct_20
                    FROM ohlcv_cache
                    WHERE ticker = ? AND date BETWEEN ? AND ?
                    ORDER BY date
                """,
                    (ticker, start_date, end_date),
                )
                cached = cursor.fetchall()
        except Exception as e:
            logger.error(f"Error reading from cache for {ticker}: {e}")
            cached = []

        if cached:
            df = pd.DataFrame(
                cached,
                columns=[
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "dollar_volume",
                    "rolling_dollar_vol_20",
                    "sma20",
                    "sma50",
                    "sma100",
                    "sma200",
                    "adr_pct_20",
                ],
            )
            df["date"] = pd.to_datetime(df["date"], format="mixed")
            df.set_index("date", inplace=True)
            df.rename(
                columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                },
                inplace=True,
            )

            if offline:
                return df

            if not df.empty:
                last_date = df.index[-1].date()
                yesterday = (datetime.now() - timedelta(days=1)).date()
                req_end = pd.to_datetime(end_date).date()
                if last_date >= req_end or last_date >= yesterday:
                    return df
        elif offline:
            return None

        # ── NIVEL 3: DESCARGA ─────────────────────────────────────────────────
        logger.info(
            f"Downloading {ticker} data from {start_date} to {end_date} using {DATA_SOURCE}..."
        )
        try:
            if DATA_SOURCE == "openbb":
                from openbb import obb

                result = obb.equity.price.historical(
                    symbol=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    interval="1d",
                    provider=OPENBB_PROVIDER,
                )

                if result and hasattr(result, "to_df"):
                    df = result.to_df()
                    if df.empty:
                        return None
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)
                    column_mapping = {
                        "open": "Open",
                        "high": "High",
                        "low": "Low",
                        "close": "Close",
                        "volume": "Volume",
                    }
                    for old_col, new_col in column_mapping.items():
                        if old_col in df.columns:
                            df.rename(columns={old_col: new_col}, inplace=True)
                else:
                    return None
            else:
                df = yf.Ticker(ticker).history(
                    start=start_date,
                    end=end_date,
                    auto_adjust=True,
                )
                
                # yf.Ticker.history returns timezone-aware index, remove timezone for SQLite
                if not df.empty and getattr(df.index, 'tz', None) is not None:
                    df.index = df.index.tz_localize(None)

            if df.empty:
                return None

            # ── [FIX] Tickers con historia insuficiente ─────────────────────
            # Si el ticker tiene pocos datos (ej: IPO reciente), lo guardamos
            # igual en Parquet. En la próxima corrida, get_ohlcv lo leerá de disco,
            # verá que no llega a la fecha requerida (o que sigue teniendo pocos días)
            # y el engine lo rechazará SIN intentar descargar de nuevo.
            min_required_days = 200 # Umbral típico para indicadores (SMA200)
            if len(df) < 10: # Si es extremadamente corto (error de data o muy nuevo)
                 logger.warning(f"Ticker {ticker} tiene historia mínima ({len(df)} días). Guardando para evitar re-descarga.")

            # ── [FIX] Isolar ticker en DataFrame multi-columna de yfinance ────
            if isinstance(df.columns, pd.MultiIndex):
                # Caso ideal: yfinance devuelve niveles [Price, Ticker]
                if "Ticker" in df.columns.names:
                    try:
                        df = df.xs(ticker.upper(), axis=1, level="Ticker")
                    except Exception:
                        # Si no está el ticker exacto, intentar con el primero
                        # pero SOLO si estamos seguros de que es el que pedimos
                        if ticker.upper() in df.columns.get_level_values("Ticker"):
                            df = df.loc[:, (slice(None), ticker.upper())]
                            df.columns = df.columns.droplevel("Ticker")
                
                # Si sigue siendo MultiIndex, intentar aplanarlo buscando el ticker
                if isinstance(df.columns, pd.MultiIndex):
                    try:
                        # Si yfinance devolvió múltiples tickers, buscamos el nuestro
                        if ticker.upper() in df.columns:
                            df = df[ticker.upper()]
                        else:
                            # Fallback: droplevel solo si el resultado tiene las columnas correctas
                            # y no hay ambigüedad (solo un ticker)
                            unique_tickers = df.columns.get_level_values(1).unique()
                            if len(unique_tickers) == 1:
                                df.columns = df.columns.droplevel(1)
                            else:
                                logger.error(f"Ambiguity in yfinance data for {ticker}: {unique_tickers}")
                                return None
                    except: pass

            # Asegurar que no hay columnas duplicadas y nombres limpios
            df = df.loc[:, ~df.columns.duplicated()]
            if not all(c in df.columns for c in ["Open", "High", "Low", "Close", "Volume"]):
                # Intentar mapeo de minúsculas si es necesario
                df.rename(columns={c: c.capitalize() for c in df.columns}, inplace=True)
            
            # Verificación final: ¿tenemos escalares en las filas?
            # Si 'Close' sigue siendo un DF o tiene duplicados, fallar para no corromper DB
            if isinstance(df["Close"], pd.DataFrame):
                logger.error(f"Data corruption risk for {ticker}: Close is still a DataFrame")
                return None

            # ── Deduplicate dates at source (root cause fix for SPY/VIX dupes) ──
            if df.index.duplicated().any():
                dupe_count = df.index.duplicated().sum()
                logger.debug(
                    f"Deduplicating {ticker}: {dupe_count} duplicate dates removed (keeping last)"
                )
                df = df[~df.index.duplicated(keep="last")]

            close_s = df["Close"]
            volume_s = df["Volume"]
            if isinstance(close_s, pd.DataFrame):
                close_s = close_s.iloc[:, 0]
            if isinstance(volume_s, pd.DataFrame):
                volume_s = volume_s.iloc[:, 0]

            df["dollar_volume"] = close_s * volume_s
            df["rolling_dollar_vol_20"] = (
                df["dollar_volume"].rolling(window=20, min_periods=1).mean()
            )
            df['sma20'] = close_s.rolling(window=20).mean()
            df['sma50'] = close_s.rolling(window=50).mean()
            df['sma100'] = close_s.rolling(window=100).mean()
            df['sma200'] = close_s.rolling(window=200).mean()
            
            high_s = df["High"]
            low_s = df["Low"]
            if isinstance(high_s, pd.DataFrame): high_s = high_s.iloc[:, 0]
            if isinstance(low_s, pd.DataFrame): low_s = low_s.iloc[:, 0]
            
            df['daily_range_pct'] = ((high_s - low_s) / low_s) * 100
            df['adr_pct_20'] = df['daily_range_pct'].rolling(window=20).mean()

            # ── TAREA 1.1: BULK INSERT — reemplaza row-by-row (10-50x más rápido) ──
            records = []
            for date, row in df.iterrows():
                try:
                    open_val = (
                        row["Open"].iloc[0]
                        if hasattr(row["Open"], "iloc")
                        else row["Open"]
                    )
                    high_val = (
                        row["High"].iloc[0]
                        if hasattr(row["High"], "iloc")
                        else row["High"]
                    )
                    low_val = (
                        row["Low"].iloc[0]
                        if hasattr(row["Low"], "iloc")
                        else row["Low"]
                    )
                    close_val = (
                        row["Close"].iloc[0]
                        if hasattr(row["Close"], "iloc")
                        else row["Close"]
                    )
                    vol_val = (
                        row["Volume"].iloc[0]
                        if hasattr(row["Volume"], "iloc")
                        else row["Volume"]
                    )
                    dv_val = (
                        row["dollar_volume"].iloc[0]
                        if hasattr(row["dollar_volume"], "iloc")
                        else row["dollar_volume"]
                    )
                    rv_raw = row["rolling_dollar_vol_20"]
                    rv_val = rv_raw.iloc[0] if hasattr(rv_raw, "iloc") else rv_raw
                    
                    sma20 = row["sma20"]
                    sma50 = row["sma50"]
                    sma100 = row["sma100"]
                    sma200 = row["sma200"]
                    adr20 = row["adr_pct_20"]
                    
                    sma20 = sma20.iloc[0] if hasattr(sma20, "iloc") else sma20
                    sma50 = sma50.iloc[0] if hasattr(sma50, "iloc") else sma50
                    sma100 = sma100.iloc[0] if hasattr(sma100, "iloc") else sma100
                    sma200 = sma200.iloc[0] if hasattr(sma200, "iloc") else sma200
                    adr20 = adr20.iloc[0] if hasattr(adr20, "iloc") else adr20

                    records.append(
                        (
                            ticker,
                            date.strftime("%Y-%m-%d"),
                            float(open_val),
                            float(high_val),
                            float(low_val),
                            float(close_val),
                            int(vol_val),
                            float(dv_val),
                            float(rv_val) if pd.notna(rv_val) else None,
                            float(sma20) if pd.notna(sma20) else None,
                            float(sma50) if pd.notna(sma50) else None,
                            float(sma100) if pd.notna(sma100) else None,
                            float(sma200) if pd.notna(sma200) else None,
                            float(adr20) if pd.notna(adr20) else None,
                        )
                    )
                except Exception as e:
                    logger.debug(f"Row prep error for {ticker} on {date}: {e}")
                    continue

            with self.lock:
                self.conn.executemany(
                    """
                    INSERT OR REPLACE INTO ohlcv_cache
                    (ticker, date, open, high, low, close, volume, dollar_volume, rolling_dollar_vol_20, sma20, sma50, sma100, sma200, adr_pct_20)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    records,
                )
                self.conn.commit()

            # ── Guardar en Parquet (reemplaza Pickle) para futuras lecturas ──
            try:
                df.index.name = "date"
                
                # [MERGE] Tarea 1.1b: Mergear con data existente en disco
                if parquet_path.exists():
                    try:
                        old_df = pd.read_parquet(parquet_path)
                        # Concatenar y eliminar duplicados (quedarse con lo más nuevo)
                        combined = pd.concat([old_df, df])
                        # Eliminar duplicados por índice (date)
                        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
                        df = combined
                    except Exception as e:
                        logger.warning(f"Failed to merge existing parquet for {ticker}: {e}")

                df.to_parquet(parquet_path, engine="pyarrow", compression="snappy")
                # Si existe el .pkl legado, borrarlo para liberar espacio
                if pkl_path.exists():
                    pkl_path.unlink()
                    logger.debug(f"Migrated {ticker}: pkl → parquet")
            except Exception as e:
                # Parquet puede fallar si pyarrow no está instalado; fallback a pickle
                logger.debug(
                    f"Parquet write failed for {ticker}, falling back to pickle: {e}"
                )
                try:
                    import pickle

                    with open(pkl_path, "wb") as f:
                        pickle.dump(df, f)
                except Exception as e2:
                    logger.debug(f"Pickle fallback also failed for {ticker}: {e2}")

            df.index.name = "date"
            return df

        except Exception as e:
            logger.error(f"Error downloading data for {ticker}: {e}")
            return None

    def close(self):
        self.conn.close()
