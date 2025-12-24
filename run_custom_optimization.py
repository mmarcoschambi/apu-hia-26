#!/usr/bin/env python3
"""
Optimización con lista personalizada de símbolos
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from find_optimal_balance import find_sweet_spot

# Símbolos personalizados
symbols = [
    'SATS', 'LITE', 'HL', 'ARWR', 'PRAX', 'PL', 'BLTE', 'KOD', 'TE', 'USAS',
    'TSHA', 'ANAB', 'NAK', 'CIEN', 'COHR', 'PAAS', 'SBSW', 'AG', 'KYMR', 'AAUC',
    'KSS', 'SVM', 'AXGN', 'RLAY', 'SLI', 'WDC', 'MDB', 'TSEM', 'IAG', 'HBM',
    'NGD', 'APGE', 'VICR', 'CENX', 'SPHR', 'CGAU', 'SYRE', 'IE', 'TGB', 'IMNM',
    'LASR', 'GCT', 'TTI', 'MU', 'APP', 'BBIO', 'EGO', 'M', 'SA', 'KDK',
    'CVNA', 'ORLA', 'STX', 'MIRM', 'ASTI', 'CUBI', 'BVN', 'OR', 'INDB', 'LRCX',
    'AGI', 'NPK', 'NRIM', 'SYF', 'UBSI', 'NNI', 'SSRM', 'MDGL', 'CAC'
]

print(f"\n🎯 OPTIMIZACIÓN CON {len(symbols)} SÍMBOLOS PERSONALIZADOS")
print("="*80)

# Rangos de prueba (más granulares)
adr_range = [1.5, 2.0, 2.5, 3.0, 3.5]
max_exp_range = [25, 30, 35, 40]

# Período de análisis
start_date = '2024-01-01'
end_date = '2024-12-20'

print(f"\n⚙️  Configuración:")
print(f"   Símbolos: {len(symbols)}")
print(f"   ADR range: {adr_range}")
print(f"   Max Exp range: {max_exp_range}")
print(f"   Combinaciones: {len(adr_range) * len(max_exp_range)}")
print(f"   Período: {start_date} a {end_date}")
print(f"\n⏱️  Tiempo estimado: 20-30 minutos\n")

# Ejecutar
winner = find_sweet_spot(
    symbols=symbols,
    start_date=start_date,
    end_date=end_date,
    adr_range=adr_range,
    max_exp_range=max_exp_range,
    equity=100000,
    risk_pct=0.5
)

if winner is not None:
    print("\n✅ OPTIMIZACIÓN COMPLETADA!")
    print(f"\n🎯 RESULTADO FINAL:")
    print(f"   ADR: {winner['adr']:.1f}%")
    print(f"   Max Exposure: {winner['max_exposure']:.0f}%")
    print(f"   Score: {winner['final_score']:.2f}")
    print(f"   Robustez: {winner['robustness_score']:.1f}/100")
else:
    print("\n❌ No se pudo completar la optimización")
