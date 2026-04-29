#!/usr/bin/env python3
"""
Backtest Runner - Easy interface for historical analysis
Usage: python3 backtest_runner.py
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.backtest.backtest import HistoricalBacktester
from src.backtest.visualizer import BacktestVisualizer


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                    📊 TRIAD BACKTEST RUNNER                                 ║
║                                                                              ║
║            Analiza cómo funcionaron los 3 Caminos en el pasado             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # Configuration
    print("📝 CONFIGURACIÓN")
    print("=" * 80)
    
    # Watchlist
    print("\n1. Watchlist (símbolos separados por espacio):")
    print("   Ejemplo: RDDT NVDA TSLA CEG PLTR")
    watchlist_input = input("   Símbolos: ").strip()
    
    if not watchlist_input:
        watchlist = ['RDDT', 'NVDA', 'TSLA', 'CEG']
        print(f"   → Usando default: {', '.join(watchlist)}")
    else:
        watchlist = watchlist_input.upper().split()
    
    # Date range
    print("\n2. Rango de fechas:")
    print("   a) Último mes")
    print("   b) Últimos 3 meses")
    print("   c) Últimos 6 meses")
    print("   d) Todo 2024")
    print("   e) Custom (ingresar fechas)")
    
    choice = input("   Opción (a/b/c/d/e): ").strip().lower()
    
    today = datetime.now()
    
    if choice == 'a':
        start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    elif choice == 'b':
        start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    elif choice == 'c':
        start_date = (today - timedelta(days=180)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    elif choice == 'd':
        start_date = '2024-01-01'
        end_date = '2024-12-31'
    elif choice == 'e':
        start_date = input("   Start date (YYYY-MM-DD): ").strip()
        end_date = input("   End date (YYYY-MM-DD): ").strip()
    else:
        start_date = '2024-01-01'
        end_date = today.strftime('%Y-%m-%d')
        print(f"   → Usando default: {start_date} to {end_date}")
    
    # Output
    print("\n3. Archivo de resultados:")
    output_file = input("   Nombre (Enter = backtest_results.csv): ").strip()
    if not output_file:
        output_file = 'backtest_results.csv'
    
    # Visualization
    print("\n4. Generar gráficos?")
    print("   a) Sí, todos (puede tardar)")
    print("   b) Sí, solo primeros 10")
    print("   c) Sí, solo primeros 5")
    print("   d) Solo dashboard resumen")
    print("   e) No generar gráficos")
    
    viz_choice = input("   Opción (a/b/c/d/e): ").strip().lower()
    
    # Run backtest
    print(f"\n{'='*80}")
    print("🚀 INICIANDO BACKTEST")
    print(f"{'='*80}")
    print(f"Símbolos: {', '.join(watchlist)}")
    print(f"Período: {start_date} to {end_date}")
    print(f"Output: {output_file}")
    print()
    
    backtester = HistoricalBacktester()
    
    results = backtester.backtest_watchlist(
        symbols=watchlist,
        start_date=start_date,
        end_date=end_date
    )
    
    if results.empty:
        print("\n❌ No se encontraron señales en el período especificado")
        print("   Intenta con:")
        print("   - Un rango de fechas más amplio")
        print("   - Más símbolos en el watchlist")
        print("   - Símbolos con más momentum/volatilidad")
        return
    
    # Save results
    backtester.save_results(results, output_file)
    
    # Summary
    print(f"\n{'='*80}")
    print("📈 RESUMEN DEL BACKTEST")
    print(f"{'='*80}")
    print(f"Total Signals: {len(results)}")
    print(f"Símbolos: {results['symbol'].nunique()}")
    print(f"Período: {results['date'].min().date()} to {results['date'].max().date()}")
    
    print(f"\nPor Camino:")
    for camino in results['camino'].unique():
        camino_results = results[results['camino'] == camino]
        wins = len(camino_results[camino_results['outcome'] == 'WIN'])
        total = len(camino_results)
        avg_return = camino_results['return_pct'].mean()
        win_rate = wins / total * 100 if total > 0 else 0
        print(f"  {camino}:")
        print(f"    Signals: {total}")
        print(f"    Wins: {wins}/{total} ({win_rate:.1f}%)")
        print(f"    Avg Return: {avg_return:+.2f}%")
    
    # Overall stats
    wins = len(results[results['outcome'] == 'WIN'])
    total = len(results)
    print(f"\n  OVERALL:")
    print(f"    Win Rate: {wins}/{total} ({wins/total*100:.1f}%)")
    print(f"    Avg Return: {results['return_pct'].mean():+.2f}%")
    print(f"    Best Trade: {results['return_pct'].max():+.2f}%")
    print(f"    Worst Trade: {results['return_pct'].min():+.2f}%")
    
    # Visualizations
    if viz_choice != 'e':
        print(f"\n{'='*80}")
        print("📊 GENERANDO VISUALIZACIONES")
        print(f"{'='*80}")
        
        visualizer = BacktestVisualizer()
        
        # Dashboard
        visualizer.create_summary_dashboard(output_file)
        
        # Individual charts
        if viz_choice in ['a', 'b', 'c']:
            max_trades = 999 if viz_choice == 'a' else (10 if viz_choice == 'b' else 5)
            visualizer.visualize_all_trades(output_file, max_trades=max_trades)
        
        print(f"\n✅ Gráficos guardados en: ./backtest_charts/")
        print(f"   - summary_dashboard.png (Resumen general)")
        print(f"   - [Symbol]_[Date]_[Camino].png (Trades individuales)")
    
    # Final message
    print(f"\n{'='*80}")
    print("✅ BACKTEST COMPLETADO")
    print(f"{'='*80}")
    print(f"\n📁 Archivos generados:")
    print(f"   - {output_file} (Resultados CSV)")
    if viz_choice != 'e':
        print(f"   - ./backtest_charts/ (Gráficos)")
    
    print(f"\n💡 Próximos pasos:")
    print(f"   1. Abre summary_dashboard.png para ver el resumen")
    print(f"   2. Revisa los gráficos individuales para estudiar cada setup")
    print(f"   3. Abre {output_file} en Excel/LibreOffice para análisis detallado")
    print(f"   4. Identifica patrones de los setups ganadores")
    print(f"   5. Ajusta parámetros en config/settings.py si es necesario")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Backtest cancelado por el usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
