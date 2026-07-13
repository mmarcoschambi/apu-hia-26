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
from src.data.market_data import MarketDataProvider
from src.strategies.triad_protocol import TriadStrategy, Camino
from src.utils.market_regime import MarketRegimeClassifier, load_spy_vix_data

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
    tp2_hit: bool = False
    initial_shares: int = 0
    entry_stage: str = 'FULL' # 'FULL' or 'QUARTER' (Earnings)
    note: str = ""
    bars_held: int = 0
    signal_type: str = "UNKNOWN"
    context_data: Dict = None
    R_inicial: float = 0.0  # Riesgo inicial (entry - stop)
    adr_valor: float = 0.0  # ADR del símbolo

@dataclass
class PendingOrder:
    symbol: str
    order_type: str # 'BUY_STOP'
    limit_price: float
    stop_loss_initial: float
    shares: int
    valid_date: pd.Timestamp
    note: str = "" # Metadata for the order
    signal_type: str = "UNKNOWN"
    context_data: Dict = None

class Portfolio:
    def __init__(self, initial_capital: float):
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[Dict] = []
        self.partial_exits: List[Dict] = []  # Nuevo: registro de salidas parciales
        self.equity_curve: List[Dict] = []
    
    @property
    def equity(self) -> float:
        return self.cash

class DailyBacktestEngine:
    def __init__(self, universe: List[str], start_date: str, end_date: str, risk_manager: RiskManager, 
                 min_mcap: float = 2e9, max_mcap: float = 20e9, 
                 min_avg_volume: int = 300000, min_adr: float = 1.5, min_price: float = 5.0,
                 min_dollar_vol: float = 15000000, min_rvol: float = 1.5, skip_filters: bool = False,
                 offline: bool = False):
        self.universe = universe
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.risk_manager = risk_manager
        self.min_mcap = min_mcap
        self.max_mcap = max_mcap
        self.min_avg_volume = min_avg_volume
        self.min_price = min_price
        self.min_dollar_vol = min_dollar_vol
        self.min_rvol = min_rvol
        self.skip_filters = skip_filters
        self.offline = offline
        
        self.portfolio = Portfolio(risk_manager.account_equity)
        self.pending_orders: List[PendingOrder] = []
        
        # ⚡ OPTIMIZACIÓN: No cargar todos los datos en memoria
        # Solo guardar el universo válido y cargar datos bajo demanda
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.validated_universe: List[str] = []  # Universo que pasó filtros
        self.spy_data = pd.DataFrame()
        self.triad_logic = TriadOpenBB()
        self.triad_strategy = TriadStrategy()
        self.data_provider = MarketDataProvider() # New instance for earnings data
        
        # New Institutional Screener with requested thresholds
        self.screener = InstitutionalScreener(
            adr_threshold=min_adr,
            min_price=min_price,
            min_avg_vol=min_avg_volume,
            min_dollar_vol=min_dollar_vol,
            min_rvol=min_rvol
        )
        
        print(f"Initializing Engine for {len(universe)} symbols...")
        if self.skip_filters:
            print("⚠️ Filters DISABLED (Direct Input Mode)")
        else:
            print(f"Filters: Mcap ${min_mcap/1e9:.1f}B-${max_mcap/1e9:.1f}B | Min Vol {min_avg_volume/1000:.0f}k | ADR > {min_adr}% | RVOL > {min_rvol}x")
        self._preload_market_data()

    def _preload_market_data(self):
        """
        OPTIMIZADO: Solo valida el universo y filtra por liquidez.
        NO carga todos los DataFrames en memoria.
        Los datos se cargarán bajo demanda durante el backtest.
        """
        fetch_start = (self.start_date - timedelta(days=200)).strftime('%Y-%m-%d')
        fetch_end = self.end_date.strftime('%Y-%m-%d')
        
        if self.skip_filters:
            print("Skipping Fundamental Filters...")
        else:
            # Note: Fundamental checks via 'obb' or 'yfinance' might still require internet
            # If offline, we might skip this or rely on cached info if available (not implemented yet for fundamentals)
            # For now, we will skip fundamental checks if offline to avoid crash, or proceed if online
            if not self.offline:
                from openbb import obb
                # 1. Filter Universe by Fundamentals (Mcap & Volume proxy)
                filtered_universe = []
                print("Filtering Universe by Fundamentals...")
                for symbol in self.universe:
                    try:
                        # Use metrics instead of overview for OpenBB v4
                        overview = obb.equity.fundamental.metrics(symbol=symbol, provider='yfinance').to_df()
                        if not overview.empty and 'market_cap' in overview.columns:
                            mcap = overview['market_cap'].iloc[0]
                            
                            # Check Market Cap
                            if not (self.min_mcap <= mcap <= self.max_mcap):
                                continue
                                
                            # Check Volume (if available in overview, otherwise check history later)
                            if 'average_volume' in overview.columns:
                                vol = overview['average_volume'].iloc[0]
                                if vol < self.min_avg_volume:
                                    continue
                            
                            filtered_universe.append(symbol)
                    except Exception as e:
                        pass
                self.universe = filtered_universe
                print(f"Universe after Funda Filter: {len(self.universe)} symbols")
            else:
                 print("⚠️ Offline Mode: Skipping live fundamental checks (Mcap). Reliance on cached price/volume data.")

        # 2. Preload SPY
        try:
            self.spy_data = self.data_provider.get_daily_data('SPY', start_date=fetch_start, end_date=fetch_end, offline=self.offline)
            if self.spy_data.empty:
                print("Warning: Could not load SPY data.")
            else:
                # Normalize SPY columns to lowercase
                self.spy_data.columns = [c.lower() for c in self.spy_data.columns]
        except:
            print("Warning: Could not load SPY data.")

        # 3. Preload Market Data & Double Check Volume/Price
        valid_data_count = 0
        total_symbols = len(self.universe)
        
        for i, symbol in enumerate(self.universe):
            # Progress indicator for large universes
            if i % 10 == 0 or i == total_symbols - 1:
                # print(f"📊 Loading data: {i+1}/{total_symbols} ({valid_data_count} valid so far)")
                print(f"__PROGRESS__{i+1}/{total_symbols}__Loading {symbol}...", flush=True)
            
            try:
                # Use centralized data provider with cache/offline support
                df = self.data_provider.get_daily_data(symbol, start_date=fetch_start, end_date=fetch_end, offline=self.offline)
                
                if not df.empty:
                    # Standardize columns just in case
                    df = df.rename(columns={
                        'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
                    })
                    # Also handle if columns are already lowercase or mixed (TickerCache returns Capitalized, OpenBB lowercase)
                    # TickerCache/yfinance: Open, High, Low, Close, Volume
                    # We ensure lowercase for internal logic
                    df.columns = [c.lower() for c in df.columns]
                    
                    df.index = pd.to_datetime(df.index)
                    
                    # --- Institutional Quality & Liquidity Filters ---
                    # Filter data up to backtest end date to avoid look-ahead bias
                    df_in_range = df[df.index <= self.end_date]
                    if len(df_in_range) < 20:
                        print(f"Skipping {symbol}: Insufficient data in backtest range")
                        continue
                    recent_tail = df_in_range.tail(20)

                    # A. Average Volume
                    if 'volume' in recent_tail.columns:
                        avg_vol_hist = recent_tail['volume'].mean()
                        if avg_vol_hist < self.min_avg_volume:
                            print(f"Skipping {symbol}: Low Avg Volume ({avg_vol_hist/1000:.0f}k < {self.min_avg_volume/1000:.0f}k)")
                            continue

                        # B. Average Dollar Volume (Price * Volume)
                        avg_dollar_vol = (recent_tail['close'] * recent_tail['volume']).mean()
                        if avg_dollar_vol < self.min_dollar_vol:
                            print(f"Skipping {symbol}: Low Dollar Vol (${avg_dollar_vol/1e6:.1f}M < ${self.min_dollar_vol/1e6:.1f}M)")
                            continue

                        # C. Minimum Price (at end of period)
                        current_price = df_in_range['close'].iloc[-1]
                        if current_price < self.min_price:
                            print(f"Skipping {symbol}: Low Price (${current_price:.2f} < ${self.min_price})")
                            continue

                        # D. Rolling Dollar Volume 20 (NEW - More Accurate Liquidity Filter)
                        if 'rolling_dollar_vol_20' in df_in_range.columns:
                            # Check if the most recent rolling value meets our threshold
                            rolling_dollar_vol = df_in_range['rolling_dollar_vol_20'].iloc[-1] if not pd.isna(df_in_range['rolling_dollar_vol_20'].iloc[-1]) else 0
                            if rolling_dollar_vol < self.min_dollar_vol:
                                print(f"Skipping {symbol}: Low Rolling Dollar Vol (${rolling_dollar_vol/1e6:.1f}M < ${self.min_dollar_vol/1e6:.1f}M)")
                                continue

                        print(f"✅ {symbol} Loaded. Price: ${current_price:.2f}, $Vol: ${avg_dollar_vol/1e6:.1f}M")
                        # NO cargar datos en memoria, solo validar que existen
                        # df = self.triad_logic._calculate_indicators(df)
                        # self.market_data[symbol] = df
                        self.validated_universe.append(symbol)
                        valid_data_count += 1
            except Exception as e:
                logger.warning(f"Failed to load data for {symbol}: {e}")
        
        print(f"Final Tradable Universe: {valid_data_count} symbols loaded.")
    
    def _get_market_data(self, symbol: str, end_date: pd.Timestamp) -> pd.DataFrame:
        """
        Obtiene datos de un símbolo de forma lazy (bajo demanda).
        Usa cache en memoria para no recargar en cada llamada del mismo día.
        """
        cache_key = f"{symbol}_{end_date.strftime('%Y-%m-%d')}"
        
        # Check if already in memory cache for today
        if cache_key in self.market_data:
            return self.market_data[cache_key]
        
        # Load from DB
        fetch_start = (self.start_date - timedelta(days=200)).strftime('%Y-%m-%d')
        df = self.data_provider.get_daily_data(
            symbol, 
            start_date=fetch_start, 
            end_date=end_date.strftime('%Y-%m-%d'),
            offline=self.offline
        )
        
        if df.empty:
            return pd.DataFrame()
        
        # Normalizar columnas
        df.columns = [c.lower() for c in df.columns]
        df.index = pd.to_datetime(df.index)
        
        # Calcular indicadores que falten (EMAs ya vienen de DB)
        df = self.triad_logic._calculate_indicators(df)
        
        # Guardar en cache temporal (se limpiará cada día)
        self.market_data[cache_key] = df
        
        return df
    
    def _cleanup_old_cache(self, current_date: pd.Timestamp):
        """
        Libera memoria eliminando datos de días anteriores del cache.
        VERSIÓN AGRESIVA: Solo mantiene posiciones abiertas.
        """
        # Mantener datos de posiciones abiertas
        open_symbols = set(self.portfolio.positions.keys())
        
        keys_to_remove = []
        for cache_key in list(self.market_data.keys()):
            symbol = cache_key.split('_')[0]
            # Si no tiene posición abierta, eliminar SIEMPRE
            if symbol not in open_symbols:
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            del self.market_data[key]
        
        # Forzar garbage collection cada 10 días
        if len(self.market_data) > 20:
            import gc
            gc.collect()

    def run(self):
        print("🚀 Starting Daily Simulation...")
        date_range = pd.date_range(start=self.start_date, end=self.end_date, freq='B')
        total_days = len(date_range)

        # Instanciar MarketRegimeClassifier para sizing dinamico por regimen
        # Usa SPY + VIX para determinar Stage 1/2/3/4 y ajustar risk_factor
        _regime_classifier = None
        try:
            _spy, _vix = load_spy_vix_data(
                str(self.start_date)[:10], str(self.end_date)[:10],
                cache=self.data_provider.cache if hasattr(self.data_provider, "cache") else None
            )
            if _spy is not None and not _spy.empty:
                _regime_classifier = MarketRegimeClassifier(_spy, _vix)
                print("MarketRegimeClassifier cargado para daily_engine")
            else:
                print("WARN: SPY no disponible, market_regime_factor=1.0 (fallback)")
        except Exception as _e:
            print(f"WARN: No se pudo instanciar MarketRegimeClassifier: {_e}. Usando factor=1.0")
        
        for i, today in enumerate(date_range):
            # Emit progress for UI
            if i % 5 == 0 or i == total_days - 1:
                print(f"__PROGRESS__{i+1}/{total_days}__{today.date()}", flush=True)
            
            # 🗑️ Limpiar cache de días anteriores para liberar memoria
            if i > 0:
                self._cleanup_old_cache(today)
            
            # 1. Manage Exits and Entries
            self._manage_positions(today)
            
            # 2. Update Equity
            self._update_equity(today)
            
            # 3. Daily Screener (After Close)
            candidates = self._run_daily_screener(today)
            
            # 4. Prepare Orders for Tomorrow
            # Calcular market_regime_factor del dia actual
            _regime_factor = 1.0
            if _regime_classifier is not None:
                try:
                    _ctx = _regime_classifier.get_market_context(today)
                    _regime_factor = float(_ctx.get("risk_multiplier", 1.0))
                except Exception:
                    _regime_factor = 1.0
            self._prepare_orders(today, candidates, self.portfolio.equity, regime_factor=_regime_factor)
        
        # CRITICAL: Close all remaining open positions at end of backtest period
        final_date = date_range[-1]
        for symbol in list(self.portfolio.positions.keys()):
            pos = self.portfolio.positions[symbol]
            df = self._get_market_data(symbol, final_date)
            if not df.empty and final_date in df.index:
                final_price = df.loc[final_date]['close']
                self._close_position(symbol, final_price, final_date, "END_OF_BACKTEST")
                print(f"⚠️ Closed open position: {symbol} at ${final_price:.2f}")
        
        # Retornar tanto closed_trades como partial_exits
        trades_df = pd.DataFrame(self.portfolio.closed_trades)
        
        # Guardar partial_exits por separado para análisis
        if self.portfolio.partial_exits:
            partial_df = pd.DataFrame(self.portfolio.partial_exits)
            partial_df.to_csv('outputs/backtests/partial_exits.csv', index=False)
            print(f"📊 Salidas parciales guardadas: {len(partial_df)} registros en outputs/backtests/partial_exits.csv")
        
        return trades_df

    def _manage_positions(self, today):
        # A. Execution of Pending Orders (CON FILTRO DE VELA VERDE)
        remaining_orders = []
        for order in self.pending_orders:
            if order.valid_date != today: continue
            
            symbol = order.symbol
            df = self._get_market_data(symbol, today)
            if df.empty or today not in df.index: 
                continue
            
            daily_bar = df.loc[today]
            
            # ✅ GREEN CANDLE CONFIRMATION: Solo ejecutar en velas alcistas
            # Basado en backtest comparativo que mostró +37.26% mejor performance
            # con win rate de 66.7% vs 50% en entrada inmediata
            is_green_candle = daily_bar['close'] > daily_bar['open']
            
            if daily_bar['high'] >= order.limit_price and is_green_candle:
                execution_price = max(daily_bar['open'], order.limit_price)
                cost = execution_price * order.shares
                if self.portfolio.cash >= cost:
                    self.portfolio.cash -= cost
                    
                    # Calcular R (riesgo inicial) y ADR
                    R_inicial = execution_price - order.stop_loss_initial
                    
                    # Calcular ADR del símbolo (últimos 20 días)
                    df_hist = df.loc[:today]
                    if len(df_hist) >= 20:
                        adr_valor = (df_hist['high'] - df_hist['low']).tail(20).mean()
                    else:
                        adr_valor = R_inicial * 2  # Default fallback
                    
                    new_pos = Position(
                        symbol=symbol,
                        entry_date=today,
                        entry_price=execution_price,
                        shares=order.shares,
                        initial_shares=order.shares,
                        stop_loss=order.stop_loss_initial,
                        take_profit_1=execution_price + (1.0 * R_inicial),  # TP1 en +1R (para activar entre +1R y +1.5R)
                        R_inicial=R_inicial,
                        adr_valor=adr_valor,
                        note=order.note,
                        signal_type=order.signal_type,
                        context_data=order.context_data
                    )
                    self.portfolio.positions[symbol] = new_pos
        self.pending_orders = []

        # B. Exit Management
        for symbol, pos in list(self.portfolio.positions.items()):
            df = self._get_market_data(symbol, today)
            if df.empty or today not in df.index: 
                continue
            
            daily_bar = df.loc[today]
            current_close = daily_bar['close']
            
            # --- 0. Update Time in Trade ---
            pos.bars_held += 1
            
            # --- 0.1 EARNINGS DEFENSE RULE ---
            # "Nunca mantenemos una posición completa a menos que tengamos un 'colchón' de beneficios de al menos un 10-15%."
            earnings_dates = self.data_provider.get_earnings_dates(symbol)
            if not earnings_dates.empty:
                future_dates = earnings_dates[earnings_dates >= pd.to_datetime(today)]
                if not future_dates.empty:
                    next_earning = future_dates[0]
                    days_to_earning = (next_earning - pd.to_datetime(today)).days
                    
                    if days_to_earning <= 1: # Imminent Report (Today/Tomorrow)
                        current_pnl_pct = (current_close - pos.entry_price) / pos.entry_price
                        if current_pnl_pct < 0.10: # Less than 10% Cushion
                             self._close_position(symbol, current_close, today, f"EARNINGS_EXIT (<10% Cushion)")
                             continue
            
            # --- 1. Hard Stop Loss ---
            if daily_bar['low'] <= pos.stop_loss:
                exit_price = min(daily_bar['open'], pos.stop_loss)
                self._close_position(symbol, exit_price, today, "STOP_LOSS")
                continue
            
            # --- 2. Momentum Validation Rules (Time-Based) ---
            # Calculate current PnL %
            pnl_pct = (current_close - pos.entry_price) / pos.entry_price
            
            # Rule A: 3-Day Momentum Confirmation (Kill if Stagnant)
            if pos.bars_held == 3:
                # If Breakeven or Red (Buffer 0.25%)
                if pnl_pct < 0.0025: 
                    self._close_position(symbol, current_close, today, "MOMENTUM_FAIL (3-Day Rule)")
                    continue

            # Rule B: 10-Day Expiration (Kill Dead Money)
            if pos.bars_held >= 10:
                # If less than 2% gain after 2 weeks
                if pnl_pct < 0.02:
                    self._close_position(symbol, current_close, today, "TIME_EXPIRATION (10-Day Rule)")
                    continue

            # --- 3. Opportunity Cost (Relative Strength Filter) ---
            # Scenario: Market Ripping (+0.8%), Stock Lagging (Red/Flat)
            if not self.spy_data.empty and today in self.spy_data.index:
                spy_day = self.spy_data.loc[today]
                # Calculate SPY Daily Return (approx based on open for simplicity or close-to-close if we had prev)
                # Ideally close-to-close, let's look at today's candle body as proxy for 'day strength'
                spy_daily_perf = (spy_day['close'] - spy_day['open']) / spy_day['open']
                
                stock_daily_perf = (current_close - daily_bar['open']) / daily_bar['open']
                
                # Condition: SPY > +0.8% AND Stock < +0.1%
                if spy_daily_perf > 0.008 and stock_daily_perf < 0.001:
                     self._close_position(symbol, current_close, today, "OPP_COST (Weak RS)")
                     continue

            # --- 4. SISTEMA DE SALIDAS ESCALONADAS (3 FASES) ---
            
            # FASE 1: CONVERSIÓN A RISK-FREE (+1R o +1 ADR)
            # Trigger: Precio toca +1R O +1 ADR (lo que ocurra primero)
            if not pos.tp1_hit:
                precio_1R = pos.entry_price + (1.0 * pos.R_inicial)
                precio_1ADR = pos.entry_price + pos.adr_valor
                
                # Check individual triggers
                hit_1R = daily_bar['high'] >= precio_1R
                hit_1ADR = daily_bar['high'] >= precio_1ADR
                
                if hit_1R or hit_1ADR:
                    # Vender 30-50% de la posición (usando 40% como balance)
                    exit_shares = int(pos.initial_shares * 0.40)
                    if exit_shares > 0 and pos.shares >= exit_shares:
                        # Determine correct exit price based on what was actually hit
                        # Priority: Gap Open > 1R > 1ADR (assuming 1R > 1ADR usually, but logic holds)
                        
                        target_price = 0.0
                        trigger_reason = ""
                        
                        # If both hit, we take the one that is 'better' or logic dictates
                        # Usually 1R > 1ADR. If High reached 1R, we fill at 1R.
                        # If High only reached 1ADR, we fill at 1ADR.
                        
                        if hit_1R:
                            target_price = precio_1R
                            trigger_reason = "+1R"
                        elif hit_1ADR:
                            target_price = precio_1ADR
                            trigger_reason = "+1ADR"
                            
                        # Handle Gap Opens (if Open is higher than target, we get Open)
                        exit_price = max(target_price, daily_bar['open'])
                        
                        pnl_partial = (exit_price - pos.entry_price) * exit_shares
                        
                        self.portfolio.cash += (exit_shares * exit_price)
                        pos.shares -= exit_shares
                        pos.tp1_hit = True
                        pos.stop_loss = pos.entry_price  # CRÍTICO: Move to BREAKEVEN
                        
                        # Determinar qué trigger se activó
                        trigger_reason = "+1R" if daily_bar['high'] >= precio_1R else "+1ADR"
                        
                        # Registrar salida parcial
                        self._register_partial_exit(
                            symbol=symbol,
                            phase="FASE_1",
                            exit_date=today,
                            entry_price=pos.entry_price,
                            exit_price=exit_price,
                            shares_sold=exit_shares,
                            shares_remaining=pos.shares,
                            pnl=pnl_partial,
                            reason=f"TP1: {trigger_reason} Risk-Free Conversion",
                            position=pos
                        )
                        
                        logger.info(f"✅ FASE 1: {symbol} - 40% vendido en {trigger_reason} (${exit_price:.2f}), Stop → BE (${pos.entry_price:.2f}), PnL: ${pnl_partial:.2f}")
            
            # FASE 2: TOMA DE BENEFICIOS EN RESISTENCIA/ADR (+2.5R o ADR completo)
            # Condición: TP1 ya ejecutado Y precio alcanza resistencia técnica o ADR
            # IMPORTANTE: Usar 'if' no 'elif' para permitir ejecución el mismo día que FASE_1
            if pos.tp1_hit and not pos.tp2_hit:
                # Opción A: Alcanzó +2R (resistencia técnica intermedia)
                precio_2R = pos.entry_price + (2.0 * pos.R_inicial)
                
                # Opción B: Ganancia desde entrada >= 1.5 * ADR (expansión significativa)
                ganancia_desde_entrada = current_close - pos.entry_price
                expansion_adr = ganancia_desde_entrada >= (pos.adr_valor * 1.5)
                
                # Opción C: Alto del día alcanzó 2.5R (extensión agresiva)
                precio_2_5R = pos.entry_price + (2.5 * pos.R_inicial)
                
                trigger_fase2 = (daily_bar['high'] >= precio_2R) or expansion_adr or (daily_bar['high'] >= precio_2_5R)
                
                # DEBUG: Log cuando tp1_hit pero no trigger fase2
                if not trigger_fase2:
                    logger.debug(f"🔍 {symbol} {today.date()}: TP1 activo pero NO FASE_2 | High:{daily_bar['high']:.2f} vs 2R:{precio_2R:.2f} | Gain:{ganancia_desde_entrada:.2f} vs 1.5ADR:{pos.adr_valor*1.5:.2f}")
                
                if trigger_fase2:
                    # Vender 30% de la posición ORIGINAL (no de lo que queda)
                    exit_shares = int(pos.initial_shares * 0.30)
                    if exit_shares > 0 and pos.shares >= exit_shares:
                        # Precio de ejecución: usar el nivel alcanzado, no el close
                        if daily_bar['high'] >= precio_2_5R:
                            exit_price = precio_2_5R
                            trigger_reason = "+2.5R"
                        elif daily_bar['high'] >= precio_2R:
                            exit_price = precio_2R
                            trigger_reason = "+2R"
                        else:
                            # Expansion ADR: usar close porque es basado en close
                            exit_price = current_close
                            trigger_reason = "+1.5ADR"
                        
                        pnl_partial = (exit_price - pos.entry_price) * exit_shares
                        
                        self.portfolio.cash += (exit_shares * exit_price)
                        pos.shares -= exit_shares
                        pos.tp2_hit = True
                        
                        self._register_partial_exit(
                            symbol=symbol,
                            phase="FASE_2",
                            exit_date=today,
                            entry_price=pos.entry_price,
                            exit_price=exit_price,
                            shares_sold=exit_shares,
                            shares_remaining=pos.shares,
                            pnl=pnl_partial,
                            reason=f"TP2: {trigger_reason} Resistance",
                            position=pos
                        )
                        
                        logger.info(f"✅ FASE 2: {symbol} - 30% vendido en {trigger_reason} (${exit_price:.2f}), PnL: ${pnl_partial:.2f}")
            
            # FASE 3: RUNNER CON TRAILING STOP (EMA 8/21 o MA 20)
            # Solo se activa si TP1 ya fue ejecutado (posición risk-free)
            # IMPORTANTE: Stop está en Breakeven, nunca pierde después de Fase 1
            if pos.tp1_hit and pos.shares > 0:
                # Validar que stop loss nunca esté por debajo de breakeven
                if pos.stop_loss < pos.entry_price:
                    pos.stop_loss = pos.entry_price  # Protección: forzar BE
                
                # Opción: EMA 8 cruza por debajo de EMA 21 (cambio de tendencia)
                if 'ema_8' in daily_bar.index and 'ema_21' in daily_bar.index:
                    if daily_bar['ema_8'] < daily_bar['ema_21']:
                        self._close_position(symbol, daily_bar['close'], today, "FASE_3_EMA_CROSS")
                        continue
                
                # Fallback: Si no hay EMAs, usar MA 20
                if 'sma_20' in daily_bar.index:
                    if current_close < daily_bar['sma_20']:
                        self._close_position(symbol, daily_bar['close'], today, "FASE_3_MA20_BREACH")
                        continue

    def _close_position(self, symbol, price, date, reason):
        pos = self.portfolio.positions.pop(symbol)
        
        # PnL del cierre final (solo shares restantes)
        final_exit_pnl = (price - pos.entry_price) * pos.shares
        self.portfolio.cash += (pos.shares * price)
        
        final_reason = reason
        if pos.note:
            final_reason = f"{reason} | {pos.note}"
        
        shares_at_close = pos.shares
        initial_shares = pos.initial_shares if pos.initial_shares > 0 else pos.shares
        
        # **CALCULAR PNL TOTAL**: Suma de salidas parciales + cierre final
        total_pnl = final_exit_pnl
        
        # Buscar salidas parciales de este símbolo y sumar su PnL
        for partial_exit in self.portfolio.partial_exits:
            if partial_exit['symbol'] == symbol and partial_exit['entry_date'] == pos.entry_date:
                total_pnl += partial_exit['pnl']
        
        # **REGISTRAR FASE_3 en partial_exits SOLO si hubo salidas parciales**
        # FASE_3 = Runner exit después de convertir a risk-free
        # Si el trade nunca llegó a +1R, NO es FASE_3 (es cierre normal)
        if pos.tp1_hit:  # Solo si ejecutó al menos FASE_1
            self._register_partial_exit(
                symbol=symbol,
                phase='FASE_3',
                exit_date=date,
                entry_price=pos.entry_price,
                exit_price=price,
                shares_sold=shares_at_close,
                shares_remaining=0,  # Ya no quedan shares
                pnl=final_exit_pnl,
                reason=reason,
                position=pos
            )
        
        # Return % se calcula desde precio de entrada
        total_return_pct = ((price - pos.entry_price) / pos.entry_price) * 100
            
        trade_record = {
            'symbol': symbol, 
            'entry_date': pos.entry_date, 
            'exit_date': date,
            'entry_price': pos.entry_price, 
            'exit_price': price, 
            'shares': shares_at_close,  # Shares al cerrar (después de parciales)
            'initial_shares': initial_shares,  # Shares originales
            'pnl': total_pnl,  # PnL TOTAL (parciales + cierre final) 
            'return_pct': total_return_pct,
            'reason': final_reason,
            'signal_type': pos.signal_type,
            'tp1_executed': pos.tp1_hit,
            'tp2_executed': pos.tp2_hit,
            'final_shares_pct': (shares_at_close / initial_shares * 100) if initial_shares > 0 else 100,
            
            # Pre-Trade Checklist (configuración al entrar)
            'R_inicial': pos.R_inicial,
            'adr_valor': pos.adr_valor,
            'entry_stage': pos.entry_stage,
            'initial_stop_loss': pos.entry_price - pos.R_inicial,  # Stop inicial calculado
        }
        
        if pos.context_data:
            trade_record['context_adr'] = pos.context_data.get('adr_pct', 0)
            trade_record['context_vol'] = pos.context_data.get('avg_volume', 0)
            trade_record['context_trend'] = pos.context_data.get('trend_sma', '')
            trade_record['context_price'] = pos.context_data.get('current_price', 0)
            trade_record['context_sma20'] = pos.context_data.get('sma_20', 0)
            trade_record['context_rvol'] = pos.context_data.get('rvol', 0)  # Usar RVOL guardado del screener
            # 🛡️ Nuevas métricas de riesgo
            trade_record['dist_sma20_pct'] = pos.context_data.get('dist_sma20_pct', 0)
            trade_record['vol_trig'] = pos.context_data.get('vol_trig', 'Unknown')
            trade_record['days_to_next_earnings'] = pos.context_data.get('days_to_next_earnings', -1)
            trade_record['time_since_earnings'] = pos.context_data.get('time_since_earnings', -1)
        else:
            trade_record['context_rvol'] = 0.0
            trade_record['dist_sma20_pct'] = 0.0
            trade_record['vol_trig'] = 'Unknown'
            trade_record['days_to_next_earnings'] = -1
            trade_record['time_since_earnings'] = -1


        self.portfolio.closed_trades.append(trade_record)
    
    def _register_partial_exit(self, symbol: str, phase: str, exit_date, entry_price: float,
                               exit_price: float, shares_sold: int, shares_remaining: int,
                               pnl: float, reason: str, position: Position):
        """
        Registra una salida parcial como evento separado para tracking detallado
        """
        partial_exit_record = {
            'symbol': symbol,
            'phase': phase,  # FASE_1, FASE_2
            'exit_date': exit_date,
            'entry_date': position.entry_date,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'shares_sold': shares_sold,
            'shares_remaining': shares_remaining,
            'pct_sold': (shares_sold / position.initial_shares * 100) if position.initial_shares > 0 else 0,
            'pnl': pnl,
            'return_pct': ((exit_price - entry_price) / entry_price) * 100,
            'reason': reason,
            'signal_type': position.signal_type,
            
            # Pre-trade context (configuración al momento de entrada)
            'pre_trade_context': {
                'R_inicial': position.R_inicial,
                'adr_valor': position.adr_valor,
                'initial_shares': position.initial_shares,
                'initial_stop': position.stop_loss if not position.tp1_hit else entry_price,
                'entry_stage': position.entry_stage,
            }
        }
        
        # Copiar contexto adicional si existe
        if position.context_data:
            partial_exit_record['pre_trade_context'].update({
                'context_adr': position.context_data.get('adr_pct', 0),
                'context_vol': position.context_data.get('avg_volume', 0),
                'context_trend': position.context_data.get('trend_sma', ''),
                'context_rvol': position.context_data.get('rvol', 0)
            })
        
        self.portfolio.partial_exits.append(partial_exit_record)

    def _run_daily_screener(self, today) -> List[Dict]:
        raw_candidates = []
        # 1. Run Basic Institutional Screener (LAZY LOADING)
        for symbol in self.validated_universe:
            df = self._get_market_data(symbol, today)
            if df.empty:
                continue
                
            res = self.screener.scan(symbol, df, self.spy_data, today)
            if res: 
                # NO guardar hist_data completo - solo lo necesario para estrategia
                # Esto ahorra mucha memoria
                res['current_bar'] = df.loc[today] if today in df.index else None
                res['ath'] = df['high'].max()
                res['ath_date'] = df['high'].idxmax()
                raw_candidates.append(res)
            
            # Liberar memoria del DataFrame inmediatamente si no es candidato
            del df
        
        # 2. Refine with Triad Strategy Logic
        refined_candidates = []
        for cand in raw_candidates:
            # NO usar hist_data completo - trabajar con lo mínimo
            current_bar = cand.get('current_bar')
            if current_bar is None:
                continue
            
            base_high = cand['entry_trigger']
            
            # AVWAP: usar datos precalculados del candidato
            ath = cand.get('ath', current_bar['close'])
            avwap_price = current_bar['close']  # Simplificado - usar precio actual
            
            # Prepare Gap Data - necesitamos recargar solo últimas 2 barras
            gap_data = {'detected': False, 'gap_pct': 0}
            # Simplificado: asumimos no gap para reducir memoria
            # Si quieres gaps, hay que optimizar más
            
            vwap_data = {
                'calculated': True,
                'current_vwap': (current_bar['high'] + current_bar['low'] + current_bar['close'])/3,
                'session_low': current_bar['low'],
                'crossed_up': False,
                'session_open': current_bar['open'],
                'above_vwap': current_bar['close'] > ((current_bar['high'] + current_bar['low'] + current_bar['close'])/3)
            }
            
            base_data = {
                'detected': True,
                'base_high': base_high,
                'base_low': cand['stop_loss'],
                'current_price': current_bar['close']
            }
            
            avwap_data = {
                'calculated': True,
                'current_avwap': avwap_price,
                'distance_to_avwap_pct': (avwap_price - current_bar['close']) / current_bar['close'] if current_bar['close'] > 0 else 0
            }
            
            # Calculate Trend from candidato data
            sma_20 = cand.get('sma_20', current_bar['close'])
            sma_50 = current_bar.get('sma_50', current_bar['close'])
            
            # Uptrend estricto: Price > SMA20 AND SMA20 > SMA50
            is_uptrend = (current_bar['close'] > sma_20) and (sma_20 > sma_50)
            trend_status = 'Uptrend' if is_uptrend else 'Weak'
            
            # Usar avg_vol del screener
            avg_volume_20 = cand.get('avg_vol', current_bar.get('volume', 0))
            
            market_context = {
                'trend_sma': trend_status,
                'sma_20': sma_20,
                'current_price': current_bar['close'],
                'rvol': cand.get('rvol', 0),  # Ya viene del screener
                'avg_volume_20': avg_volume_20
            }

            # Run Strategy
            signal = self.triad_strategy.analyze(
                base_data=base_data,
                avwap_data=avwap_data,
                vwap_data=vwap_data,
                gap_data=gap_data,
                market_context=market_context,
                adr=cand.get('adr_pct', 2.0)/100 * current_bar['close']
            )
            
            if signal.action == 'BUY_STOP':
                # Use Strategy Signals
                cand['signal_type'] = signal.camino.name
                cand['entry_trigger'] = signal.entry_price
                cand['stop_loss'] = signal.stop_loss
                cand['reason'] = signal.reasoning
                
                # DEBUG: Verificar que dist_sma20_pct se mantenga
                if 'dist_sma20_pct' in cand:
                    logger.info(f"✅ {cand['symbol']} mantiene dist_sma20_pct={cand['dist_sma20_pct']:.2f}%")
                else:
                    logger.warning(f"⚠️ {cand['symbol']} NO TIENE dist_sma20_pct!")
                
                refined_candidates.append(cand)
            elif signal.action == 'WAIT' and signal.camino == Camino.SAFETY_CHECK:
                 pass
                 
        return refined_candidates

    def _prepare_orders(self, today, candidates, equity, regime_factor: float = 1.0):
        for cand in candidates:
            if cand['symbol'] in self.portfolio.positions: continue
            
            # ═══════════════════════════════════════════════════════════════
            # 🛡️ FILTROS DE RIESGO DUROS (BASADOS EN ESTADÍSTICAS)
            # ═══════════════════════════════════════════════════════════════
            
            # 🚫 FILTRO 1: SOBREEXTENSIÓN (Dist SMA20 > 7%)
            # Regla: Si el precio está >7% sobre SMA20, RECHAZAR trade
            # Razón: Estos son los peores perdedores estadísticamente
            dist_sma20 = cand.get('dist_sma20_pct', 0)
            
            # DEBUG: Mostrar SIEMPRE el valor para verificar
            if dist_sma20 != 0:
                logger.info(f"🔍 {cand['symbol']} dist_sma20_pct={dist_sma20:.2f}%")
            
            if dist_sma20 > 7.0:
                logger.info(f"❌ {cand['symbol']} REJECTED: Sobreextendido {dist_sma20:.2f}% > 7% de SMA20")
                continue  # SKIP este trade
            
            # ⚠️ FILTRO 2: VolTrig = Danger (RVOL >= 3x)
            # Regla: Si VolTrig == 'Danger', reducir tamaño al 50%
            # Razón: El edge desaparece con volumen extremo
            vol_trig = cand.get('vol_trig', 'Safe')
            vol_trig_reduction = 1.0  # Default: sin reducción
            vol_trig_note = ""
            
            if vol_trig == 'Danger':
                vol_trig_reduction = 0.5  # Reducir a 50%
                vol_trig_note = f"⚠️ VolTrig=DANGER (RVOL={cand.get('rvol', 0):.2f}x) - Size reduced 50%"
                logger.info(f"⚠️ {cand['symbol']} {vol_trig_note}")
            
            # ═══════════════════════════════════════════════════════════════
            
            trigger_price = cand['entry_trigger'] * 1.005
            technical_stop = cand['stop_loss']
            
            # --- RISK MANAGEMENT: STOP LOSS CAP ---
            # Rule: Stop never > 8% OR 2x ADR
            entry_price = trigger_price
            current_risk_pct = (entry_price - technical_stop) / entry_price
            
            cand_adr = cand.get('adr_pct', 2.0) / 100.0 # Default to 2% if missing
            max_risk_adr = cand_adr * 2.0
            max_risk_hard = 0.08 # 8% Hard Cap
            
            allowed_risk_pct = min(max_risk_adr, max_risk_hard)
            
            risk_note = ""
            final_stop = technical_stop
            
            if current_risk_pct > allowed_risk_pct:
                # Clamp stop to max allowed
                final_stop = entry_price * (1 - allowed_risk_pct)
                risk_note = f"Risk Clamped: {current_risk_pct*100:.1f}% -> {allowed_risk_pct*100:.1f}% (Max 2xADR/8%)"
            
            stop_price = final_stop

            self.risk_manager.account_equity = equity
            self.risk_manager.buying_power = self.portfolio.cash
            
            # Obtener ADR y volumen - USAR DATOS DEL SCREENER (ya calculados)
            # No recargar datos para evitar consumo de memoria
            adr_pct = cand.get('adr_pct', 4.0)
            avg_volume = cand.get('avg_vol', 1000000)
            
            sizing = self.risk_manager.calculate_position_size(
                entry_price=trigger_price,
                stop_price=stop_price,
                adr_percent=adr_pct,
                avg_daily_volume=avg_volume,
                market_regime_factor=regime_factor  # dinamico por Stage 1/2/3/4
            )
            
            # ═══════════════════════════════════════════════════════════════
            # 🛡️ APLICAR REDUCCIÓN POR VolTrig (antes de otras reducciones)
            # ═══════════════════════════════════════════════════════════════
            if vol_trig_reduction < 1.0:
                original_shares = sizing['shares']
                sizing['shares'] = int(original_shares * vol_trig_reduction)
                if sizing['shares'] == 0 and original_shares > 0:
                    sizing['shares'] = 1  # Mínimo 1 share si había shares
            
            # --- EARNINGS CHECK ---
            earnings_dates = self.data_provider.get_earnings_dates(cand['symbol'])
            earnings_note = ""
            if not earnings_dates.empty:
                # Find next earnings date after today
                future_dates = earnings_dates[earnings_dates > pd.to_datetime(today)]
                if not future_dates.empty:
                    next_earning = future_dates[0]
                    days_to_earning = (next_earning - pd.to_datetime(today)).days
                    
                    if 0 <= days_to_earning < 5:
                        # ⚠️ EARNINGS RISK: Reduce size to 1/4
                        original_shares = sizing['shares']
                        sizing['shares'] = int(original_shares * 0.25)
                        earnings_note = f"EARNINGS_RISK ({days_to_earning}d away) - Size reduced 75% ({original_shares}->{sizing['shares']})"
                        # If size becomes 0, we effectively "NO ENTER"
            
            # --- HIGH VOLATILITY CHECK (ADR) ---
            # Rule: If ADR > 5-6%, reduce position to 1/3 or 1/4 of normal
            adr_note = ""
            if adr_pct > 5.0:  # ADR threshold
                if adr_pct > 6.0:
                    # Very high volatility: reduce to 1/4
                    reduction_factor = 0.25
                    reduction_desc = "1/4 (75% reduction)"
                else:
                    # High volatility: reduce to 1/3
                    reduction_factor = 0.33
                    reduction_desc = "1/3 (67% reduction)"
                
                original_shares = sizing['shares']
                sizing['shares'] = int(original_shares * reduction_factor)
                adr_note = f"HIGH_VOLATILITY (ADR {adr_pct:.1f}%) - Size reduced to {reduction_desc} ({original_shares}->{sizing['shares']})"
            
            # Combine notes
            final_note = " | ".join(filter(None, [risk_note, vol_trig_note, earnings_note, adr_note, cand.get('reason', '')]))
            
            # Capture Context Data for Analysis
            # Determinar trend_sma del candidato (viene del screener)
            trend_sma = 'Uptrend' if cand.get('price', 0) > cand.get('sma_20', 0) else 'Weak'
            
            # Earnings metrics for Context (Fix Issue #1)
            days_to_earning_val = -1
            time_since_earning_val = -1
            try:
                if not earnings_dates.empty:
                    earning_dt = pd.to_datetime(earnings_dates).tz_localize(None)
                    today_dt = pd.to_datetime(today).tz_localize(None)
                    
                    future_earnings = earning_dt[earning_dt > today_dt]
                    if not future_earnings.empty:
                        days_to_earning_val = int((future_earnings[0] - today_dt).days)
                        
                    past_earnings = earning_dt[earning_dt <= today_dt]
                    if not past_earnings.empty:
                        time_since_earning_val = int((today_dt - past_earnings[-1]).days)
            except Exception as e:
                logger.debug(f"Error calculating daily engine earnings context: {e}")

            context = {
                'adr_pct': adr_pct,
                'avg_volume': avg_volume,
                'rvol': cand.get('rvol', 0),  # Tomar RVOL del screener
                'dist_sma20_pct': dist_sma20,  # Agregar métrica de extensión
                'vol_trig': vol_trig,  # Agregar clasificación VolTrig
                'trend_sma': trend_sma,
                'days_to_next_earnings': days_to_earning_val,
                'time_since_earnings': time_since_earning_val
            }


            if sizing['shares'] > 0:
                self.pending_orders.append(PendingOrder(
                    symbol=cand['symbol'], order_type='BUY_STOP', limit_price=trigger_price,
                    stop_loss_initial=stop_price, shares=sizing['shares'],
                    valid_date=today + pd.tseries.offsets.BusinessDay(1),
                    note=final_note,
                    signal_type=cand.get('signal_type', 'UNKNOWN'),
                    context_data=context
                ))

    def _update_equity(self, today):
        open_pnl = 0
        for symbol, pos in self.portfolio.positions.items():
            df = self._get_market_data(symbol, today)
            if not df.empty and today in df.index:
                close_col = 'close' if 'close' in df.columns else 'Close'
                open_pnl += (df.loc[today][close_col] - pos.entry_price) * pos.shares
        self.portfolio.equity_curve.append({'date': today, 'equity': self.portfolio.cash + open_pnl})