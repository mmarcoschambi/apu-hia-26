#!/usr/bin/env python3
"""
AUDITORÍA QUIRÚRGICA DE HUECOS INTRADAY
=======================================
Detecta faltantes de datos en la base de datos intradía (5 minutos),
respetando estrictamente el calendario de mercado NYSE (Feriados, Fines de Semana).

Características:
1. Usa 'pandas_market_calendars' para precisión absoluta de días hábiles.
2. Analiza la base de datos SQLite 'data/intraday_cache.db'.
3. Genera reporte CSV 'gaps_report.csv'.
4. Genera script de reparación 'fix_intraday_gaps.sh'.

Uso:
    python3 audit_intraday_gaps.py
"""

import sqlite3
import pandas as pd
import pandas_market_calendars as mcal
from datetime import datetime, time, timedelta
import argparse
from tqdm import tqdm
import os

# Configuración
DB_PATH = 'data/intraday_cache.db'
OUTPUT_CSV = 'gaps_report.csv'
FIX_SCRIPT = 'fix_intraday_gaps.sh'

def get_market_schedule(start_date, end_date):
    """Obtiene días de trading válidos usando calendario NYSE"""
    nyse = mcal.get_calendar('NYSE')
    # Añadimos un buffer de días por si acaso
    schedule = nyse.schedule(start_date=start_date, end_date=end_date)
    return schedule

def analyze_ticker_gaps(conn, ticker, nyse_schedule):
    """Busca días faltantes para un ticker específico"""
    
    # 1. Obtener todas las fechas DISPONIBLES para este ticker (solo la parte de fecha)
    # Optimizamos la query para solo traer fechas únicas, es muy rápido en SQLite.
    query = """
        SELECT DISTINCT date(datetime) as day 
        FROM intraday_5m 
        WHERE ticker = ? 
        ORDER BY day
    """
    existing_dates_df = pd.read_sql_query(query, conn, params=(ticker,))
    
    if existing_dates_df.empty:
        return []

    existing_dates = pd.to_datetime(existing_dates_df['day'])
    
    min_date = existing_dates.min()
    max_date = existing_dates.max()
    
    # 2. Filtrar el calendario de mercado para el rango de vida de este ticker
    # Solo nos importa lo que DEBERÍA existir entre su primer y último dato registrado.
    # (No reportamos 'missing data' antes de que la empresa existiera o empezáramos a trackearla)
    expected_schedule = nyse_schedule.loc[min_date:max_date]
    expected_days = expected_schedule.index
    
    # 3. Encontrar la diferencia (Días esperados - Días existentes)
    # Convertimos ambos a set de fechas normalizadas para restar rápido
    expected_set = set(expected_days.date)
    existing_set = set(existing_dates.dt.date)
    
    missing_dates = sorted(list(expected_set - existing_set))
    
    gaps = []
    if not missing_dates:
        return gaps

    # Agrupar fechas consecutivas en rangos para que el reporte sea legible
    if not missing_dates:
        return []
        
    current_start = missing_dates[0]
    current_end = missing_dates[0]
    
    for next_date in missing_dates[1:]:
        if next_date <= current_end + timedelta(days=3): # Tolerancia a fin de semana para agrupar
            current_end = next_date
        else:
            gaps.append((current_start, current_end))
            current_start = next_date
            current_end = next_date
    gaps.append((current_start, current_end))
    
    return gaps

def main():
    print("🚀 AUDITOR DE GAPS INTRADAY (NYSE AWARE)")
    print(f"   Base de Datos: {DB_PATH}")
    print("="*60)
    
    if not os.path.exists(DB_PATH):
        print("❌ Error: No existe la base de datos.")
        return

    # Conexión optimizada para lectura
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA mmap_size = 30000000000;")
    
    # Obtener lista de tickers
    print("📥 Leyendo lista de tickers...")
    tickers_df = pd.read_sql_query("SELECT DISTINCT ticker FROM intraday_5m ORDER BY ticker", conn)
    tickers = tickers_df['ticker'].tolist()
    print(f"   Tickers encontrados: {len(tickers)}")
    
    if not tickers:
        print("   Nada que auditar.")
        return

    # Obtener rango global para descargar el calendario una sola vez
    print("📅 Cargando calendario NYSE...")
    dates_global = pd.read_sql_query("SELECT min(datetime), max(datetime) FROM intraday_5m", conn)
    min_glob = pd.to_datetime(dates_global.iloc[0,0]).date()
    max_glob = pd.to_datetime(dates_global.iloc[0,1]).date()
    
    # Descargar calendario con un buffer
    schedule = get_market_schedule(min_glob, max_glob)
    print(f"   Calendario cargado: {len(schedule)} días de trading válidos.")
    
    # Analizar
    all_gaps = []
    tickers_with_problems = set()
    
    print("\n🕵️  Analizando huecos (ignorando feriados)...")
    for ticker in tqdm(tickers):
        gaps = analyze_ticker_gaps(conn, ticker, schedule)
        for start, end in gaps:
            days_count = (end - start).days + 1
            all_gaps.append({
                'Ticker': ticker,
                'Start Date': start,
                'End Date': end,
                'Days Missing': days_count
            })
            tickers_with_problems.add(ticker)
    
    conn.close()
    
    # Reporte
    print("\n" + "="*60)
    if not all_gaps:
        print("✅ FELICIDADES: No se encontraron huecos en los días de trading.")
        print("   Tu data está perfecta según el calendario NYSE.")
    else:
        df_gaps = pd.DataFrame(all_gaps)
        df_gaps.to_csv(OUTPUT_CSV, index=False)
        
        print(f"⚠️  SE ENCONTRARON PROBLEMAS:")
        print(f"   Tickers afectados: {len(tickers_with_problems)}")
        print(f"   Total de huecos:   {len(df_gaps)}")
        print(f"   Reporte guardado en: {OUTPUT_CSV}")
        
        # Generar script de fix
        print("\n🔧 Generando script de reparación...")
        with open(FIX_SCRIPT, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Script de reparación de huecos intraday\n")
            f.write("echo 'Iniciando reparación de data intraday...\n'")
            # Agrupar en una sola llamada para eficiencia, o varias si son muchos
            tickers_str = ",".join(list(tickers_with_problems))
            # Si son muchos, dividimos en chunks para no romper la línea de comandos
            chunk_size = 50
            problem_list = list(tickers_with_problems)
            for i in range(0, len(problem_list), chunk_size):
                chunk = problem_list[i:i+chunk_size]
                chunk_str = ",".join(chunk)
                f.write(f"python3 cache_intraday_data.py --tickers {chunk_str} --days 60 --replace\n")
        
        print(f"   Script creado: {FIX_SCRIPT}")
        print(f"   Ejecuta: bash {FIX_SCRIPT}")

if __name__ == "__main__":
    main()
