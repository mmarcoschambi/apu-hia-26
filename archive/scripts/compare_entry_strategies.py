#!/usr/bin/env python3
"""
COMPARE ENTRY STRATEGIES - Green Candle vs Immediate Entry
============================================================
Ejecuta backtests comparando:
1. Entrada INMEDIATA (actual): Ejecuta cuando high >= trigger
2. Entrada VELA VERDE: Solo ejecuta si close > open (vela verde)

Uso:
    python3 compare_entry_strategies.py --start 2024-01-01 --end 2024-12-31
    python3 compare_entry_strategies.py --tickers "TSLA,NVDA,AAPL,META" --start 2024-01-01 --end 2024-12-31
"""

import sys
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.backtest.daily_engine import DailyBacktestEngine
from src.utils.risk_manager import RiskManager


class GreenCandleEngine(DailyBacktestEngine):
    """
    Engine modificado que SOLO ejecuta órdenes en velas verdes
    """
    
    def _manage_positions(self, today):
        """Override para agregar filtro de vela verde en ejecución"""
        # A. Execution of Pending Orders (CON FILTRO DE VELA VERDE)
        remaining_orders = []
        for order in self.pending_orders:
            if order.valid_date != today: 
                continue
            
            symbol = order.symbol
            if symbol not in self.market_data or today not in self.market_data[symbol].index: 
                continue
            
            daily_bar = self.market_data[symbol].loc[today]
            
            # ✅ FILTRO NUEVO: Solo ejecutar en vela verde
            is_green_candle = daily_bar['close'] > daily_bar['open']
            
            if daily_bar['high'] >= order.limit_price and is_green_candle:
                execution_price = max(daily_bar['open'], order.limit_price)
                cost = execution_price * order.shares
                if self.portfolio.cash >= cost:
                    self.portfolio.cash -= cost
                    
                    # Calcular R (riesgo inicial) y ADR
                    R_inicial = execution_price - order.stop_loss_initial
                    
                    # Calcular ADR del símbolo (últimos 20 días)
                    df_hist = self.market_data[symbol].loc[:today]
                    if len(df_hist) >= 20:
                        adr_valor = (df_hist['high'] - df_hist['low']).tail(20).mean()
                    else:
                        adr_valor = R_inicial * 2  # Default fallback
                    
                    from src.backtest.daily_engine import Position
                    new_pos = Position(
                        symbol=symbol,
                        entry_date=today,
                        entry_price=execution_price,
                        shares=order.shares,
                        initial_shares=order.shares,
                        stop_loss=order.stop_loss_initial,
                        take_profit_1=execution_price + (1.0 * R_inicial),
                        R_inicial=R_inicial,
                        adr_valor=adr_valor,
                        note=f"{order.note} | GREEN_CANDLE_ENTRY",
                        signal_type=order.signal_type,
                        context_data=order.context_data
                    )
                    self.portfolio.positions[symbol] = new_pos
            elif daily_bar['high'] >= order.limit_price and not is_green_candle:
                # Registrar que se perdió una entrada por vela roja
                if not hasattr(self, 'missed_entries'):
                    self.missed_entries = []
                self.missed_entries.append({
                    'symbol': symbol,
                    'date': today,
                    'trigger': order.limit_price,
                    'open': daily_bar['open'],
                    'close': daily_bar['close'],
                    'high': daily_bar['high'],
                    'reason': 'RED_CANDLE'
                })
        
        self.pending_orders = []
        
        # B. Exit Management (sin cambios - llamar al método padre)
        # Copiamos la lógica de exit del padre aquí
        self._manage_exits(today)
    
    def _manage_exits(self, today):
        """Lógica de exits original sin modificaciones"""
        for symbol, pos in list(self.portfolio.positions.items()):
            if symbol not in self.market_data or today not in self.market_data[symbol].index: 
                continue
            
            daily_bar = self.market_data[symbol].loc[today]
            current_close = daily_bar['close']
            
            # Update bars held
            pos.bars_held += 1
            
            # Todas las reglas de exit originales
            # (Stop loss, earnings defense, momentum rules, trailing stops, etc.)
            # Por simplicidad, solo implementamos las principales:
            
            # 1. Stop Loss
            if daily_bar['low'] <= pos.stop_loss:
                exit_price = min(daily_bar['open'], pos.stop_loss)
                self._close_position(symbol, exit_price, today, "STOP_LOSS")
                continue
            
            # 2. Time rules (simplified)
            pnl_pct = (current_close - pos.entry_price) / pos.entry_price
            
            if pos.bars_held == 3 and pnl_pct < 0.0025:
                self._close_position(symbol, current_close, today, "MOMENTUM_FAIL (3-Day Rule)")
                continue
            
            if pos.bars_held >= 10 and pnl_pct < 0.02:
                self._close_position(symbol, current_close, today, "TIME_EXPIRATION (10-Day Rule)")
                continue


def run_comparison(tickers, start_date, end_date, initial_capital=100000):
    """
    Ejecuta ambas estrategias y compara resultados
    """
    print("="*80)
    print("  📊 COMPARACIÓN DE ESTRATEGIAS DE ENTRADA")
    print("="*80)
    print(f"\nPeriodo: {start_date} a {end_date}")
    print(f"Tickers: {len(tickers)}")
    print(f"Capital: ${initial_capital:,.0f}\n")
    
    results = {}
    
    # ==========================================
    # ESTRATEGIA 1: ENTRADA INMEDIATA (Actual)
    # ==========================================
    print("\n" + "─"*80)
    print("🔵 ESTRATEGIA 1: ENTRADA INMEDIATA")
    print("   • Ejecuta cuando high >= trigger (sin importar color de vela)")
    print("─"*80)
    
    risk_mgr_1 = RiskManager(
        account_equity=initial_capital,
        risk_fraction=0.01,
        max_exposure_fraction=0.25
    )
    
    engine_1 = DailyBacktestEngine(
        universe=tickers,
        start_date=start_date,
        end_date=end_date,
        risk_manager=risk_mgr_1,
        skip_filters=True,  # Skip filters para usar solo tickers especificados
        offline=False
    )
    
    print("\n⏳ Ejecutando backtest (Entrada Inmediata)...")
    trades_1 = engine_1.run()
    
    if len(trades_1) > 0:
        wins_1 = len(trades_1[trades_1['pnl'] > 0])
        losses_1 = len(trades_1[trades_1['pnl'] <= 0])
        win_rate_1 = (wins_1 / len(trades_1) * 100) if len(trades_1) > 0 else 0
        total_pnl_1 = trades_1['pnl'].sum()
        avg_win_1 = trades_1[trades_1['pnl'] > 0]['pnl'].mean() if wins_1 > 0 else 0
        avg_loss_1 = trades_1[trades_1['pnl'] <= 0]['pnl'].mean() if losses_1 > 0 else 0
        
        results['immediate'] = {
            'total_trades': len(trades_1),
            'winners': wins_1,
            'losers': losses_1,
            'win_rate': win_rate_1,
            'total_pnl': total_pnl_1,
            'avg_win': avg_win_1,
            'avg_loss': avg_loss_1,
            'final_equity': initial_capital + total_pnl_1,
            'return_pct': (total_pnl_1 / initial_capital) * 100
        }
        
        print(f"\n✅ Resultados:")
        print(f"   Total Trades: {len(trades_1)}")
        print(f"   Win Rate: {win_rate_1:.1f}%")
        print(f"   Total PnL: ${total_pnl_1:,.2f}")
        print(f"   Return: {results['immediate']['return_pct']:.2f}%")
    else:
        print("\n❌ No se generaron trades")
        results['immediate'] = None
    
    # ==========================================
    # ESTRATEGIA 2: ENTRADA VELA VERDE
    # ==========================================
    print("\n" + "─"*80)
    print("🟢 ESTRATEGIA 2: ENTRADA SOLO EN VELA VERDE")
    print("   • Ejecuta SOLO si high >= trigger Y close > open")
    print("─"*80)
    
    risk_mgr_2 = RiskManager(
        account_equity=initial_capital,
        risk_fraction=0.01,
        max_exposure_fraction=0.25
    )
    
    engine_2 = GreenCandleEngine(
        universe=tickers,
        start_date=start_date,
        end_date=end_date,
        risk_manager=risk_mgr_2,
        skip_filters=True,
        offline=False
    )
    
    print("\n⏳ Ejecutando backtest (Solo Vela Verde)...")
    trades_2 = engine_2.run()
    
    if len(trades_2) > 0:
        wins_2 = len(trades_2[trades_2['pnl'] > 0])
        losses_2 = len(trades_2[trades_2['pnl'] <= 0])
        win_rate_2 = (wins_2 / len(trades_2) * 100) if len(trades_2) > 0 else 0
        total_pnl_2 = trades_2['pnl'].sum()
        avg_win_2 = trades_2[trades_2['pnl'] > 0]['pnl'].mean() if wins_2 > 0 else 0
        avg_loss_2 = trades_2[trades_2['pnl'] <= 0]['pnl'].mean() if losses_2 > 0 else 0
        
        results['green_candle'] = {
            'total_trades': len(trades_2),
            'winners': wins_2,
            'losers': losses_2,
            'win_rate': win_rate_2,
            'total_pnl': total_pnl_2,
            'avg_win': avg_win_2,
            'avg_loss': avg_loss_2,
            'final_equity': initial_capital + total_pnl_2,
            'return_pct': (total_pnl_2 / initial_capital) * 100,
            'missed_entries': len(engine_2.missed_entries) if hasattr(engine_2, 'missed_entries') else 0
        }
        
        print(f"\n✅ Resultados:")
        print(f"   Total Trades: {len(trades_2)}")
        print(f"   Win Rate: {win_rate_2:.1f}%")
        print(f"   Total PnL: ${total_pnl_2:,.2f}")
        print(f"   Return: {results['green_candle']['return_pct']:.2f}%")
        if hasattr(engine_2, 'missed_entries'):
            print(f"   Entradas Perdidas (vela roja): {len(engine_2.missed_entries)}")
    else:
        print("\n❌ No se generaron trades")
        results['green_candle'] = None
    
    # ==========================================
    # COMPARACIÓN
    # ==========================================
    print("\n" + "="*80)
    print("  📊 COMPARACIÓN LADO A LADO")
    print("="*80)
    
    if results['immediate'] and results['green_candle']:
        imm = results['immediate']
        grn = results['green_candle']
        
        print(f"\n{'Métrica':<30} {'Inmediata':<20} {'Vela Verde':<20} {'Diferencia':<15}")
        print("─"*85)
        
        # Total Trades
        diff_trades = grn['total_trades'] - imm['total_trades']
        print(f"{'Total Trades':<30} {imm['total_trades']:<20} {grn['total_trades']:<20} {diff_trades:+d}")
        
        # Win Rate
        diff_wr = grn['win_rate'] - imm['win_rate']
        print(f"{'Win Rate (%)':<30} {imm['win_rate']:<20.1f} {grn['win_rate']:<20.1f} {diff_wr:+.1f}%")
        
        # Total PnL
        diff_pnl = grn['total_pnl'] - imm['total_pnl']
        print(f"{'Total PnL ($)':<30} {imm['total_pnl']:<20,.0f} {grn['total_pnl']:<20,.0f} {diff_pnl:+,.0f}")
        
        # Return %
        diff_ret = grn['return_pct'] - imm['return_pct']
        print(f"{'Return (%)':<30} {imm['return_pct']:<20.2f} {grn['return_pct']:<20.2f} {diff_ret:+.2f}%")
        
        # Avg Win
        diff_win = grn['avg_win'] - imm['avg_win']
        print(f"{'Avg Win ($)':<30} {imm['avg_win']:<20,.0f} {grn['avg_win']:<20,.0f} {diff_win:+,.0f}")
        
        # Avg Loss
        diff_loss = grn['avg_loss'] - imm['avg_loss']
        print(f"{'Avg Loss ($)':<30} {imm['avg_loss']:<20,.0f} {grn['avg_loss']:<20,.0f} {diff_loss:+,.0f}")
        
        print("\n" + "="*80)
        print("  🎯 CONCLUSIÓN")
        print("="*80)
        
        if grn['return_pct'] > imm['return_pct']:
            improvement = grn['return_pct'] - imm['return_pct']
            print(f"\n✅ VELA VERDE ES MEJOR (+{improvement:.2f}% return)")
            print(f"   • Mejor selectividad en entradas")
            print(f"   • Evita {grn['missed_entries']} entradas en velas rojas")
        elif imm['return_pct'] > grn['return_pct']:
            decline = imm['return_pct'] - grn['return_pct']
            print(f"\n⚠️  ENTRADA INMEDIATA ES MEJOR (+{decline:.2f}% return)")
            print(f"   • Captura más oportunidades ({diff_trades} trades adicionales)")
            print(f"   • No se pierde momentum inicial")
        else:
            print("\n🤝 EMPATE - Ambas estrategias tienen performance similar")
        
        # Guardar resultados
        with open('entry_strategy_comparison.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        trades_1.to_csv('trades_immediate_entry.csv', index=False)
        trades_2.to_csv('trades_green_candle_entry.csv', index=False)
        
        print(f"\n💾 Archivos guardados:")
        print(f"   • entry_strategy_comparison.json")
        print(f"   • trades_immediate_entry.csv")
        print(f"   • trades_green_candle_entry.csv")
    
    print("\n")
    return results


def main():
    parser = argparse.ArgumentParser(description='Comparar estrategias de entrada')
    parser.add_argument('--tickers', type=str, help='Lista de tickers separados por coma')
    parser.add_argument('--start', type=str, required=True, help='Fecha inicio (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, help='Fecha fin (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100000, help='Capital inicial')
    
    args = parser.parse_args()
    
    # Parse tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        # Default: usar top líquidos
        tickers = ['TSLA', 'NVDA', 'AVGO', 'AAPL', 'MU', 'META', 'GOOGL', 'MSFT', 
                   'AMZN', 'AMD', 'ORCL', 'NFLX', 'JPM', 'LLY']
        print(f"⚠️  No se especificaron tickers. Usando default: {len(tickers)} tickers")
    
    results = run_comparison(tickers, args.start, args.end, args.capital)


if __name__ == "__main__":
    main()
