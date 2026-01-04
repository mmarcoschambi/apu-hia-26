#!/usr/bin/env python3
"""
Optimizador de Parámetros ADR y Max Exposure
Encuentra la combinación óptima para maximizar ganancias
"""

import pandas as pd
import numpy as np
import subprocess
import json
import os
from datetime import datetime
from itertools import product
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

class FilterOptimizer:
    def __init__(self, symbols, start_date, end_date, equity=100000, risk_pct=0.5):
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.equity = equity
        self.risk_pct = risk_pct
        self.results = []
        
    def run_backtest(self, adr, max_exp, min_vol=300, min_dollar_vol=15):
        """Ejecuta un backtest con parámetros específicos"""
        temp_watchlist = 'outputs/temp_optimize.json'
        with open(temp_watchlist, 'w') as f:
            json.dump({"OPTIMIZE": self.symbols}, f)
        
        cmd = [
            "python3", "daily_backtest_runner.py",
            "--start", str(self.start_date),
            "--end", str(self.end_date),
            "--watchlist", temp_watchlist,
            "--equity", str(self.equity),
            "--risk", str(self.risk_pct / 100.0),
            "--max_exp", str(max_exp / 100.0),
            "--min_adr", str(adr),
            "--min_volume", str(int(min_vol * 1000)),
            "--min_dollar_vol", str(int(min_dollar_vol * 1e6)),
            "--skip_filters"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            # Leer resultados
            if os.path.exists('outputs/backtests/backtest_results.csv'):
                df = pd.read_csv('outputs/backtests/backtest_results.csv')
                if not df.empty:
                    return self._calculate_metrics(df)
            return None
        except Exception as e:
            print(f"Error en backtest: {e}")
            return None
        finally:
            if os.path.exists(temp_watchlist):
                os.remove(temp_watchlist)
    
    def _calculate_metrics(self, df):
        """Calcula métricas de performance"""
        trades = df[df['exit_date'].notna()].copy()
        
        if trades.empty:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'profit_factor': 0,
                'score': 0
            }
        
        # Usar la columna correcta según lo que esté disponible
        if 'pnl_pct' in trades.columns:
            trades['return_pct'] = trades['pnl_pct']
        elif 'return_pct' in trades.columns:
            trades['return_pct'] = trades['return_pct']
        elif 'returns_pct' in trades.columns:
            trades['return_pct'] = trades['returns_pct']
        else:
            print(f"⚠️  Warning: No return column found. Available: {list(trades.columns)}")
            return None
        
        total_trades = len(trades)
        winners = trades[trades['return_pct'] > 0]
        losers = trades[trades['return_pct'] <= 0]
        
        win_rate = len(winners) / total_trades if total_trades > 0 else 0
        avg_return = trades['return_pct'].mean()
        
        # Usar columna de PnL si existe
        if 'pnl' in trades.columns:
            total_pnl = trades['pnl'].sum()
        elif 'pnl_dollars' in trades.columns:
            total_pnl = trades['pnl_dollars'].sum()
        else:
            total_pnl = 0
        
        # Sharpe Ratio
        if trades['return_pct'].std() > 0:
            sharpe = (avg_return / trades['return_pct'].std()) * np.sqrt(252)
        else:
            sharpe = 0
        
        # Max Drawdown
        cumulative = (1 + trades['return_pct'] / 100).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_dd = abs(drawdown.min()) * 100
        
        # Profit Factor
        gross_profit = winners['return_pct'].sum() if not winners.empty else 0
        gross_loss = abs(losers['return_pct'].sum()) if not losers.empty else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Score compuesto (ajustable según preferencias)
        score = (
            win_rate * 30 +  # 30% peso a win rate
            (avg_return / 10) * 25 +  # 25% peso a avg return normalizado
            (sharpe / 2) * 20 +  # 20% peso a sharpe normalizado
            (profit_factor / 3) * 15 +  # 15% peso a profit factor
            (1 - max_dd/100) * 10  # 10% peso a evitar drawdown
        )
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate * 100,
            'total_pnl': total_pnl,
            'avg_return': avg_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'profit_factor': profit_factor,
            'score': score
        }
    
    def optimize_grid_search(self, adr_range, max_exp_range, verbose=True):
        """Grid search sobre rangos de ADR y Max Exposure"""
        print("\n" + "="*70)
        print("🔍 OPTIMIZACIÓN DE FILTROS - GRID SEARCH")
        print("="*70)
        print(f"Símbolos: {', '.join(self.symbols)}")
        print(f"Período: {self.start_date} a {self.end_date}")
        print(f"ADR Range: {adr_range}")
        print(f"Max Exp Range: {max_exp_range}%")
        print(f"Total combinaciones: {len(adr_range) * len(max_exp_range)}")
        print("="*70 + "\n")
        
        total_combinations = len(adr_range) * len(max_exp_range)
        current = 0
        
        for adr, max_exp in product(adr_range, max_exp_range):
            current += 1
            
            if verbose:
                print(f"[{current}/{total_combinations}] Probando ADR={adr:.1f}%, Max Exp={max_exp:.0f}%", end="... ", flush=True)
            
            metrics = self.run_backtest(adr, max_exp)
            
            if metrics:
                result = {
                    'adr': adr,
                    'max_exposure': max_exp,
                    **metrics
                }
                self.results.append(result)
                
                if verbose:
                    print(f"✓ Score={metrics['score']:.2f} | Trades={metrics['total_trades']} | "
                          f"Win%={metrics['win_rate']:.1f} | Avg={metrics['avg_return']:.2f}%")
            else:
                if verbose:
                    print("✗ Sin datos")
        
        return self.get_results_df()
    
    def get_results_df(self):
        """Retorna resultados como DataFrame ordenado por score"""
        if not self.results:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.results)
        df = df.sort_values('score', ascending=False)
        return df
    
    def print_top_results(self, n=10):
        """Imprime los mejores N resultados"""
        df = self.get_results_df()
        
        if df.empty:
            print("❌ No hay resultados disponibles")
            return
        
        print("\n" + "="*100)
        print(f"🏆 TOP {n} COMBINACIONES ÓPTIMAS")
        print("="*100)
        
        cols = ['adr', 'max_exposure', 'score', 'total_trades', 'win_rate', 
                'avg_return', 'sharpe_ratio', 'profit_factor', 'max_drawdown', 'total_pnl']
        
        for idx, row in df.head(n).iterrows():
            rank = idx + 1 if isinstance(idx, int) else list(df.index).index(idx) + 1
            print(f"\n#{rank}")
            print(f"  ADR: {row['adr']:.1f}% | Max Exposure: {row['max_exposure']:.0f}%")
            print(f"  Score: {row['score']:.2f}")
            print(f"  Trades: {row['total_trades']} | Win Rate: {row['win_rate']:.1f}%")
            print(f"  Avg Return: {row['avg_return']:.2f}% | Total PnL: ${row['total_pnl']:.2f}")
            print(f"  Sharpe: {row['sharpe_ratio']:.2f} | Profit Factor: {row['profit_factor']:.2f}")
            print(f"  Max DD: {row['max_drawdown']:.1f}%")
        
        print("\n" + "="*100)
        
        # Mejor combinación
        best = df.iloc[0]
        print(f"\n✨ CONFIGURACIÓN ÓPTIMA RECOMENDADA:")
        print(f"   ADR: {best['adr']:.1f}%")
        print(f"   Max Exposure: {best['max_exposure']:.0f}%")
        print(f"   Score Esperado: {best['score']:.2f}")
        print("="*100 + "\n")
    
    def save_results(self, filename='optimization_results.csv'):
        """Guarda resultados a CSV"""
        df = self.get_results_df()
        if not df.empty:
            df.to_csv(filename, index=False)
            print(f"✅ Resultados guardados en {filename}")
    
    def plot_heatmap(self):
        """Genera heatmap de Score vs ADR y Max Exposure"""
        try:
            import plotly.graph_objects as go
            
            df = self.get_results_df()
            if df.empty:
                print("No hay datos para graficar")
                return
            
            pivot = df.pivot(index='adr', columns='max_exposure', values='score')
            
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values,
                x=pivot.columns,
                y=pivot.index,
                colorscale='RdYlGn',
                text=pivot.values,
                texttemplate='%{text:.1f}',
                textfont={"size": 10},
            ))
            
            fig.update_layout(
                title='Optimization Heatmap: Score vs ADR & Max Exposure',
                xaxis_title='Max Exposure (%)',
                yaxis_title='ADR (%)',
                width=900,
                height=600
            )
            
            fig.write_html('optimization_heatmap.html')
            print("✅ Heatmap guardado en optimization_heatmap.html")
            
        except ImportError:
            print("⚠️  Plotly no disponible. Instala con: pip install plotly")


def main():
    import sys
    
    # Ejemplo de uso
    print("\n🎯 OPTIMIZADOR DE FILTROS ADR & MAX EXPOSURE")
    print("Este script encuentra la mejor combinación para maximizar ganancias\n")
    
    # Detectar modo
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        print("🚀 MODO RÁPIDO activado (menos combinaciones)\n")
        symbols = ['AAPL', 'NVDA', 'TSLA', 'META', 'PLTR', 'AMD']  # Solo 6 símbolos
        adr_range = [1.5, 2.5, 3.5]  # Solo 3 valores
        max_exp_range = [20, 30, 40]  # Solo 3 valores
        start_date = '2024-06-01'  # Período más corto
        end_date = '2024-12-20'
    else:
        print("⏱️  MODO COMPLETO (esto puede tardar 30-60 minutos)")
        print("💡 Tip: Usa --quick para prueba rápida (2-5 minutos)\n")
        
        # Preguntar confirmación
        response = input("¿Continuar con optimización completa? (y/n): ")
        if response.lower() != 'y':
            print("❌ Cancelado. Usa: python3 optimize_filters.py --quick")
            return
        
        # Símbolos a testear (ajusta según tu universo)
        symbols = ['MU', 'HYMC', 'KGC', 'B', 'CDE', 'CIEN', 'HL', 'IAG', 'ITRG', 'JBL', 'KRMN', 'LITE', 'NGD', 'PL', 'TE', 'TGB', 'VZLA', 'AEO', 'AG', 'AGI', 'ALAB', 'ARMN', 'AU', 'BENF', 'CENX', 'CGAU', 'CSTM', 'EQX', 'FIGR', 'FIGS', 'FLEX', 'GLW', 'HUT', 'LRCX', 'ONDS', 'ORLA', 'PPTA', 'COMM', 'GRAL', 'PACS', 'RKLB', 'STX', 'TTMI', 'ASTS', 'AUGO', 'COHR', 'TPC', 'DRD', 'APP', 'APH', 'FSLR', 'GOOGL', 'XME', 'TSLA', 'PLTR']
        
        # Rangos a probar
        adr_range = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]  # %
        max_exp_range = [15, 20, 25, 30, 35, 40]  # %
        start_date = '2024-01-01'
        end_date = '2024-12-20'
    
    print(f"Símbolos: {len(symbols)} | Combinaciones: {len(adr_range) * len(max_exp_range)}\n")
    
    # Crear optimizador
    optimizer = FilterOptimizer(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        equity=100000,
        risk_pct=0.5
    )
    
    # Ejecutar grid search
    results_df = optimizer.optimize_grid_search(adr_range, max_exp_range, verbose=True)
    
    # Mostrar mejores resultados
    optimizer.print_top_results(n=10)
    
    # Guardar resultados
    optimizer.save_results('optimization_results.csv')
    
    # Generar heatmap
    optimizer.plot_heatmap()
    
    print("\n✅ Optimización completada!")
    print("   Revisa 'optimization_results.csv' para análisis detallado")
    print("   Revisa 'optimization_heatmap.html' para visualización interactiva\n")


if __name__ == "__main__":
    main()
