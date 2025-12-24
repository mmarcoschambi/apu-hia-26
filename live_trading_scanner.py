#!/usr/bin/env python3
"""
LIVE TRADING SCANNER - Pre-Market & Intraday
Daily scanner que ejecutas cada mañana antes de la apertura

Usage:
    python live_trading_scanner.py                    # Scan acciones_activas.csv
    python live_trading_scanner.py AAPL NVDA TSLA     # Scan símbolos específicos
    python live_trading_scanner.py --monitor          # Monitor continuo durante RTH
"""
import sys
import time
import json
from pathlib import Path
from datetime import datetime, time as dt_time
import pandas as pd
from typing import List, Dict
import argparse

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.scanner import TriadScanner
from src.data.market_data import MarketDataProvider


class LiveTradingScanner:
    """Scanner para trading real con output optimizado para decisiones rápidas"""
    
    def __init__(self):
        self.scanner = TriadScanner()
        self.data_provider = MarketDataProvider()
        self.results_file = project_root / "live_scan_results.json"
        self.alerts_file = project_root / "live_alerts.txt"
        
    def scan_watchlist(self, symbols: List[str]) -> List[Dict]:
        """Escanea watchlist y retorna setups accionables"""
        print(f"\n{'='*80}")
        print(f"🔍 LIVE TRADING SCANNER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        print(f"📋 Scanning {len(symbols)} symbols...\n")
        
        results = []
        actionable_setups = []
        
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/{len(symbols)}] {symbol}...", end=" ", flush=True)
            
            try:
                result = self.scanner.scan_symbol(symbol)
                results.append(result)
                
                # Filtrar solo setups accionables
                if result.get('signal') and result['signal'].action in ['BUY_STOP', 'MANUAL_WATCH']:
                    actionable_setups.append(result)
                    print("✅ SETUP FOUND!")
                else:
                    print("—")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
                results.append({'symbol': symbol, 'error': str(e)})
        
        # Guardar resultados
        self._save_results(results, actionable_setups)
        
        # Mostrar resumen
        self._print_summary(actionable_setups)
        
        return actionable_setups
    
    def _print_summary(self, setups: List[Dict]):
        """Print actionable summary for quick decision making"""
        
        if not setups:
            print(f"\n{'='*80}")
            print("⚠️  NO ACTIONABLE SETUPS")
            print("This is normal - the system waits for high-probability opportunities.")
            print(f"{'='*80}\n")
            return
        
        print(f"\n{'='*80}")
        print(f"🎯 ACTIONABLE SETUPS ({len(setups)} found)")
        print(f"{'='*80}\n")
        
        # Separar por tipo
        buy_stops = [s for s in setups if s['signal'].action == 'BUY_STOP']
        manual_watches = [s for s in setups if s['signal'].action == 'MANUAL_WATCH']
        
        if buy_stops:
            print("📍 BUY STOP ORDERS (Place now, execute automatically):")
            print("-" * 80)
            for setup in buy_stops:
                self._print_setup_card(setup)
        
        if manual_watches:
            print("\n👀 MANUAL WATCH (Monitor during market hours):")
            print("-" * 80)
            for setup in manual_watches:
                self._print_setup_card(setup)
        
        print(f"\n{'='*80}")
        print("💾 Results saved to: live_scan_results.json")
        print("📝 Alerts saved to: live_alerts.txt")
        print(f"{'='*80}\n")
    
    def _print_setup_card(self, setup: Dict):
        """Print compact setup card"""
        signal = setup['signal']
        symbol = setup['symbol']
        
        print(f"\n🔹 {symbol} - {signal.camino.name if signal.camino else 'UNKNOWN'}")
        print(f"   Entry:  ${signal.entry_price:.2f}" if signal.entry_price else "   Entry:  TBD")
        print(f"   Stop:   ${signal.stop_loss:.2f}" if signal.stop_loss else "   Stop:   TBD")
        
        if signal.entry_price and signal.stop_loss:
            risk_per_share = signal.entry_price - signal.stop_loss
            risk_pct = (risk_per_share / signal.entry_price) * 100
            print(f"   Risk:   {risk_pct:.2f}% (${risk_per_share:.2f}/share)")
        
        print(f"   Size:   {signal.position_size_multiplier*100:.0f}% of standard")
        print(f"   📋 {signal.reasoning[:70]}...")
        
        # Quick action items
        if signal.action == 'BUY_STOP':
            print(f"   ⚡ ACTION: Place Buy Stop at ${signal.entry_price:.2f}")
        else:
            print(f"   ⚡ ACTION: Watch for VWAP reclaim during market hours")
    
    def _save_results(self, all_results: List[Dict], actionable: List[Dict]):
        """Save results to file for later reference"""
        
        # JSON para programmatic access
        save_data = {
            'timestamp': datetime.now().isoformat(),
            'total_scanned': len(all_results),
            'actionable_count': len(actionable),
            'setups': []
        }
        
        for setup in actionable:
            signal = setup['signal']
            save_data['setups'].append({
                'symbol': setup['symbol'],
                'camino': signal.camino.name if signal.camino else None,
                'action': signal.action,
                'entry_price': signal.entry_price,
                'stop_loss': signal.stop_loss,
                'position_multiplier': signal.position_size_multiplier,
                'reasoning': signal.reasoning
            })
        
        with open(self.results_file, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        # TXT para quick reference
        with open(self.alerts_file, 'w') as f:
            f.write(f"LIVE TRADING ALERTS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
            
            if not actionable:
                f.write("No actionable setups found.\n")
            else:
                for setup in actionable:
                    signal = setup['signal']
                    f.write(f"{setup['symbol']} - {signal.camino.name if signal.camino else 'N/A'}\n")
                    f.write(f"  Action: {signal.action}\n")
                    if signal.entry_price:
                        f.write(f"  Entry: ${signal.entry_price:.2f}\n")
                    if signal.stop_loss:
                        f.write(f"  Stop: ${signal.stop_loss:.2f}\n")
                    f.write(f"  Reasoning: {signal.reasoning}\n")
                    f.write("\n" + "-"*80 + "\n\n")
    
    def monitor_mode(self, symbols: List[str], interval_minutes: int = 15):
        """
        Monitor mode: Continuamente escanea durante RTH
        Útil para Camino 2 (VWAP Reclaim) que requiere timing preciso
        """
        print(f"\n{'='*80}")
        print("🔴 LIVE MONITOR MODE")
        print(f"Rescanning every {interval_minutes} minutes during market hours")
        print("Press Ctrl+C to stop")
        print(f"{'='*80}\n")
        
        try:
            while True:
                now = datetime.now().time()
                
                # Solo durante RTH (9:30 AM - 4:00 PM ET)
                market_open = dt_time(9, 30)
                market_close = dt_time(16, 0)
                
                if market_open <= now <= market_close:
                    print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} - Scanning...")
                    self.scan_watchlist(symbols)
                    print(f"\n💤 Next scan in {interval_minutes} minutes...")
                    time.sleep(interval_minutes * 60)
                else:
                    print(f"⏸️  Outside market hours. Waiting...")
                    time.sleep(300)  # Check every 5 min
                    
        except KeyboardInterrupt:
            print("\n\n✋ Monitor stopped by user.")


def load_watchlist_from_file() -> List[str]:
    """Load watchlist from acciones_activas.csv or default"""
    watchlist_file = project_root / "acciones_activas.csv"
    
    if watchlist_file.exists():
        try:
            df = pd.read_csv(watchlist_file)
            return df['Ticker'].tolist()
        except Exception as e:
            print(f"⚠️  Error reading {watchlist_file}: {e}")
    
    # Fallback
    return ['AAPL', 'NVDA', 'TSLA', 'GOOGL', 'META', 'MSFT']


def main():
    parser = argparse.ArgumentParser(description='Live Trading Scanner')
    parser.add_argument('symbols', nargs='*', help='Symbols to scan (optional)')
    parser.add_argument('--monitor', action='store_true', help='Continuous monitoring mode')
    parser.add_argument('--interval', type=int, default=15, help='Monitor interval in minutes')
    
    args = parser.parse_args()
    
    # Determinar watchlist
    if args.symbols:
        watchlist = args.symbols
    else:
        watchlist = load_watchlist_from_file()
    
    scanner = LiveTradingScanner()
    
    if args.monitor:
        scanner.monitor_mode(watchlist, interval_minutes=args.interval)
    else:
        scanner.scan_watchlist(watchlist)


if __name__ == "__main__":
    main()
