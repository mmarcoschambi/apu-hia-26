#!/usr/bin/env python3
"""
POSITION TRACKER - Track Active Trades
Gestiona tus posiciones abiertas y calcula P&L en tiempo real

Usage:
    python position_tracker.py                        # Ver todas las posiciones
    python position_tracker.py --add AAPL 150.50 145.20 100  # Añadir posición
    python position_tracker.py --close AAPL 155.00    # Cerrar posición
    python position_tracker.py --update               # Actualizar precios actuales
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.market_data import MarketDataProvider


class Position:
    """Clase para representar una posición abierta"""
    
    def __init__(self, symbol: str, entry_price: float, stop_loss: float, 
                 shares: int, entry_date: str = None, camino: str = None):
        self.symbol = symbol
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.shares = shares
        self.entry_date = entry_date or datetime.now().strftime('%Y-%m-%d')
        self.camino = camino
        self.current_price = entry_price
        
    @property
    def cost_basis(self) -> float:
        return self.entry_price * self.shares
    
    @property
    def current_value(self) -> float:
        return self.current_price * self.shares
    
    @property
    def unrealized_pnl(self) -> float:
        return self.current_value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self) -> float:
        return (self.unrealized_pnl / self.cost_basis) * 100 if self.cost_basis > 0 else 0
    
    @property
    def risk_per_share(self) -> float:
        return self.entry_price - self.stop_loss
    
    @property
    def total_risk(self) -> float:
        return self.risk_per_share * self.shares
    
    @property
    def r_multiple(self) -> float:
        """Cuántos R's estás arriba/abajo"""
        if self.risk_per_share <= 0:
            return 0
        return self.unrealized_pnl / self.total_risk
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'shares': self.shares,
            'entry_date': self.entry_date,
            'camino': self.camino,
            'current_price': self.current_price
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Position':
        pos = cls(
            symbol=data['symbol'],
            entry_price=data['entry_price'],
            stop_loss=data['stop_loss'],
            shares=data['shares'],
            entry_date=data.get('entry_date'),
            camino=data.get('camino')
        )
        pos.current_price = data.get('current_price', data['entry_price'])
        return pos


class PositionTracker:
    """Gestiona el portfolio de posiciones activas"""
    
    def __init__(self, positions_file: Path = None):
        self.positions_file = positions_file or project_root / "outputs/active_positions.json"
        self.closed_trades_file = project_root / "outputs/backtests/closed_trades.csv"
        self.data_provider = MarketDataProvider()
        self.positions: Dict[str, Position] = {}
        self._load_positions()
    
    def _load_positions(self):
        """Cargar posiciones del archivo"""
        if self.positions_file.exists():
            with open(self.positions_file, 'r') as f:
                data = json.load(f)
                self.positions = {
                    k: Position.from_dict(v) for k, v in data.items()
                }
    
    def _save_positions(self):
        """Guardar posiciones al archivo"""
        data = {k: v.to_dict() for k, v in self.positions.items()}
        with open(self.positions_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_position(self, symbol: str, entry_price: float, stop_loss: float,
                    shares: int, camino: str = None):
        """Añadir nueva posición"""
        if symbol in self.positions:
            print(f"⚠️  {symbol} already has an open position. Close it first or use a different symbol.")
            return False
        
        self.positions[symbol] = Position(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            shares=shares,
            camino=camino
        )
        self._save_positions()
        
        print(f"✅ Position added: {symbol}")
        print(f"   Entry: ${entry_price:.2f} x {shares} shares = ${entry_price * shares:.2f}")
        print(f"   Stop: ${stop_loss:.2f}")
        print(f"   Risk: ${(entry_price - stop_loss) * shares:.2f}")
        
        return True
    
    def close_position(self, symbol: str, exit_price: float, notes: str = ""):
        """Cerrar posición y registrar en closed_trades"""
        if symbol not in self.positions:
            print(f"❌ No open position for {symbol}")
            return False
        
        pos = self.positions[symbol]
        
        # Calcular resultados
        pnl = (exit_price - pos.entry_price) * pos.shares
        pnl_pct = (pnl / pos.cost_basis) * 100
        r_multiple = pnl / pos.total_risk if pos.total_risk > 0 else 0
        
        # Registrar trade cerrado
        trade_record = {
            'symbol': symbol,
            'entry_date': pos.entry_date,
            'exit_date': datetime.now().strftime('%Y-%m-%d'),
            'camino': pos.camino,
            'entry_price': pos.entry_price,
            'exit_price': exit_price,
            'shares': pos.shares,
            'stop_loss': pos.stop_loss,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'r_multiple': r_multiple,
            'notes': notes
        }
        
        # Append to CSV
        df_new = pd.DataFrame([trade_record])
        if self.closed_trades_file.exists():
            df_existing = pd.read_csv(self.closed_trades_file)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.to_csv(self.closed_trades_file, index=False)
        else:
            df_new.to_csv(self.closed_trades_file, index=False)
        
        # Remover de posiciones activas
        del self.positions[symbol]
        self._save_positions()
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"🏁 POSITION CLOSED: {symbol}")
        print(f"{'='*60}")
        print(f"Entry: ${pos.entry_price:.2f} → Exit: ${exit_price:.2f}")
        print(f"Shares: {pos.shares}")
        print(f"P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)")
        print(f"R Multiple: {r_multiple:+.2f}R")
        print(f"{'='*60}\n")
        
        return True
    
    def update_prices(self):
        """Actualizar precios actuales de todas las posiciones"""
        if not self.positions:
            print("No active positions to update.")
            return
        
        print("🔄 Updating current prices...")
        
        for symbol, pos in self.positions.items():
            try:
                df = self.data_provider.get_intraday_data(symbol, interval='1m', days=1)
                if not df.empty:
                    pos.current_price = df['Close'].iloc[-1]
                    print(f"  {symbol}: ${pos.current_price:.2f}")
                else:
                    print(f"  {symbol}: No data available")
            except Exception as e:
                print(f"  {symbol}: Error - {e}")
        
        self._save_positions()
        print("✅ Prices updated\n")
    
    def show_dashboard(self):
        """Mostrar dashboard de posiciones"""
        if not self.positions:
            print("\n📭 No active positions\n")
            return
        
        print(f"\n{'='*100}")
        print(f"💼 ACTIVE POSITIONS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*100}\n")
        
        # Portfolio totals
        total_cost = sum(p.cost_basis for p in self.positions.values())
        total_value = sum(p.current_value for p in self.positions.values())
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        total_risk = sum(p.total_risk for p in self.positions.values())
        
        # Individual positions
        for symbol, pos in self.positions.items():
            print(f"{'─'*100}")
            print(f"🔹 {symbol} ({pos.camino or 'N/A'}) - Entered {pos.entry_date}")
            print(f"   Entry: ${pos.entry_price:.2f} → Current: ${pos.current_price:.2f}")
            print(f"   Shares: {pos.shares} | Cost Basis: ${pos.cost_basis:,.2f} | Current Value: ${pos.current_value:,.2f}")
            print(f"   Stop Loss: ${pos.stop_loss:.2f} | Total Risk: ${pos.total_risk:,.2f}")
            
            # P&L con color
            pnl_sign = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
            print(f"   {pnl_sign} P&L: ${pos.unrealized_pnl:+,.2f} ({pos.unrealized_pnl_pct:+.2f}%) | {pos.r_multiple:+.2f}R")
        
        print(f"{'─'*100}\n")
        
        # Portfolio summary
        print(f"📊 PORTFOLIO SUMMARY")
        print(f"   Total Positions: {len(self.positions)}")
        print(f"   Total Cost Basis: ${total_cost:,.2f}")
        print(f"   Total Current Value: ${total_value:,.2f}")
        print(f"   Total Risk at Risk: ${total_risk:,.2f}")
        
        pnl_sign = "🟢" if total_pnl >= 0 else "🔴"
        print(f"   {pnl_sign} Total Unrealized P&L: ${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)")
        print(f"{'='*100}\n")
    
    def show_closed_trades(self, last_n: int = 10):
        """Mostrar últimos trades cerrados"""
        if not self.closed_trades_file.exists():
            print("\n📭 No closed trades yet\n")
            return
        
        df = pd.read_csv(self.closed_trades_file)
        
        if df.empty:
            print("\n📭 No closed trades yet\n")
            return
        
        print(f"\n{'='*100}")
        print(f"📜 CLOSED TRADES (Last {last_n})")
        print(f"{'='*100}\n")
        
        df_recent = df.tail(last_n)
        
        for _, trade in df_recent.iterrows():
            outcome = "🟢 WIN" if trade['pnl'] >= 0 else "🔴 LOSS"
            print(f"{outcome} | {trade['symbol']} | {trade['entry_date']} → {trade['exit_date']}")
            print(f"      ${trade['entry_price']:.2f} → ${trade['exit_price']:.2f} | "
                  f"P&L: ${trade['pnl']:+.2f} ({trade['pnl_pct']:+.2f}%) | {trade['r_multiple']:+.2f}R")
            if pd.notna(trade.get('notes')) and trade['notes']:
                print(f"      Notes: {trade['notes']}")
            print()
        
        # Stats
        total_trades = len(df)
        winners = len(df[df['pnl'] > 0])
        losers = len(df[df['pnl'] < 0])
        win_rate = (winners / total_trades * 100) if total_trades > 0 else 0
        avg_r = df['r_multiple'].mean()
        total_pnl = df['pnl'].sum()
        
        print(f"{'─'*100}")
        print(f"📊 STATISTICS")
        print(f"   Total Trades: {total_trades} | Winners: {winners} | Losers: {losers}")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   Average R: {avg_r:+.2f}R")
        print(f"   Total P&L: ${total_pnl:+,.2f}")
        print(f"{'='*100}\n")


def main():
    parser = argparse.ArgumentParser(description='Position Tracker')
    parser.add_argument('--add', nargs=5, metavar=('SYMBOL', 'ENTRY', 'STOP', 'SHARES', 'CAMINO'),
                       help='Add new position')
    parser.add_argument('--close', nargs=2, metavar=('SYMBOL', 'EXIT_PRICE'),
                       help='Close position')
    parser.add_argument('--update', action='store_true', help='Update current prices')
    parser.add_argument('--history', action='store_true', help='Show closed trades')
    
    args = parser.parse_args()
    
    tracker = PositionTracker()
    
    if args.add:
        symbol, entry, stop, shares, camino = args.add
        tracker.add_position(
            symbol=symbol.upper(),
            entry_price=float(entry),
            stop_loss=float(stop),
            shares=int(shares),
            camino=camino
        )
    elif args.close:
        symbol, exit_price = args.close
        notes = input("Notes (optional): ").strip()
        tracker.close_position(symbol.upper(), float(exit_price), notes)
    elif args.update:
        tracker.update_prices()
    elif args.history:
        tracker.show_closed_trades()
    
    # Always show dashboard
    tracker.show_dashboard()


if __name__ == "__main__":
    main()
