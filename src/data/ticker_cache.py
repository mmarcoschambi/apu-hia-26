import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
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
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.setup_database()
    
    def setup_database(self):
        """Crea tablas si no existen"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS universe (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                exchange TEXT,
                sector TEXT,
                industry TEXT,
                last_updated DATE
            )
        ''')
        
        self.conn.execute('''
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
                PRIMARY KEY (ticker, date)
            )
        ''')
        
        # Nueva tabla para guardar el Top 500 de cada mes y no recalcularlo
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS monthly_universe_cache (
                year_month TEXT PRIMARY KEY,  -- Formato 'YYYY-MM'
                tickers TEXT,                 -- JSON list
                created_at DATE
            )
        ''')
        self.conn.commit()
    
    def update_universe(self, force=False):
        """
        Actualiza lista de tickers (correr 1 vez por semana)
        """
        cursor = self.conn.execute(
            "SELECT last_updated FROM universe LIMIT 1"
        )
        row = cursor.fetchone()
        
        # Si la última actualización fue hace menos de 7 días, skip
        if row and not force:
            try:
                last_update = datetime.strptime(row[0], '%Y-%m-%d')
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
            logger.warning(f"Error fetching tickers from yahoo_fin: {e}. Trying fallback...")
            
            # Fallback to Wikipedia (more reliable)
            try:
                import requests
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                
                # S&P 500
                url_sp500 = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
                r_sp500 = requests.get(url_sp500, headers=headers)
                sp500 = pd.read_html(r_sp500.text)[0]
                all_tickers.update(sp500['Symbol'].tolist())
                
                # Nasdaq 100
                url_ndx = 'https://en.wikipedia.org/wiki/Nasdaq-100'
                r_ndx = requests.get(url_ndx, headers=headers)
                # Table index might vary, try to find it
                tables = pd.read_html(r_ndx.text)
                for table in tables:
                    if 'Ticker' in table.columns:
                        all_tickers.update(table['Ticker'].tolist())
                        break
                
                logger.info(f"Fetched {len(all_tickers)} tickers from Wikipedia fallback")
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return
        
        # Guardar en DB
        count = 0
        for ticker in all_tickers:
            if not ticker or not isinstance(ticker, str):
                continue
            # Clean ticker
            ticker = ticker.replace('.', '-')
            try:
                self.conn.execute('''
                    INSERT OR IGNORE INTO universe (ticker, last_updated)
                    VALUES (?, ?)
                ''', (
                    ticker,
                    datetime.now().strftime('%Y-%m-%d')
                ))
                count += 1
            except Exception as e:
                logger.debug(f"Error inserting ticker {ticker}: {e}")
        
        self.conn.commit()
        logger.info(f"Universe updated: {len(all_tickers)} tickers total. Added {count} new entries.")

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
            
            ticker = ticker.strip().upper().replace('.', '-')
            
            # Check if exists
            cursor = self.conn.execute("SELECT 1 FROM universe WHERE ticker = ?", (ticker,))
            if not cursor.fetchone():
                try:
                    self.conn.execute('''
                        INSERT OR IGNORE INTO universe (ticker, last_updated)
                        VALUES (?, ?)
                    ''', (
                        ticker,
                        datetime.now().strftime('%Y-%m-%d')
                    ))
                    new_tickers.append(ticker)
                    count += 1
                except Exception as e:
                    logger.debug(f"Error inserting ticker {ticker}: {e}")
        
        self.conn.commit()
        
        if count > 0:
            logger.info(f"Added {count} new tickers to universe: {new_tickers}")
            # Optional: Update detailed info for new tickers in background
            # For now, we won't block execution for this
            
        return count

    def update_ticker_info(self, ticker):
        """Actualiza info detallada de un ticker específico"""
        try:
            info = yf.Ticker(ticker).info
            self.conn.execute('''
                UPDATE universe 
                SET name = ?, exchange = ?, sector = ?, industry = ?, last_updated = ?
                WHERE ticker = ?
            ''', (
                info.get('longName', ''),
                info.get('exchange', ''),
                info.get('sector', ''),
                info.get('industry', ''),
                datetime.now().strftime('%Y-%m-%d'),
                ticker
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating info for {ticker}: {e}")
            return False
    
    def get_active_tickers(self, filters=None, sort_by='alphabetical', limit=None, date_filter=None, min_price=5.0, min_rolling_dollar_vol=15000000):
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
        if sort_by == 'liquidity':
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
                if 'sector' in filters:
                    query += " AND u.sector = ?"
                    params.append(filters['sector'])
                if 'exchange' in filters:
                    if isinstance(filters['exchange'], (list, tuple)):
                        placeholders = ','.join(['?' for _ in filters['exchange']])
                        query += f" AND u.exchange IN ({placeholders})"
                        params.extend(filters['exchange'])
                    else:
                        query += " AND u.exchange = ?"
                        params.append(filters['exchange'])

            if date_filter:
                # Si estamos filtrando por fecha, no necesitamos GROUP BY ni HAVING
                if filters:
                    if 'sector' in filters:
                        query += " AND u.sector = ?"
                        params.append(filters['sector'])
                    if 'exchange' in filters:
                        if isinstance(filters['exchange'], (list, tuple)):
                            placeholders = ','.join(['?' for _ in filters['exchange']])
                            query += f" AND u.exchange IN ({placeholders})"
                            params.extend(filters['exchange'])
                        else:
                            query += " AND u.exchange = ?"
                            params.append(filters['exchange'])
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
                (year_month,)
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
                (year_month, json.dumps(tickers), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving monthly cache: {e}")

    def get_ohlcv(self, ticker, start_date, end_date, offline=False):
            query = "SELECT ticker FROM universe WHERE 1=1"
            params = []

            if filters:
                if 'sector' in filters:
                    query += " AND sector = ?"
                    params.append(filters['sector'])
                if 'exchange' in filters:
                    if isinstance(filters['exchange'], (list, tuple)):
                        placeholders = ','.join(['?' for _ in filters['exchange']])
                        query += f" AND exchange IN ({placeholders})"
                        params.extend(filters['exchange'])
                    else:
                        query += " AND exchange = ?"
                        params.append(filters['exchange'])

            if sort_by == 'random':
                query += " ORDER BY RANDOM()"
            else:
                query += " ORDER BY ticker"

            if limit:
                query += f" LIMIT {limit}"

            cursor = self.conn.execute(query, params)
            return [row[0] for row in cursor.fetchall()]
    
    def get_ohlcv(self, ticker, start_date, end_date, offline=False):
        """
        Obtiene datos OHLCV con todas las métricas calculadas, usa cache o descarga.
        If offline=True, never downloads, returns what is available.
        
        Returns DataFrame with columns:
        - OHLCV básico: Open, High, Low, Close, Volume
        - Métricas calculadas: dollar_volume, rolling_dollar_vol_20, avg_volume_20
        - ADR: adr_14, adr_pct_14
        - SMAs: sma_50, sma_200
        - Trend flags: price_above_sma50, price_above_sma200, sma50_above_sma200, trend_aligned
        - market_cap (si disponible)
        """
        if isinstance(start_date, datetime):
            start_date = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, datetime):
            end_date = end_date.strftime('%Y-%m-%d')

        # Primero buscar en cache con TODAS las columnas calculadas
        cursor = self.conn.execute('''
            SELECT date, open, high, low, close, volume,
                   dollar_volume, rolling_dollar_vol_20, market_cap, avg_volume_20,
                   adr_14, adr_pct_14, sma_50, sma_200,
                   price_above_sma50, price_above_sma200, sma50_above_sma200, trend_aligned
            FROM ohlcv_cache
            WHERE ticker = ? AND date BETWEEN ? AND ?
            ORDER BY date
        ''', (ticker, start_date, end_date))
        
        cached = cursor.fetchall()
        
        # Si tenemos datos en cache
        if cached:
            df = pd.DataFrame(
                cached, 
                columns=['date', 'open', 'high', 'low', 'close', 'volume',
                        'dollar_volume', 'rolling_dollar_vol_20', 'market_cap', 'avg_volume_20',
                        'adr_14', 'adr_pct_14', 'sma_50', 'sma_200',
                        'price_above_sma50', 'price_above_sma200', 'sma50_above_sma200', 'trend_aligned']
            )
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # Ensure proper capitalization for consistency (OHLCV básico)
            df.rename(columns={
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }, inplace=True)
            
            if offline:
                return df
            
            # Si no es offline, verificamos si necesitamos actualizar
            last_date = df.index[-1].date()
            yesterday = (datetime.now() - timedelta(days=1)).date()
            
            # Si el rango solicitado termina mucho después de lo que tenemos, descargar
            if last_date >= pd.to_datetime(end_date).date() or last_date >= yesterday:
                 return df
        elif offline:
            return None
        
        # Descargar usando la fuente configurada
        logger.info(f"Downloading {ticker} data from {start_date} to {end_date} using {DATA_SOURCE}...")
        try:
            if DATA_SOURCE == "openbb":
                from openbb import obb
                result = obb.equity.price.historical(
                    symbol=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    interval="1d",
                    provider=OPENBB_PROVIDER
                )
                
                if result and hasattr(result, 'to_df'):
                    df = result.to_df()
                    if df.empty:
                        return None
                    
                    # Ensure DatetimeIndex
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)
                    
                    # Normalize column names
                    column_mapping = {
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume'
                    }
                    for old_col, new_col in column_mapping.items():
                        if old_col in df.columns:
                            df.rename(columns={old_col: new_col}, inplace=True)
                else:
                    return None
            else:
                df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            
            if df.empty:
                return None
            
            # Fix for yfinance returning MultiIndex columns
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    df.columns = df.columns.get_level_values(0)
                except:
                    pass

            # Calcular dollar_volume y rolling_dollar_vol_20
            df['dollar_volume'] = df['Close'] * df['Volume']
            df['rolling_dollar_vol_20'] = df['dollar_volume'].rolling(window=20, min_periods=1).mean()

            # Guardar en cache
            for date, row in df.iterrows():
                # Safe extraction handling potential Series or Scalar
                open_val = row['Open'].iloc[0] if hasattr(row['Open'], 'iloc') else row['Open']
                high_val = row['High'].iloc[0] if hasattr(row['High'], 'iloc') else row['High']
                low_val = row['Low'].iloc[0] if hasattr(row['Low'], 'iloc') else row['Low']
                close_val = row['Close'].iloc[0] if hasattr(row['Close'], 'iloc') else row['Close']
                vol_val = row['Volume'].iloc[0] if hasattr(row['Volume'], 'iloc') else row['Volume']
                dollar_vol_val = row['dollar_volume']
                rolling_dollar_vol_val = row['rolling_dollar_vol_20']

                self.conn.execute('''
                    INSERT OR REPLACE INTO ohlcv_cache 
                    (ticker, date, open, high, low, close, volume, dollar_volume, rolling_dollar_vol_20)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ticker,
                    date.strftime('%Y-%m-%d'),
                    float(open_val),
                    float(high_val),
                    float(low_val),
                    float(close_val),
                    int(vol_val),
                    float(dollar_vol_val),
                    float(rolling_dollar_vol_val) if pd.notna(rolling_dollar_vol_val) else None
                ))
            
            self.conn.commit()
            return df
        except Exception as e:
            logger.error(f"Error downloading data for {ticker}: {e}")
            return None
    
    def close(self):
        self.conn.close()
