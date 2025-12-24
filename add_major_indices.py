#!/usr/bin/env python3
"""
Agregar principales índices (S&P 500 + NASDAQ 100) desde listas estáticas
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.universe_manager import UniverseManager

# Top 100 S&P 500 más líquidos
SP500_TOP = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "LLY", "V",
    "UNH", "JPM", "XOM", "JNJ", "WMT", "MA", "PG", "AVGO", "HD", "CVX",
    "MRK", "ABBV", "COST", "KO", "PEP", "ADBE", "CRM", "NFLX", "MCD", "CSCO",
    "ACN", "TMO", "LIN", "ABT", "ORCL", "DIS", "CMCSA", "NKE", "INTC", "VZ",
    "AMD", "QCOM", "TXN", "DHR", "PM", "UPS", "NEE", "HON", "RTX", "INTU",
    "LOW", "AMGN", "SPGI", "BMY", "BA", "SBUX", "T", "AMAT", "UNP", "COP",
    "ELV", "DE", "BLK", "MDT", "CAT", "AXP", "GILD", "PLD", "ISRG", "MMC",
    "GE", "LRCX", "CI", "VRTX", "SYK", "SCHW", "CB", "BKNG", "ADI", "AMT",
    "REGN", "MO", "ZTS", "PGR", "TJX", "MDLZ", "SO", "BSX", "EOG", "DUK",
    "ITW", "CME", "ETN", "CSX", "MMM", "NOC", "WM", "EMR", "APD", "PH"
]

# NASDAQ 100 principales
NASDAQ100_TOP = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "NFLX",
    "ASML", "ADBE", "PEP", "AMD", "CSCO", "TMUS", "QCOM", "INTC", "CMCSA", "TXN",
    "INTU", "HON", "AMGN", "AMAT", "BKNG", "ADP", "ISRG", "ADI", "VRTX", "GILD",
    "LRCX", "MU", "REGN", "PANW", "SBUX", "KLAC", "MDLZ", "SNPS", "CDNS", "MELI",
    "PYPL", "ABNB", "NXPI", "MAR", "CRWD", "WDAY", "MNST", "ADSK", "MRVL", "CTAS",
    "ORLY", "FTNT", "DASH", "AEP", "PCAR", "KDP", "ROST", "PAYX", "KHC", "FAST",
    "ODFL", "DDOG", "CPRT", "VRSK", "BKR", "CTSH", "IDXX", "EA", "GEHC", "XEL",
    "TEAM", "DXCM", "ZS", "EXC", "CSGP", "LULU", "TTWO", "ANSS", "ON", "WBD",
    "CDW", "FANG", "GFS", "MDB", "DLTR", "WBA", "ILMN", "BIIB", "ZM", "MRNA"
]

def main():
    print("="*80)
    print("  📊 AGREGAR PRINCIPALES ÍNDICES (S&P 500 + NASDAQ 100)")
    print("="*80)
    
    manager = UniverseManager()
    
    # Combinar listas
    all_tickers = list(set(SP500_TOP + NASDAQ100_TOP))
    
    print(f"\n✅ Total tickers a agregar: {len(all_tickers)}")
    print(f"   S&P 500 Top 100: {len(SP500_TOP)}")
    print(f"   NASDAQ 100 Top 90: {len(NASDAQ100_TOP)}")
    print(f"   Únicos (sin duplicados): {len(all_tickers)}")
    
    print("\n⏳ Agregando tickers...")
    manager.add_custom_tickers(all_tickers)
    
    print("\n🔄 Reconstruyendo universo...")
    universe = manager.build_universe(force_refresh=True)
    
    print(f"\n✅ ¡Listo! Universo con {len(universe)} tickers")
    print("\nVerifica con:")
    print("  python manage_universe.py --info")

if __name__ == "__main__":
    main()
