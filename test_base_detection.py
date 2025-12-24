#!/usr/bin/env python3
"""
Test mejorado de detección de bases con criterios profesionales
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.market_data import MarketDataProvider
from src.indicators.triad import TriadIndicators
import pandas as pd


def test_base_detection(symbol: str):
    """Prueba la detección de base con criterios profesionales"""
    
    print(f"\n{'='*80}")
    print(f"🔍 ANÁLISIS DE BASE PROFESIONAL - {symbol}")
    print(f"{'='*80}\n")
    
    provider = MarketDataProvider()
    df = provider.get_daily_data(symbol, period='1y')
    
    if df.empty:
        print(f"❌ No se pudo obtener datos para {symbol}")
        return
    
    # Detectar base con nuevos criterios
    base_result = TriadIndicators.detect_base(
        df, 
        lookback=20,
        min_prior_advance=0.30,  # 30% mínimo
        max_base_range=0.15,      # 15% máximo
        tightness_days=5
    )
    
    # Mostrar resultados
    print("📊 RESULTADO:")
    print("-" * 80)
    
    if base_result['detected']:
        print("✅ BASE VÁLIDA DETECTADA\n")
    else:
        print("❌ NO HAY BASE VÁLIDA\n")
        print(f"Razón: {base_result['reason']}\n")
    
    # Métricas principales
    print("🎯 MÉTRICAS DE LA BASE:")
    print("-" * 80)
    print(f"Base High:     ${base_result['base_high']:.2f}")
    print(f"Base Low:      ${base_result['base_low']:.2f}")
    print(f"Current Price: ${base_result['current_price']:.2f}")
    print(f"Range:         {base_result['compression_pct']*100:.1f}% {'✅' if base_result['compression_pct'] <= 0.15 else '❌'}")
    print(f"Distance High: {base_result['distance_from_high_pct']*100:.1f}%")
    
    # Criterios de calidad
    print(f"\n📈 CRITERIOS DE CALIDAD (Score: {base_result['quality_score']}/3):")
    print("-" * 80)
    
    # 1. Tendencia previa
    print(f"1. Prior Advance:  {base_result['prior_advance_pct']*100:.1f}% ", end="")
    if base_result['has_prior_advance']:
        print("✅ (>30%)")
    else:
        print(f"❌ (need 30%)")
    
    # 2. Volumen seco
    print(f"2. Volume Dried:   Ratio {base_result['volume_dry_ratio']:.2f} ", end="")
    if base_result['volume_dried_up']:
        print("✅ (red days <75% volume)")
    else:
        print("❌ (red days too heavy)")
    
    # 3. Tightness
    print(f"3. Tightness:      Avg range {base_result['avg_recent_range_pct']*100:.2f}% ", end="")
    if base_result['is_tight']:
        print("✅ (compressed)")
    else:
        print("❌ (not tight)")
    
    # 4. Moving averages
    print(f"\n📊 MEDIAS MÓVILES:")
    print("-" * 80)
    print(f"EMA10:  ${base_result['ema10']:.2f}")
    print(f"EMA20:  ${base_result['ema20']:.2f}")
    print(f"SMA50:  ${base_result['sma50']:.2f}")
    print(f"SMA200: ${base_result['sma200']:.2f}")
    
    aligned = "✅ Aligned" if base_result['mas_aligned'] else "❌ Not aligned"
    above_ema20 = "✅ Above" if base_result['price_above_ema20'] else "❌ Below"
    print(f"\nAlignment: {aligned} | Price vs EMA20: {above_ema20}")
    
    # Recomendación
    print(f"\n💡 RECOMENDACIÓN:")
    print("-" * 80)
    if base_result['detected']:
        print(f"✅ Esta es una base de CALIDAD INSTITUCIONAL")
        print(f"   - Entry: ${base_result['base_high'] * 1.01:.2f} (base high + 1%)")
        print(f"   - Stop:  ${base_result['base_low']:.2f} (base low)")
        print(f"   - Risk:  {((base_result['base_high'] - base_result['base_low']) / base_result['base_high'] * 100):.1f}%")
    else:
        print(f"⚠️  Esperar a que se forme una base válida")
        
        # Sugerencias
        if not base_result['has_prior_advance']:
            print(f"   - Necesita más subida previa (actual: {base_result['prior_advance_pct']*100:.1f}%)")
        if base_result['compression_pct'] > 0.15:
            print(f"   - Rango muy amplio, esperar consolidación")
        if not base_result['volume_dried_up']:
            print(f"   - Volumen no se ha secado en días rojos")
        if not base_result['is_tight']:
            print(f"   - Esperar apretamiento (velas más pequeñas)")
        if not base_result['mas_aligned']:
            print(f"   - Medias móviles no alineadas correctamente")
    
    print("=" * 80)


def main():
    """Test con varios símbolos"""
    
    # Símbolos a probar (algunos con bases buenas, otros no)
    symbols = ['TSLA', 'PLTR', 'NVDA', 'AAPL', 'AMD', 'META']
    
    print("\n🔬 TEST DE DETECCIÓN PROFESIONAL DE BASES")
    print("Criterios: Prior Advance 30% + Volume Dry + Tightness + MAs Aligned")
    
    for symbol in symbols:
        try:
            test_base_detection(symbol)
            input("\nPresiona Enter para continuar...")
        except Exception as e:
            print(f"\n❌ Error con {symbol}: {e}\n")
    
    print("\n✅ Test completado!")


if __name__ == "__main__":
    main()
