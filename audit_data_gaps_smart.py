"""
Smart data gaps auditor - filters by liquidity and excludes foreign/OTC tickers
"""
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
        SELECT DISTINCT DATE(date) as day FROM ohlcv_cache 
        WHERE ticker = 'SPY' 
        AND strftime('%Y', date) = ?
        ORDER BY day
    """
    cursor = conn.execute(query, (str(year),))
    dates = [row[0] for row in cursor.fetchall()]
    return set(dates)

def get_liquid_tickers(conn, year, min_avg_volume=100000):
    """
    Obtiene solo tickers líquidos con volumen promedio mínimo
    Excluye: OTC, foreign exchanges, índices
    """
    query = """
        SELECT ticker, AVG(volume) as avg_vol
        FROM ohlcv_cache
        WHERE strftime('%Y', date) = ?
        AND ticker NOT LIKE '%-KS'
        AND ticker NOT LIKE '%-KQ'
        AND ticker NOT LIKE '%-SW'
        AND ticker NOT LIKE '%-HK'
        AND ticker NOT LIKE '%-L'
        AND ticker NOT LIKE '%-TA'
        AND ticker NOT LIKE '%-SR'
        AND ticker NOT LIKE '%-KW'
        AND ticker NOT LIKE '%-%'
        AND ticker NOT LIKE '^%'
        AND ticker NOT LIKE '%.%'
        AND LENGTH(ticker) <= 5
        GROUP BY ticker
        HAVING avg_vol >= ?
        ORDER BY avg_vol DESC
    """
    cursor = conn.execute(query, (str(year), min_avg_volume))
    tickers = [row[0] for row in cursor.fetchall()]
    return tickers

def audit_gaps(year, min_volume=100000, max_gap_pct=5.0):
    """
    Audita gaps solo en tickers líquidos
    
    Args:
        year: Año a auditar
        min_volume: Volumen promedio mínimo
        max_gap_pct: % máximo de gaps permitidos antes de alertar
    """
    print(f"🕵️  AUDITORÍA SMART DE GAPS PARA {year}")
    print(f"📊 Filtros: Volumen ≥ {min_volume:,} | Solo US tickers líquidos")
    
    conn = get_db_connection()
    
    # 1. Cargar Calendario Maestro (SPY)
    print("\n📅 Cargando calendario de mercado (SPY)...")
    spy_days = get_market_calendar(conn, year)
    
    if not spy_days:
        print(f"❌ Error: No hay datos de SPY para {year}.")
        return

    print(f"✅ SPY operó {len(spy_days)} días en {year}")

    # 2. Obtener solo tickers líquidos
    print(f"\n👥 Obteniendo tickers líquidos (volumen ≥ {min_volume:,})...")
    tickers = get_liquid_tickers(conn, year, min_volume)
    
    if not tickers:
        print("❌ No se encontraron tickers con ese volumen mínimo")
        return
    
    print(f"✅ {len(tickers)} tickers líquidos encontrados")
    
    gaps_report = []
    ticker_summary = []
    
    # 3. Analizar gaps
    print(f"\n🚀 Analizando gaps...")
    
    for ticker in tqdm(tickers):
        query = """
            SELECT DISTINCT DATE(date) as day FROM ohlcv_cache 
            WHERE ticker = ? 
            AND strftime('%Y', date) = ?
        """
        cursor = conn.execute(query, (ticker, str(year)))
        ticker_days = set([row[0] for row in cursor.fetchall()])
        
        if not ticker_days:
            continue
            
        # Calcular gaps internos
        missing_days = spy_days - ticker_days
        
        if missing_days:
            min_ticker_date = min(ticker_days)
            max_ticker_date = max(ticker_days)
            
            real_gaps = []
            for day in missing_days:
                if min_ticker_date < day < max_ticker_date:
                    real_gaps.append(day)
            
            if real_gaps:
                gap_pct = len(real_gaps) / len(spy_days) * 100
                
                ticker_summary.append({
                    'Ticker': ticker,
                    'Days_Present': len(ticker_days),
                    'Days_Missing': len(real_gaps),
                    'Gap_Pct': round(gap_pct, 2),
                    'First_Date': min_ticker_date,
                    'Last_Date': max_ticker_date
                })
                
                for gap_date in sorted(real_gaps):
                    gaps_report.append({
                        'Ticker': ticker,
                        'Missing_Date': gap_date,
                        'Gap_Type': 'Internal'
                    })

    conn.close()
    
    # 4. Resultados
    print("\n" + "="*70)
    
    if gaps_report:
        df_gaps = pd.DataFrame(gaps_report)
        df_summary = pd.DataFrame(ticker_summary)
        
        # Filtrar tickers problemáticos (>X% gaps)
        problem_tickers = df_summary[df_summary['Gap_Pct'] > max_gap_pct]
        
        filename = f"gaps_report_{year}_liquid.csv"
        df_gaps.to_csv(filename, index=False)
        
        summary_filename = f"gaps_summary_{year}_liquid.csv"
        df_summary.to_csv(summary_filename, index=False)
        
        print(f"📊 RESUMEN DE GAPS (Tickers Líquidos)")
        print(f"📄 Reporte detallado: {filename}")
        print(f"📄 Resumen por ticker: {summary_filename}")
        print(f"\n   Total días perdidos: {len(df_gaps):,}")
        print(f"   Tickers afectados: {df_summary['Ticker'].nunique()}")
        print(f"   Tickers con >{max_gap_pct}% gaps: {len(problem_tickers)}")
        
        if len(problem_tickers) > 0:
            print(f"\n⚠️  TICKERS PROBLEMÁTICOS (>{max_gap_pct}% gaps):")
            print(problem_tickers.sort_values('Gap_Pct', ascending=False).head(15).to_string(index=False))
        
        print(f"\n✅ TICKERS CON MEJOR COBERTURA:")
        print(df_summary.sort_values('Gap_Pct').head(10).to_string(index=False))
        
    else:
        print("✨ ¡PERFECTO! No se detectaron gaps en tickers líquidos.")
        print("   Tu base de datos es sólida para trading.")
    
    print("="*70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Smart Gap Auditor - Filtra por liquidez')
    parser.add_argument('--year', type=int, default=2025, help='Año a auditar')
    parser.add_argument('--min-volume', type=int, default=100000, 
                       help='Volumen promedio mínimo (default: 100,000)')
    parser.add_argument('--max-gap-pct', type=float, default=5.0,
                       help='% máximo de gaps antes de alertar (default: 5.0)')
    args = parser.parse_args()
    
    audit_gaps(args.year, args.min_volume, args.max_gap_pct)
