#!/usr/bin/env python3
"""
LIVE TRADING SCANNER - Sistema Completo de Operación Diaria
===========================================================
Implementa el flujo completo del día de trading:
1. Market Health Check (pre-market)
2. Sector Rotation Analysis
3. Dynamic Universe Scanning  
4. Pattern Detection con precios reales
5. Focus List Generation con precios trigger

Features:
- Cache persistente que sobrevive entre sesiones
- Multiprocessing para escanear el universo rápido
- UI de progreso visual
- Market filters integrados (SPX tendencia, VIX, sectores)
"""

import sys
from pathlib import Path
import argparse
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging
from tqdm import tqdm
import time
from multiprocessing import Pool, cpu_count
import yfinance as yf
import warnings

warnings.filterwarnings('ignore')

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.cache_manager import CacheManager
from src.data.market_data import MarketDataProvider
from src.core.market_context import MarketContext
from src.core.pattern_screener import PatternScreener
from src.utils.risk_manager import RiskManager
from config.scanner_combo_adapter import (
    calculate_effective_entry_price,
    calculate_adjusted_pnl,
    is_regime_blocked,
)

# ── Multi-Screener System ──────────────────────────────────────────────────
try:
    from src.screeners import ScreenerRegistry, ScreenerPipeline
    _SCREENERS_AVAILABLE = True
except ImportError as _se:
    _SCREENERS_AVAILABLE = False
# ──────────────────────────────────────────────────────────────────────────

# ── Multi-Screener System ──────────────────────────────────────────────────
try:
    from src.screeners import ScreenerRegistry, ScreenerPipeline
    _SCREENERS_AVAILABLE = True
except ImportError:
    _SCREENERS_AVAILABLE = False
    logger = logging.getLogger(__name__)  # puede que aún no esté definido
# ──────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# UNIVERSE PROVIDERS
# ============================================================================

def load_static_universe():
    """Carga universo desde archivo estático"""
    universe_file = Path(__file__).parent / "universe_tickers.txt"
    
    if not universe_file.exists():
        logger.warning("universe_tickers.txt not found, using minimal fallback")
        return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 
                'BRK.B', 'V', 'JNJ', 'WMT', 'JPM', 'MA', 'PG', 'UNH']
    
    tickers = []
    with open(universe_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Separar por comas
                line_tickers = [t.strip() for t in line.split(',') if t.strip()]
                tickers.extend(line_tickers)
    
    return sorted(list(set(tickers)))


def get_sp500_tickers():
    """Descarga S&P 500 actualizado con fallback"""
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df['Symbol'].tolist()
        tickers = [t.replace('.', '-') for t in tickers]
        return tickers
    except Exception as e:
        logger.warning(f"Could not download S&P 500 from Wikipedia: {e}")
        logger.info("Using static universe file instead...")
        return load_static_universe()


def get_nasdaq100_tickers():
    """Descarga NASDAQ 100 con fallback"""
    try:
        url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        tables = pd.read_html(url)
        df = tables[4]
        return df['Ticker'].tolist()
    except Exception as e:
        logger.warning(f"Could not download NASDAQ 100 from Wikipedia: {e}")
        return []  # El S&P 500 ya incluye muchos del NASDAQ


def get_universe(include_sp500=True, include_nasdaq=True, use_static=False):
    """
    Obtiene el universo completo de trading
    Args:
        use_static: Si True, usa archivo estático directamente
    Returns: Lista única de tickers
    """
    # Si se solicita usar estático directamente
    if use_static:
        logger.info("Loading universe from static file...")
        tickers = load_static_universe()
        logger.info(f"✅ Loaded {len(tickers)} tickers from static file")
        return tickers
    
    # Intentar descargar dinámicamente
    tickers = []
    sp500_downloaded = False
    
    if include_sp500:
        logger.info("Downloading S&P 500...")
        sp500 = get_sp500_tickers()
        if len(sp500) > 100:  # Si descargó exitosamente
            tickers.extend(sp500)
            sp500_downloaded = True
            logger.info(f"✅ S&P 500: {len(sp500)} tickers")
        else:
            logger.warning("S&P 500 download failed, falling back to static file")
            tickers = load_static_universe()
            logger.info(f"✅ Loaded {len(tickers)} tickers from static file")
            return tickers
    
    if include_nasdaq and sp500_downloaded:
        logger.info("Downloading NASDAQ 100...")
        nasdaq = get_nasdaq100_tickers()
        tickers.extend(nasdaq)
        logger.info(f"✅ NASDAQ 100: {len(nasdaq)} tickers")
    
    # Eliminar duplicados
    unique_tickers = sorted(list(set(tickers)))
    
    # Si el universo está muy pequeño, usar archivo estático
    if len(unique_tickers) < 50:
        logger.warning("Universe too small, using static file as fallback")
        return load_static_universe()
    
    logger.info(f"✅ Total universe: {len(unique_tickers)} unique tickers")
    
    return unique_tickers


# ============================================================================
# MARKET HEALTH MONITOR
# ============================================================================

class MarketHealthMonitor:
    """Evalúa condiciones del mercado antes de operar"""
    
    def __init__(self, cache_manager):
        self.cache = cache_manager
    
    def check_market_health(self):
        """
        Verifica:
        - SPX en tendencia alcista (SMA5 > SMA20)
        - Volatilidad baja/estable
        - Momentum general
        
        Returns: dict con status y métricas
        """
        logger.info("Checking market health...")
        
        # Descargar SPX y QQQ
        spx_data = yf.download('^GSPC', period='3mo', progress=False)
        qqq_data = yf.download('QQQ', period='3mo', progress=False)
        vix_data = yf.download('^VIX', period='1mo', progress=False)

        # Handle yfinance MultiIndex column format (newer versions)
        if isinstance(spx_data.columns, pd.MultiIndex):
            spx_data.columns = spx_data.columns.droplevel(1)
        if isinstance(qqq_data.columns, pd.MultiIndex):
            qqq_data.columns = qqq_data.columns.droplevel(1)
        if isinstance(vix_data.columns, pd.MultiIndex):
            vix_data.columns = vix_data.columns.droplevel(1)

        # 1. Tendencia SPX
        spx_data['SMA5'] = spx_data['Close'].rolling(5).mean()
        spx_data['SMA20'] = spx_data['Close'].rolling(20).mean()
        spx_bullish = spx_data['SMA5'].iloc[-1] > spx_data['SMA20'].iloc[-1]

        # 2. VIX
        vix_current = float(vix_data['Close'].iloc[-1])
        vix_5d_ago = float(vix_data['Close'].iloc[-5]) if len(vix_data) >= 5 else vix_current
        vix_stable = vix_current <= vix_5d_ago
        vix_low = vix_current < 20
        
        # 3. Volatilidad realizada
        spx_returns = np.log(spx_data['Close'] / spx_data['Close'].shift(1))
        spx_vol = spx_returns.rolling(20).std().iloc[-1] * np.sqrt(252) * 100
        
        # Scoring
        points = 0
        reasons = []

        if spx_bullish:
            points += 2
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
            reasons.append("✅ VIX ESTABLE/BAJANDO")
        else:
            reasons.append("❌ VIX SUBIENDO")

        if spx_vol < 15:
            points += 2
            reasons.append(f"✅ Volatilidad BAJA ({spx_vol:.1f}%)")
        elif spx_vol < 20:
            points += 1
            reasons.append(f"⚠️ Volatilidad MODERADA ({spx_vol:.1f}%)")
        else:
            reasons.append(f"❌ Volatilidad ALTA ({spx_vol:.1f}%)")

        # Decision (con régimen numérico para blocked_mask)
        # Régimen: 1=bull, 2=neutral, 3=bear, 4=crash
        if points >= 5:
            status = "🟢 GREEN LIGHT"
            can_trade = True
            max_positions = 4
            regime_status = 1  # bull
        elif points >= 3:
            status = "🟡 YELLOW LIGHT"
            can_trade = True
            max_positions = 2
            regime_status = 2  # neutral
        else:
            status = "🔴 RED LIGHT"
            can_trade = False
            max_positions = 0
            regime_status = 3  # bear
        
        return {
            'status': status,
            'can_trade': can_trade,
            'max_positions': max_positions,
            'points': points,
            'total_points': 7,
            'reasons': reasons,
            'spx_bullish': spx_bullish,
            'vix_current': vix_current,
            'vix_stable': vix_stable,
            'spx_volatility': spx_vol,
            'regime_status': regime_status,  # NEW: 1=bull, 2=neutral, 3=bear, 4=crash
        }


# ============================================================================
# SECTOR ROTATION ANALYZER
# ============================================================================

SECTOR_ETFS = {
    'XLK': 'Technology',
    'XLF': 'Financials',
    'XLV': 'Healthcare',
    'XLE': 'Energy',
    'XLY': 'Consumer Discretionary',
    'XLP': 'Consumer Staples',
    'XLI': 'Industrials',
    'XLB': 'Materials',
    'XLRE': 'Real Estate',
    'XLU': 'Utilities',
    'XLC': 'Communication Services'
}


class SectorRotationAnalyzer:
    """Identifica sectores fuertes"""
    
    def analyze_sectors(self):
        """Rankea sectores por momentum"""
        logger.info("Analyzing sector rotation...")
        
        results = []
        
        for etf, name in SECTOR_ETFS.items():
            try:
                data = yf.download(etf, period='3mo', progress=False)

                # Handle yfinance MultiIndex column format
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(1)

                if len(data) < 60:
                    continue

                # Rendimientos en diferentes timeframes
                rend_5d = ((float(data['Close'].iloc[-1]) / float(data['Close'].iloc[-5])) - 1) * 100
                rend_20d = ((float(data['Close'].iloc[-1]) / float(data['Close'].iloc[-20])) - 1) * 100
                rend_60d = ((float(data['Close'].iloc[-1]) / float(data['Close'].iloc[-60])) - 1) * 100
                
                # Score ponderado
                score = 0
                if rend_5d > 0:
                    score += 1
                if rend_20d > 0:
                    score += 2  # Peso mayor al medio plazo
                if rend_60d > 0:
                    score += 1
                
                results.append({
                    'etf': etf,
                    'sector': name,
                    'rend_5d': rend_5d,
                    'rend_20d': rend_20d,
                    'rend_60d': rend_60d,
                    'score': score
                })
            
            except Exception as e:
                logger.warning(f"Error analyzing {etf}: {e}")
                continue
        
        df = pd.DataFrame(results)
        df = df.sort_values(['score', 'rend_20d'], ascending=False)
        
        return df


# ============================================================================
# PATTERN SCANNER (con multiprocessing)
# ============================================================================

def scan_ticker_for_patterns(args):
    """
    Worker function para escanear un ticker
    Esta función se ejecuta en paralelo
    """
    ticker, start_date, end_date = args

    try:
        # Descargar datos
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)

        # Handle yfinance MultiIndex column format
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        if len(data) < 40:
            return None

        # Precio y volumen actuales
        current_price = float(data['Close'].iloc[-1])
        avg_volume = float(data['Volume'].tail(20).mean())

        # Filtros básicos
        if current_price < 10 or current_price > 500:
            return None
        if avg_volume < 500000:
            return None
        
        # Detectar patrones
        pattern = detect_cup_and_handle(data) or detect_flat_base(data) or detect_vcp(data)
        
        if pattern:
            return {
                'ticker': ticker,
                'pattern': pattern['pattern'],
                'pivot': pattern['pivot'],
                'current_price': current_price,
                'distance_to_pivot': ((pattern['pivot'] - current_price) / current_price) * 100,
                'avg_volume': avg_volume
            }
        
        return None
    
    except Exception as e:
        return None


def detect_cup_and_handle(data, tolerance=0.03):
    """Detecta patrón Cup & Handle"""
    if len(data) < 40:
        return None
    
    left_peak = data['High'][-60:-30].max() if len(data) >= 60 else data['High'][:len(data)//2].max()
    right_peak = data['High'][-20:-1].max()
    bottom = data['Low'][-45:-15].min() if len(data) >= 45 else data['Low'].min()
    
    peak_diff = abs(left_peak - right_peak) / left_peak if left_peak > 0 else 1
    depth = (left_peak - bottom) / left_peak if left_peak > 0 else 0
    
    if peak_diff < tolerance and 0.12 < depth < 0.33:
        return {
            'pattern': 'Cup & Handle',
            'pivot': right_peak,
            'depth': depth * 100
        }
    
    return None


def detect_flat_base(data):
    """Detecta Flat Base"""
    if len(data) < 20:
        return None
    
    last_20 = data.tail(20)
    high = last_20['High'].max()
    low = last_20['Low'].min()
    range_pct = (high - low) / low if low > 0 else 1
    
    if range_pct < 0.15:
        return {
            'pattern': 'Flat Base',
            'pivot': high,
            'range': range_pct * 100
        }
    
    return None


def detect_vcp(data):
    """Detecta VCP (Volatility Contraction Pattern)"""
    if len(data) < 30:
        return None
    
    # Calcular ATR simple
    high_low = data['High'] - data['Low']
    atr = high_low.rolling(14).mean()
    
    if len(atr) < 20:
        return None
    
    atr_recent = atr.tail(10).mean()
    atr_previous = atr.iloc[-20:-10].mean()
    
    if atr_recent < atr_previous * 0.7 and atr_previous > 0:
        return {
            'pattern': 'VCP',
            'pivot': data['High'].tail(20).max(),
            'contraction': ((atr_previous - atr_recent) / atr_previous) * 100
        }
    
    return None


class PatternScanner:
    """Escanea el universo en paralelo buscando patrones"""

    def __init__(
        self, 
        n_processes=None,
        fee_rate=0.001,
        slippage_rate=0.001,
        regime_blocked=None,
        scanner_filter="default",
        pattern_filter="",
        lookback_days=180,
        max_setups=5,
    ):
        self.n_processes = n_processes or max(1, cpu_count() - 1)
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.regime_blocked = regime_blocked or [3, 4]
        self.scanner_filter = scanner_filter
        self.pattern_filter = pattern_filter
        self.lookback_days = lookback_days
        self.max_setups = max_setups

    def scan_universe(self, tickers, lookback_days=None, market_regime_status=None):
        """
        Escanea el universo completo usando multiprocessing
        
        Args:
            tickers: List of ticker symbols to scan
            lookback_days: Override for lookback period
            market_regime_status: Current market regime status (1-4)
        """
        # Check regime filter (Fase 1: Kill-switch)
        if market_regime_status is not None:
            is_blocked = is_regime_blocked(market_regime_status, self.regime_blocked)
            if is_blocked:
                logger.warning(
                    f"🔴 TRADING BLOCKED - Regime {market_regime_status} in blocked list {self.regime_blocked}"
                )
                return pd.DataFrame()
        
        effective_lookback = lookback_days or self.lookback_days
        
        logger.info(f"Scanning {len(tickers)} tickers using {self.n_processes} processes...")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=effective_lookback)

        # Preparar argumentos para workers
        args = [(ticker, start_date, end_date) for ticker in tickers]

        # Escanear en paralelo con barra de progreso
        results = []
        with Pool(processes=self.n_processes) as pool:
            with tqdm(total=len(tickers), desc="Scanning tickers") as pbar:
                for result in pool.imap_unordered(scan_ticker_for_patterns, args, chunksize=10):
                    if result:
                        results.append(result)
                    pbar.update()

        df = pd.DataFrame(results)

        if len(df) > 0:
            df = df.sort_values('distance_to_pivot')
            
            # Apply fees and slippage adjustment to entry prices
            df['entry_price_effective'] = df['pivot'].apply(
                lambda p: calculate_effective_entry_price(
                    p, self.fee_rate, self.slippage_rate
                )
            )
            
            # Filter out setups where edge < costs
            df['distance_to_pivot_effective'] = (
                (df['entry_price_effective'] - df['current_price']) / df['current_price'] * 100
            )
            
            # Log cost analysis
            total_cost_bps = (self.fee_rate + self.slippage_rate) * 10000 * 2
            logger.info(
                f"Transaction costs: {total_cost_bps:.0f}bps "
                f"(fee={self.fee_rate*10000:.0f}bps + slippage={self.slippage_rate*10000:.0f}bps)"
            )

        logger.info(f"✅ Found {len(df)} setups with patterns")

        return df


# ============================================================================
# FOCUS LIST GENERATOR
# ============================================================================

class FocusListGenerator:
    """Filtra watchlist para generar lista de foco diaria"""
    
    def generate_focus_list(self, watchlist, max_setups=5):
        """
        Filtra watchlist para setups inminentes
        Criterios:
        - Distancia al pivot < 2%
        - Volumen contrayendo
        - ATR bajando
        """
        logger.info("Generating focus list...")
        
        if len(watchlist) == 0:
            return pd.DataFrame()
        
        focus = []
        
        for _, row in watchlist.iterrows():
            ticker = row['ticker']
            
            try:
                # Proximidad al pivot
                if row['distance_to_pivot'] > 2:
                    continue
                
                # Descargar datos recientes
                data = yf.download(ticker, period='1mo', progress=False)

                # Handle yfinance MultiIndex column format
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(1)

                if len(data) < 10:
                    continue

                # Volumen bajo
                vol_recent = float(data['Volume'].tail(3).mean())
                vol_avg = float(data['Volume'].tail(20).mean())
                
                if vol_recent > vol_avg * 0.8:
                    continue
                
                # Calcular trigger price
                pivot = row['pivot']
                if pivot < 200:
                    trigger = pivot + 0.10
                else:
                    trigger = pivot + 0.20
                
                # Evitar números redondos
                if trigger % 1.0 < 0.05:
                    trigger += 0.05
                
                stop_loss = trigger * 0.92
                
                focus.append({
                    'ticker': ticker,
                    'pattern': row['pattern'],
                    'current_price': row['current_price'],
                    'pivot': pivot,
                    'trigger_price': trigger,
                    'stop_loss': stop_loss,
                    'distance_%': row['distance_to_pivot']
                })
            
            except Exception as e:
                logger.warning(f"Error processing {ticker}: {e}")
                continue
        
        df = pd.DataFrame(focus)
        
        if len(df) > 0:
            df = df.head(max_setups)
        
        return df


# ============================================================================
# MAIN SCANNER
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Live Trading Scanner')
    parser.add_argument('--sp500', action='store_true', default=True, help='Include S&P 500')
    parser.add_argument('--nasdaq', action='store_true', default=True, help='Include NASDAQ 100')
    parser.add_argument('--static', action='store_true', help='Use static universe file (no download)')
    parser.add_argument('--processes', type=int, default=None, help='Number of parallel processes')
    parser.add_argument('--max-setups', type=int, default=5, help='Max setups in focus list')
    parser.add_argument('--combo', type=str, default=None, 
                        help='Combo YAML config name (e.g., combo_pullback_entry)')
    parser.add_argument('--screener', type=str, default=None,
                        help='Screener post-pattern. Opciones: minervini_trend, ema21_pullback, '
                             'qullamaggie_momentum, vcp_enhanced. Combinar con + '
                             '(ej. minervini_trend+vcp_enhanced)')
    parser.add_argument('--screener-config', type=str, default=None,
                        help='Path a JSON de configuracion del screener')
    parser.add_argument('--screener-mode', type=str, default='all',
                        choices=['all', 'any', 'sequential'],
                        help='Modo de combinacion cuando se usan multiples screeners (default: all)')

    args = parser.parse_args()

    print("\n" + "="*80)
    print("🚀 LIVE TRADING SCANNER")
    print("="*80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Load YAML combo config if specified
    combo_params = {}
    if args.combo:
        try:
            from config.combo_loader import get_combo_by_name, load_combo_configs
            combos = load_combo_configs()
            combo = get_combo_by_name(combos, args.combo)
            if combo:
                combo_params = {
                    'fee_rate': combo.fee_rate,
                    'slippage_rate': combo.slippage_rate,
                    'regime_blocked': combo.regime_blocked,
                    'scanner_filter': combo.scanner_filter,
                    'pattern_filter': combo.pattern_filter,
                    'lookback_days': combo.lookback_days,
                    'max_setups': combo.max_setups,
                }
                print(f"✅ Loaded combo: {combo.name} (Sharpe={combo.wf_sharpe_mean:.2f})")
            else:
                print(f"⚠️  Combo '{args.combo}' not found, using defaults")
        except Exception as e:
            print(f"⚠️  Failed to load combo: {e}, using defaults")
    
    # PASO 0: Inicializar cache
    cache = CacheManager()
    
    # PASO 1: Market Health Check
    print("\n" + "="*80)
    print("🚦 STEP 1: MARKET HEALTH CHECK")
    print("="*80)
    
    health_monitor = MarketHealthMonitor(cache)
    health = health_monitor.check_market_health()
    
    print(f"\nStatus: {health['status']}")
    print(f"Score: {health['points']}/{health['total_points']}")
    print(f"Regime: {health['regime_status']} (1=bull, 2=neutral, 3=bear, 4=crash)")
    print("\nAnalysis:")
    for reason in health['reasons']:
        print(f"  {reason}")
    
    print(f"\nCan Trade: {'YES' if health['can_trade'] else 'NO'}")
    print(f"Max Positions: {health['max_positions']}")
    
    if not health['can_trade']:
        print("\n🔴 MARKET CONDITIONS NOT FAVORABLE - STOPPING")
        return
    
    # PASO 2: Sector Rotation
    print("\n" + "="*80)
    print("🔄 STEP 2: SECTOR ROTATION ANALYSIS")
    print("="*80)
    
    sector_analyzer = SectorRotationAnalyzer()
    sectors = sector_analyzer.analyze_sectors()
    
    print(f"\n{'Sector':<30} {'5d %':>8} {'20d %':>8} {'60d %':>8} {'Score':>7}")
    print("-"*80)
    
    for _, row in sectors.head(11).iterrows():
        emoji = "🔥" if row['score'] >= 3 else "✅" if row['score'] == 2 else "⚠️"
        print(f"{row['sector']:<30} {row['rend_5d']:>7.2f}% {row['rend_20d']:>7.2f}% "
              f"{row['rend_60d']:>7.2f}% {row['score']:>6}/4 {emoji}")
    
    top_sectors = sectors.head(3)
    print(f"\n🎯 Top 3 Sectors:")
    for i, (_, row) in enumerate(top_sectors.iterrows(), 1):
        print(f"  {i}. {row['sector']} ({row['etf']})")
    
    # PASO 3: Get Universe
    print("\n" + "="*80)
    print("🌎 STEP 3: BUILDING UNIVERSE")
    print("="*80)
    
    universe = get_universe(include_sp500=args.sp500, include_nasdaq=args.nasdaq, use_static=args.static)
    print(f"\n✅ Universe: {len(universe)} tickers")
    
    # PASO 4: Pattern Scanning
    print("\n" + "="*80)
    print("🔍 STEP 4: PATTERN SCANNING")
    print("="*80)

    # Create scanner with combo params (Fase 2: Centralized config)
    scanner = PatternScanner(
        n_processes=args.processes,
        fee_rate=combo_params.get('fee_rate', 0.001),
        slippage_rate=combo_params.get('slippage_rate', 0.001),
        regime_blocked=combo_params.get('regime_blocked', [3, 4]),
        scanner_filter=combo_params.get('scanner_filter', 'default'),
        pattern_filter=combo_params.get('pattern_filter', ''),
        lookback_days=combo_params.get('lookback_days', 180),
        max_setups=combo_params.get('max_setups', 5),
    )
    
    # Pass market regime status for kill-switch (Fase 1: Kill-switch)
    watchlist = scanner.scan_universe(
        universe, 
        market_regime_status=health['regime_status']
    )
    
    if len(watchlist) > 0:
        print(f"\n✅ Found {len(watchlist)} candidates")
        print(f"\n{'Ticker':<8} {'Pattern':<15} {'Current':<10} {'Pivot':<10} {'Eff. Entry':<12} {'Dist %':<10}")
        print("-"*80)

        for _, row in watchlist.head(20).iterrows():
            eff_entry = row.get('entry_price_effective', row['pivot'])
            dist_eff = row.get('distance_to_pivot_effective', row['distance_to_pivot'])
            print(f"{row['ticker']:<8} {row['pattern']:<15} ${row['current_price']:<9.2f} "
                  f"${row['pivot']:<9.2f} ${eff_entry:<11.2f} {dist_eff:<9.2f}%")

        if len(watchlist) > 20:
            print(f"\n... and {len(watchlist) - 20} more candidates")
        
        # Print cost summary
        total_cost_bps = (scanner.fee_rate + scanner.slippage_rate) * 10000 * 2
        print(f"\n💰 Transaction Costs: {total_cost_bps:.0f}bps "
              f"(fee={scanner.fee_rate*10000:.0f}bps + slippage={scanner.slippage_rate*10000:.0f}bps)")
    else:
        print("\n❌ No patterns found")
        return
    
    # PASO 4b: Screener Filter (opcional)
    if args.screener and _SCREENERS_AVAILABLE and len(watchlist) > 0:
        print("\n" + "="*80)
        print(f"🔬 STEP 4b: SCREENER FILTER  [{args.screener}]")
        print("="*80)

        screener_names = [s.strip() for s in args.screener.split("+")]
        try:
            screener_instances = [
                ScreenerRegistry.get(n, ScreenerRegistry.load_config(n, args.screener_config))
                for n in screener_names
            ]
            active_screener = (
                ScreenerPipeline(screener_instances, mode=args.screener_mode)
                if len(screener_instances) > 1
                else screener_instances[0]
            )
        except ValueError as e:
            print(f"⚠️  Screener no disponible: {e}")
            active_screener = None

        if active_screener:
            from src.data.ticker_cache import TickerCache
            _tc = TickerCache()
            filtered_rows = []
            for _, row in watchlist.iterrows():
                t = row['ticker']
                try:
                    df_t = _tc.get_ohlcv(t)
                    if df_t is not None and len(df_t) > 0:
                        result = active_screener.scan(t, df_t)
                        if result.passed:
                            row = row.copy()
                            row['screener_score'] = result.score
                            row['screener_reason'] = result.reason
                            filtered_rows.append(row)
                        else:
                            logger.debug(f"{t} filtrado por screener: {result.reason}")
                except Exception as exc:
                    logger.debug(f"{t} error en screener: {exc}")

            before = len(watchlist)
            watchlist = pd.DataFrame(filtered_rows) if filtered_rows else watchlist.iloc[:0]
            print(f"  Candidates antes: {before}  →  después: {len(watchlist)}")
    elif args.screener and not _SCREENERS_AVAILABLE:
        print("⚠️  Sistema de screeners no disponible (import error). Continuando sin filtro.")

    # PASO 4b: Screener Filter (opcional)
    if args.screener and _SCREENERS_AVAILABLE and len(watchlist) > 0:
        print("\n" + "="*80)
        print(f"STEP 4b: SCREENER FILTER  [{args.screener}]")
        print("="*80)
        screener_names = [s.strip() for s in args.screener.split("+")]
        try:
            screener_instances = [
                ScreenerRegistry.get(n, ScreenerRegistry.load_config(n, args.screener_config))
                for n in screener_names
            ]
            active_screener = (
                ScreenerPipeline(screener_instances, mode=args.screener_mode)
                if len(screener_instances) > 1
                else screener_instances[0]
            )
        except ValueError as e:
            print(f"  Screener no disponible: {e}")
            active_screener = None

        if active_screener:
            try:
                from src.data.ticker_cache import TickerCache
                _tc = TickerCache()
            except Exception:
                _tc = None

            filtered_rows = []
            for _, row in watchlist.iterrows():
                t = row['ticker']
                try:
                    df_t = _tc.get_ohlcv(t) if _tc else None
                    if df_t is not None and len(df_t) > 0:
                        result = active_screener.scan(t, df_t)
                        if result.passed:
                            row = row.copy()
                            row['screener_score'] = result.score
                            row['screener_reason'] = result.reason
                            filtered_rows.append(row)
                        else:
                            logger.debug(f"{t} filtrado: {result.reason}")
                except Exception as exc:
                    logger.debug(f"{t} screener error: {exc}")

            before = len(watchlist)
            watchlist = pd.DataFrame(filtered_rows) if filtered_rows else watchlist.iloc[:0]
            print(f"  Candidates antes: {before}  despues: {len(watchlist)}")

    elif args.screener and not _SCREENERS_AVAILABLE:
        print("  Sistema de screeners no disponible. Continuando sin filtro.")

    # PASO 5: Focus List
    print("\n" + "="*80)
    print("🎯 STEP 5: FOCUS LIST GENERATION")
    print("="*80)
    
    focus_gen = FocusListGenerator()
    focus_list = focus_gen.generate_focus_list(watchlist, max_setups=args.max_setups)
    
    if len(focus_list) > 0:
        print(f"\n✅ {len(focus_list)} setups ready for today:\n")
        print(f"{'Ticker':<8} {'Pattern':<15} {'Current':<10} {'Trigger':<10} {'Stop':<10}")
        print("-"*80)
        
        for _, row in focus_list.iterrows():
            print(f"{row['ticker']:<8} {row['pattern']:<15} ${row['current_price']:<9.2f} "
                  f"${row['trigger_price']:<9.2f} ${row['stop_loss']:<9.2f}")
        
        # Guardar CSV
        output_file = 'live_trading_focus_list.csv'
        focus_list.to_csv(output_file, index=False)
        print(f"\n💾 Focus list saved to: {output_file}")
    else:
        print("\n⚠️ No setups ready for immediate entry")
        print("   → Continue monitoring watchlist")
    
    # RESUMEN FINAL
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"Universe Scanned: {len(universe)} tickers")
    print(f"Market Status: {health['status']}")
    print(f"Max Positions: {health['max_positions']}")
    print(f"Candidates Found: {len(watchlist)}")
    print(f"Focus List: {len(focus_list)} setups")
    print(f"Top Sectors: {', '.join([r['sector'] for _, r in top_sectors.iterrows()])}")
    print("="*80)
    
    if len(focus_list) > 0:
        print("\n📋 YOUR ACTION ITEMS:")
        print("  1. Add these tickers to your trading platform watchlist:")
        for ticker in focus_list['ticker']:
            print(f"     → {ticker}")
        print("  2. Set alerts at the Trigger Prices")
        print("  3. When alert fires → Check RVOL > 1.5x")
        print("  4. If confirmed → EXECUTE ENTRY")
        print("  5. Place stop loss immediately")
        print("="*80 + "\n")


if __name__ == "__main__":
    main()
