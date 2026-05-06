#!/usr/bin/env python3
"""
LIVE TRADING SCANNER - Pre-Market & Intraday
Daily scanner que ejecutas cada mañana antes de la apertura

Usage:
    python live_trading_scanner.py                    # Scan outputs/backtests/acciones_activas.csv
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

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

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
        
        console.clear()
        console.print(Panel(
            f"[bold cyan]Scanning {len(symbols)} symbols...[/bold cyan]", 
            title=f"[bold magenta]🔍 LIVE TRADING SCANNER - {datetime.now().strftime('%H:%M:%S')}[/bold magenta]", 
            border_style="bright_blue", box=box.ROUNDED
        ))
        
        results = []
        actionable_setups = []
        
        with console.status("[bold green]Scanning market data...") as status:
            for i, symbol in enumerate(symbols, 1):
                status.update(f"[bold green]Scanning market data... ({i}/{len(symbols)}) [yellow]{symbol}[/yellow]")
                
                try:
                    result = self.scanner.scan_symbol(symbol)
                    results.append(result)
                    
                    # Filtrar solo setups accionables
                    if result.get('signal') and result['signal'].action in ['BUY_STOP', 'MANUAL_WATCH']:
                        actionable_setups.append(result)
                        console.print(f"[green]✅ {symbol}: SETUP FOUND![/green]")
                        
                except Exception as e:
                    console.print(f"[red]❌ Error on {symbol}: {e}[/red]")
                    results.append({'symbol': symbol, 'error': str(e)})
        
        # Guardar resultados
        self._save_results(results, actionable_setups)
        
        # Mostrar resumen
        self._print_summary(actionable_setups)
        
        return actionable_setups
    
    def _print_summary(self, setups: List[Dict]):
        """Print actionable summary for quick decision making using Rich"""
        
        console.print("\n")
        
        if not setups:
            console.print(Panel(
                "[yellow]This is normal - the system waits for high-probability opportunities.[/yellow]", 
                title="[bold yellow]⚠️ NO ACTIONABLE SETUPS FOUND[/bold yellow]", 
                border_style="yellow", box=box.ROUNDED
            ))
            return
            
        console.print(Panel(
            f"[bold green]Found {len(setups)} actionable setups ready for review.[/bold green]", 
            title="[bold green]🎯 ACTIONABLE SETUPS[/bold green]", 
            border_style="green", box=box.ROUNDED
        ))
        
        # Separar por tipo
        buy_stops = [s for s in setups if s['signal'].action == 'BUY_STOP']
        manual_watches = [s for s in setups if s['signal'].action == 'MANUAL_WATCH']
        
        if buy_stops:
            table = Table(title="[bold cyan]📍 BUY STOP ORDERS (Place now, execute automatically)[/bold cyan]", box=box.SIMPLE_HEAD)
            table.add_column("Symbol", style="bold yellow")
            table.add_column("Setup", style="magenta")
            table.add_column("Entry", justify="right", style="green")
            table.add_column("Stop", justify="right", style="red")
            table.add_column("Risk %", justify="right", style="bright_red")
            table.add_column("Size", justify="right", style="cyan")
            table.add_column("Action", style="bold bright_green")
            
            for setup in buy_stops:
                signal = setup['signal']
                risk_pct = 0.0
                if signal.entry_price and signal.stop_loss:
                    risk_pct = ((signal.entry_price - signal.stop_loss) / signal.entry_price) * 100
                    
                table.add_row(
                    setup['symbol'],
                    signal.camino.name if signal.camino else 'UNKNOWN',
                    f"${signal.entry_price:.2f}" if signal.entry_price else "TBD",
                    f"${signal.stop_loss:.2f}" if signal.stop_loss else "TBD",
                    f"{risk_pct:.2f}%",
                    f"{signal.position_size_multiplier*100:.0f}%",
                    f"Buy Stop @ ${signal.entry_price:.2f}"
                )
            console.print(table)
            
        if manual_watches:
            table = Table(title="[bold yellow]👀 MANUAL WATCH (Monitor during market hours)[/bold yellow]", box=box.SIMPLE_HEAD)
            table.add_column("Symbol", style="bold yellow")
            table.add_column("Setup", style="magenta")
            table.add_column("Entry", justify="right", style="green")
            table.add_column("Stop", justify="right", style="red")
            table.add_column("Action", style="bold yellow")
            
            for setup in manual_watches:
                signal = setup['signal']
                table.add_row(
                    setup['symbol'],
                    signal.camino.name if signal.camino else 'UNKNOWN',
                    f"${signal.entry_price:.2f}" if signal.entry_price else "TBD",
                    f"${signal.stop_loss:.2f}" if signal.stop_loss else "TBD",
                    "Watch for VWAP reclaim"
                )
            console.print(table)
            
        console.print("\n[dim]💾 Results saved to: live_scan_results.json | 📝 Alerts saved to: live_alerts.txt[/dim]\n")
        
    def _print_setup_card(self, setup: Dict):
        # Obsolete, replaced by rich table in _print_summary
        pass
    
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
        console.clear()
        console.print(Panel(
            f"[bold green]Rescanning {len(symbols)} symbols every {interval_minutes} minutes during market hours[/bold green]\n[dim]Press Ctrl+C to stop[/dim]", 
            title="[bold red]🔴 LIVE MONITOR MODE ACTIVATED[/bold red]", 
            border_style="red", box=box.HEAVY
        ))
        
        try:
            while True:
                now = datetime.now().time()
                
                # Solo durante RTH (9:30 AM - 4:00 PM ET)
                market_open = dt_time(9, 30)
                market_close = dt_time(16, 0)
                
                if market_open <= now <= market_close:
                    self.scan_watchlist(symbols)
                    
                    next_scan = datetime.now() + pd.Timedelta(minutes=interval_minutes)
                    with console.status(f"[bold blue]💤 Sleeping... Next scan at {next_scan.strftime('%H:%M:%S')} (in {interval_minutes} minutes)[/bold blue]") as status:
                        time.sleep(interval_minutes * 60)
                else:
                    with console.status(f"[bold yellow]⏸️  Outside market hours. Waiting for 9:30 AM ET...[/bold yellow]") as status:
                        time.sleep(300)  # Check every 5 min
                    
        except KeyboardInterrupt:
            console.print("\n\n[bold red]✋ Monitor stopped by user.[/bold red]")


def load_watchlist_from_file() -> List[str]:
    """Load dynamic daily watchlist from Finviz snapshot, fallback to CSV or default"""
    
    # 1. Try to load from today's Finviz snapshot first
    today_str = datetime.now().strftime("%Y-%m-%d")
    snapshot_file = project_root / "outputs" / "paper_finviz" / today_str / "snapshot.json"
    
    if snapshot_file.exists():
        try:
            with open(snapshot_file, 'r') as f:
                snap = json.load(f)
                watchlist_scored = snap.get("watchlist_scored", {})
                
                # Sort by RS score descending and take the top 50 to avoid overloading the intraday scanner
                sorted_wl = sorted(watchlist_scored.items(), key=lambda x: x[1], reverse=True)
                tickers = [t for t, _ in sorted_wl[:50]]
                
                if tickers:
                    console.print(f"[bold green]✅ Loaded {len(tickers)} candidates from today's Finviz Watchlist ({today_str})[/bold green]")
                    return tickers
        except Exception as e:
            console.print(f"[yellow]⚠️ Error reading Finviz snapshot {snapshot_file}: {e}[/yellow]")

    # 2. Fallback to old CSV
    watchlist_file = project_root / "outputs/backtests/acciones_activas.csv"
    if watchlist_file.exists():
        try:
            df = pd.read_csv(watchlist_file)
            return df['Ticker'].tolist()
        except Exception as e:
            console.print(f"[yellow]⚠️ Error reading {watchlist_file}: {e}[/yellow]")
    
    # 3. Ultimate Fallback
    console.print("[bold yellow]⚠️ Using hardcoded fallback watchlist.[/bold yellow]")
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
