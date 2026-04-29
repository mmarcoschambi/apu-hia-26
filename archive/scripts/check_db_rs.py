import sqlite3
import pandas as pd

def check_rs_rankings():
    conn = sqlite3.connect('data/ticker_cache.db')
    ticker = 'TSLA'
    date = '2020-12-30'
    
    print(f"--- Buscando RS para {ticker} el {date} ---")
    
    # Ver si la tabla existe
    try:
        res = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_rs_rankings'").fetchone()
        if not res:
            print("ERROR: La tabla daily_rs_rankings NO existe en ticker_cache.db")
            return
        
        # Ver columnas
        cols = conn.execute("PRAGMA table_info(daily_rs_rankings)").fetchall()
        print(f"Columnas: {[c[1] for c in cols]}")
        
        # Buscar dato
        query = "SELECT * FROM daily_rs_rankings WHERE ticker=? AND date=?"
        row = conn.execute(query, (ticker, date)).fetchone()
        if row:
            print(f"Fila encontrada: {row}")
        else:
            print("No se encontró fila para esa combinación ticker/fecha.")
            
            # Ver fechas disponibles
            dates = conn.execute("SELECT DISTINCT date FROM daily_rs_rankings ORDER BY date DESC LIMIT 5").fetchall()
            print(f"Últimas 5 fechas en la tabla: {dates}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_rs_rankings()
