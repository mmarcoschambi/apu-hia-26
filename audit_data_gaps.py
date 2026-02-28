import sys
import argparse
import pandas as pd
import sqlite3
from pathlib import Path
from tqdm import tqdm

def get_db_connection():
    db_path = Path('data/ticker_cache.db')
    if not db_path.exists():
        print("❌ No se encontró la base de datos data/ticker_cache.db")
        sys.exit(1)
    return sqlite3.connect(db_path)

def get_market_calendar(conn, year):
    """Obtiene los días que SPY operó ese año (Patrón Oro)"""
    query = """
        SELECT date FROM ohlcv_cache 
        WHERE ticker = 'SPY' 
        AND strftime('%Y', date) = ?
        ORDER BY date
    """
    cursor = conn.execute(query, (str(year),))
    dates = [row[0] for row in cursor.fetchall()]
    return set(dates)

def audit_gaps(year):
    print(f"🕵️  AUDITORÍA DE GAPS PARA EL AÑO {year}")
    
    conn = get_db_connection()
    
    # 1. Cargar Calendario Maestro (SPY)
    print("📅 Cargando calendario de mercado (SPY)...")
    spy_days = get_market_calendar(conn, year)
    
    if not spy_days:
        print(f"❌ Error: No hay datos de SPY para {year}. Ejecuta 'python3 populate_market_data.py' primero.")
        return

    print(f"✅ SPY operó {len(spy_days)} días en {year}. Usando esto como referencia.")

    # 2. Obtener lista de todos los tickers
    print("👥 Obteniendo lista de tickers...")
    cursor = conn.execute("SELECT DISTINCT ticker FROM ohlcv_cache WHERE ticker != 'SPY'")
    tickers = [row[0] for row in cursor.fetchall()]
    
    gaps_report = []
    
    # 3. Analizar Ticker por Ticker
    print(f"🚀 Analizando {len(tickers)} tickers en busca de gaps REALES...")
    
    for ticker in tqdm(tickers):
        # Obtener días del ticker en ese año
        query = """
            SELECT date FROM ohlcv_cache 
            WHERE ticker = ? 
            AND strftime('%Y', date) = ?
        """
        cursor = conn.execute(query, (ticker, str(year)))
        ticker_days = set([row[0] for row in cursor.fetchall()])
        
        if not ticker_days:
            # Caso: Ticker no tiene data ese año (quizás IPO posterior o Delisted)
            continue
            
        # Calcular Gaps: Días que SPY operó pero el Ticker NO
        missing_days = spy_days - ticker_days
        
        # Lógica inteligente: Ignorar gaps antes de la IPO o después del deslistado
        # Si la acción empezó a cotizar en Junio, Enero-Mayo no son gaps reales de data, es que no existía.
        if missing_days:
            min_ticker_date = min(ticker_days)
            max_ticker_date = max(ticker_days)
            
            real_gaps = []
            for day in missing_days:
                # Solo nos importan gaps DENTRO del periodo de vida de la acción en ese año
                # Esto filtra fines de semana (ya filtrados por SPY) y tiempos pre-IPO/post-delisting
                if min_ticker_date < day < max_ticker_date:
                    real_gaps.append(day)
            
            if real_gaps:
                for gap_date in sorted(real_gaps):
                    gaps_report.append({
                        'Ticker': ticker,
                        'Missing_Date': gap_date,
                        'Gap_Type': 'Internal' # Gap en medio de la data (Peligroso)
                    })

    conn.close()
    
    # 4. Guardar Reporte
    if gaps_report:
        df_gaps = pd.DataFrame(gaps_report)
        filename = f"gaps_report_{year}.csv"
        
        # Ordenar por ticker y fecha
        df_gaps = df_gaps.sort_values(['Ticker', 'Missing_Date'])
        
        df_gaps.to_csv(filename, index=False)
        
        print("\n" + "="*60)
        print(f"❌ SE DETECTARON GAPS INTERNOS.")
        print(f"📄 Reporte guardado en: {filename}")
        print(f"📊 Total de días perdidos encontrados: {len(df_gaps)}")
        print(f"🤕 Tickers afectados: {df_gaps['Ticker'].nunique()}")
        print("="*60)
        print("\nPrimeras 5 líneas del reporte:")
        print(df_gaps.head().to_string(index=False))
    else:
        print("\n✨ ¡INCREÍBLE! No se detectaron gaps internos reales contra SPY.")
        print("   Tu base de datos es sólida como una roca para este año.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Auditar Gaps de Datos vs SPY')
    parser.add_argument('--year', type=int, default=2025, help='Año a auditar')
    args = parser.parse_args()
    
    audit_gaps(args.year)