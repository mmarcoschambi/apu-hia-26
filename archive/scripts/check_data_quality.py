#!/usr/bin/env python3
"""
CHECK DATA QUALITY - Detector de Splits no ajustados y Crashes
==============================================================
Analiza la base de datos buscando caídas porcentuales sospechosas
que suelen indicar que la data NO está ajustada por splits.

Ejemplo:
- Caída de ~50%  -> Posible Split 2:1 no ajustado
- Caída de ~33%  -> Posible Split 3:2 no ajustado
- Caída de ~90%  -> Posible Split 10:1 no ajustado

Uso:
    python3 check_data_quality.py
"""

import sqlite3
import pandas as pd
import numpy as np
from tqdm import tqdm

DB_PATH = "data/ticker_cache.db"
CRASH_THRESHOLD = -0.25  # Reportar cualquier caída mayor al 25% en un día

def get_tickers(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ticker FROM ohlcv_cache")
    return [row[0] for row in cursor.fetchall()]

def analyze_ticker(conn, ticker):
    query = "SELECT date, close FROM ohlcv_cache WHERE ticker = ? ORDER BY date ASC"
    df = pd.read_sql_query(query, conn, params=(ticker,))
    
    if df.empty or len(df) < 2:
        return []
    
    # Calcular cambio porcentual
    df['pct_change'] = df['close'].pct_change()
    
    # Filtrar caídas grandes
    crashes = df[df['pct_change'] < CRASH_THRESHOLD].copy()
    
    suspicious_events = []
    
    for idx, row in crashes.iterrows():
        pct = row['pct_change']
        date = row['date']
        
        event_type = "📉 Crash Fuerte"
        
        # Detección heurística de Splits comunes
        if -0.52 < pct < -0.48:
            event_type = "✂️  POSIBLE SPLIT 2:1 (-50%)"
        elif -0.35 < pct < -0.31:
            event_type = "✂️  POSIBLE SPLIT 3:2 (-33%)"
        elif -0.77 < pct < -0.73:
            event_type = "✂️  POSIBLE SPLIT 4:1 (-75%)"
        elif -0.82 < pct < -0.78:
            event_type = "✂️  POSIBLE SPLIT 5:1 (-80%)"
        elif -0.91 < pct < -0.89:
            event_type = "✂️  POSIBLE SPLIT 10:1 (-90%)"
            
        suspicious_events.append({
            'date': date,
            'pct': pct,
            'type': event_type,
            'price_before': df.loc[idx-1, 'close'] if idx-1 in df.index else 0,
            'price_after': row['close']
        })
        
    return suspicious_events

def main():
    print("🕵️  AUDITORÍA DE CALIDAD DE DATOS Y SPLITS")
    print("==========================================")
    
    conn = sqlite3.connect(DB_PATH)
    tickers = get_tickers(conn)
    
    print(f"📊 Analizando {len(tickers)} tickers...")
    
    split_suspects = 0
    total_issues = 0
    
    # Usar una muestra si son muchos, o todos si tienes tiempo.
    # Por defecto analizamos todos.
    
    for ticker in tqdm(tickers):
        events = analyze_ticker(conn, ticker)
        if events:
            # Filtrar solo si hay eventos tipo Split para no llenar la pantalla de ruido
            splits = [e for e in events if "SPLIT" in e['type']]
            
            if splits:
                print(f"\n🚨 {ticker}:")
                split_suspects += 1
                for e in splits:
                    print(f"   {e['date']}: {e['pct']:.2%} -> {e['type']}")
                    print(f"      Precio: {e['price_before']:.2f} -> {e['price_after']:.2f}")
                total_issues += len(splits)

    conn.close()
    
    print("\n" + "="*50)
    print("📊 RESUMEN FINAL")
    print("="*50)
    if split_suspects > 0:
        print(f"⚠️  Se detectaron {split_suspects} tickers con posibles splits NO ajustados.")
        print(f"🔴 Total de eventos sospechosos: {total_issues}")
        print("\nCONCLUSIÓN: Tu data NO está totalmente ajustada por splits.")
        print("SOLUCIÓN: Debes configurar 'auto_adjust=True' en tu script de descarga.")
    else:
        print("✅ No se detectaron patrones obvios de splits no ajustados.")
        print("   Tu base de datos parece estar correctamente ajustada.")

if __name__ == "__main__":
    main()
