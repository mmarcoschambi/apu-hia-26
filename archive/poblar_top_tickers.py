#!/usr/bin/env python3
"""
Script para poblar datos históricos de los tickers de top_global_tickers.txt
"""

import subprocess
import sys
from pathlib import Path

def main():
    # Leer tickers del archivo
    ticker_file = Path("top_global_tickers.txt")
    
    if not ticker_file.exists():
        print("❌ No se encontró el archivo top_global_tickers.txt")
        print("   Ejecuta primero: python3 get_top_liquidity_tickers.py")
        return
    
    with open(ticker_file, 'r') as f:
        tickers = [line.strip() for line in f if line.strip()]
    
    # Asegurar que índices críticos estén presentes para Market Regime
    critical_tickers = ['SPY', 'VIX', 'QQQ', '^VIX']
    for t in critical_tickers:
        if t not in tickers:
            tickers.insert(0, t)
    
    print(f"📊 Se encontraron {len(tickers)} tickers en top_global_tickers.txt (incluyendo índices)")
    
    # Configuración
    years = 3  # Años de historia a descargar
    delay = 0.5  # Segundos de espera entre requests
    
    print(f"📅 Descargando {years} años de historia...")
    print(f"⏱️  Delay: {delay}s entre requests")
    print(f"⚠️  Esto tomará tiempo (aprox {len(tickers) * delay / 60:.1f} minutos)")
    
    # Ejecutar script de poblar con los tickers
    cmd = [
        sys.executable,
        "populate_historical_openbb.py",
        "--tickers"
    ] + tickers + [
        "--years", str(years),
        "--delay", str(delay)
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("\n✅ Datos poblados exitosamente")
    except KeyboardInterrupt:
        print("\n🛑 Proceso interrumpido por usuario")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
