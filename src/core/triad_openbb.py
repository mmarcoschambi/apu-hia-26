from openbb import obb
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class TriadOpenBB:
    """
    Clase para implementar la estrategia TRIAD usando OpenBB como fuente de datos
    """
    
    def __init__(self):
        self.obb = obb
    
    def calculate_avwap_ath(self, symbol: str, start_date: str = '2020-01-01') -> Optional[Dict]:
        """
        Calcular AVWAP y ATH basado en datos de OpenBB
        """
        try:
            # Obtener datos históricos
            hist_data = obb.equity.price.historical(
                symbol=symbol,
                start_date=start_date,
                provider='yfinance'  # Podemos especificar proveedor
            ).to_df()
            
            if hist_data.empty:
                logger.warning(f"No se encontraron datos para {symbol}")
                return None
            
            # Calcular AVWAP (Average Volume Weighted Average Price)
            # AVWAP = sum(Close * Volume) / sum(Volume)
            if 'volume' in hist_data.columns and hist_data['volume'].sum() > 0:
                hist_data['close_volume'] = hist_data['close'] * hist_data['volume']
                avwap = hist_data['close_volume'].sum() / hist_data['volume'].sum()
            else:
                # Si no hay volumen, usar media simple
                avwap = hist_data['close'].mean()
            
            # Encontrar ATH (All Time High)
            ath = hist_data['high'].max()
            ath_date = hist_data['high'].idxmax()
            
            # Calcular distancia al ATH
            current_price = hist_data['close'].iloc[-1]
            ath_distance = (current_price - ath) / ath * 100
            
            result = {
                'symbol': symbol,
                'avwap': avwap,
                'ath': ath,
                'ath_date': ath_date,
                'current_price': current_price,
                'ath_distance_pct': ath_distance,
                'data_available': len(hist_data)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculando AVWAP/ATH para {symbol}: {str(e)}")
            return None
    
    def detect_caminos(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detectar los 3 caminos (momentum patterns) en los datos
        """
        signals = []
        
        # Asegurar que el dataframe tiene las columnas necesarias
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.warning("Columnas insuficientes para detección de patrones")
            return signals
        
        # Calcular indicadores técnicos
        df = self._calculate_indicators(df)
        
        # Detectar patrones de momentum (caminos)
        for i in range(20, len(df)):  # Empezar después de tener suficientes datos para indicadores
            current = df.iloc[i]
            prev = df.iloc[i-1]
            
            # Patrón 1: Momentum alcista (Camino 1)
            if (current['close'] > current['sma_20'] and 
                current['rsi'] < 70 and current['rsi'] > 50 and
                current['close'] > prev['close'] and
                current['volume'] > current['sma_volume_20']):
                
                signals.append({
                    'date': current.name,
                    'type': 'camino_1',
                    'price': current['close'],
                    'reason': 'momentum_1'
                })
            
            # Patrón 2: Pullback con soporte (Camino 2)
            elif (current['close'] < current['sma_20'] and 
                  current['close'] > current['sma_50'] and
                  current['rsi'] > 30 and current['rsi'] < 50 and
                  current['close'] > prev['close']):
                
                signals.append({
                    'date': current.name,
                    'type': 'camino_2',
                    'price': current['close'],
                    'reason': 'pullback_2'
                })
            
            # Patrón 3: Breakout (Camino 3)
            elif (current['close'] > current['upper_bb'] and
                  current['rsi'] < 80 and current['rsi'] > 50 and
                  current['volume'] > current['sma_volume_20'] * 1.5):
                
                signals.append({
                    'date': current.name,
                    'type': 'camino_3',
                    'price': current['close'],
                    'reason': 'breakout_3'
                })
        
        return signals
    
    def backtest_with_openbb(self, symbols: List[str], start: str, end: str) -> pd.DataFrame:
        """
        Backtest usando datos de OpenBB
        """
        results = []
        
        for symbol in symbols:
            try:
                # Obtener datos diarios
                daily_data = obb.equity.price.historical(
                    symbol=symbol,
                    start_date=start,
                    end_date=end
                ).to_df()
                
                if daily_data.empty:
                    logger.warning(f"No se encontraron datos para {symbol}")
                    continue
                
                # Detectar señales
                signals = self.detect_caminos(daily_data)
                
                # Simular trades para cada señal
                for signal in signals:
                    outcome = self.simulate_trade(daily_data, signal)
                    if outcome:
                        outcome['symbol'] = symbol
                        results.append(outcome)
                        
            except Exception as e:
                logger.error(f"Error en backtest para {symbol}: {str(e)}")
                continue
        
        return pd.DataFrame(results) if results else pd.DataFrame()
    
    def simulate_trade(self, data: pd.DataFrame, signal: Dict) -> Optional[Dict]:
        """
        Simular trade basado en señal
        """
        try:
            # Encontrar índice del signal
            signal_idx = data.index.get_loc(signal['date'])
            
            # Simular trade por 5 días hábiles
            holding_period = 5
            if signal_idx + holding_period >= len(data):
                return None  # No hay suficientes datos
            
            entry_price = signal['price']
            exit_price = data.iloc[signal_idx + holding_period]['close']
            
            # Calcular retorno
            returns_pct = (exit_price - entry_price) / entry_price * 100
            
            # Determinar si fue ganancia o pérdida
            is_profitable = returns_pct > 0
            
            trade_result = {
                'entry_date': signal['date'],
                'exit_date': data.index[signal_idx + holding_period],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'returns_pct': returns_pct,
                'is_profitable': is_profitable,
                'signal_type': signal['type'],
                'signal_reason': signal['reason']
            }
            
            return trade_result
            
        except Exception as e:
            logger.error(f"Error simulando trade: {str(e)}")
            return None
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcular indicadores técnicos necesarios
        """
        # SMA 20
        df['sma_20'] = df['close'].rolling(window=20).mean()
        
        # SMA 50
        df['sma_50'] = df['close'].rolling(window=50).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Bandas de Bollinger
        df['middle_bb'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['upper_bb'] = df['middle_bb'] + (bb_std * 2)
        df['lower_bb'] = df['middle_bb'] - (bb_std * 2)
        
        # SMA de volumen
        df['sma_volume_20'] = df['volume'].rolling(window=20).mean()
        
        return df