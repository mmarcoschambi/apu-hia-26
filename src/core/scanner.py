"""
Triad Scanner - Main Entry Point
Scans watchlist and generates signals using the Triad Protocol
"""
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.data.market_data import MarketDataProvider
from src.indicators.triad import TriadIndicators
from src.strategies.triad_protocol import TriadStrategy, Camino
from src.core.market_context import MarketContext
from config.settings import CACHE_DIR, LOG_DIR, INTRADAY_TIMEFRAME

# Setup logging
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f'triad_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TriadScanner:
    
    def __init__(self):
        self.data_provider = MarketDataProvider(cache_dir=CACHE_DIR)
        self.indicators = TriadIndicators()
        self.strategy = TriadStrategy()
        self.market_context = MarketContext(self.data_provider)
    
    def scan_symbol(self, symbol: str) -> dict:
        """
        Complete analysis pipeline for a single symbol
        Returns signal and all supporting data
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Scanning {symbol}")
        logger.info(f"{'='*60}")
        
        try:
            # 1. Fetch Market Data
            logger.info("Fetching market data...")
            daily_df = self.data_provider.get_daily_data(symbol, period="1y")
            intraday_df = self.data_provider.get_intraday_data(symbol, interval=INTRADAY_TIMEFRAME, days=5)
            adr = self.data_provider.calculate_adr(symbol, period=20)
            
            if daily_df.empty:
                logger.warning(f"No daily data for {symbol}")
                return {'symbol': symbol, 'signal': None, 'error': 'No daily data'}
            
            # 2. Calculate Indicators
            logger.info("Calculating Triad indicators...")
            base_data = self.indicators.detect_base(daily_df, lookback=20)
            avwap_data = self.indicators.calculate_avwap_from_ath(daily_df)
            
            logger.info(f"Base detected: {base_data['detected']}")
            if base_data['detected']:
                logger.info(f"  Base High: ${base_data['base_high']:.2f}")
                logger.info(f"  Base Low: ${base_data['base_low']:.2f}")
                logger.info(f"  Current Price: ${base_data['current_price']:.2f}")
            
            logger.info(f"AVWAP calculated: {avwap_data['calculated']}")
            if avwap_data['calculated']:
                logger.info(f"  ATH: ${avwap_data['ath_price']:.2f} on {avwap_data['ath_date']}")
                logger.info(f"  Current AVWAP: ${avwap_data['current_avwap']:.2f}")
                logger.info(f"  Distance to AVWAP: {avwap_data['distance_to_avwap_pct']*100:.2f}%")
            
            # 3. Intraday VWAP (if available)
            vwap_data = {}
            gap_data = {}
            if not intraday_df.empty:
                vwap_data = self.indicators.calculate_intraday_vwap(intraday_df)
                previous_close = daily_df['Close'].iloc[-2] if len(daily_df) > 1 else daily_df['Close'].iloc[-1]
                gap_data = self.indicators.detect_gap_down(intraday_df, previous_close)
                
                if vwap_data.get('calculated'):
                    logger.info(f"Intraday VWAP: ${vwap_data['current_vwap']:.2f}")
                    logger.info(f"  Above VWAP: {vwap_data['above_vwap']}")
                    logger.info(f"  Crossed Up: {vwap_data['crossed_up']}")
                
                if gap_data.get('detected'):
                    logger.info(f"Gap Down detected: {gap_data['gap_pct']*100:.2f}%")
            
            # 4. Market Context
            logger.info("Analyzing market context...")
            market_ctx = self.market_context.analyze_indices(['SPY', 'QQQ'])
            logger.info(f"Market Weak: {market_ctx.get('market_weak', False)}")
            
            # 5. Generate Signal
            logger.info("Generating signal...")
            signal = self.strategy.analyze(
                base_data=base_data,
                avwap_data=avwap_data,
                vwap_data=vwap_data,
                gap_data=gap_data,
                market_context=market_ctx,
                adr=adr
            )
            
            # Log Signal
            self._log_signal(symbol, signal)
            
            return {
                'symbol': symbol,
                'signal': signal,
                'base_data': base_data,
                'avwap_data': avwap_data,
                'vwap_data': vwap_data,
                'market_context': market_ctx,
                'adr': adr,
                'timestamp': datetime.now()
            }
        
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}", exc_info=True)
            return {'symbol': symbol, 'signal': None, 'error': str(e)}
    
    def _log_signal(self, symbol: str, signal):
        """Pretty print signal output"""
        logger.info(f"\n{'*'*60}")
        logger.info(f"SIGNAL FOR {symbol}")
        logger.info(f"{'*'*60}")
        
        if signal.camino:
            logger.info(f"Camino: {signal.camino.name}")
        
        logger.info(f"Action: {signal.action}")
        
        if signal.entry_price:
            logger.info(f"Entry Price: ${signal.entry_price:.2f}")
        
        if signal.stop_loss:
            logger.info(f"Stop Loss: ${signal.stop_loss:.2f}")
            if signal.entry_price:
                risk_pct = (signal.entry_price - signal.stop_loss) / signal.entry_price * 100
                logger.info(f"Risk: {risk_pct:.2f}%")
        
        logger.info(f"Position Size: {signal.position_size_multiplier*100:.0f}% of standard")
        logger.info(f"\nReasoning: {signal.reasoning}")
        logger.info(f"{'*'*60}\n")
    
    def scan_watchlist(self, symbols: list) -> list:
        """Scan multiple symbols"""
        results = []
        
        logger.info(f"\nScanning {len(symbols)} symbols: {', '.join(symbols)}\n")
        
        for symbol in symbols:
            result = self.scan_symbol(symbol)
            results.append(result)
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("SCAN SUMMARY")
        logger.info(f"{'='*60}")
        
        actionable = [r for r in results if r.get('signal') and r['signal'].action in ['BUY_STOP', 'MANUAL_WATCH']]
        
        logger.info(f"Total Scanned: {len(results)}")
        logger.info(f"Actionable Signals: {len(actionable)}")
        
        if actionable:
            logger.info("\nActionable Setups:")
            for r in actionable:
                signal = r['signal']
                logger.info(f"  {r['symbol']}: {signal.camino.name if signal.camino else 'N/A'} - {signal.action}")
        
        return results


def main():
    """Example usage"""
    scanner = TriadScanner()
    
    # Example watchlist - replace with your tickers
    watchlist = ['RDDT', 'CEG', 'AAPL', 'NVDA', 'TSLA']
    
    results = scanner.scan_watchlist(watchlist)
    
    # You can also scan a single symbol
    # result = scanner.scan_symbol('RDDT')


if __name__ == "__main__":
    main()
