"""
Triad Indicators - The Three Forces
1. Base Detection (El Mapa)
2. AVWAP from ATH (El Peaje)
3. Intraday VWAP (El Pedal)
"""
import pandas as pd
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class TriadIndicators:
    
    @staticmethod
    def detect_base(df: pd.DataFrame, lookback: int = 20, 
                   min_prior_advance: float = 0.30,
                   max_base_range: float = 0.15,
                   tightness_days: int = 5) -> dict:
        """
        Detect professional consolidation base (El Mapa)
        
        Criterios institucionales:
        1. Tendencia Previa: Subida de al menos 30% antes de la base
        2. Volumen en la Base: Volumen seco (bajo) en días rojos
        3. Tightness: Últimas velas apretadas antes de ruptura
        4. Medias Móviles: Ordenadas correctamente (10>20>50>200)
        
        Args:
            lookback: Días de consolidación a analizar
            min_prior_advance: % mínimo de subida previa requerida (default 30%)
            max_base_range: % máximo de rango de la base (default 15%)
            tightness_days: Días finales para verificar apretamiento
        """
        if df.empty or len(df) < lookback + 60:  # Need history for prior advance
            return {'detected': False, 'reason': 'Insufficient data'}
        
        # =================================================================
        # 1. TENDENCIA PREVIA: ¿Subió al menos 30% antes de la base?
        # =================================================================
        # Buscar el punto bajo antes de la base (últimos 60 días antes del lookback)
        prior_period = df.iloc[-(lookback + 60):-lookback]
        if len(prior_period) < 20:
            return {'detected': False, 'reason': 'Insufficient prior data'}
        
        prior_low = prior_period['Low'].min()
        base_start_price = df.iloc[-lookback]['Close']
        prior_advance = (base_start_price - prior_low) / prior_low
        
        has_prior_advance = prior_advance >= min_prior_advance
        
        # =================================================================
        # 2. ANÁLISIS DE LA BASE
        # =================================================================
        recent = df.tail(lookback)
        
        range_high = recent['High'].max()
        range_low = recent['Low'].min()
        range_pct = (range_high - range_low) / range_low
        
        current_price = df['Close'].iloc[-1]
        distance_from_high = (range_high - current_price) / current_price
        
        is_compressed = range_pct <= max_base_range
        near_highs = distance_from_high < 0.03  # Within 3% of base high
        
        # =================================================================
        # 3. VOLUMEN EN LA BASE: ¿Se secó en días rojos?
        # =================================================================
        recent_with_vol = recent.copy()
        recent_with_vol['is_red'] = recent_with_vol['Close'] < recent_with_vol['Open']
        recent_with_vol['is_green'] = recent_with_vol['Close'] >= recent_with_vol['Open']
        
        red_days = recent_with_vol[recent_with_vol['is_red']]
        green_days = recent_with_vol[recent_with_vol['is_green']]
        
        if len(red_days) > 0 and len(green_days) > 0:
            avg_red_volume = red_days['Volume'].mean()
            avg_green_volume = green_days['Volume'].mean()
            
            # Volumen en rojos debe ser menor que en verdes (idealmente 50-70% menos)
            volume_dry_ratio = avg_red_volume / avg_green_volume if avg_green_volume > 0 else 1.0
            volume_dried_up = volume_dry_ratio < 0.75  # Rojos tienen <75% del volumen de verdes
        else:
            volume_dry_ratio = 1.0
            volume_dried_up = False
        
        # =================================================================
        # 4. TIGHTNESS: ¿Últimas velas son apretadas?
        # =================================================================
        last_days = recent.tail(tightness_days)
        
        # Calcular rango promedio de las últimas velas
        last_days_ranges = (last_days['High'] - last_days['Low']) / last_days['Low']
        avg_recent_range = last_days_ranges.mean()
        
        # Comparar con rango promedio de toda la base
        all_ranges = (recent['High'] - recent['Low']) / recent['Low']
        avg_base_range = all_ranges.mean()
        
        # Las últimas velas deben ser más apretadas (menor rango)
        is_tight = avg_recent_range < avg_base_range * 0.8  # 20% más apretadas
        
        # =================================================================
        # 5. MEDIAS MÓVILES: ¿Están ordenadas? (10>20>50>200)
        # =================================================================
        # Calcular EMAs
        df_calc = df.copy()
        df_calc['EMA10'] = df_calc['Close'].ewm(span=10, adjust=False).mean()
        df_calc['EMA20'] = df_calc['Close'].ewm(span=20, adjust=False).mean()
        df_calc['SMA50'] = df_calc['Close'].rolling(window=50).mean()
        df_calc['SMA200'] = df_calc['Close'].rolling(window=200).mean()
        
        current_emas = df_calc.iloc[-1]
        
        # Verificar orden (con tolerancia de 1% para evitar rechazos por decimales)
        ema10 = current_emas['EMA10']
        ema20 = current_emas['EMA20']
        sma50 = current_emas['SMA50']
        sma200 = current_emas['SMA200']
        
        # Permitir que estén muy cerca (dentro de 1%)
        mas_aligned = (
            ema10 >= ema20 * 0.99 and
            ema20 >= sma50 * 0.99 and
            sma50 >= sma200 * 0.99
        )
        
        # Además, precio debe estar sobre EMA20 (mínimo)
        price_above_ema20 = current_price >= ema20 * 0.98
        
        # =================================================================
        # DECISIÓN FINAL: ¿Es una base válida?
        # =================================================================
        # Criterios OBLIGATORIOS:
        # 1. Subida previa de 30%+
        # 2. Rango comprimido (<15%)
        # 3. Precio cerca de los altos
        
        # Criterios DESEABLES (mejoran calidad):
        # 4. Volumen seco en rojos
        # 5. Tightness en últimos días
        # 6. MAs alineadas
        
        # Base detectada si cumple obligatorios + al menos 2 de 3 deseables
        mandatory_met = has_prior_advance and is_compressed and near_highs
        quality_score = sum([volume_dried_up, is_tight, mas_aligned and price_above_ema20])
        
        is_valid_base = mandatory_met and quality_score >= 2
        
        # Determinar razón si falla
        if not is_valid_base:
            reasons = []
            if not has_prior_advance:
                reasons.append(f"No prior advance (only {prior_advance*100:.1f}%, need {min_prior_advance*100:.0f}%)")
            if not is_compressed:
                reasons.append(f"Range too wide ({range_pct*100:.1f}% > {max_base_range*100:.0f}%)")
            if not near_highs:
                reasons.append(f"Price too far from high ({distance_from_high*100:.1f}%)")
            if not volume_dried_up:
                reasons.append(f"Volume not dried (ratio {volume_dry_ratio:.2f})")
            if not is_tight:
                reasons.append("Not tight enough")
            if not mas_aligned:
                reasons.append("MAs not aligned")
            if not price_above_ema20:
                reasons.append("Price below EMA20")
            
            reason = " | ".join(reasons) if reasons else "Unknown"
        else:
            reason = "Valid base detected"
        
        return {
            'detected': is_valid_base,
            'reason': reason,
            # Base metrics
            'base_high': range_high,
            'base_low': range_low,
            'compression_pct': range_pct,
            'distance_from_high_pct': distance_from_high,
            'current_price': current_price,
            # Quality metrics
            'prior_advance_pct': prior_advance,
            'has_prior_advance': has_prior_advance,
            'volume_dry_ratio': volume_dry_ratio,
            'volume_dried_up': volume_dried_up,
            'is_tight': is_tight,
            'avg_recent_range_pct': avg_recent_range,
            'mas_aligned': mas_aligned,
            'price_above_ema20': price_above_ema20,
            'quality_score': quality_score,
            # Moving averages
            'ema10': ema10,
            'ema20': ema20,
            'sma50': sma50,
            'sma200': sma200
        }
    
    @staticmethod
    def calculate_avwap_from_ath(df: pd.DataFrame) -> dict:
        """
        Calculate Anchored VWAP from All-Time High (El Peaje)
        This is where old bag holders are trapped
        """
        if df.empty:
            return {'calculated': False}
        
        # Find ATH
        ath_idx = df['High'].idxmax()
        ath_price = df.loc[ath_idx, 'High']
        
        # Calculate AVWAP from ATH forward
        df_from_ath = df.loc[ath_idx:]
        
        if len(df_from_ath) < 2:
            return {
                'calculated': False,
                'ath_price': ath_price,
                'ath_date': ath_idx
            }
        
        # AVWAP calculation: cumulative (volume * typical_price) / cumulative volume
        typical_price = (df_from_ath['High'] + df_from_ath['Low'] + df_from_ath['Close']) / 3
        cumulative_vp = (typical_price * df_from_ath['Volume']).cumsum()
        cumulative_vol = df_from_ath['Volume'].cumsum()
        
        avwap = cumulative_vp / cumulative_vol
        current_avwap = avwap.iloc[-1]
        
        return {
            'calculated': True,
            'ath_price': ath_price,
            'ath_date': ath_idx,
            'current_avwap': current_avwap,
            'current_price': df['Close'].iloc[-1],
            'distance_to_avwap_pct': (current_avwap - df['Close'].iloc[-1]) / df['Close'].iloc[-1]
        }
    
    @staticmethod
    def calculate_intraday_vwap(df_intraday: pd.DataFrame) -> dict:
        """
        Calculate Intraday VWAP (El Pedal)
        Reset daily - confirms institutional flow
        """
        if df_intraday.empty:
            return {'calculated': False}
        
        # Get today's session only
        today = df_intraday.index[-1].date()
        df_today = df_intraday[df_intraday.index.date == today]
        
        if df_today.empty:
            return {'calculated': False}
        
        # Calculate VWAP for today's session
        typical_price = (df_today['High'] + df_today['Low'] + df_today['Close']) / 3
        cumulative_vp = (typical_price * df_today['Volume']).cumsum()
        cumulative_vol = df_today['Volume'].cumsum()
        
        vwap = cumulative_vp / cumulative_vol
        current_vwap = vwap.iloc[-1]
        current_price = df_today['Close'].iloc[-1]
        
        # Detect if price is above/below VWAP
        above_vwap = current_price > current_vwap
        
        # Detect recent cross (last 2 candles)
        if len(vwap) >= 2:
            prev_price = df_today['Close'].iloc[-2]
            prev_vwap = vwap.iloc[-2]
            
            crossed_up = (prev_price <= prev_vwap) and (current_price > current_vwap)
            crossed_down = (prev_price >= prev_vwap) and (current_price < current_vwap)
        else:
            crossed_up = False
            crossed_down = False
        
        return {
            'calculated': True,
            'current_vwap': current_vwap,
            'current_price': current_price,
            'above_vwap': above_vwap,
            'crossed_up': crossed_up,
            'crossed_down': crossed_down,
            'distance_pct': (current_price - current_vwap) / current_vwap,
            'session_open': df_today['Open'].iloc[0],
            'session_high': df_today['High'].max(),
            'session_low': df_today['Low'].min()
        }
    
    @staticmethod
    def detect_gap_down(df_intraday: pd.DataFrame, previous_close: float) -> dict:
        """
        Detect gap down at market open (for Camino 2)
        """
        if df_intraday.empty:
            return {'detected': False}
        
        today = df_intraday.index[-1].date()
        df_today = df_intraday[df_intraday.index.date == today]
        
        if df_today.empty:
            return {'detected': False}
        
        session_open = df_today['Open'].iloc[0]
        gap_pct = (session_open - previous_close) / previous_close
        
        is_gap_down = gap_pct < -0.005  # At least -0.5% gap
        
        return {
            'detected': is_gap_down,
            'gap_pct': gap_pct,
            'session_open': session_open,
            'previous_close': previous_close
        }
