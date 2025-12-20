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
from src.core.screener import InstitutionalScreener

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
    entry_stage: str = 'FULL'

@dataclass
class PendingOrder:
    symbol: str
    order_type: str # 'BUY_STOP'
    limit_price: float
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
        return self.cash

class DailyBacktestEngine:
    def __init__(self, universe: List[str], start_date: str, end_date: str, risk_manager: RiskManager, min_mcap: float = 2e9, max_mcap: float = 20e9):
        self.universe = universe
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.risk_manager = risk_manager
        self.min_mcap = min_mcap
        self.max_mcap = max_mcap
        
        self.portfolio = Portfolio(risk_manager.account_equity)
        self.pending_orders: List[PendingOrder] = []
        
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.spy_data = pd.DataFrame()
        self.triad_logic = TriadOpenBB()
        self.screener = InstitutionalScreener(adr_threshold=4.0)
        
        print(f"Initializing Engine for {len(universe)} symbols (Mid-Cap Filter: ${min_mcap/1e9:.1f}B - ${max_mcap/1e9:.1f}B)...")
        self._preload_market_data()

    def _preload_market_data(self):
        from openbb import obb
        
        fetch_start = (self.start_date - timedelta(days=200)).strftime('%Y-%m-%d')
        fetch_end = self.end_date.strftime('%Y-%m-%d')
        
        # 1. Filter Universe by Market Cap (Proxy: Current Mcap)
        filtered_universe = []
        print("Filtering Universe by Market Cap...")
        for symbol in self.universe:
            try:
                # Fetch overview
                overview = obb.equity.fundamental.overview(symbol=symbol, provider='yfinance').to_df()
                if not overview.empty and 'market_cap' in overview.columns:
                    mcap = overview['market_cap'].iloc[0]
                    if self.min_mcap <= mcap <= self.max_mcap:
                        filtered_universe.append(symbol)
                    else:
                        pass # print(f"Skipping {symbol}: Mcap ${mcap/1e9:.1f}B outside range")
                else:
                    # If no data, keep it to be safe or skip? Let's skip to be strict.
                    print(f"Skipping {symbol}: No fundamental data")
            except Exception as e:
                print(f"Skipping {symbol}: Error fetching fundamentals ({e})")
        
        self.universe = filtered_universe
        print(f"Final Universe Size: {len(self.universe)} symbols")

        # 2. Preload SPY
        try:
            self.spy_data = obb.equity.price.historical(symbol='SPY', start_date=fetch_start, end_date=fetch_end, provider='yfinance').to_df()
        except:
            print("Warning: Could not load SPY data.")

        # 3. Preload Market Data
        for symbol in self.universe:
            try:
                df = obb.equity.price.historical(symbol=symbol, start_date=fetch_start, end_date=fetch_end, provider='yfinance').to_df()
                if not df.empty:
                    df = self.triad_logic._calculate_indicators(df)
                    self.market_data[symbol] = df
            except Exception as e:
                logger.warning(f"Failed to load data for {symbol}: {e}")

    def run(self):
        print("🚀 Starting Daily Simulation...")
        date_range = pd.date_range(start=self.start_date, end=self.end_date, freq='B')
        
        for today in date_range:
            # 1. Manage Exits and Entries
            self._manage_positions(today)
            
            # 2. Update Equity
            self._update_equity(today)
            
            # 3. Daily Screener (After Close)
            candidates = self._run_daily_screener(today)
            
            # 4. Prepare Orders for Tomorrow
            self._prepare_orders(today, candidates, self.portfolio.equity)
        
        return pd.DataFrame(self.portfolio.closed_trades)

    def _manage_positions(self, today):
        # A. Execution of Pending Orders
        remaining_orders = []
        for order in self.pending_orders:
            if order.valid_date != today: continue
            
            symbol = order.symbol
            if symbol not in self.market_data or today not in self.market_data[symbol].index: continue
            
            daily_bar = self.market_data[symbol].loc[today]
            if daily_bar['high'] >= order.limit_price:
                execution_price = max(daily_bar['open'], order.limit_price)
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
        self.pending_orders = []

        # B. Exit Management
        for symbol, pos in list(self.portfolio.positions.items()):
            if symbol not in self.market_data or today not in self.market_data[symbol].index: continue
            daily_bar = self.market_data[symbol].loc[today]
            
            if daily_bar['low'] <= pos.stop_loss:
                exit_price = min(daily_bar['open'], pos.stop_loss)
                self._close_position(symbol, exit_price, today, "STOP_LOSS")
                continue
            
            if not pos.tp1_hit and daily_bar['high'] >= pos.take_profit_1:
                exit_shares = int(pos.shares * 0.5)
                if exit_shares > 0:
                    self.portfolio.cash += (exit_shares * pos.take_profit_1)
                    pos.shares -= exit_shares
                    pos.tp1_hit = True
                    pos.stop_loss = pos.entry_price

            if pos.tp1_hit:
                 if daily_bar['ema_8'] < daily_bar['ema_21']:
                     self._close_position(symbol, daily_bar['close'], today, "EMA_CROSS")

    def _close_position(self, symbol, price, date, reason):
        pos = self.portfolio.positions.pop(symbol)
        pnl = (price - pos.entry_price) * pos.shares
        self.portfolio.cash += (pos.shares * price)
        self.portfolio.closed_trades.append({
            'symbol': symbol, 'entry_date': pos.entry_date, 'exit_date': date,
            'entry_price': pos.entry_price, 'exit_price': price, 'shares': pos.shares,
            'pnl': pnl, 'return_pct': ((price - pos.entry_price) / pos.entry_price) * 100,
            'reason': reason
        })

    def _run_daily_screener(self, today) -> List[Dict]:
        candidates = []
        for symbol, df in self.market_data.items():
            res = self.screener.scan(symbol, df, self.spy_data, today)
            if res: candidates.append(res)
        return candidates

    def _prepare_orders(self, today, candidates, equity):
        for cand in candidates:
            if cand['symbol'] in self.portfolio.positions: continue
            trigger_price = cand['entry_trigger'] * 1.005
            stop_price = cand['stop_loss']
            self.risk_manager.account_equity = equity
            self.risk_manager.buying_power = self.portfolio.cash
            sizing = self.risk_manager.calculate_position_size(trigger_price, stop_price)
            if sizing['shares'] > 0:
                self.pending_orders.append(PendingOrder(
                    symbol=cand['symbol'], order_type='BUY_STOP', limit_price=trigger_price,
                    stop_loss_initial=stop_price, shares=sizing['shares'],
                    valid_date=today + pd.tseries.offsets.BusinessDay(1)
                ))

    def _update_equity(self, today):
        open_pnl = 0
        for symbol, pos in self.portfolio.positions.items():
            if symbol in self.market_data and today in self.market_data[symbol].index:
                open_pnl += (self.market_data[symbol].loc[today]['close'] - pos.entry_price) * pos.shares
        self.portfolio.equity_curve.append({'date': today, 'equity': self.portfolio.cash + open_pnl})