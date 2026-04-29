#!/usr/bin/env python3
"""Backtest simplificado optimizado para diagnóstico"""

import sys
import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("simplified_backtest")

def get_sp500_universe():
    """Carga solo los tickers del S&P 500"""
    file_path = Path("sp500_tickers_since_2014.txt")
    if not file_path.exists():
        return []
    
    with open(file_path, 'r') as f:
        tickers = [line.strip() for line in f if line.strip()]
    
    conn = sqlite3.connect('data/ticker_cache.db')
    cursor = conn.execute("SELECT DISTINCT ticker FROM ohlcv_cache")
    available = set([row[0] for row in cursor.fetchall()])
    conn.close()
    
    return [t for t in tickers if t in available]

def calculate_atr(high_df, low_df, close_df, period=14):
    """Calculate ATR (Average True Range)"""
    high = high_df.values
    low = low_df.values
    close = close_df.values
    
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    tr = np.maximum.reduce([tr1, tr2, tr3], axis=0)
    tr[0] = 0  # First TR is NaN
    
    atr = pd.DataFrame(tr, index=close_df.index, columns=close_df.columns).rolling(period).mean()
    return atr

def simplified_simulation(engine, entries):
    """
    Simulación simplificada sin todos los filtros complejos.
    OPTIMIZADO: Vectorizado y sin bucles anidados excesivos.
    """
    logger.info("⚡ Ejecutando simulación simplificada...")
    
    cash = engine.initial_capital
    equity_curve = []
    positions = {}  # {ticker: {'shares': X, 'entry_price': Y, 'stop_price': Z}}
    trade_log = []
    
    # Calcular ATR
    atr_df = calculate_atr(engine.high, engine.low, engine.close, 14)
    
    # Convertir a numpy arrays para acceso rápido
    close_arr = engine.close.values
    high_arr = engine.high.values
    low_arr = engine.low.values
    atr_arr = atr_df.values
    
    # Filtrar solo fechas de backtest
    backtest_start = engine.start_date
    entries_backtest = entries[entries.index >= backtest_start]
    entries_arr = entries_backtest.values
    dates = entries_backtest.index
    
    ticker_to_idx = {ticker: idx for idx, ticker in enumerate(engine.close.columns)}
    num_tickers = len(engine.close.columns)
    
    logger.info(f"   • Fechas a simular: {len(dates)}")
    logger.info(f"   • Tickers: {num_tickers}")
    
    for i, date in enumerate(dates):
        # Obtener datos del día
        day_close = close_arr[i]
        day_high = high_arr[i]
        day_low = low_arr[i]
        day_atr = atr_arr[i]
        day_entries = entries_arr[i]
        
        # === PROCESAR SALIDAS (EXITS) ===
        for ticker, pos in list(positions.items()):
            ticker_idx = ticker_to_idx.get(ticker)
            if ticker_idx is None:
                continue
            
            current_price = day_close[ticker_idx]
            if pd.isna(current_price):
                continue
            
            entry_price = pos['entry_price']
            shares = pos['shares']
            stop_price = pos['stop_price']
            r_value = pos.get('r_value', 1.0)
            
            # Stop Loss
            if day_low[ticker_idx] <= stop_price:
                exit_price = stop_price
                pnl = (exit_price - entry_price) * shares
                cash += exit_price * shares
                
                trade_log.append({
                    'ticker': ticker,
                    'entry_date': pos['entry_date'],
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'shares': shares,
                    'pnl': pnl,
                    'exit_phase': 'STOP'
                })
                
                del positions[ticker]
                continue
            
            # Take Profit (2R)
            tp_price = entry_price + (r_value * 2.0)
            if day_high[ticker_idx] >= tp_price:
                exit_price = tp_price
                pnl = (exit_price - entry_price) * shares
                cash += exit_price * shares
                
                trade_log.append({
                    'ticker': ticker,
                    'entry_date': pos['entry_date'],
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'shares': shares,
                    'pnl': pnl,
                    'exit_phase': 'TP_2R'
                })
                
                del positions[ticker]
                continue
        
        # === PROCESAR ENTRADAS (ENTRIES) ===
        # OPTIMIZACIÓN: Solo iterar sobre índices con entries
        entry_indices = np.where(day_entries)[0]
        
        for ticker_idx in entry_indices:
            ticker = engine.close.columns[ticker_idx]
            if ticker in positions:
                continue  # Ya tiene posición
            
            entry_price = day_close[ticker_idx]
            if pd.isna(entry_price):
                continue
            
            # Calcular stop loss
            r_value = day_atr[ticker_idx]
            if pd.isna(r_value) or r_value <= 0:
                continue
            
            stop_price = entry_price - (r_value * 1.5)  # 1.5ATR stop
            
            # Calcular tamaño de posición
            risk_per_share = entry_price - stop_price
            if risk_per_share <= 0:
                continue
            
            shares = int(150 / risk_per_share)  # $150 riesgo fijo
            if shares < 1:
                continue
            
            position_value = shares * entry_price
            if cash < position_value:
                continue  # No tiene suficiente cash
            
            # Abrir posición
            cash -= position_value
            positions[ticker] = {
                'shares': shares,
                'entry_price': entry_price,
                'entry_date': date,
                'stop_price': stop_price,
                'r_value': r_value
            }
        
        # Calcular equity del día
        positions_value = 0
        for ticker, pos in positions.items():
            ticker_idx = ticker_to_idx.get(ticker)
            if ticker_idx >= 0:
                positions_value += pos['shares'] * day_close[ticker_idx]
        
        equity_curve.append(cash + positions_value)
    
    # Cerrar posiciones abiertas al final
    for ticker, pos in positions.items():
        ticker_idx = ticker_to_idx.get(ticker)
        if ticker_idx is None or ticker_idx < 0:
            continue
            
        final_price = close_arr[-1][ticker_idx]
        if pd.isna(final_price):
            final_price = pos['entry_price']
        
        pnl = (final_price - pos['entry_price']) * pos['shares']
        cash += final_price * pos['shares']
        
        trade_log.append({
            'ticker': ticker,
            'entry_date': pos['entry_date'],
            'exit_date': dates[-1],
            'entry_price': pos['entry_price'],
            'exit_price': final_price,
            'shares': pos['shares'],
            'pnl': pnl,
            'exit_phase': 'EOD'
        })
    
    return pd.DataFrame(trade_log), pd.Series(equity_curve, index=dates)

def main():
    universe = get_sp500_universe()[:100]  # 100 tickers para velocidad
    start_date = "2023-01-01"
    end_date = "2023-06-30"  # 6 meses
    
    print("="*80)
    print("🎯 BACKTEST SIMPLIFICADO - DIAGNÓSTICO")
    print("="*80)
    print(f"   • Tickers: {len(universe)}")
    print(f"   • Periodo: {start_date} a {end_date}")
    
    params = {
        'initial_capital': 100000,
        'risk_dollars': 150,
        'min_rvol': 1.5,
        'min_adr': 2.0,
        'min_dollar_volume': 1_000_000,
        'use_adaptive_filtering': False,
        'use_market_regime_filter': False,
        'require_spy_above_sma50': False,
        'offline_mode': True
    }
    
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        **params
    )
    
    print("\n📥 Cargando datos...")
    close_df = engine.load_data()
    
    print(f"✅ Datos cargados: {len(close_df.columns)} tickers, {len(close_df)} días")
    
    # Calcular entries
    safe_sma20 = engine.sma_20.fillna(0)
    safe_avg_vol = engine.avg_volume_20.fillna(1)
    
    entries = (
        (engine.close > safe_sma20) &
        (engine.volume > safe_avg_vol * 1.5)
    )
    
    total_entries = entries.sum().sum()
    print(f"🎯 Entries calculadas: {total_entries:,}")
    
    # Ejecutar simulación
    trades_df, equity_curve = simplified_simulation(engine, entries)
    
    # Resultados
    print("\n" + "="*80)
    print("📊 RESULTADOS")
    print("="*80)
    
    if trades_df.empty:
        print("❌ 0 trades generados")
    else:
        print(f"✅ {len(trades_df)} trades generados")
        
        total_pnl = trades_df['pnl'].sum()
        win_rate = len(trades_df[trades_df['pnl'] > 0]) / len(trades_df) * 100
        avg_pnl = trades_df['pnl'].mean()
        max_win = trades_df['pnl'].max()
        max_loss = trades_df['pnl'].min()
        
        print(f"   • Total PnL: ${total_pnl:,.2f}")
        print(f"   • Win Rate: {win_rate:.1f}%")
        print(f"   • Avg PnL/trade: ${avg_pnl:.2f}")
        print(f"   • Max Win: ${max_win:,.2f}")
        print(f"   • Max Loss: ${max_loss:,.2f}")
        
        # Equity curve
        print(f"\n📈 Equity Curve:")
        print(f"   • Inicial: ${equity_curve.iloc[0]:,.2f}")
        print(f"   • Final: ${equity_curve.iloc[-1]:,.2f}")
        print(f"   • Return: {(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100:.2f}%")
        print(f"   • Max DD: {(equity_curve / equity_curve.cummax() - 1).min() * 100:.2f}%")
        
        # Por fase de salida
        print(f"\n🎯 Salidas por fase:")
        exit_counts = trades_df['exit_phase'].value_counts()
        for phase, count in exit_counts.items():
            avg_pnl_phase = trades_df[trades_df['exit_phase'] == phase]['pnl'].mean()
            print(f"   • {phase}: {count} trades, avg PnL: ${avg_pnl_phase:.2f}")

if __name__ == "__main__":
    main()
