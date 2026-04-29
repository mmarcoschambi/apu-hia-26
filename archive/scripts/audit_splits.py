
import yfinance as yf
import pandas as pd
import sqlite3
import numpy as np
from pathlib import Path

# Configurar tickers a auditar
audit_targets = [
    {"symbol": "ATLO", "date": "2022-01-07", "cached_price": 18.26},
    {"symbol": "AAP", "date": "2018-07-18", "cached_price": 43.00}
]

db_path = Path("data/ticker_cache.db")

print(f"--- 🕵️ AUDITORÍA DE AJUSTES (SPLITS/DIVIDENDOS) ---")

for item in audit_targets:
    symbol = item['symbol']
    target_date = item['date']
    cached_val = item['cached_price']
    
    print(f"\n[{symbol}] Analizando fecha {target_date}...")
    
    # 1. Obtener Data Real de Yahoo (Adjusted vs Unadjusted)
    ticker = yf.Ticker(symbol)
    
    # Bajamos un rango pequeño
    start_dt = pd.to_datetime(target_date) - pd.Timedelta(days=5)
    end_dt = pd.to_datetime(target_date) + pd.Timedelta(days=5)
    
    try:
        # A) Auto Adjust = True (Lo que ve el visualizador hoy)
        df_adj = ticker.history(start=start_dt, end=end_dt, auto_adjust=True)
        if target_date not in df_adj.index:
            # Buscar fecha más cercana si es fin de semana
            real_date = df_adj.index.asof(target_date)
            print(f"   ⚠️ Fecha exacta no encontrada, usando: {real_date.date()}")
            target_date = str(real_date.date())
        
        price_adj_yahoo = df_adj.loc[target_date]['Close']
        
        # B) Auto Adjust = False (Precio "Raw" histórico real)
        df_raw = ticker.history(start=start_dt, end=end_dt, auto_adjust=False)
        price_raw_yahoo = df_raw.loc[target_date]['Close']
        
        # C) Acciones (Splits y Dividendos) desde esa fecha hasta hoy
        actions = ticker.actions
        # Filtrar acciones POSTERIORES a la fecha del trade
        relevant_actions = actions[actions.index > target_date]
        
        splits = relevant_actions[relevant_actions['Stock Splits'] != 0]
        dividends = relevant_actions[relevant_actions['Dividends'] != 0]
        
        total_splits_ratio = np.prod(splits['Stock Splits']) if not splits.empty else 1.0
        sum_dividends = dividends['Dividends'].sum()
        
        print(f"   1. Tu Caché (SQL):      ${cached_val:.2f}")
        print(f"   2. Yahoo RAW (Real):    ${price_raw_yahoo:.2f}")
        print(f"   3. Yahoo ADJ (Hoy):     ${price_adj_yahoo:.2f}")
        
        print(f"   --- Análisis de Ajustes ---")
        print(f"   Splits posteriores:     {len(splits)} (Factor acumulado: {total_splits_ratio:.4f})")
        print(f"   Dividendos posteriores: {len(dividends)} (Suma total: ${sum_dividends:.2f})")
        
        # Intentos de Reconciliación
        print(f"   --- Intentos de Reconciliación ---")
        
        # Hipótesis 1: Tu caché es RAW puro
        diff_raw = abs(cached_val - price_raw_yahoo) / price_raw_yahoo * 100
        match_raw = "✅ SI" if diff_raw < 1.0 else "❌ NO"
        print(f"   A) ¿Es RAW?             {match_raw} (Diferencia: {diff_raw:.2f}%)")
        
        # Hipótesis 2: Tu caché está ajustado por Splits pero NO por dividendos
        # (Si hubo splits, aplicamos el factor al precio Raw)
        if total_splits_ratio != 1:
            simulated_split_adj = price_raw_yahoo / total_splits_ratio
            diff_split = abs(cached_val - simulated_split_adj) / simulated_split_adj * 100
            print(f"   B) ¿Solo Split Adj?     {'✅ SI' if diff_split < 1 else '❌ NO'} (${simulated_split_adj:.2f})")
        
        # Hipótesis 3: Tu caché es el Ajustado TOTAL (Yahoo ADJ)
        diff_adj = abs(cached_val - price_adj_yahoo) / price_adj_yahoo * 100
        match_adj = "✅ SI" if diff_adj < 1.0 else "❌ NO"
        print(f"   C) ¿Es Yahoo ADJ?       {match_adj} (Diferencia: {diff_adj:.2f}%)")

        # Conclusión
        if diff_raw > 5 and diff_adj > 5:
            print(f"\n   🚨 CONCLUSIÓN: DATA CORRUPTA. Tu valor (${cached_val}) no coincide ni con el precio real histórico (${price_raw_yahoo}) ni con el ajustado (${price_adj_yahoo}).")
        elif match_raw == "✅ SI":
             print(f"\n   ℹ️ CONCLUSIÓN: Tu caché tiene precios RAW (Sin ajustar).")
        elif match_adj == "✅ SI":
             print(f"\n   ℹ️ CONCLUSIÓN: Tu caché está correctamente AJUSTADO.")
            
    except Exception as e:
        print(f"   ❌ Error procesando {symbol}: {e}")

