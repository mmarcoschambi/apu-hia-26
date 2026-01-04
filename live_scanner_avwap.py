#!/usr/bin/env python3
"""
LIVE SCANNER CON AVWAP - End of Day Focus List Generator
=========================================================
Escanea el universo al cierre del mercado y genera una Focus List
con triggers calculados usando AVWAP + Base Detection.

FLUJO:
1. Market Health Check (SPX trend, VIX)
2. Scan Universe (pattern detection con daily data)
3. Calculate AVWAP from intraday cache (si disponible)
4. Apply Triad Strategy (3 Caminos)
5. Generate Focus List con triggers precisos

OUTPUT:
- CSV con tickers, triggers, stops, tamaño posición
- Dashboard visual con clasificación por Camino

USO:
    # Escanear S&P 500
    python3 live_scanner_avwap.py --universe sp500
    
    # Escanear archivo custom
    python3 live_scanner_avwap.py --universe universe_tickers.txt
    
    # Solo verificar mercado
    python3 live_scanner_avwap.py --market-check-only
"""

import sys
from pathlib import Path
import argparse
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging
from tqdm import tqdm
import yfinance as yf
import warnings

warnings.filterwarnings('ignore')

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.market_data import MarketDataProvider
from src.core.triad_openbb import TriadOpenBB
from src.strategies.triad_protocol import TriadStrategy, Camino
from src.utils.risk_manager import RiskManager
from src.indicators.pattern_detection import PatternDetectionEngine
from cache_intraday_data import IntradayCacheManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AVWAPLiveScanner:
    """
    Live scanner con cálculo de AVWAP para triggers precisos
    """
    
    def __init__(self, capital=100000, risk_per_trade=0.02):
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        
        self.data_provider = MarketDataProvider()
        self.triad_logic = TriadOpenBB()
        self.triad_strategy = TriadStrategy()
        self.risk_manager = RiskManager(account_equity=capital)
        self.intraday_cache = IntradayCacheManager()
        
        logger.info("✅ Scanner initialized")
    
    def market_health_check(self):
        """
        Verifica condiciones de mercado para trading
        
        Returns:
            dict con status y max_positions permitidas
        """
        logger.info("🏥 Market Health Check...")
        
        try:
            # SPY data
            spy = yf.download('SPY', period='3mo', progress=False)
            
            if len(spy) < 50:
                return {'status': '❌ ERROR', 'can_trade': False, 'max_positions': 0}
            
            # SPX trend (EMA 21 vs 50)
            spy['ema21'] = spy['Close'].ewm(span=21).mean()
            spy['ema50'] = spy['Close'].ewm(span=50).mean()
            spx_bullish = spy['ema21'].iloc[-1] > spy['ema50'].iloc[-1]
            
            # VIX
            vix = yf.download('^VIX', period='1mo', progress=False)
            vix_current = vix['Close'].iloc[-1]
            vix_avg = vix['Close'].mean()
            vix_low = vix_current < 20
            vix_stable = vix_current <= vix_avg
            
            # Volatility (20-day ATR)
            spy['atr'] = spy['High'] - spy['Low']
            spy_vol = (spy['atr'].tail(20).mean() / spy['Close'].iloc[-1]) * 100
            
            # Scoring
            points = 0
            reasons = []
            
            if spx_bullish:
                points += 3
                reasons.append("✅ SPX en tendencia ALCISTA")
            else:
                reasons.append("❌ SPX en tendencia BAJISTA")
            
            if vix_low:
                points += 2
                reasons.append(f"✅ VIX BAJO ({vix_current:.1f})")
            elif vix_current < 25:
                points += 1
                reasons.append(f"⚠️ VIX MODERADO ({vix_current:.1f})")
            else:
                reasons.append(f"❌ VIX ALTO ({vix_current:.1f})")
            
            if vix_stable:
                points += 1
                reasons.append("✅ VIX ESTABLE")
            
            if spy_vol < 2.0:
                points += 1
                reasons.append(f"✅ Volatilidad BAJA ({spy_vol:.1f}%)")
            
            # Decision
            if points >= 5:
                status = "🟢 GREEN LIGHT"
                can_trade = True
                max_positions = 4
            elif points >= 3:
                status = "🟡 YELLOW LIGHT"
                can_trade = True
                max_positions = 2
            else:
                status = "🔴 RED LIGHT"
                can_trade = False
                max_positions = 0
            
            print("\n" + "="*60)
            print("🏥 MARKET HEALTH CHECK")
            print("="*60)
            print(f"Status: {status} ({points}/7 points)")
            print(f"Max Positions: {max_positions}")
            print("\nReasons:")
            for reason in reasons:
                print(f"  {reason}")
            print("="*60 + "\n")
            
            return {
                'status': status,
                'can_trade': can_trade,
                'max_positions': max_positions,
                'points': points,
                'reasons': reasons
            }
            
        except Exception as e:
            logger.error(f"Market health check failed: {e}")
            return {'status': '❌ ERROR', 'can_trade': False, 'max_positions': 0}
    
    def scan_ticker(self, ticker):
        """
        Escanea un ticker individual con AVWAP
        
        Returns:
            dict con setup info o None
        """
        try:
            # 1. Get daily data
            df_daily = self.data_provider.get_daily_data(
                ticker,
                start_date=(datetime.now() - timedelta(days=200)).strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d')
            )
            
            if len(df_daily) < 50:
                return None
            
            # Lowercase columns
            df_daily.columns = [c.lower() for c in df_daily.columns]
            
            # Current price
            current_price = df_daily['close'].iloc[-1]
            
            # Basic filters
            if current_price < 10 or current_price > 1000:
                return None
            
            avg_volume = df_daily['volume'].tail(20).mean()
            if avg_volume < 500000:
                return None
            
            # 2. Calculate indicators
            df_daily = self.triad_logic._calculate_indicators(df_daily)
            
            # 3. Detect patterns (Base)
            engine = PatternDetectionEngine(ticker, df_daily)
            patterns = engine.scan_all_patterns()
            
            if not patterns:
                return None
            
            best_pattern = patterns[0]
            
            # Must be close to pivot (< 3%)
            distance_to_pivot = ((best_pattern.pivot_price - current_price) / current_price) * 100
            if distance_to_pivot > 3:
                return None
            
            # 4. Try to get AVWAP from cache
            avwap_data = None
            try:
                df_intraday = self.intraday_cache.get_cached_data(ticker, days=5)
                
                if not df_intraday.empty and len(df_intraday) > 10:
                    # Calculate AVWAP ATH from cached intraday
                    avwap_result = self._calculate_avwap_from_cache(df_intraday, df_daily)
                    if avwap_result:
                        avwap_data = avwap_result
            except Exception as e:
                logger.debug(f"{ticker}: Could not load intraday cache: {e}")
            
            # 5. Apply Triad Strategy
            base_data = {
                'detected': True,
                'base_high': best_pattern.pivot_price,
                'base_low': best_pattern.pivot_price * (1 - best_pattern.base_depth),
                'base_length': best_pattern.base_length
            }
            
            if avwap_data:
                # Full Triad with AVWAP
                decision = self.triad_strategy.execute(
                    current_price=current_price,
                    base_data=base_data,
                    avwap_data=avwap_data,
                    adr_pct=2.0  # Placeholder
                )
            else:
                # Fallback: Simple breakout (Camino 1 sin AVWAP)
                decision = type('obj', (object,), {
                    'camino': Camino.BLUE_SKY,
                    'entry_price': best_pattern.entry_price,
                    'stop_loss': best_pattern.stop_loss,
                    'reasoning': "Base detected, AVWAP not available (using pattern entry)",
                    'context': {}
                })()
            
            # 6. Calculate position size
            risk_dollars = self.capital * self.risk_per_trade
            stop_distance = decision.entry_price - decision.stop_loss
            
            if stop_distance <= 0:
                return None
            
            shares = int(risk_dollars / stop_distance)
            
            if shares == 0:
                return None
            
            position_value = shares * decision.entry_price
            
            return {
                'ticker': ticker,
                'camino': decision.camino.name,
                'pattern': best_pattern.pattern_type.value,
                'current_price': current_price,
                'trigger': decision.entry_price,
                'stop_loss': decision.stop_loss,
                'shares': shares,
                'position_value': position_value,
                'risk_reward': (best_pattern.pivot_price * 1.08 - decision.entry_price) / stop_distance if stop_distance > 0 else 0,
                'pattern_confidence': best_pattern.confidence,
                'reasoning': decision.reasoning,
                'distance_to_trigger': ((decision.entry_price - current_price) / current_price) * 100,
                'has_avwap': avwap_data is not None
            }
            
        except Exception as e:
            logger.debug(f"{ticker}: Error scanning: {e}")
            return None
    
    def _calculate_avwap_from_cache(self, df_intraday, df_daily):
        """Calcula AVWAP desde datos intraday cacheados"""
        try:
            # Find ATH
            ath_price = df_daily['high'].max()
            ath_date = df_daily['high'].idxmax()
            
            # Get intraday data from ATH onwards
            df_since_ath = df_intraday[df_intraday.index >= ath_date]
            
            if len(df_since_ath) < 10:
                return None
            
            # Calculate AVWAP
            if 'vwap' in df_since_ath.columns:
                current_avwap = df_since_ath['vwap'].iloc[-1]
            else:
                typical_price = (df_since_ath['high'] + df_since_ath['low'] + df_since_ath['close']) / 3
                current_avwap = (typical_price * df_since_ath['volume']).sum() / df_since_ath['volume'].sum()
            
            current_price = df_daily['close'].iloc[-1]
            distance_pct = (current_avwap - current_price) / current_price
            
            return {
                'calculated': True,
                'current_avwap': current_avwap,
                'ath_price': ath_price,
                'ath_date': str(ath_date),
                'distance_to_avwap_pct': distance_pct,
                'days_since_ath': (datetime.now() - ath_date).days
            }
            
        except Exception as e:
            logger.debug(f"AVWAP calculation failed: {e}")
            return None
    
    def scan_universe(self, tickers, max_setups=10):
        """
        Escanea universo completo
        
        Returns:
            DataFrame con focus list
        """
        logger.info(f"🔍 Scanning {len(tickers)} tickers...")
        
        results = []
        
        for ticker in tqdm(tickers, desc="Scanning"):
            setup = self.scan_ticker(ticker)
            if setup:
                results.append(setup)
        
        if not results:
            logger.info("❌ No setups found")
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        
        # Sort by Camino priority and confidence
        camino_priority = {'BLUE_SKY': 1, 'VWAP_RECLAIM': 2, 'SAFETY_CHECK': 3}
        df['camino_priority'] = df['camino'].map(camino_priority)
        df = df.sort_values(['camino_priority', 'pattern_confidence'], ascending=[True, False])
        df = df.drop('camino_priority', axis=1)
        
        # Limit to max setups
        df = df.head(max_setups)
        
        logger.info(f"✅ Found {len(df)} high-quality setups")
        
        return df
    
    def save_focus_list(self, df, filename='focus_list.csv'):
        """Guarda focus list a CSV"""
        if df.empty:
            logger.warning("No setups to save")
            return
        
        output_file = Path(filename)
        df.to_csv(output_file, index=False)
        logger.info(f"💾 Focus list saved to {output_file}")
    
    def print_focus_list(self, df):
        """Imprime focus list formateada"""
        if df.empty:
            print("\n❌ No setups found\n")
            return
        
        print("\n" + "="*100)
        print(f"📋 FOCUS LIST - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*100)
        
        for camino_name in ['BLUE_SKY', 'VWAP_RECLAIM', 'SAFETY_CHECK']:
            subset = df[df['camino'] == camino_name]
            if len(subset) == 0:
                continue
            
            print(f"\n🎯 {camino_name} ({len(subset)} setups)")
            print("-"*100)
            print(f"{'Ticker':<8} {'Pattern':<18} {'Price':<10} {'Trigger':<10} {'Stop':<10} {'Shares':<8} {'R:R':<6} {'AVWAP':<6}")
            print("-"*100)
            
            for _, row in subset.iterrows():
                avwap_status = "✅" if row['has_avwap'] else "❌"
                print(f"{row['ticker']:<8} {row['pattern']:<18} "
                      f"${row['current_price']:<9.2f} ${row['trigger']:<9.2f} "
                      f"${row['stop_loss']:<9.2f} {row['shares']:<8} "
                      f"{row['risk_reward']:<6.2f} {avwap_status:<6}")
        
        print("="*100 + "\n")


def load_universe(source):
    """Carga universo de tickers"""
    if source == 'sp500':
        try:
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            tables = pd.read_html(url)
            tickers = tables[0]['Symbol'].tolist()
            return [t.replace('.', '-') for t in tickers]
        except:
            logger.warning("Could not download S&P 500, using fallback")
            source = 'universe_tickers.txt'
    
    # Load from file
    filepath = Path(source)
    if not filepath.exists():
        logger.error(f"Universe file not found: {source}")
        return []
    
    tickers = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                tickers.extend([t.strip() for t in line.split(',') if t.strip()])
    
    return sorted(list(set(tickers)))


def main():
    parser = argparse.ArgumentParser(description='Live Scanner with AVWAP')
    parser.add_argument('--universe', type=str, default='sp500', 
                       help='Universe source: sp500 or file path')
    parser.add_argument('--capital', type=float, default=100000,
                       help='Account capital')
    parser.add_argument('--risk-per-trade', type=float, default=0.02,
                       help='Risk per trade (0.02 = 2%%)')
    parser.add_argument('--max-setups', type=int, default=10,
                       help='Maximum setups to return')
    parser.add_argument('--market-check-only', action='store_true',
                       help='Only run market health check')
    parser.add_argument('--output', type=str, default='focus_list.csv',
                       help='Output CSV filename')
    parser.add_argument('--limit', type=int,
                       help='Limit tickers (for testing)')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("🚀 LIVE SCANNER WITH AVWAP")
    print("="*60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Capital: ${args.capital:,.0f}")
    print(f"Risk per trade: {args.risk_per_trade*100:.1f}%")
    print("="*60 + "\n")
    
    scanner = AVWAPLiveScanner(capital=args.capital, risk_per_trade=args.risk_per_trade)
    
    try:
        # Market health check
        health = scanner.market_health_check()
        
        if args.market_check_only:
            return
        
        if not health['can_trade']:
            print("❌ Market conditions not favorable for trading")
            print("   Stopping scan.\n")
            return
        
        # Load universe
        tickers = load_universe(args.universe)
        
        if args.limit:
            tickers = tickers[:args.limit]
        
        print(f"📊 Universe: {len(tickers)} tickers")
        print(f"🎯 Max setups: {args.max_setups}")
        print(f"🚦 Max positions: {health['max_positions']}\n")
        
        # Scan
        focus_list = scanner.scan_universe(tickers, max_setups=args.max_setups)
        
        # Display & Save
        scanner.print_focus_list(focus_list)
        scanner.save_focus_list(focus_list, args.output)
        
        print(f"\n💡 Next steps:")
        print(f"   1. Review focus list: {args.output}")
        print(f"   2. Open charts for visual confirmation")
        print(f"   3. Place buy-stop orders at trigger prices")
        print(f"   4. Set stop-loss orders")
        print(f"\n✅ Scanner completed!\n")
        
    finally:
        scanner.intraday_cache.close()


if __name__ == "__main__":
    main()
