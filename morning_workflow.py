#!/usr/bin/env python3
"""
MORNING WORKFLOW - Complete Pre-Market Routine
Ejecuta toda tu rutina matinal en un solo comando

Usage:
    python morning_workflow.py                  # Full morning routine
    python morning_workflow.py --health-only    # Solo health check
    python morning_workflow.py --scan-only      # Solo scan (skip health)
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime, time as dt_time

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from market_health_check import MarketHealthChecker
from live_trading_scanner import LiveTradingScanner, load_watchlist_from_file
from position_tracker import PositionTracker


class MorningWorkflow:
    """Workflow completo para pre-market"""
    
    def __init__(self):
        self.health_checker = MarketHealthChecker()
        self.scanner = LiveTradingScanner()
        self.tracker = PositionTracker()
        self.watchlist = load_watchlist_from_file()
    
    def run_full_routine(self):
        """Ejecuta rutina completa de pre-market"""
        
        print("\n" + "="*80)
        print("🌅 GOOD MORNING - STARTING PRE-MARKET ROUTINE")
        print("="*80)
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 Watchlist: {len(self.watchlist)} symbols")
        print("="*80 + "\n")
        
        input("Press ENTER to continue...")
        
        # STEP 1: Market Health Check
        print("\n" + "🔹"*40)
        print("STEP 1/4: MARKET HEALTH CHECK")
        print("🔹"*40 + "\n")
        
        health_result = self.health_checker.check(detailed=False)
        
        if not health_result['market_favorable']:
            print("\n⚠️  ROUTINE PAUSED: Market not favorable for longs")
            print("📋 Recommendation: Skip scanning today, focus on other activities")
            
            response = input("\nDo you want to scan anyway? (yes/no): ").lower()
            if response != 'yes':
                print("\n✋ Morning routine ended. Stay disciplined!")
                return
            else:
                print("\n⚠️  Proceeding with scan (against recommendation)...\n")
        
        # STEP 2: Review Existing Positions
        print("\n" + "🔹"*40)
        print("STEP 2/4: REVIEW EXISTING POSITIONS")
        print("🔹"*40 + "\n")
        
        self.tracker.show_dashboard()
        
        input("Press ENTER to continue to scan...")
        
        # STEP 3: Scan for New Setups
        print("\n" + "🔹"*40)
        print("STEP 3/4: SCAN FOR NEW SETUPS")
        print("🔹"*40 + "\n")
        
        setups = self.scanner.scan_watchlist(self.watchlist)
        
        # STEP 4: Action Plan
        print("\n" + "🔹"*40)
        print("STEP 4/4: ACTION PLAN")
        print("🔹"*40 + "\n")
        
        self._generate_action_plan(health_result, setups)
        
        # Save morning report
        self._save_morning_report(health_result, setups)
        
        print("\n" + "="*80)
        print("✅ MORNING ROUTINE COMPLETE")
        print("="*80)
        print(f"📄 Report saved to: morning_report_{datetime.now().strftime('%Y%m%d')}.txt")
        print("="*80 + "\n")
    
    def _generate_action_plan(self, health_result, setups):
        """Genera plan de acción específico para hoy"""
        
        mode = health_result['mode']
        
        print("📋 TODAY'S ACTION PLAN")
        print("="*80 + "\n")
        
        print(f"⚙️  Trading Mode: {mode}")
        
        if mode == "NO_TRADE":
            print("\n🚫 NO TRADING TODAY")
            print("   1. ✅ Review existing positions only")
            print("   2. ✅ Study charts and patterns")
            print("   3. ✅ Prepare watchlist for tomorrow")
            print("   4. ✅ Journal about past trades")
            print("   5. ✅ Mental reset - avoid FOMO")
            
        elif mode == "AGGRESSIVE":
            print("\n🚀 AGGRESSIVE MODE")
            print(f"   • Max positions: 5")
            print(f"   • Risk per trade: 2%")
            print(f"   • Setups found: {len(setups)}")
            print(f"   • All 3 Caminos active")
            
            if setups:
                print("\n📍 Orders to Place (9:20 AM):")
                self._list_orders(setups, risk_pct=0.02)
            else:
                print("\n⏸️  No setups today - that's OK!")
                print("   Quality > Quantity. Wait for next opportunity.")
        
        elif mode == "STANDARD":
            print("\n💪 STANDARD MODE")
            print(f"   • Max positions: 3-4")
            print(f"   • Risk per trade: 1.5-2%")
            print(f"   • Setups found: {len(setups)}")
            print(f"   • Prefer Camino 1 (Blue Sky)")
            
            if setups:
                print("\n📍 Orders to Place (9:20 AM):")
                self._list_orders(setups, risk_pct=0.015)
            else:
                print("\n⏸️  No setups today - that's OK!")
        
        elif mode == "DEFENSIVE":
            print("\n⚠️  DEFENSIVE MODE")
            print(f"   • Max positions: 1-2")
            print(f"   • Risk per trade: 0.5-1%")
            print(f"   • Setups found: {len(setups)}")
            print(f"   • Only perfect Blue Sky setups")
            
            # Filter only Blue Sky
            blue_sky_setups = [s for s in setups 
                              if s.get('signal') and 
                              s['signal'].camino and 
                              s['signal'].camino.name == 'CAMINO_1_BLUE_SKY']
            
            if blue_sky_setups:
                print("\n📍 Orders to Place (9:20 AM):")
                self._list_orders(blue_sky_setups, risk_pct=0.01)
            else:
                print("\n⏸️  No perfect Blue Sky setups - STAY CASH")
        
        # General reminders
        print("\n⏰ TIMELINE:")
        print("   9:20 AM - Place orders in broker")
        print("   9:30 AM - Monitor fills")
        print("   10:30 AM - Cancel unfilled orders")
        print("   12:00 PM - Mid-day check")
        print("   4:00 PM - EOD review")
        
        print("\n⚠️  REMINDERS:")
        print("   • Use buy stop limit orders")
        print("   • Set stop loss BEFORE entering")
        print("   • Position size = risk / (entry - stop)")
        print("   • Max loss today: 6% of account")
        print("   • Journal every trade")
    
    def _list_orders(self, setups, risk_pct=0.02):
        """Lista órdenes a colocar con cálculos de position size"""
        
        # Assume $25,000 account (user can adjust)
        account_size = 25000
        risk_amount = account_size * risk_pct
        
        buy_stops = [s for s in setups if s.get('signal') and s['signal'].action == 'BUY_STOP']
        manual = [s for s in setups if s.get('signal') and s['signal'].action == 'MANUAL_WATCH']
        
        if buy_stops:
            print("\n   📍 BUY STOP ORDERS:")
            print("   " + "-"*76)
            
            for setup in buy_stops[:3]:  # Limit to top 3
                signal = setup['signal']
                symbol = setup['symbol']
                
                if signal.entry_price and signal.stop_loss:
                    risk_per_share = signal.entry_price - signal.stop_loss
                    shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
                    total_cost = shares * signal.entry_price
                    
                    print(f"\n   🔹 {symbol} ({signal.camino.name if signal.camino else 'N/A'})")
                    print(f"      Order: BUY STOP LIMIT")
                    print(f"      Stop Price: ${signal.entry_price:.2f}")
                    print(f"      Limit Price: ${signal.entry_price + 0.50:.2f}")
                    print(f"      Quantity: {shares} shares")
                    print(f"      Cost: ${total_cost:,.2f} ({total_cost/account_size*100:.1f}% of account)")
                    print(f"      Stop Loss: ${signal.stop_loss:.2f}")
                    print(f"      Risk: ${risk_amount:.2f} ({risk_pct*100:.1f}%)")
        
        if manual:
            print("\n   👀 MANUAL WATCH (Set Alerts):")
            print("   " + "-"*76)
            
            for setup in manual:
                signal = setup['signal']
                symbol = setup['symbol']
                print(f"\n   🔹 {symbol} - Watch for VWAP reclaim")
                print(f"      Alert: {symbol} crosses above VWAP")
    
    def _save_morning_report(self, health_result, setups):
        """Guarda reporte de la mañana"""
        
        report_file = project_root / f"morning_report_{datetime.now().strftime('%Y%m%d')}.txt"
        
        with open(report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write(f"MORNING REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
            
            # Health check
            f.write("MARKET HEALTH CHECK\n")
            f.write("-"*80 + "\n")
            f.write(f"SPY: ${health_result['spy_price']:.2f} (EMA20: ${health_result['spy_ema20']:.2f})\n")
            f.write(f"Above EMA20: {health_result['spy_above_ema20']}\n")
            f.write(f"Breadth Improving: {health_result['breadth_improving']}\n")
            f.write(f"Positive GEX: {health_result['positive_gex']}\n")
            f.write(f"Market Favorable: {health_result['market_favorable']}\n")
            f.write(f"Trading Mode: {health_result['mode']}\n")
            f.write(f"Health Score: {health_result['health_score']}/{health_result['max_score']}\n")
            f.write("\n")
            
            # Setups
            f.write("SETUPS FOUND\n")
            f.write("-"*80 + "\n")
            f.write(f"Total: {len(setups)}\n\n")
            
            for setup in setups:
                signal = setup.get('signal')
                if signal:
                    f.write(f"{setup['symbol']} - {signal.camino.name if signal.camino else 'N/A'}\n")
                    f.write(f"  Action: {signal.action}\n")
                    f.write(f"  Entry: ${signal.entry_price:.2f}\n" if signal.entry_price else "  Entry: TBD\n")
                    f.write(f"  Stop: ${signal.stop_loss:.2f}\n" if signal.stop_loss else "  Stop: TBD\n")
                    f.write(f"  Reasoning: {signal.reasoning}\n")
                    f.write("\n")


def main():
    parser = argparse.ArgumentParser(description='Morning Workflow')
    parser.add_argument('--health-only', action='store_true', 
                       help='Only run health check')
    parser.add_argument('--scan-only', action='store_true', 
                       help='Skip health check, only scan')
    
    args = parser.parse_args()
    
    workflow = MorningWorkflow()
    
    if args.health_only:
        workflow.health_checker.check(detailed=True)
    elif args.scan_only:
        watchlist = load_watchlist_from_file()
        scanner = LiveTradingScanner()
        scanner.scan_watchlist(watchlist)
    else:
        workflow.run_full_routine()


if __name__ == "__main__":
    main()
