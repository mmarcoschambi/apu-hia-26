import sqlite3
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"

def main():
    if not DB_PATH.exists():
        print(f"Error: DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    print("Database connected successfully.")
    
    # Query to see count of records per month in 2025 and 2026
    query = """
    SELECT 
        strftime('%Y-%m', date) as month, 
        count(distinct ticker) as unique_tickers,
        count(*) as total_records
    FROM ohlcv_cache
    WHERE date BETWEEN '2025-01-01' AND '2026-06-30'
    GROUP BY month
    ORDER BY month;
    """
    
    try:
        df = pd.read_sql_query(query, conn)
        print("\nRecords per month in ohlcv_cache:")
        print(df.to_string(index=False))
        
        # Check a sample ticker's data in 2025
        print("\nChecking sample SPY data in 2025:")
        spy_df = pd.read_sql_query(
            "SELECT date, close FROM ohlcv_cache WHERE ticker = 'SPY' AND date BETWEEN '2025-01-01' AND '2025-02-15' ORDER BY date",
            conn
        )
        print(spy_df.head(10))
        
    except Exception as e:
        print(f"Error executing query: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
