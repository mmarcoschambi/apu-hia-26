#!/usr/bin/env python3
"""
QUICK ADD TICKERS - Atajo rápido para agregar tickers
======================================================
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.universe_manager import UniverseManager

# Lista de tickers a agregar
NEW_TICKERS = """
ASMB, CYTK, BBNX, ISSC, GOLD, RKLB, SII, AAOI, HUT, FSLR, 
ARRY, RUN, TFPM, CGAU, LPLA, ARMN, PHAT, VSEC, TPB, VRDN, 
AGI, DRD, GE, AEM, AUGO, PL, AXSM, HG, KNSA, CSTM, KDK, 
ANAB, XMTR, WSBC, TPC, TBBB, OR, MIRM, MU, NGD, EQX, ACMR, 
SGML, DJCO, SSRM, WDC, NBN, CUBI, HROW, IAG
"""

def main():
    print("="*80)
    print("  ➕ AGREGAR TICKERS NUEVOS")
    print("="*80)
    
    manager = UniverseManager()
    
    print(f"\n📋 Tickers a agregar:")
    tickers_list = [t.strip() for t in NEW_TICKERS.replace('\n', ',').split(',') if t.strip()]
    
    for i, ticker in enumerate(tickers_list, 1):
        if i % 10 == 0:
            print(f"  {ticker}")
        else:
            print(f"  {ticker}", end='')
    
    print(f"\n\nTotal: {len(tickers_list)} tickers")
    print("\n⏳ Agregando tickers...")
    
    # Agregar directamente
    manager.add_custom_tickers(tickers_list)
    
    # Reconstruir universo
    print("\n🔄 Reconstruyendo universo completo...")
    universe = manager.build_universe(force_refresh=True)
    
    print(f"\n✅ ¡Listo! Universo actualizado con {len(universe)} tickers totales")
    print("\nPuedes verificar con:")
    print("  python manage_universe.py --info")

if __name__ == "__main__":
    main()
