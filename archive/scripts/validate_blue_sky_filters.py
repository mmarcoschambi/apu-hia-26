#!/usr/bin/env python3
"""
Script para validar que los filtros de Blue Sky estén funcionando
después de ejecutar un nuevo backtest
"""

import pandas as pd
import sys

def validate_filters():
    print("=" * 80)
    print("🔍 VALIDACIÓN DE FILTROS BLUE SKY")
    print("=" * 80)
    print()
    
    try:
        # Load backtest results
        df = pd.read_csv('backtest_results.csv')
        print(f"✅ Archivo cargado: {len(df)} trades totales")
        print()
        
        # Filter Blue Sky trades
        blue_sky = df[df['signal_type'].str.contains('BLUE_SKY', na=False)]
        print(f"🚀 Blue Sky trades: {len(blue_sky)}")
        print()
        
        if blue_sky.empty:
            print("⚠️  No hay trades de Blue Sky en este backtest")
            return
        
        # VALIDATION 1: Trend Filter
        print("=" * 80)
        print("VALIDACIÓN 1: FILTRO DE TENDENCIA")
        print("=" * 80)
        
        if 'context_trend' in blue_sky.columns:
            trend_counts = blue_sky['context_trend'].value_counts()
            print("\nDistribución de tendencias:")
            for trend, count in trend_counts.items():
                print(f"  {trend}: {count} trades")
            
            weak_trades = blue_sky[blue_sky['context_trend'] == 'Weak']
            if len(weak_trades) > 0:
                print(f"\n❌ FALLO: {len(weak_trades)} Blue Sky trades con Weak trend encontrados!")
                print("\nTrades problemáticos:")
                for idx, row in weak_trades.iterrows():
                    print(f"  • {row['symbol']} | {row['entry_date']} | Return: {row['returns_pct']:.2f}%")
                print("\n⚠️  Estos trades NO deberían existir con el filtro activo")
            else:
                print(f"\n✅ ÉXITO: Ningún Blue Sky trade con Weak trend!")
                print("   Filtro de tendencia funcionando correctamente")
        else:
            print("⚠️  Columna 'context_trend' no encontrada")
        
        # VALIDATION 2: RVOL Filter
        print("\n" + "=" * 80)
        print("VALIDACIÓN 2: FILTRO DE RVOL")
        print("=" * 80)
        
        if 'context_rvol' in blue_sky.columns:
            rvol_min = blue_sky['context_rvol'].min()
            rvol_max = blue_sky['context_rvol'].max()
            rvol_mean = blue_sky['context_rvol'].mean()
            
            print(f"\nEstadísticas de RVOL:")
            print(f"  Mínimo:  {rvol_min:.2f}x")
            print(f"  Máximo:  {rvol_max:.2f}x")
            print(f"  Promedio: {rvol_mean:.2f}x")
            
            low_rvol_trades = blue_sky[blue_sky['context_rvol'] < 1.5]
            if len(low_rvol_trades) > 0:
                print(f"\n❌ FALLO: {len(low_rvol_trades)} Blue Sky trades con RVOL < 1.5x encontrados!")
                print("\nTrades problemáticos:")
                for idx, row in low_rvol_trades.iterrows():
                    rvol = row.get('context_rvol', 0)
                    print(f"  • {row['symbol']} | {row['entry_date']} | RVOL: {rvol:.2f}x | Return: {row['returns_pct']:.2f}%")
                print("\n⚠️  Estos trades NO deberían existir con el filtro activo")
            else:
                print(f"\n✅ ÉXITO: Todos los Blue Sky trades tienen RVOL ≥ 1.5x!")
                print("   Filtro de RVOL funcionando correctamente")
                
                # Check ideal threshold
                ideal_trades = blue_sky[blue_sky['context_rvol'] >= 2.0]
                print(f"\n📊 {len(ideal_trades)}/{len(blue_sky)} trades con RVOL ≥ 2.0x (ideal)")
        else:
            print("⚠️  Columna 'context_rvol' no encontrada")
        
        # VALIDATION 3: Combined Performance
        print("\n" + "=" * 80)
        print("VALIDACIÓN 3: RENDIMIENTO CON FILTROS")
        print("=" * 80)
        
        if 'context_trend' in blue_sky.columns and 'context_rvol' in blue_sky.columns:
            # Perfect trades (both filters pass)
            perfect = blue_sky[(blue_sky['context_trend'] == 'Uptrend') & 
                              (blue_sky['context_rvol'] >= 1.5)]
            
            if not perfect.empty:
                winners = perfect[perfect['returns_pct'] > 0]
                win_rate = len(winners) / len(perfect) * 100
                avg_win = winners['returns_pct'].mean() if len(winners) > 0 else 0
                avg_loss = perfect[perfect['returns_pct'] < 0]['returns_pct'].mean()
                
                print(f"\n📊 Blue Sky con Uptrend + RVOL ≥ 1.5x:")
                print(f"   Total: {len(perfect)} trades")
                print(f"   Winners: {len(winners)} ({win_rate:.1f}%)")
                print(f"   Avg Win: {avg_win:+.2f}%")
                print(f"   Avg Loss: {avg_loss:+.2f}%")
                print(f"   Total P&L: ${perfect['Result'].sum():,.2f}")
        
        # SUMMARY
        print("\n" + "=" * 80)
        print("RESUMEN")
        print("=" * 80)
        
        checks_passed = 0
        checks_total = 2
        
        if 'context_trend' in blue_sky.columns:
            weak_count = len(blue_sky[blue_sky['context_trend'] == 'Weak'])
            if weak_count == 0:
                checks_passed += 1
                print("✅ Filtro de Tendencia: PASADO")
            else:
                print(f"❌ Filtro de Tendencia: FALLO ({weak_count} trades con Weak)")
        
        if 'context_rvol' in blue_sky.columns:
            low_rvol_count = len(blue_sky[blue_sky['context_rvol'] < 1.5])
            if low_rvol_count == 0:
                checks_passed += 1
                print("✅ Filtro de RVOL: PASADO")
            else:
                print(f"❌ Filtro de RVOL: FALLO ({low_rvol_count} trades con RVOL < 1.5)")
        
        print()
        print(f"Resultado: {checks_passed}/{checks_total} validaciones pasadas")
        
        if checks_passed == checks_total:
            print("\n🎉 ¡TODOS LOS FILTROS FUNCIONANDO CORRECTAMENTE!")
            return 0
        else:
            print("\n⚠️  Algunos filtros no están funcionando. Revisa la implementación.")
            return 1
            
    except FileNotFoundError:
        print("❌ Error: Archivo 'backtest_results.csv' no encontrado")
        print("\n💡 Ejecuta un backtest primero:")
        print("   streamlit run app.py")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = validate_filters()
    sys.exit(exit_code)
