#!/usr/bin/env python3
"""
Quick Diagnostics - 30 Second Health Check
===========================================

Diagnóstico rápido del backtest:
- Winners vs Losers comparison
- Identificación de problemas  
- Métricas por rango

Uso: python3 quick_diagnostics.py [--file path/to/trade_log.csv]
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sys
import argparse

def find_latest_trade_log():
    """Busca automáticamente el trade_log más reciente."""
    search_paths = [
        Path('outputs/backtests/trade_log.csv'),
        Path('trade_log.csv'),
    ]
    
    # Buscar archivos con timestamp
    backtest_dir = Path('outputs/backtests')
    if backtest_dir.exists():
        timestamped = list(backtest_dir.glob('*trade_log*.csv'))
        if timestamped:
            latest = max(timestamped, key=lambda p: p.stat().st_mtime)
            return latest
    
    # Buscar en paths estándar
    for path in search_paths:
        if path.exists():
            return path
    
    return None

def load_trades(filepath=None):
    """Carga el trade log, buscando automáticamente si no se especifica."""
    if filepath:
        path = Path(filepath)
    else:
        path = find_latest_trade_log()
    
    if path is None or not path.exists():
        print("❌ No se encontró trade_log.csv")
        print("\n💡 Ejecuta un backtest primero o especifica el archivo:")
        print("   python3 quick_diagnostics.py --file mi_archivo.csv")
        sys.exit(1)
    
    print(f"📂 Cargando: {path}")
    print(f"   Modificado: {datetime.fromtimestamp(path.stat().st_mtime)}")
    
    df = pd.read_csv(path)
    print(f"   Eventos: {len(df)}\n")
    
    # Group by trade if needed
    if 'exit_phase' in df.columns:
        # Group partial exits
        grouped = df.groupby(['ticker', 'entry_date']).agg({
            'pnl': 'sum',
            'entry_date': 'first',
            'exit_date': 'last',
            'dist_sma20_pct': 'first',
            'consolidation_days': 'first',
            'context_rvol': 'first',
            'context_adr': 'first',
            'sector_strength': 'first',
        }).reset_index(drop=True)
        
        grouped['is_winner'] = grouped['pnl'] > 0
        grouped['r_multiple'] = grouped['pnl'] / 100  # Approximate
        
        print(f"   ✅ Agrupados en {len(grouped)} trades completos\n")
        return grouped, path
    
    return df, path

def quick_diagnostics(df):
    """Diagnóstico rápido de 30 segundos."""
    
    print("="*80)
    print("🔍 QUICK DIAGNOSTICS - BACKTEST HEALTH CHECK")
    print("="*80)
    print(f"Total Trades: {len(df)}\n")
    
    # === 1. OVERALL METRICS ===
    print("📊 OVERALL METRICS:")
    print("-"*80)
    
    winners = df[df['is_winner'] == True] if 'is_winner' in df.columns else df[df['pnl'] > 0]
    losers = df[df['is_winner'] == False] if 'is_winner' in df.columns else df[df['pnl'] <= 0]
    
    win_rate = len(winners) / len(df) * 100 if len(df) > 0 else 0
    avg_r = df['r_multiple'].mean() if 'r_multiple' in df.columns else 0
    pnl = df['pnl'].sum() if 'pnl' in df.columns else 0
    
    print(f"Win Rate:        {win_rate:.1f}%")
    print(f"Winners/Losers:  {len(winners)} / {len(losers)}")
    print(f"Avg R-Multiple:  {avg_r:+.2f}R")
    print(f"Total PnL:       ${pnl:,.2f}\n")
    
    # === 2. WINNERS VS LOSERS ===
    print("⚖️  WINNERS VS LOSERS COMPARISON:")
    print("-"*80)
    
    metrics_to_compare = [
        ('dist_sma20_pct', 'Distance from SMA20', '%'),
        ('consolidation_days', 'Consolidation Days', 'd'),
        ('context_rvol', 'RVOL', 'x'),
        ('context_adr', 'ADR', '%'),
        ('sector_strength', 'Sector Strength', ''),
    ]
    
    for col, label, unit in metrics_to_compare:
        if col in df.columns:
            win_avg = winners[col].mean()
            lose_avg = losers[col].mean()
            diff = win_avg - lose_avg
            diff_pct = (diff / lose_avg * 100) if lose_avg != 0 else 0
            
            # Diagnóstico
            if abs(diff_pct) < 5:
                status = "⚪ NO DIFERENCIA"
            elif diff_pct > 10:
                status = "🟢 WINNERS MAYORES"
            elif diff_pct < -10:
                status = "🔴 LOSERS MAYORES"
            else:
                status = "🟡 LEVE DIFERENCIA"
            
            print(f"{label:25s}: Winners={win_avg:7.2f}{unit}  "
                 f"Losers={lose_avg:7.2f}{unit}  "
                 f"Diff={diff_pct:+6.1f}%  {status}")
    
    print()
    
    # === 3. PROBLEMAS IDENTIFICADOS ===
    print("⚠️  POTENTIAL ISSUES:")
    print("-"*80)
    
    issues = []
    
    # Check 1: Win rate muy bajo
    if win_rate < 35:
        issues.append(f"🔴 Win Rate muy bajo ({win_rate:.1f}%) - Objetivo: >40%")
    
    # Check 2: R-multiple negativo
    if avg_r < 0:
        issues.append(f"🔴 Avg R-Multiple negativo ({avg_r:.2f}R) - Sistema no rentable")
    
    # Check 3: Profit Factor
    gross_win = winners['pnl'].sum() if 'pnl' in winners.columns else 0
    gross_loss = abs(losers['pnl'].sum()) if 'pnl' in losers.columns else 0
    pf = gross_win / gross_loss if gross_loss > 0 else 0
    if pf < 1.0:
        issues.append(f"�� Profit Factor < 1.0 ({pf:.2f}) - Perdiendo dinero")
    elif pf < 1.5:
        issues.append(f"🟡 Profit Factor bajo ({pf:.2f}) - Objetivo: >1.5")
    
    # Check 4: RVOL issues
    if 'context_rvol' in df.columns:
        # Note: RVOL shown as huge numbers suggests wrong calculation
        if df['context_rvol'].mean() > 100:
            issues.append("🔴 RVOL tiene valores enormes - Posible bug en cálculo")
            issues.append(f"   Promedio: {df['context_rvol'].mean():,.0f}x (debería ser 1-5x)")
    
    # Check 5: Muy pocos trades
    if len(df) < 50:
        issues.append(f"🟡 Pocos trades ({len(df)}) - Difícil sacar conclusiones")
    
    if issues:
        for issue in issues:
            print(issue)
    else:
        print("✅ No se detectaron problemas obvios")
    
    print()
    
    # === 4. RECOMMENDATIONS ===
    print("💡 RECOMMENDATIONS:")
    print("-"*80)
    
    if 'context_rvol' in df.columns and df['context_rvol'].mean() > 100:
        print("🔧 FIX RVOL: Revisa cálculo de RVOL en el motor")
        print("   RVOL = Volume_Today / Avg_Volume_20d (debería ser 1-5x)")
    
    if win_rate < 40:
        print("🎯 Ajusta filtros para MAYOR selectividad:")
        print("   - Aumenta min_rvol (prueba 2.0x)")
        print("   - Reduce max_dist_sma20 (prueba 7%)")
        print("   - Aumenta min_consolidation_days (prueba 15d)")
    
    if avg_r < 0.5:
        print("💰 Mejora R/R ratio:")
        print("   - Revisa stops (¿muy apretados?)")
        print("   - Revisa targets (¿muy conservadores?)")
    
    if pf < 1.5:
        print("📈 Aumenta Profit Factor:")
        print("   - Deja correr ganadores (trailing stops)")
        print("   - Corta perdedores más rápido")
    
    print()
    print("="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Fix issues identificados arriba")
    print("2. Run: python3 scripts/optimization/range_finder.py")
    print("="*80)

def main():
    parser = argparse.ArgumentParser(description='Quick backtest diagnostics')
    parser.add_argument('--file', type=str, help='Path to trade_log.csv')
    args = parser.parse_args()
    
    # Load trades
    df, source_path = load_trades(args.file)
    
    # Run diagnostics
    quick_diagnostics(df)
    
    print("\n✅ Diagnóstico completo!")

if __name__ == '__main__':
    main()
