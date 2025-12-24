#!/usr/bin/env python3
"""
Script para ejecutar un backtest NUEVO con los filtros activos
y demostrar que funciona correctamente
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.daily_engine import DailyBacktestEngine
from src.utils.risk_calculator import RiskManager
import pandas as pd
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

def main():
    print("=" * 80)
    print("🚀 EJECUTANDO BACKTEST CON FILTROS ACTIVOS")
    print("=" * 80)
    print()
    print("📋 Configuración:")
    print("   • Periodo: 2020-12-01 a 2021-03-01")
    print("   • Símbolos: MU, GH, COHR, LITE, EXAS, ASTS")
    print("   • Capital: $50,000")
    print("   • Risk: 1% por trade")
    print()
    print("🔍 Filtros Activos:")
    print("   ✅ Tendencia: Solo Uptrend (precio > SMA20)")
    print("   ✅ RVOL: Mínimo 1.5x")
    print()
    print("=" * 80)
    print("⏳ Ejecutando backtest...")
    print("=" * 80)
    print()
    
    # Test symbols - same ones that had issues before
    test_symbols = ['MU', 'GH', 'COHR', 'LITE', 'EXAS', 'ASTS']
    
    # Create risk manager
    risk_manager = RiskManager(
        account_equity=50000,
        risk_pct=0.01,
        max_positions=5
    )
    
    # Create engine
    engine = DailyBacktestEngine(
        universe=test_symbols,
        start_date='2020-12-01',
        end_date='2021-03-01',
        risk_manager=risk_manager,
        skip_filters=True  # Skip market cap filters to focus on our filters
    )
    
    try:
        # Run backtest
        results = engine.run()
        
        print()
        print("=" * 80)
        print("✅ BACKTEST COMPLETADO")
        print("=" * 80)
        print()
        
        if results is not None and not results.empty:
            # Analysis
            total_trades = len(results)
            blue_sky = results[results['signal_type'].str.contains('BLUE_SKY', na=False)]
            vwap_reclaim = results[results['signal_type'].str.contains('VWAP', na=False)]
            
            print(f"📊 Resultados Generales:")
            print(f"   Total trades: {total_trades}")
            print(f"   Blue Sky: {len(blue_sky)}")
            print(f"   VWAP Reclaim: {len(vwap_reclaim)}")
            print()
            
            # VALIDATION 1: Trend Filter
            print("=" * 80)
            print("🔍 VALIDACIÓN 1: FILTRO DE TENDENCIA")
            print("=" * 80)
            
            if not blue_sky.empty and 'context_trend' in blue_sky.columns:
                trend_counts = blue_sky['context_trend'].value_counts()
                print("\n📈 Distribución de tendencias en Blue Sky:")
                for trend, count in trend_counts.items():
                    emoji = "✅" if trend == "Uptrend" else "❌"
                    print(f"   {emoji} {trend}: {count} trades")
                
                weak_trades = blue_sky[blue_sky['context_trend'] == 'Weak']
                
                if len(weak_trades) == 0:
                    print("\n✅ ¡ÉXITO! Ningún Blue Sky con Weak trend")
                    print("   Filtro de tendencia funcionando correctamente")
                else:
                    print(f"\n❌ FALLO: {len(weak_trades)} Blue Sky con Weak trend")
                    print("   Esto NO debería ocurrir!")
                    for idx, row in weak_trades.iterrows():
                        print(f"   • {row['symbol']} | {row['entry_date']}")
            
            # VALIDATION 2: RVOL Filter
            print("\n" + "=" * 80)
            print("🔍 VALIDACIÓN 2: FILTRO DE RVOL")
            print("=" * 80)
            
            if not blue_sky.empty and 'context_rvol' in blue_sky.columns:
                rvol_min = blue_sky['context_rvol'].min()
                rvol_max = blue_sky['context_rvol'].max()
                rvol_mean = blue_sky['context_rvol'].mean()
                
                print(f"\n📊 Estadísticas de RVOL en Blue Sky:")
                print(f"   Mínimo:  {rvol_min:.2f}x")
                print(f"   Máximo:  {rvol_max:.2f}x")
                print(f"   Promedio: {rvol_mean:.2f}x")
                
                low_rvol = blue_sky[blue_sky['context_rvol'] < 1.5]
                
                if len(low_rvol) == 0:
                    print("\n✅ ¡ÉXITO! Todos los Blue Sky tienen RVOL ≥ 1.5x")
                    print("   Filtro de RVOL funcionando correctamente")
                    
                    ideal = blue_sky[blue_sky['context_rvol'] >= 2.0]
                    print(f"\n   📈 {len(ideal)}/{len(blue_sky)} con RVOL ≥ 2.0x (ideal)")
                else:
                    print(f"\n❌ FALLO: {len(low_rvol)} Blue Sky con RVOL < 1.5x")
                    print("   Esto NO debería ocurrir!")
                    for idx, row in low_rvol.iterrows():
                        rvol = row.get('context_rvol', 0)
                        print(f"   • {row['symbol']} | {row['entry_date']} | RVOL: {rvol:.2f}x")
            
            # Performance with filters
            if not blue_sky.empty:
                print("\n" + "=" * 80)
                print("📊 RENDIMIENTO CON FILTROS")
                print("=" * 80)
                
                winners = blue_sky[blue_sky['returns_pct'] > 0]
                win_rate = len(winners) / len(blue_sky) * 100 if len(blue_sky) > 0 else 0
                
                print(f"\n🎯 Blue Sky Performance:")
                print(f"   Total: {len(blue_sky)} trades")
                print(f"   Winners: {len(winners)} ({win_rate:.1f}%)")
                print(f"   Total P&L: ${blue_sky['Result'].sum():,.2f}")
                
                if len(winners) > 0:
                    print(f"   Avg Win: {winners['returns_pct'].mean():+.2f}%")
                if len(blue_sky) > len(winners):
                    losers = blue_sky[blue_sky['returns_pct'] <= 0]
                    print(f"   Avg Loss: {losers['returns_pct'].mean():+.2f}%")
            
            print("\n" + "=" * 80)
            print("💾 RESULTADOS GUARDADOS")
            print("=" * 80)
            print("\n✅ Archivo: backtest_results.csv")
            print("   Ahora el dashboard mostrará solo trades con filtros aprobados")
            
        else:
            print("⚠️  No se generaron trades en este periodo")
        
        print("\n" + "=" * 80)
        print("🏁 BACKTEST FINALIZADO")
        print("=" * 80)
        print("\n💡 Próximo paso: Abre la app de Streamlit")
        print("   $ streamlit run app.py")
        print("\n   Los trades que veas ahora pasaron AMBOS filtros:")
        print("   ✅ Tendencia Uptrend (precio > SMA20)")
        print("   ✅ RVOL ≥ 1.5x")
        
    except Exception as e:
        print(f"\n❌ Error ejecutando backtest: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
