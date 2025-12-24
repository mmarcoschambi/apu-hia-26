#!/usr/bin/env python3
"""
DAILY TRADING WORKFLOW - Complete Pre-Market to Post-Market
Flujo completo automatizado para tu rutina diaria de trading

Usage:
    python daily_workflow.py pre-market      # Pre-market scan (antes de 9:30 AM)
    python daily_workflow.py market-open     # Market open check (9:30-10:00 AM)
    python daily_workflow.py mid-day         # Mid-day review (12:00 PM)
    python daily_workflow.py market-close    # EOD review (después de 4:00 PM)
    python daily_workflow.py full            # Run all steps automatically
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime, time as dt_time
import time as time_module

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from live_trading_scanner import LiveTradingScanner, load_watchlist_from_file
from position_tracker import PositionTracker


class DailyWorkflow:
    """Workflow automatizado para trading diario"""
    
    def __init__(self):
        self.scanner = LiveTradingScanner()
        self.tracker = PositionTracker()
        self.watchlist = load_watchlist_from_file()
        
    def pre_market_routine(self):
        """Rutina Pre-Market (antes de 9:30 AM)"""
        print("\n" + "="*80)
        print("🌅 PRE-MARKET ROUTINE")
        print("="*80 + "\n")
        
        # Step 1: Scan for new setups
        print("📍 STEP 1: Scanning for new setups...")
        print("-" * 80)
        setups = self.scanner.scan_watchlist(self.watchlist)
        
        if setups:
            print("\n✅ Setups found! Review and place orders.")
            self._show_order_placement_guide(setups)
        else:
            print("\n⏸️  No new setups today. Focus on existing positions.")
        
        # Step 2: Review existing positions
        print("\n" + "="*80)
        print("📍 STEP 2: Review existing positions")
        print("-" * 80 + "\n")
        self.tracker.show_dashboard()
        
        # Step 3: Action plan
        print("="*80)
        print("📋 PRE-MARKET ACTION PLAN")
        print("="*80)
        print("1. ✅ Place any BUY STOP orders from scan")
        print("2. ✅ Verify stop losses on existing positions")
        print("3. ✅ Set alerts for MANUAL_WATCH setups")
        print("4. ✅ Review market context (SPY/QQQ)")
        print("5. ✅ Be ready at 9:30 AM for executions")
        print("="*80 + "\n")
    
    def market_open_check(self):
        """Market Open Check (9:30-10:00 AM)"""
        print("\n" + "="*80)
        print("🔔 MARKET OPEN CHECK")
        print("="*80 + "\n")
        
        # Update positions
        print("📍 Updating current prices...")
        self.tracker.update_prices()
        
        # Show dashboard
        self.tracker.show_dashboard()
        
        print("="*80)
        print("⚡ MARKET OPEN ACTIONS")
        print("="*80)
        print("1. ✅ Check if any BUY STOP orders filled")
        print("2. ✅ Watch MANUAL setups for VWAP reclaim")
        print("3. ✅ Monitor for flush + recovery patterns")
        print("4. ✅ Cancel unfilled orders by 10:30 AM if no trigger")
        print("="*80 + "\n")
    
    def mid_day_review(self):
        """Mid-Day Review (12:00 PM)"""
        print("\n" + "="*80)
        print("☀️ MID-DAY REVIEW")
        print("="*80 + "\n")
        
        # Update positions
        self.tracker.update_prices()
        self.tracker.show_dashboard()
        
        print("="*80)
        print("🎯 MID-DAY CHECKLIST")
        print("="*80)
        print("1. ✅ Any positions in profit? Consider partial exit")
        print("2. ✅ Any positions near stop? Prepare mentally")
        print("3. ✅ Any MANUAL setups developed? Entry/pass decision")
        print("4. ✅ Cancel any unfilled BUY STOP orders")
        print("="*80 + "\n")
    
    def market_close_review(self):
        """Market Close Review (después de 4:00 PM)"""
        print("\n" + "="*80)
        print("🌆 END OF DAY REVIEW")
        print("="*80 + "\n")
        
        # Update final prices
        print("📍 Updating final prices...")
        self.tracker.update_prices()
        
        # Show dashboard
        self.tracker.show_dashboard()
        
        # Show recent closed trades
        print("\n" + "="*80)
        print("📍 Recent Closed Trades")
        print("="*80 + "\n")
        self.tracker.show_closed_trades(last_n=5)
        
        # Journal prompts
        print("="*80)
        print("📝 TRADING JOURNAL PROMPTS")
        print("="*80)
        print("1. What setups did I see today?")
        print("2. What did I execute and why?")
        print("3. What did I pass on and why?")
        print("4. How did I manage emotions?")
        print("5. What will I do differently tomorrow?")
        print("="*80 + "\n")
        
        # Prep for tomorrow
        print("="*80)
        print("🔮 PREP FOR TOMORROW")
        print("="*80)
        print("1. ✅ Review/update watchlist if needed")
        print("2. ✅ Note any patterns forming")
        print("3. ✅ Set calendar reminder for pre-market scan")
        print("4. ✅ Rest - mental capital is everything")
        print("="*80 + "\n")
    
    def full_workflow(self):
        """Execute full workflow with time-based automation"""
        print("\n" + "="*80)
        print("🤖 AUTOMATED DAILY WORKFLOW")
        print("="*80 + "\n")
        print("Running based on current time...")
        
        now = datetime.now().time()
        
        # Pre-market: before 9:30 AM
        pre_market_time = dt_time(9, 30)
        market_open_time = dt_time(10, 0)
        mid_day_time = dt_time(12, 0)
        market_close_time = dt_time(16, 0)
        
        if now < pre_market_time:
            print("⏰ Time for PRE-MARKET routine\n")
            self.pre_market_routine()
            
        elif pre_market_time <= now < market_open_time:
            print("⏰ Time for MARKET OPEN check\n")
            self.market_open_check()
            
        elif market_open_time <= now < mid_day_time:
            print("⏰ Time for MID-DAY review\n")
            self.mid_day_review()
            
        elif now >= market_close_time:
            print("⏰ Time for MARKET CLOSE review\n")
            self.market_close_review()
            
        else:
            print("⏰ Market hours - focus on execution\n")
            self.tracker.update_prices()
            self.tracker.show_dashboard()
    
    def _show_order_placement_guide(self, setups):
        """Quick guide for order placement"""
        buy_stops = [s for s in setups if s['signal'].action == 'BUY_STOP']
        
        if not buy_stops:
            return
        
        print("\n" + "="*80)
        print("📝 ORDER PLACEMENT GUIDE")
        print("="*80 + "\n")
        
        for setup in buy_stops:
            signal = setup['signal']
            symbol = setup['symbol']
            
            print(f"🔹 {symbol}")
            print(f"   Order Type: BUY STOP LIMIT")
            print(f"   Stop Price: ${signal.entry_price:.2f}")
            print(f"   Limit Price: ${signal.entry_price + 0.50:.2f} (add slippage)")
            print(f"   Stop Loss: ${signal.stop_loss:.2f}")
            print(f"   Duration: Day Order (cancel at 10:30 AM if not filled)")
            print()


def main():
    parser = argparse.ArgumentParser(description='Daily Trading Workflow')
    parser.add_argument('routine', choices=['pre-market', 'market-open', 'mid-day', 'market-close', 'full'],
                       help='Which routine to run')
    
    args = parser.parse_args()
    
    workflow = DailyWorkflow()
    
    routines = {
        'pre-market': workflow.pre_market_routine,
        'market-open': workflow.market_open_check,
        'mid-day': workflow.mid_day_review,
        'market-close': workflow.market_close_review,
        'full': workflow.full_workflow
    }
    
    routines[args.routine]()


if __name__ == "__main__":
    main()
