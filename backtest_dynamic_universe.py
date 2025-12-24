#!/usr/bin/env python3
"""
BACKTEST CON UNIVERSO DINÁMICO - Simula Trading Real
=====================================================

En lugar de backtest con lista fija, este sistema:
1. Cada día del backtest busca oportunidades en el universo completo
2. Genera señales con los precios reales de ese día
3. Simula cómo operarías en la vida real

Uso:
    python backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-01
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

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.market_data import MarketDataProvider
from src.core.market_context import MarketContext
from src.core.pattern_screener import PatternScreener
from src.utils.risk_manager import RiskManager

logging.basicConfig(level=logging.WARNING)  # Reduce noise
logger = logging.getLogger(__name__)


# ============================================================================
# PROGRESS UI CLASS
# ============================================================================

class ProgressUI:
    """Interfaz visual para progreso del backtest"""
    
    def __init__(self):
        self.start_time = None
        self.stats = {
            'total_days': 0,
            'days_processed': 0,
            'total_scans': 0,
            'setups_found': 0,
            'trades_entered': 0,
            'market_green_days': 0,
            'market_yellow_days': 0,
            'market_red_days': 0
        }
    
    def start(self, total_days):
        """Inicia el tracker de progreso"""
        self.start_time = time.time()
        self.stats['total_days'] = total_days
        
        print("\n" + "="*80)
        print("🚀 BACKTEST DINÁMICO - INICIANDO")
        print("="*80)
        print(f"Total trading days: {total_days}")
        print(f"Start time: {datetime.now().strftime('%H:%M:%S')}")
        print("="*80 + "\n")
    
    def update_day(self, date, market_health, setups_count, trades_count):
        """Actualiza progreso de un día"""
        self.stats['days_processed'] += 1
        self.stats['total_scans'] += 1
        
        if setups_count > 0:
            self.stats['setups_found'] += setups_count
        
        if trades_count > 0:
            self.stats['trades_entered'] += trades_count
        
        # Track market health
        health = market_health.get('health_score', 0)
        if health >= 5:
            self.stats['market_green_days'] += 1
        elif health >= 3:
            self.stats['market_yellow_days'] += 1
        else:
            self.stats['market_red_days'] += 1
    
    def print_progress(self):
        """Muestra barra de progreso"""
        days = self.stats['days_processed']
        total = self.stats['total_days']
        pct = (days / total * 100) if total > 0 else 0
        
        # Tiempo transcurrido y ETA
        elapsed = time.time() - self.start_time
        if days > 0:
            avg_time_per_day = elapsed / days
            remaining_days = total - days
            eta_seconds = remaining_days * avg_time_per_day
            eta_str = self._format_time(eta_seconds)
        else:
            eta_str = "Calculating..."
        
        # Progress bar
        bar_width = 50
        filled = int(bar_width * pct / 100)
        bar = '█' * filled + '░' * (bar_width - filled)
        
        # Stats line
        print(f"\rProgress: [{bar}] {pct:.1f}% | "
              f"Days: {days}/{total} | "
              f"Setups: {self.stats['setups_found']} | "
              f"Trades: {self.stats['trades_entered']} | "
              f"ETA: {eta_str}", end='', flush=True)
    
    def print_summary(self, final_equity, initial_capital):
        """Muestra resumen final"""
        elapsed = time.time() - self.start_time
        total_return = ((final_equity - initial_capital) / initial_capital) * 100
        
        print("\n\n" + "="*80)
        print("📊 BACKTEST COMPLETADO")
        print("="*80)
        print(f"\n⏱️  TIME STATISTICS:")
        print(f"   Total time: {self._format_time(elapsed)}")
        print(f"   Days processed: {self.stats['days_processed']}")
        print(f"   Avg time/day: {elapsed/self.stats['days_processed']:.2f}s")
        
        print(f"\n🔍 SCANNING STATISTICS:")
        print(f"   Total scans: {self.stats['total_scans']}")
        print(f"   Setups found: {self.stats['setups_found']}")
        print(f"   Avg setups/day: {self.stats['setups_found']/self.stats['total_scans']:.1f}")
        
        print(f"\n📈 MARKET HEALTH:")
        print(f"   🟢 Green days: {self.stats['market_green_days']} ({self.stats['market_green_days']/self.stats['days_processed']*100:.1f}%)")
        print(f"   🟡 Yellow days: {self.stats['market_yellow_days']} ({self.stats['market_yellow_days']/self.stats['days_processed']*100:.1f}%)")
        print(f"   🔴 Red days: {self.stats['market_red_days']} ({self.stats['market_red_days']/self.stats['days_processed']*100:.1f}%)")
        
        print(f"\n💰 TRADING RESULTS:")
        print(f"   Trades entered: {self.stats['trades_entered']}")
        print(f"   Initial capital: ${initial_capital:,.2f}")
        print(f"   Final equity: ${final_equity:,.2f}")
        print(f"   Total return: {total_return:+.2f}%")
        
        print("\n" + "="*80 + "\n")
    
    def _format_time(self, seconds):
        """Formatea segundos a formato legible"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h {mins}m"


# ============================================================================
# SCANNER CLASS
# ============================================================================

class DynamicUniverseScanner:
    """Escanea el universo completo buscando oportunidades cada día"""
    
    def __init__(self, data_provider):
        self.data_provider = data_provider
        self.pattern_screener = PatternScreener(data_provider)
        
        # Universo base (S&P 500 + NASDAQ 100 líquidas)
        self.universo_base = self._build_base_universe()
    
    def _build_base_universe(self):
        """
        Construye universo base de acciones líquidas
        
        En producción esto descargaría de Wikipedia/APIs
        Aquí usamos una lista curada para velocidad
        """
        logger.info("📦 Construyendo universo base...")
        
        # Top 200 acciones más líquidas (curated list)
        universo = [
            # Mega caps tech
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA',
            'AVGO', 'ORCL', 'AMD', 'CRM', 'ADBE', 'CSCO', 'INTC',
            'QCOM', 'TXN', 'AMAT', 'MU', 'KLAC', 'LRCX', 'SNPS',
            
            # Growth/momentum stocks
            'NFLX', 'ABNB', 'UBER', 'DASH', 'COIN', 'HOOD', 'SHOP',
            'SQ', 'PYPL', 'PLTR', 'SNOW', 'DDOG', 'CRWD', 'ZS',
            'NET', 'OKTA', 'MDB', 'FTNT', 'PANW', 'SMCI',
            
            # Healthcare
            'UNH', 'JNJ', 'LLY', 'ABBV', 'MRK', 'TMO', 'ABT',
            'DHR', 'PFE', 'AMGN', 'GILD', 'VRTX', 'REGN',
            
            # Financials
            'JPM', 'BAC', 'WFC', 'MS', 'GS', 'C', 'BLK', 'SCHW',
            'AXP', 'SPGI', 'ICE', 'CME', 'V', 'MA', 'PYPL',
            
            # Consumer
            'AMZN', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'LOW',
            'TJX', 'BKNG', 'MAR', 'CMG', 'YUM', 'LULU', 'DECK',
            
            # Industrial
            'CAT', 'BA', 'HON', 'UNP', 'RTX', 'LMT', 'DE',
            'GE', 'MMM', 'EMR', 'ETN', 'ITW', 'PH',
            
            # Energy
            'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX',
            
            # Communication
            'GOOGL', 'META', 'NFLX', 'DIS', 'CMCSA', 'T', 'VZ',
            'TMUS', 'CHTR', 'EA', 'TTWO', 'RBLX',
            
            # ETFs for sector checks
            'SPY', 'QQQ', 'IWM',
            'XLK', 'XLF', 'XLV', 'XLE', 'XLY', 'XLP', 'XLI', 'XLB'
        ]
        
        # Eliminar duplicados y ordenar
        universo = sorted(list(set(universo)))
        
        logger.info(f"✅ Universo base: {len(universo)} tickers")
        
        return universo
    
    def scan_for_opportunities(self, date, market_context):
        """
        Escanea el universo completo EN ESA FECHA específica
        
        Esto simula lo que harías en pre-market:
        1. Revisar market health
        2. Escanear todo el universo
        3. Encontrar setups listos
        
        Args:
            date: Fecha específica del backtest
            market_context: Contexto del mercado ese día
            
        Returns:
            Lista de setups encontrados
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"📅 Escaneando oportunidades para {date.strftime('%Y-%m-%d')}")
        logger.info(f"{'='*80}")
        
        # 1. Verificar market health
        if not market_context.get('market_favorable_for_longs', False):
            logger.info("❌ Market not favorable - No scan today")
            return []
        
        # 2. Obtener sectores líderes
        sector_leaders = market_context.get('sector_leaders', {})
        top_sectors = list(sector_leaders.keys())[:3] if sector_leaders else []
        
        if top_sectors:
            logger.debug(f"🎯 Top sectors: {', '.join(top_sectors)}")
        
        # 3. Escanear universo con progress bar
        setups = []
        total = len(self.universo_base)
        
        # Progress bar para el escaneo
        with tqdm(total=total, desc="Scanning universe", 
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                  ncols=100) as pbar:
            
            for ticker in self.universo_base:
                try:
                    # Obtener datos históricos hasta esa fecha
                    setup = self._analyze_ticker_for_date(ticker, date, market_context)
                    
                    if setup:
                        setups.append(setup)
                        pbar.set_postfix({'setups': len(setups)})
                
                except Exception as e:
                    logger.debug(f"Error analyzing {ticker}: {e}")
                
                pbar.update(1)
        
        logger.debug(f"\n✅ Found {len(setups)} setups for {date.strftime('%Y-%m-%d')}")
        
        # 4. Rankear por calidad
        setups = self._rank_setups(setups, market_context)
        
        return setups
    
    def _analyze_ticker_for_date(self, ticker, date, market_context):
        """
        Analiza un ticker específico en una fecha específica
        
        Esto es CRÍTICO: solo usa datos disponibles HASTA esa fecha
        (no future peeking)
        """
        # Obtener datos históricos (90 días antes de la fecha)
        start_date = date - timedelta(days=90)
        
        try:
            df = self.data_provider.get_daily_data(
                ticker, 
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=date.strftime('%Y-%m-%d')
            )
            
            if df.empty or len(df) < 30:
                return None
            
            # Verificar que estamos en la fecha correcta
            if df.index[-1].date() != date.date():
                return None
            
            # Detectar patrones usando el screener
            signal = self.pattern_screener.screen_stock(ticker, df, market_context)
            
            if signal and signal.action in ['BUY_STOP', 'MANUAL_WATCH']:
                return {
                    'ticker': ticker,
                    'date': date,
                    'signal': signal,
                    'current_price': df['Close'].iloc[-1],
                    'volume': df['Volume'].iloc[-1],
                    'atr': self._calculate_atr(df, 14)
                }
        
        except Exception as e:
            logger.debug(f"Error analyzing {ticker} for {date}: {e}")
            return None
        
        return None
    
    def _calculate_atr(self, df, period=14):
        """Calcula ATR"""
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean()
        
        return atr.iloc[-1] if len(atr) > 0 else None
    
    def _rank_setups(self, setups, market_context):
        """
        Rankea setups por calidad
        
        Prioriza:
        1. Sectores líderes
        2. Camino 1 (Blue Sky)
        3. Mayor R:R
        4. Mejor proximidad al trigger
        """
        if not setups:
            return []
        
        sector_leaders = market_context.get('sector_leaders', {})
        top_3_sectors = list(sector_leaders.keys())[:3]
        
        # Scoring
        for setup in setups:
            score = 0
            signal = setup['signal']
            
            # Sector líder (+3 puntos)
            if hasattr(signal, 'sector'):
                if signal.sector in top_3_sectors:
                    score += 3
            
            # Camino 1 (+2 puntos)
            if signal.camino and 'BLUE_SKY' in signal.camino.name:
                score += 2
            
            # Entry price definido (+1 punto)
            if signal.entry_price:
                score += 1
            
            # Buen R:R estimado
            if signal.entry_price and signal.stop_loss:
                risk = signal.entry_price - signal.stop_loss
                reward = risk * 3  # Assume 3R target
                if reward / risk >= 3:
                    score += 1
            
            setup['quality_score'] = score
        
        # Ordenar por score
        setups.sort(key=lambda x: x['quality_score'], reverse=True)
        
        return setups


class DynamicBacktestEngine:
    """
    Motor de backtest que simula trading real:
    - Cada día escanea el universo completo
    - Genera señales basadas en datos de ese día
    - Ejecuta trades como lo harías en vivo
    """
    
    def __init__(self, start_date, end_date, initial_capital=100000):
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
        self.data_provider = MarketDataProvider()
        self.market_context = MarketContext(self.data_provider)
        self.scanner = DynamicUniverseScanner(self.data_provider)
        self.risk_manager = RiskManager(initial_capital)
        
        # Position tracking
        self.positions = []
        self.max_positions = 5
        
        # Storage
        self.daily_scans = []
        self.trades = []
        self.equity_curve = []
        
        # Progress UI
        self.ui = ProgressUI()
        
    def run(self):
        """
        Ejecuta el backtest completo
        
        Para cada día de trading:
        1. Evaluar market health
        2. Escanear universo completo
        3. Generar señales
        4. Gestionar posiciones existentes
        5. Ejecutar nuevas entradas (si hay capital)
        """
        # Generar días de trading
        trading_days = pd.bdate_range(start=self.start_date, end=self.end_date)
        total_days = len(trading_days)
        
        logger.info(f"\nTotal trading days: {total_days}")
        
        # Iniciar UI
        total_days = len(trading_days)
        self.ui.start(total_days)
        
        for day_num, current_date in enumerate(trading_days, 1):
            # 1. Market Health Check
            try:
                context = self.market_context.analyze_indices_for_date(current_date)
            except:
                logger.warning(f"Could not get market context for {current_date}")
                context = {'market_favorable_for_longs': False}
            
            # 2. Escanear oportunidades ESE DÍA
            setups = []
            trades_count = 0
            
            if context.get('market_favorable_for_longs', False):
                setups = self.scanner.scan_for_opportunities(current_date, context)
                
                # Guardar scan del día
                self.daily_scans.append({
                    'date': current_date,
                    'setups_found': len(setups),
                    'market_score': context.get('health_score', 0),
                    'top_setups': setups[:5]  # Top 5
                })
                
                # 3. Ejecutar nuevas entradas
                if setups:
                    trades_before = len(self.trades)
                    self._execute_entries(current_date, setups, context)
                    trades_count = len(self.trades) - trades_before
            else:
                self.daily_scans.append({
                    'date': current_date,
                    'setups_found': 0,
                    'market_score': context.get('health_score', 0),
                    'top_setups': []
                })
            
            # 4. Gestionar posiciones existentes
            self._manage_positions(current_date)
            
            # 5. Actualizar equity curve
            current_equity = self._calculate_current_equity(current_date)
            self.equity_curve.append({
                'date': current_date,
                'equity': current_equity,
                'open_positions': len(self.positions)
            })
            
            # 6. Actualizar UI
            self.ui.update_day(current_date, context, len(setups), trades_count)
            self.ui.print_progress()
        
        # 7. Resultados finales
        self._generate_results()
    
    def _execute_entries(self, date, setups, context):
        """Ejecuta nuevas entradas si hay capital disponible"""
        
        # Limitar trades según market health
        max_trades = context.get('max_concurrent_trades', 5)
        current_positions = len(self.positions)
        
        if current_positions >= max_trades:
            logger.info(f"⚠️ Max positions reached ({current_positions}/{max_trades})")
            return
        
        # Tomar top setups
        available_slots = max_trades - current_positions
        candidates = setups[:available_slots]
        
        for setup in candidates:
            # Verificar si tenemos capital
            position_value = setup['current_price'] * 100  # Estimate
            if self.current_capital < position_value:
                logger.info("⚠️ Insufficient capital for new positions")
                break
            
            # Ejecutar entrada
            self._enter_trade(date, setup)
    
    def _enter_trade(self, date, setup):
        """Ejecuta entrada en un trade"""
        signal = setup['signal']
        ticker = setup['ticker']
        
        # Precio de entrada (simular fill)
        entry_price = signal.entry_price or setup['current_price']
        stop_loss = signal.stop_loss
        
        if not stop_loss:
            # Calcular stop por defecto (8%)
            stop_loss = entry_price * 0.92
        
        # Calcular ADR para position sizing
        adr_percent = setup.get('atr', 0) / entry_price * 100 if setup.get('atr') else 3.0
        avg_volume = setup.get('volume', 1000000)
        
        # Position sizing usando RiskManager institucional
        try:
            result = self.risk_manager.calculate_position_size(
                entry_price=entry_price,
                stop_price=stop_loss,
                adr_percent=adr_percent,
                avg_daily_volume=avg_volume,
                market_regime_factor=1.0
            )
            
            shares = result['shares']
        except Exception as e:
            logger.warning(f"Error calculating position size for {ticker}: {e}")
            shares = 0
        
        if shares == 0:
            return
        
        # Registrar trade
        trade = {
            'ticker': ticker,
            'entry_date': date,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'shares': shares,
            'camino': signal.camino.name if signal.camino else 'UNKNOWN',
            'pattern': signal.pattern,
            'status': 'OPEN'
        }
        
        self.trades.append(trade)
        
        # Track position
        self.positions.append({
            'ticker': ticker,
            'entry_price': entry_price,
            'shares': shares,
            'stop_loss': stop_loss
        })
        
        # Update capital
        position_cost = entry_price * shares
        self.current_capital -= position_cost
        
        logger.info(f"✅ ENTRY: {ticker} @ ${entry_price:.2f} x {shares} shares")
        logger.info(f"   Stop: ${stop_loss:.2f} | Risk: ${(entry_price-stop_loss)*shares:.2f}")
    
    def _manage_positions(self, date):
        """Gestiona posiciones existentes (stops, targets, etc)"""
        # Implementar lógica de salida
        # Por ahora, placeholder
        pass
    
    def _calculate_current_equity(self, date):
        """Calcula equity actual"""
        cash = self.current_capital
        positions_value = 0
        
        for pos in self.positions:
            # Get current price
            try:
                current_price = self._get_price_for_date(pos['ticker'], date)
                if current_price:
                    positions_value += current_price * pos['shares']
                else:
                    positions_value += pos['entry_price'] * pos['shares']
            except:
                positions_value += pos['entry_price'] * pos['shares']
        
        return cash + positions_value
    
    def _get_price_for_date(self, ticker, date):
        """Obtiene precio de cierre para una fecha específica"""
        df = self.data_provider.get_daily_data(
            ticker,
            start_date=(date - timedelta(days=5)).strftime('%Y-%m-%d'),
            end_date=date.strftime('%Y-%m-%d')
        )
        
        if not df.empty:
            return df['Close'].iloc[-1]
        
        return None
    
    def _generate_results(self):
        """Genera reporte de resultados"""
        # Equity curve
        if self.equity_curve:
            initial = self.equity_curve[0]['equity']
            final = self.equity_curve[-1]['equity']
            
            # Mostrar resumen con UI
            self.ui.print_summary(final, initial)
        
        # Daily scans summary
        total_scans = len(self.daily_scans)
        days_with_setups = sum(1 for s in self.daily_scans if s['setups_found'] > 0)
        
        # Save results
        self._save_results()
    
    def _save_results(self):
        """Guarda resultados a CSV"""
        print("\n📁 Saving results...")
        
        # Trades
        if self.trades:
            df_trades = pd.DataFrame(self.trades)
            df_trades.to_csv('backtest_dynamic_trades.csv', index=False)
            print("   ✅ Trades: backtest_dynamic_trades.csv")
        
        # Daily scans
        if self.daily_scans:
            df_scans = pd.DataFrame(self.daily_scans)
            df_scans.to_csv('backtest_dynamic_scans.csv', index=False)
            print("   ✅ Scans: backtest_dynamic_scans.csv")
        
        # Equity curve
        if self.equity_curve:
            df_equity = pd.DataFrame(self.equity_curve)
            df_equity.to_csv('backtest_dynamic_equity.csv', index=False)
            print("   ✅ Equity: backtest_dynamic_equity.csv")


def main():
    parser = argparse.ArgumentParser(description='Dynamic Universe Backtest')
    parser.add_argument('--start', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100000, help='Initial capital')
    
    args = parser.parse_args()
    
    # Run backtest
    engine = DynamicBacktestEngine(
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital
    )
    
    engine.run()


if __name__ == "__main__":
    main()
