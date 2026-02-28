from openbb import obb
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
import sys
from pathlib import Path

# Add project root to path to ensure imports work if run directly
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.risk_manager import RiskManager

logger = logging.getLogger(__name__)

class TriadOpenBB:
    """
    Clase para implementar la estrategia TRIAD usando OpenBB como fuente de datos.
    Implementa gestión de posición avanzada tipo Quant (TP1, TP2, Runner, Breakeven).
    """
    
    def __init__(self):
        self.obb = obb
    
    # ... (calculate_avwap_ath remains same)
    def calculate_avwap_ath(self, symbol: str, start_date: str = '2020-01-01') -> Optional[Dict]:
        """Calcula AVWAP y ATH (Sin cambios)"""
        try:
            hist_data = obb.equity.price.historical(
                symbol=symbol, start_date=start_date, provider='yfinance'
            ).to_df()
            
            if hist_data.empty: return None
            
            # Handle both lowercase and uppercase column names
            close_col = 'close' if 'close' in hist_data.columns else 'Close'
            high_col = 'high' if 'high' in hist_data.columns else 'High'
            volume_col = 'volume' if 'volume' in hist_data.columns else 'Volume'
            
            if volume_col in hist_data.columns and hist_data[volume_col].sum() > 0:
                hist_data['close_volume'] = hist_data[close_col] * hist_data[volume_col]
                avwap = hist_data['close_volume'].sum() / hist_data[volume_col].sum()
            else:
                avwap = hist_data[close_col].mean()
            
            ath = hist_data[high_col].max()
            ath_date = hist_data[high_col].idxmax()
            current_price = hist_data[close_col].iloc[-1]
            ath_distance = (current_price - ath) / ath * 100
            
            result = {
                'symbol': symbol, 'avwap': avwap, 'ath': ath, 'ath_date': ath_date,
                'current_price': current_price, 'ath_distance_pct': ath_distance,
                'data_available': len(hist_data)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculando AVWAP/ATH para {symbol}: {str(e)}")
            return None

    # ... (detect_caminos remains same)
    def detect_caminos(self, df: pd.DataFrame) -> List[Dict]:
        """Detecta patrones de entrada (Sin cambios sustanciales, asegura indicadores)"""
        signals = []
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            return signals
        
        df = self._calculate_indicators(df)
        
        # Handle both lowercase and uppercase column names
        close_col = 'close' if 'close' in df.columns else 'Close'
        volume_col = 'volume' if 'volume' in df.columns else 'Volume'
        
        for i in range(20, len(df)):
            current = df.iloc[i]
            prev = df.iloc[i-1]
            
            # Camino 1: Momentum
            if (current[close_col] > current['sma_20'] and 
                current['rsi'] < 70 and current['rsi'] > 50 and
                current[close_col] > prev[close_col] and
                current[volume_col] > current['sma_volume_20']):
                signals.append({'date': current.name, 'type': 'camino_1', 'price': current[close_col], 'reason': 'momentum_1'})
            
            # Camino 2: Pullback
            elif (current[close_col] < current['sma_20'] and 
                  current[close_col] > current['sma_50'] and
                  current['rsi'] > 30 and current['rsi'] < 50 and
                  current[close_col] > prev[close_col]):
                signals.append({'date': current.name, 'type': 'camino_2', 'price': current[close_col], 'reason': 'pullback_2'})
            
            # Camino 3: Breakout
            elif (current[close_col] > current['upper_bb'] and
                  current['rsi'] < 80 and current['rsi'] > 50 and
                  current[volume_col] > current['sma_volume_20'] * 1.5):
                signals.append({'date': current.name, 'type': 'camino_3', 'price': current[close_col], 'reason': 'breakout_3'})
        
        return signals

    def backtest_with_openbb(self, symbols: List[str], start: str, end: str, stop_loss_pct: Optional[float] = None, risk_manager: Optional[RiskManager] = None) -> pd.DataFrame:
        """Backtest iterativo"""
        results = []
        for symbol in symbols:
            try:
                daily_data = obb.equity.price.historical(symbol=symbol, start_date=start, end_date=end).to_df()
                if daily_data.empty: continue
                
                signals = self.detect_caminos(daily_data)
                for signal in signals:
                    outcome = self.simulate_trade_advanced(daily_data, signal, stop_loss_pct, risk_manager)
                    if outcome:
                        outcome['symbol'] = symbol
                        results.append(outcome)
            except Exception as e:
                logger.error(f"Error backtest {symbol}: {e}")
                continue
        return pd.DataFrame(results) if results else pd.DataFrame()

    def simulate_trade_advanced(self, data: pd.DataFrame, signal: Dict, stop_loss_pct: Optional[float] = None, risk_manager: Optional[RiskManager] = None) -> Optional[Dict]:
        """
        MOTOR DE GESTIÓN DE POSICIONES (Senior Quant Logic)
        Implementa máquina de estados: ENTRY -> PARTIAL_1 -> PARTIAL_2 -> RUNNER -> EXIT
        """
        try:
            # --- 1. CONFIGURACIÓN INICIAL DEL TRADE ---
            idx_entry = data.index.get_loc(signal['date'])
            if idx_entry + 1 >= len(data): return None # Sin datos futuros
            
            entry_price = signal['price']
            entry_date = signal['date']
            
            # Handle both lowercase and uppercase column names
            close_col = 'close' if 'close' in data.columns else 'Close'
            high_col = 'high' if 'high' in data.columns else 'High'
            low_col = 'low' if 'low' in data.columns else 'Low'
            
            # Stop Loss Inicial:
            if stop_loss_pct is not None and stop_loss_pct > 0:
                # Usar porcentaje fijo si se provee
                stop_loss = entry_price * (1 - (stop_loss_pct / 100))
            else:
                # Lógica por defecto: Mínimo del día de señal (Swing Low proxy)
                low_of_day = data.iloc[idx_entry][low_col]
                stop_loss = low_of_day
                if (entry_price - stop_loss) / entry_price < 0.01:
                    stop_loss = entry_price * 0.97
            
            risk_per_share = entry_price - stop_loss
            if risk_per_share <= 0: risk_per_share = entry_price * 0.02 # Fallback
            
            # --- RISK MANAGEMENT CALCULATION ---
            shares = 1
            position_value = entry_price
            monetary_risk = risk_per_share
            
            if risk_manager:
                # Calcular ADR (Average Daily Range) de últimos 20 días
                recent_data = data.iloc[max(0, idx_entry-20):idx_entry+1]
                if len(recent_data) > 1:
                    adr_pct = ((recent_data[high_col] - recent_data[low_col]) / recent_data[close_col] * 100).mean()
                    avg_volume = int(recent_data['Volume'].mean())
                else:
                    adr_pct = 4.0  # Default conservador
                    avg_volume = 1000000  # Default 1M shares
                
                sizing = risk_manager.calculate_position_size(
                    entry_price=entry_price,
                    stop_price=stop_loss,
                    adr_percent=adr_pct,
                    avg_daily_volume=avg_volume,
                    market_regime_factor=1.0  # Default for now, could be dynamic
                )
                shares = sizing['shares']
                position_value = sizing['position_value']
                monetary_risk = sizing['risk_monetary']
                
                if shares == 0:
                    return None # Risk manager rejected trade

            # Objetivos basados en R
            target_1r = entry_price + risk_per_share
            target_1_5r = entry_price + (1.5 * risk_per_share)
            
            # --- 2. ESTADO DEL TRADE ---
            position_pct = 1.0  # 100% de la posición viva
            realized_pnl_pct = 0.0 # PnL acumulado (ponderado)
            state = "ENTRY"
            
            exit_reasons = []
            final_exit_date = None
            final_exit_price = 0.0
            
            # --- 3. BUCLE DE SIMULACIÓN (BAR-BY-BAR) ---
            # Iteramos hasta 60 días máximo o fin de datos
            max_days = 60
            
            for i in range(1, max_days + 1):
                curr_idx = idx_entry + i
                if curr_idx >= len(data):
                    # Fin de datos: cerrar todo lo que queda
                    close_price = data.iloc[-1]['Close']
                    realized_pnl_pct += ((close_price - entry_price) / entry_price) * position_pct
                    exit_reasons.append("End of Data")
                    final_exit_date = data.index[-1]
                    final_exit_price = close_price # Precio ref último cierre
                    break
                
                row = data.iloc[curr_idx]
                curr_date = data.index[curr_idx]
                
                # A. VERIFICAR STOP LOSS / HARD EXIT
                if row['Low'] <= stop_loss:
                    # SL Ejecutado al precio de Stop
                    loss_pct = ((stop_loss - entry_price) / entry_price) * position_pct
                    realized_pnl_pct += loss_pct
                    exit_reasons.append(f"Stop Loss ({state})")
                    final_exit_date = curr_date
                    final_exit_price = stop_loss
                    state = "FULL_EXIT"
                    break
                
                # B. LÓGICA DE ESTADOS
                
                # --- ESTADO: ENTRY ---
                if state == "ENTRY":
                    # TP1 Check: 1.5R alcanzado (High >= Target)
                    if row['High'] >= target_1_5r:
                        # ACCIÓN: Vender 40% (TP1 - Risk Off)
                        exit_price_tp1 = target_1_5r
                        gain_pct = ((exit_price_tp1 - entry_price) / entry_price) * 0.40
                        realized_pnl_pct += gain_pct
                        position_pct -= 0.40
                        
                        # ACCIÓN: Mover Stop a Breakeven
                        stop_loss = entry_price * 1.005 # Levemente sobre BE para cubrir fees
                        
                        state = "PARTIAL_1_TAKEN"
                        exit_reasons.append("TP1 (1.5R)")
                
                # --- ESTADO: PARTIAL_1_TAKEN ---
                elif state == "PARTIAL_1_TAKEN":
                    # TP2 Check: Momentum (4 días tras entrada)
                    if i >= 4:
                        # ACCIÓN: Vender 30% adicional
                        exit_price_tp2 = row['Close']
                        gain_pct = ((exit_price_tp2 - entry_price) / entry_price) * 0.30
                        realized_pnl_pct += gain_pct
                        position_pct -= 0.30
                        
                        state = "PARTIAL_2_TAKEN" # (Runner Active)
                        exit_reasons.append("TP2 (Time/Mom)")

                # --- ESTADO: PARTIAL_2_TAKEN (RUNNER) ---
                elif state == "PARTIAL_2_TAKEN":
                    # Trailing Stop Dinámico: Cruce EMA 8 < EMA 21
                    # "Condición de salida final: Runner activo con trailing stop dinámico (8/21 cross)"
                    if row['ema_8'] < row['ema_21']:
                        # ACCIÓN: Cerrar Runner (restante ~30%)
                        exit_price_runner = row['Close']
                        gain_pct = ((exit_price_runner - entry_price) / entry_price) * position_pct
                        realized_pnl_pct += gain_pct
                        
                        final_exit_date = curr_date
                        final_exit_price = row['Close']
                        exit_reasons.append("Runner Exit (EMA 8/21 Cross)")
                        state = "FULL_EXIT"
                        break
            
            # --- 4. COMPILACIÓN DE RESULTADOS ---
            # Si el bucle termina y aún hay posición (ej. runner nunca tocó EMA10 en 60 días)
            if state != "FULL_EXIT" and position_pct > 0:
                close_price = data.iloc[curr_idx]['Close'] # Último precio iterado
                realized_pnl_pct += ((close_price - entry_price) / entry_price) * position_pct
                final_exit_date = data.index[curr_idx]
                final_exit_price = close_price
                exit_reasons.append("Max Hold Reached")

            return {
                'entry_date': entry_date,
                'exit_date': final_exit_date,
                'entry_price': entry_price,
                'exit_price': final_exit_price, # Precio ref del último cierre
                'returns_pct': realized_pnl_pct * 100, # Convertir a porcentaje visual
                'is_profitable': realized_pnl_pct > 0,
                'signal_type': signal['type'],
                'signal_reason': f"{signal['reason']} | {' + '.join(exit_reasons)}",
                'shares': shares,
                'position_value': position_value,
                'monetary_risk': monetary_risk
            }

        except Exception as e:
            logger.error(f"Error advanced simulation: {e}")
            return None

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Indicadores necesarios para la lógica Quant"""
        # Handle both lowercase and uppercase column names
        close_col = 'close' if 'close' in df.columns else 'Close'
        volume_col = 'volume' if 'volume' in df.columns else 'Volume'
        
        # Solo calcular si no existe (pueden venir de la DB)
        if 'sma_20' not in df.columns:
            df['sma_20'] = df[close_col].rolling(window=20).mean()
        
        if 'sma_50' not in df.columns:
            df['sma_50'] = df[close_col].rolling(window=50).mean()
        
        # EMAs para el Runner Trailing Stop (8 y 21)
        # Si ya vienen de la DB, no recalcular (ahorra memoria y CPU)
        if 'ema_8' not in df.columns:
            df['ema_8'] = df[close_col].ewm(span=8, adjust=False).mean()
        if 'ema_21' not in df.columns:
            df['ema_21'] = df[close_col].ewm(span=21, adjust=False).mean()
        
        # SMA Volumen para confirmación
        if 'sma_volume_20' not in df.columns:
            df['sma_volume_20'] = df[volume_col].rolling(window=20).mean()
        
        # RSI
        if 'rsi' not in df.columns:
            delta = df[close_col].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
        
        # Bandas Bollinger (para Camino 3)
        if 'middle_bb' not in df.columns:
            df['middle_bb'] = df[close_col].rolling(window=20).mean()
            bb_std = df[close_col].rolling(window=20).std()
            df['upper_bb'] = df['middle_bb'] + (bb_std * 2)
            df['lower_bb'] = df['middle_bb'] - (bb_std * 2)
        
        return df