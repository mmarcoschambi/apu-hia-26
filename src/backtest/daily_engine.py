"""
Institutional Daily Backtesting Engine
--------------------------------------
Simulates a professional trading desk workflow:
1. Morning: Portfolio Management (Exits)
2. Close: Daily Screener (Scanning)
3. Night: Order Sizing & Prep (Risk Manager)
4. Next Day: Execution (Bar Advance)

Strictly enforces ZERO LOOK-AHEAD BIAS.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

from src.utils.risk_manager import RiskManager
from src.core.triad_openbb import TriadOpenBB

logger = logging.getLogger(__name__)

@dataclass
class Position:
    symbol: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: int
    stop_loss: float
    take_profit_1: float
    tp1_hit: bool = False
    entry_stage: str = 'FULL' # or 'FEELER' if tiered

@dataclass
class PendingOrder:
    symbol: str
    order_type: str # 'BUY_STOP', 'MARKET'
    limit_price: float # Trigger price
    stop_loss_initial: float
    shares: int
    valid_date: pd.Timestamp

class Portfolio:
    def __init__(self, initial_capital: float):
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[Dict] = []
        self.equity_curve: List[Dict] = []
    
    @property
    def equity(self) -> float:
        # Cash + Market Value of Positions (needs current prices, approximations used during loop)
        return self.cash # Simplified, updated in update_mark_to_market
    
    @property
    def buying_power(self) -> float:
        # Simple cash account model
        return self.cash

class DailyBacktestEngine:
    def __init__(self, universe: List[str], start_date: str, end_date: str, risk_manager: RiskManager):
        self.universe = universe
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.risk_manager = risk_manager
        
        self.portfolio = Portfolio(risk_manager.account_equity)
        self.pending_orders: List[PendingOrder] = []
        
        # Data Cache (The "Market Database")
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.triad_logic = TriadOpenBB()
        
        print(f"Initializing Engine for {len(universe)} symbols...")
        self._preload_market_data()

    def _preload_market_data(self):
        """
        Pre-fetch and pre-calculate indicators for the universe.
        Equivalent to having a local SQL database of OHLCV + Indicators.
        """
        from openbb import obb
        
        # We fetch a bit more history for indicators
        fetch_start = (self.start_date - timedelta(days=200)).strftime('%Y-%m-%d')
        fetch_end = self.end_date.strftime('%Y-%m-%d')
        
        for symbol in self.universe:
            try:
                df = obb.equity.price.historical(symbol=symbol, start_date=fetch_start, end_date=fetch_end, provider='yfinance').to_df()
                if not df.empty:
                    # Calculate indicators ONCE (Vectorized)
                    # This is valid as long as row T doesn't use T+1 info.
                    # Our indicators (SMA, RSI) are backward looking.
                    df = self.triad_logic._calculate_indicators(df)
                    self.market_data[symbol] = df
            except Exception as e:
                logger.warning(f"Failed to load data for {symbol}: {e}")

    def run(self):
        """
        Main Daily Loop
        """
        print("🚀 Starting Daily Simulation...")
        
        # Generate calendar of trading days (using SPY as reference if available, or just range)
        date_range = pd.date_range(start=self.start_date, end=self.end_date, freq='B')
        
        current_equity = self.portfolio.initial_capital
        
        for today in date_range:
            # Skip if no data for this day (weekend/holiday check simplified)
            # We check if 'today' exists in at least one symbol's data
            
            # --- STEP 1: MORNING PORTFOLIO MANAGEMENT ---
            self._manage_positions(today)
            
            # Update Equity Curve (Mark to Market)
            self._update_equity(today)
            current_equity = self.portfolio.equity
            
            # --- STEP 2: DAILY SCREENER (After Close) ---
            # Scans for candidates using data UP TO today.
            candidates = self._run_daily_screener(today)
            
            # --- STEP 3: NIGHT ORDER PREPARATION ---
            self._prepare_orders(today, candidates, current_equity)
            
            # --- STEP 4: NEXT DAY EXECUTION ---
            # Orders placed tonight are executed "Tomorrow" (next loop iteration's Morning/Session)
            # But in this loop structure, we process executions for orders placed YESTERDAY based on TODAY's price action.
            # So, actually:
            # 1. Manage Positions (Exits today)
            # 2. Process Pending Orders (Entries today) <-- Added step
            # 3. Screen (for tomorrow)
            # 4. Prepare Orders (for tomorrow)
            pass 
            
            # Refined Flow for Code Clarity:
            # We are AT 'today'. We see today's Open/High/Low/Close.
            # 1. Check entries for orders created yesterday (did today's High hit buy stop?)
            # 2. Check exits for existing positions (did today's Low hit stop loss?)
            # 3. Screen today's Close for TOMORROW's setups.
        
        return pd.DataFrame(self.portfolio.closed_trades)

    def _execute_orders_and_manage_positions(self, today):
        """
        Combined step to process price action for 'today'.
        """
        # A. Process Pending Orders (Entries)
        # Check if today's price action triggered any Buy Stops from yesterday
        remaining_orders = []
        for order in self.pending_orders:
            if order.valid_date != today:
                continue # Expired order
            
            symbol = order.symbol
            if symbol not in self.market_data or today not in self.market_data[symbol].index:
                continue
                
            daily_bar = self.market_data[symbol].loc[today]
            
            # BUY STOP LOGIC: Did Price > Limit?
            # Conservative: Did High > Limit?
            # More Conservative: Did Open > Limit? (Gap Up) -> Buy at Open
            # Standard: Buy at Limit
            
            entry_triggered = False
            execution_price = 0.0
            
            if daily_bar['high'] >= order.limit_price:
                entry_triggered = True
                # Slippage logic: max(Open, Limit) usually
                execution_price = max(daily_bar['open'], order.limit_price)
                
                # Check Buying Power
                cost = execution_price * order.shares
                if self.portfolio.cash >= cost:
                    self.portfolio.cash -= cost
                    
                    new_pos = Position(
                        symbol=symbol,
                        entry_date=today,
                        entry_price=execution_price,
                        shares=order.shares,
                        stop_loss=order.stop_loss_initial,
                        take_profit_1=execution_price + (1.5 * (execution_price - order.stop_loss_initial))
                    )
                    self.portfolio.positions[symbol] = new_pos
                    # print(f"[{today.date()}] BUY {symbol} @ {execution_price:.2f} ({order.shares} shares)")
                else:
                    # print(f"[{today.date()}] SKIPPED {symbol} - Insufficient BP")
                    pass
            
            if not entry_triggered:
                # Order not triggered today, cancel it (Swing orders usually Day Only or Good Till Cancelled)
                # Strategy says: "No orders are executed today" -> "Next Day: ... if price hits buy stop".
                # We assume Day orders for this system.
                pass
        
        self.pending_orders = [] # Clear daily orders

        # B. Manage Existing Positions (Exits)
        # Check stops/targets against today's Low/High
        # Note: In reality, if we entered today, we usually don't exit today unless heavy crash.
        # We iterate a copy to allow deletion
        for symbol, pos in list(self.portfolio.positions.items()):
            if symbol not in self.market_data or today not in self.market_data[symbol].index:
                continue
            
            daily_bar = self.market_data[symbol].loc[today]
            
            # 1. Stop Loss Check
            if daily_bar['low'] <= pos.stop_loss:
                # Exit at Stop Price (or Open if gapped down)
                exit_price = min(daily_bar['open'], pos.stop_loss)
                self._close_position(symbol, exit_price, today, "STOP_LOSS")
                continue
            
            # 2. Take Profit 1 Check (Simplified Partial)
            if not pos.tp1_hit and daily_bar['high'] >= pos.take_profit_1:
                # Sell 50%
                exit_shares = int(pos.shares * 0.5)
                if exit_shares > 0:
                    revenue = exit_shares * pos.take_profit_1
                    self.portfolio.cash += revenue
                    pos.shares -= exit_shares
                    pos.tp1_hit = True
                    # Move Stop to Breakeven
                    pos.stop_loss = pos.entry_price
                    # Log partial (optional)

            # 3. Technical Exit (End of Day) - e.g. Close < EMA10 (Runner)
            # This happens AFTER the session
            if pos.tp1_hit: # Runner phase
                if 'ema_8' in daily_bar and 'ema_21' in daily_bar:
                     if daily_bar['ema_8'] < daily_bar['ema_21']:
                         self._close_position(symbol, daily_bar['close'], today, "EMA_CROSS")

    def _close_position(self, symbol, price, date, reason):
        pos = self.portfolio.positions.pop(symbol)
        revenue = pos.shares * price
        self.portfolio.cash += revenue
        
        # Log Trade
        pnl = (price - pos.entry_price) * pos.shares
        ret_pct = (price - pos.entry_price) / pos.entry_price
        
        self.portfolio.closed_trades.append({
            'symbol': symbol,
            'entry_date': pos.entry_date,
            'exit_date': date,
            'entry_price': pos.entry_price,
            'exit_price': price,
            'shares': pos.shares,
            'pnl': pnl,
            'return_pct': ret_pct * 100,
            'reason': reason
        })

    def _run_daily_screener(self, today) -> List[Dict]:
        """
        Step 2: After Close Screener
        Returns list of candidates: {'symbol': 'AAPL', 'setup': 'MOMENTUM', 'stop': 150.0}
        """
        candidates = []
        
        for symbol, df in self.market_data.items():
            if today not in df.index:
                continue
            
            # Get row for today (and prev days for context)
            idx_loc = df.index.get_loc(today)
            if idx_loc < 20: continue # Need history
            
            # Logic extracted from TriadOpenBB but applied to single day
            row = df.iloc[idx_loc]
            prev = df.iloc[idx_loc-1]
            
            # Institutional Filter: ADR > 3%? Volume?
            # (Simplified for example)
            
            # Setup Detection
            setup = None
            stop_level = 0.0
            
            # Camino 1 Logic (Simplified)
            if (row['close'] > row['sma_20'] and 
                row['close'] > prev['close'] and
                row['volume'] > row['sma_volume_20']):
                setup = 'MOMENTUM'
                stop_level = row['low'] # Swing Low
            
            if setup:
                candidates.append({
                    'symbol': symbol,
                    'setup': setup,
                    'close': row['close'],
                    'high': row['high'],
                    'stop': stop_level
                })
        
        return candidates

    def _prepare_orders(self, today, candidates, equity):
        """
        Step 3: Night Order Preparation
        Calculate sizes and create PendingOrders for tomorrow.
        """
        for cand in candidates:
            # 1. Filter: Don't buy if already holding
            if cand['symbol'] in self.portfolio.positions:
                continue
            
            # 2. Risk Sizing
            # Trigger Price (Buy Stop) = Today's High + Buffer
            trigger_price = cand['high'] * 1.005 # 0.5% buffer
            stop_price = cand['stop']
            
            # Update Risk Manager equity
            self.risk_manager.account_equity = equity
            self.risk_manager.buying_power = self.portfolio.cash
            
            sizing = self.risk_manager.calculate_position_size(
                entry_price=trigger_price,
                stop_price=stop_price
            )
            
            shares = sizing['shares']
            
            if shares > 0:
                self.pending_orders.append(PendingOrder(
                    symbol=cand['symbol'],
                    order_type='BUY_STOP',
                    limit_price=trigger_price,
                    stop_loss_initial=stop_price,
                    shares=shares,
                    valid_date=today + pd.tseries.offsets.BusinessDay(1) # Next trading day
                ))

    def _update_equity(self, today):
        # Calculate Mark-to-Market Equity
        open_pnl = 0
        for symbol, pos in self.portfolio.positions.items():
            if symbol in self.market_data and today in self.market_data[symbol].index:
                current_price = self.market_data[symbol].loc[today]['close']
                open_pnl += (current_price - pos.entry_price) * pos.shares
        
        self.portfolio.equity_curve.append({
            'date': today,
            'equity': self.portfolio.cash + open_pnl,
            'cash': self.portfolio.cash
        })

    def _manage_positions(self, today):
        """Wrapper for the daily execution/management step"""
        self._execute_orders_and_manage_positions(today)

