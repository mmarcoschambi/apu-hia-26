"""
Pattern Detection Engine - Institutional Base Structures
=========================================================
Detecta 4 patrones principales de acumulación institucional:
1. Cup & Handle (Taza con Asa)
2. Flat Base (Base Plana)
3. High Tight Flag (Bandera Ajustada)
4. VCP (Volatility Contraction Pattern)

Plus: Pocket Pivots para entradas anticipadas
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Tipos de patrones detectables"""
    CUP_AND_HANDLE = "CUP_AND_HANDLE"
    FLAT_BASE = "FLAT_BASE"
    HIGH_TIGHT_FLAG = "HIGH_TIGHT_FLAG"
    VCP = "VCP"
    POCKET_PIVOT = "POCKET_PIVOT"


@dataclass
class PatternResult:
    """Resultado de detección de patrón"""
    detected: bool
    pattern_type: PatternType
    confidence: float  # 0.0 - 1.0
    entry_price: Optional[float]
    stop_loss: Optional[float]
    pivot_price: Optional[float]
    base_depth: Optional[float]
    base_length: int  # días
    characteristics: Dict
    reasoning: str


class PatternDetectionEngine:
    """
    Motor principal de detección de estructuras institucionales
    """
    
    def __init__(self, symbol: str, df: pd.DataFrame, lookback: int = 200):
        """
        Args:
            symbol: Ticker del símbolo
            df: DataFrame con columnas [open, high, low, close, volume]
            lookback: Días de historia para analizar
        """
        self.symbol = symbol
        self.df = df.tail(lookback).copy()
        self.lookback = lookback
        
        # Calcular indicadores necesarios
        self._calculate_indicators()
    
    def _calculate_indicators(self):
        """Calcular indicadores técnicos necesarios"""
        # Moving Averages
        self.df['sma_10'] = self.df['close'].rolling(window=10).mean()
        self.df['sma_20'] = self.df['close'].rolling(window=20).mean()
        self.df['sma_50'] = self.df['close'].rolling(window=50).mean()
        self.df['sma_200'] = self.df['close'].rolling(window=200).mean()
        
        # Volatility (ATR)
        high_low = self.df['high'] - self.df['low']
        high_close = np.abs(self.df['high'] - self.df['close'].shift())
        low_close = np.abs(self.df['low'] - self.df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        self.df['atr'] = true_range.rolling(14).mean()
        
        # Volume MA
        self.df['volume_ma_50'] = self.df['volume'].rolling(50).mean()
    
    def scan_all_patterns(self) -> List[PatternResult]:
        """
        Escanea todas las estructuras en orden de prioridad
        
        Returns:
            Lista de patrones detectados ordenados por confianza
        """
        patterns_detected = []
        
        # Orden de evaluación (de más agresivo a más conservador)
        patterns_to_check = [
            ('high_tight_flag', self.detect_high_tight_flag),
            ('flat_base', self.detect_flat_base),
            ('cup_and_handle', self.detect_cup_and_handle),
            ('vcp', self.detect_vcp),
            ('pocket_pivot', self.detect_pocket_pivot)
        ]
        
        for pattern_name, detection_func in patterns_to_check:
            try:
                result = detection_func()
                if result.detected:
                    patterns_detected.append(result)
                    logger.info(f"✅ {self.symbol}: {result.pattern_type.value} detected "
                              f"(confidence: {result.confidence:.2f})")
            except Exception as e:
                logger.error(f"Error detecting {pattern_name} for {self.symbol}: {e}")
        
        # Ordenar por confianza
        patterns_detected.sort(key=lambda x: x.confidence, reverse=True)
        
        return patterns_detected
    
    # ========================================================================
    # PATRÓN 1: CUP & HANDLE
    # ========================================================================
    
    def detect_cup_and_handle(self, min_weeks: int = 7, max_weeks: int = 65) -> PatternResult:
        """
        Cup & Handle: Corrección en U + consolidación lateral
        
        Criterios:
        - Cup: Corrección de 12-33% en forma de U
        - Handle: Corrección de 8-12% después del cup
        - Duración: 7-65 semanas para el cup
        - Handle: 1-4 semanas típicamente
        - Volumen seco en correcciones
        - Breakout con volumen
        
        Returns:
            PatternResult con detección y características
        """
        if len(self.df) < 50:
            return PatternResult(
                detected=False, pattern_type=PatternType.CUP_AND_HANDLE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={}, reasoning="Insufficient data"
            )
        
        current_price = self.df['close'].iloc[-1]
        
        # Buscar el prior peak (inicio del cup)
        lookback_bars = min(len(self.df), 150)
        recent_data = self.df.tail(lookback_bars)
        
        # Encontrar el máximo (left peak)
        left_peak_idx = recent_data['high'].idxmax()
        left_peak_price = recent_data.loc[left_peak_idx, 'high']
        
        # Datos desde el left peak hasta ahora
        cup_data = self.df.loc[left_peak_idx:]
        
        if len(cup_data) < 35:  # Mínimo 7 semanas = ~35 días
            return PatternResult(
                detected=False, pattern_type=PatternType.CUP_AND_HANDLE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={}, reasoning="Cup too short"
            )
        
        # Buscar el bottom del cup (punto más bajo)
        cup_bottom_idx = cup_data['low'].idxmin()
        cup_bottom_price = cup_data.loc[cup_bottom_idx, 'low']
        
        # Calcular profundidad del cup
        cup_depth_pct = (left_peak_price - cup_bottom_price) / left_peak_price * 100
        
        # Validar profundidad del cup (12-33% típico)
        if cup_depth_pct < 12 or cup_depth_pct > 50:
            return PatternResult(
                detected=False, pattern_type=PatternType.CUP_AND_HANDLE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=cup_depth_pct, base_length=0,
                characteristics={'cup_depth_pct': cup_depth_pct},
                reasoning=f"Cup depth {cup_depth_pct:.1f}% outside range [12-50%]"
            )
        
        # Buscar el handle (últimas 1-4 semanas después del cup bottom)
        # Handle debe formarse en la segunda mitad del cup
        cup_midpoint_idx = len(cup_data) // 2
        handle_search_start = cup_data.index[cup_midpoint_idx]
        handle_data = cup_data.loc[handle_search_start:]
        
        if len(handle_data) < 5:
            return PatternResult(
                detected=False, pattern_type=PatternType.CUP_AND_HANDLE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=cup_depth_pct, base_length=len(cup_data),
                characteristics={'cup_depth_pct': cup_depth_pct},
                reasoning="No handle formed yet"
            )
        
        # Right peak (antes del handle) - debe ser similar al left peak
        # Buscar máximo en la parte derecha antes de las últimas 20 barras
        right_side_data = handle_data.iloc[:-5] if len(handle_data) > 5 else handle_data
        if len(right_side_data) < 5:
            right_peak_price = handle_data['high'].max()
        else:
            right_peak_price = right_side_data['high'].max()
        
        # Validar que right peak esté cerca del left peak (95-100% típico)
        right_peak_pct = (right_peak_price / left_peak_price) * 100
        
        # Handle pullback (últimas barras)
        handle_length = min(20, len(handle_data))  # Máximo 4 semanas
        handle_bars = handle_data.tail(handle_length)
        handle_low = handle_bars['low'].min()
        handle_high = handle_bars['high'].max()
        
        # Profundidad del handle desde el right peak
        handle_depth_pct = (handle_high - handle_low) / handle_high * 100
        
        # Validar handle (8-12% típico, máximo 15%)
        if handle_depth_pct > 15:
            return PatternResult(
                detected=False, pattern_type=PatternType.CUP_AND_HANDLE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=cup_depth_pct, base_length=len(cup_data),
                characteristics={
                    'cup_depth_pct': cup_depth_pct,
                    'handle_depth_pct': handle_depth_pct
                },
                reasoning=f"Handle too deep: {handle_depth_pct:.1f}% > 15%"
            )
        
        # VALIDACIÓN DE VOLUMEN
        # Cup bottom debe tener volumen bajo
        cup_bottom_window = cup_data.loc[cup_bottom_idx:].head(10)
        avg_volume_bottom = cup_bottom_window['volume'].mean()
        avg_volume_base = cup_data['volume'].mean()
        volume_ratio_bottom = avg_volume_bottom / avg_volume_base if avg_volume_base > 0 else 1.0
        
        # Handle debe tener volumen seco
        avg_volume_handle = handle_bars['volume'].mean()
        volume_ratio_handle = avg_volume_handle / avg_volume_base if avg_volume_base > 0 else 1.0
        
        volume_dried_up = volume_ratio_handle < 0.85  # Handle tiene <85% del volumen promedio
        
        # CALCULAR CONFIANZA
        confidence = 0.0
        confidence_factors = []
        
        # Factor 1: Profundidad del cup (óptimo 15-25%)
        if 15 <= cup_depth_pct <= 25:
            confidence += 0.25
            confidence_factors.append("Optimal cup depth")
        elif 12 <= cup_depth_pct <= 33:
            confidence += 0.15
            confidence_factors.append("Acceptable cup depth")
        
        # Factor 2: Handle depth (óptimo 8-12%)
        if 8 <= handle_depth_pct <= 12:
            confidence += 0.25
            confidence_factors.append("Optimal handle depth")
        elif handle_depth_pct <= 15:
            confidence += 0.15
            confidence_factors.append("Acceptable handle depth")
        
        # Factor 3: Right peak cerca del left peak (95-100%)
        if right_peak_pct >= 95:
            confidence += 0.20
            confidence_factors.append("Strong right peak")
        elif right_peak_pct >= 90:
            confidence += 0.10
            confidence_factors.append("Acceptable right peak")
        
        # Factor 4: Volumen seco
        if volume_dried_up:
            confidence += 0.20
            confidence_factors.append("Volume dried up in handle")
        
        # Factor 5: Precio cerca del pivot
        distance_to_pivot_pct = (handle_high - current_price) / current_price * 100
        if distance_to_pivot_pct < 2:
            confidence += 0.10
            confidence_factors.append("Near pivot point")
        
        # Detección positiva si confianza >= 0.5
        is_valid = confidence >= 0.5
        
        # Calcular entry y stop
        pivot_price = handle_high
        entry_price = pivot_price + 0.10  # 10 cents sobre pivot
        stop_loss = handle_low
        
        return PatternResult(
            detected=is_valid,
            pattern_type=PatternType.CUP_AND_HANDLE,
            confidence=confidence,
            entry_price=entry_price if is_valid else None,
            stop_loss=stop_loss if is_valid else None,
            pivot_price=pivot_price,
            base_depth=cup_depth_pct,
            base_length=len(cup_data),
            characteristics={
                'cup_depth_pct': cup_depth_pct,
                'handle_depth_pct': handle_depth_pct,
                'right_peak_pct': right_peak_pct,
                'volume_ratio_handle': volume_ratio_handle,
                'left_peak_price': left_peak_price,
                'cup_bottom_price': cup_bottom_price,
                'right_peak_price': right_peak_price,
                'handle_high': handle_high,
                'handle_low': handle_low,
                'handle_length_days': len(handle_bars)
            },
            reasoning=f"Cup & Handle detected. {', '.join(confidence_factors)}" if is_valid else 
                     f"Cup & Handle incomplete. Confidence: {confidence:.2f}"
        )
    
    # ========================================================================
    # PATRÓN 2: FLAT BASE
    # ========================================================================
    
    def detect_flat_base(self, min_weeks: int = 5, max_weeks: int = 15) -> PatternResult:
        """
        Flat Base: Consolidación lateral tight después de un rally
        
        Criterios:
        - Corrección máxima: 8-15% (muy tight)
        - Duración: 5-15 semanas típicamente
        - Precio debe estar dentro de 15% del high
        - Volumen seco en correcciones
        - Forma rectangular (no U)
        
        Returns:
            PatternResult con detección y características
        """
        if len(self.df) < 25:
            return PatternResult(
                detected=False, pattern_type=PatternType.FLAT_BASE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={}, reasoning="Insufficient data"
            )
        
        # Buscar consolidación reciente (5-15 semanas = 25-75 días)
        min_bars = min_weeks * 5
        max_bars = min(max_weeks * 5, len(self.df))
        
        # Analizar últimos 25-75 días
        base_data = self.df.tail(max_bars)
        current_price = base_data['close'].iloc[-1]
        
        # Encontrar high y low de la base
        base_high = base_data['high'].max()
        base_low = base_data['low'].min()
        
        # Calcular profundidad de la base
        base_depth_pct = (base_high - base_low) / base_high * 100
        
        # Validar que sea "flat" (8-15% máximo)
        if base_depth_pct > 15:
            return PatternResult(
                detected=False, pattern_type=PatternType.FLAT_BASE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=base_depth_pct, base_length=len(base_data),
                characteristics={'base_depth_pct': base_depth_pct},
                reasoning=f"Base too deep: {base_depth_pct:.1f}% > 15%"
            )
        
        if base_depth_pct < 5:
            return PatternResult(
                detected=False, pattern_type=PatternType.FLAT_BASE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=base_depth_pct, base_length=len(base_data),
                characteristics={'base_depth_pct': base_depth_pct},
                reasoning=f"Base too shallow: {base_depth_pct:.1f}% < 5%"
            )
        
        # Validar duración
        if len(base_data) < min_bars:
            return PatternResult(
                detected=False, pattern_type=PatternType.FLAT_BASE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=base_depth_pct, base_length=len(base_data),
                characteristics={'base_depth_pct': base_depth_pct},
                reasoning=f"Base too short: {len(base_data)} days < {min_bars}"
            )
        
        # Validar que el precio esté cerca del high (dentro del top 15% de la base)
        distance_from_high = (base_high - current_price) / base_high * 100
        if distance_from_high > 15:
            return PatternResult(
                detected=False, pattern_type=PatternType.FLAT_BASE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=base_depth_pct, base_length=len(base_data),
                characteristics={
                    'base_depth_pct': base_depth_pct,
                    'distance_from_high_pct': distance_from_high
                },
                reasoning=f"Price too far from high: {distance_from_high:.1f}% > 15%"
            )
        
        # Validar que sea "flat" (no U-shaped)
        # Dividir base en 3 tercios y verificar que los lows no estén en el medio
        third = len(base_data) // 3
        left_third = base_data.iloc[:third]
        middle_third = base_data.iloc[third:2*third]
        right_third = base_data.iloc[2*third:]
        
        left_low = left_third['low'].min()
        middle_low = middle_third['low'].min()
        right_low = right_third['low'].min()
        
        # Si el low está en el medio, es más Cup que Flat
        is_cup_shaped = (middle_low < left_low * 0.98) and (middle_low < right_low * 0.98)
        
        if is_cup_shaped:
            return PatternResult(
                detected=False, pattern_type=PatternType.FLAT_BASE,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=base_depth_pct, base_length=len(base_data),
                characteristics={'base_depth_pct': base_depth_pct},
                reasoning="Pattern is U-shaped (cup), not flat"
            )
        
        # VALIDACIÓN DE VOLUMEN
        avg_volume = base_data['volume'].mean()
        recent_volume = base_data.tail(10)['volume'].mean()
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
        volume_dried_up = volume_ratio < 0.85
        
        # VALIDACIÓN DE TIGHTNESS (últimas barras deben ser tight)
        last_10 = base_data.tail(10)
        recent_range_pct = ((last_10['high'] - last_10['low']) / last_10['low']).mean() * 100
        is_tight = recent_range_pct < 3.0  # Menos de 3% diario
        
        # CALCULAR CONFIANZA
        confidence = 0.0
        confidence_factors = []
        
        # Factor 1: Profundidad ideal (8-12%)
        if 8 <= base_depth_pct <= 12:
            confidence += 0.30
            confidence_factors.append("Optimal depth")
        elif 5 <= base_depth_pct <= 15:
            confidence += 0.15
            confidence_factors.append("Acceptable depth")
        
        # Factor 2: Cerca del high (<5%)
        if distance_from_high < 5:
            confidence += 0.25
            confidence_factors.append("Near highs")
        elif distance_from_high < 10:
            confidence += 0.15
            confidence_factors.append("Close to highs")
        
        # Factor 3: Volumen seco
        if volume_dried_up:
            confidence += 0.20
            confidence_factors.append("Volume dried up")
        
        # Factor 4: Tightness
        if is_tight:
            confidence += 0.15
            confidence_factors.append("Tight action")
        
        # Factor 5: Duración adecuada (7-12 semanas óptimo)
        weeks = len(base_data) / 5
        if 7 <= weeks <= 12:
            confidence += 0.10
            confidence_factors.append("Optimal duration")
        
        is_valid = confidence >= 0.5
        
        # Calcular entry y stop
        pivot_price = base_high
        entry_price = pivot_price + 0.10
        stop_loss = base_low
        
        return PatternResult(
            detected=is_valid,
            pattern_type=PatternType.FLAT_BASE,
            confidence=confidence,
            entry_price=entry_price if is_valid else None,
            stop_loss=stop_loss if is_valid else None,
            pivot_price=pivot_price,
            base_depth=base_depth_pct,
            base_length=len(base_data),
            characteristics={
                'base_depth_pct': base_depth_pct,
                'base_high': base_high,
                'base_low': base_low,
                'distance_from_high_pct': distance_from_high,
                'volume_ratio': volume_ratio,
                'recent_range_pct': recent_range_pct,
                'duration_weeks': weeks
            },
            reasoning=f"Flat Base detected. {', '.join(confidence_factors)}" if is_valid else
                     f"Flat Base incomplete. Confidence: {confidence:.2f}"
        )
    
    # ========================================================================
    # PATRÓN 3: HIGH TIGHT FLAG (continuación en siguiente mensaje)
    # ========================================================================
    
    def detect_high_tight_flag(self, min_gain_pct: float = 90, max_weeks: int = 8) -> PatternResult:
        """
        High Tight Flag: Rally fuerte + consolidación tight
        
        Criterios Mark Minervini:
        - Rally de 90-120%+ en 4-8 semanas
        - Consolidación de 10-25% por 3-5 semanas
        - Extremadamente raro y poderoso
        - Volumen altísimo en el rally
        - Precio sobre todas las MAs
        
        Returns:
            PatternResult con detección y características
        """
        if len(self.df) < 60:
            return PatternResult(
                detected=False, pattern_type=PatternType.HIGH_TIGHT_FLAG,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={}, reasoning="Insufficient data"
            )
        
        # Buscar rally fuerte reciente (últimas 8 semanas = 40 días)
        rally_window = 40
        rally_data = self.df.tail(rally_window)
        
        # Encontrar el low del rally
        rally_low = rally_data['low'].min()
        rally_low_idx = rally_data['low'].idxmin()
        
        # Precio actual
        current_price = rally_data['close'].iloc[-1]
        
        # Calcular ganancia desde el low
        gain_pct = (current_price - rally_low) / rally_low * 100
        
        # Validar ganancia mínima (90%+)
        if gain_pct < min_gain_pct:
            return PatternResult(
                detected=False, pattern_type=PatternType.HIGH_TIGHT_FLAG,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={'gain_pct': gain_pct},
                reasoning=f"Insufficient gain: {gain_pct:.1f}% < {min_gain_pct}%"
            )
        
        # Buscar la consolidación (flag) - últimas 3-5 semanas
        flag_window = min(25, len(rally_data) // 2)
        flag_data = rally_data.tail(flag_window)
        
        if len(flag_data) < 15:  # Mínimo 3 semanas
            return PatternResult(
                detected=False, pattern_type=PatternType.HIGH_TIGHT_FLAG,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={'gain_pct': gain_pct},
                reasoning="Flag not formed yet"
            )
        
        # Calcular profundidad del flag
        flag_high = flag_data['high'].max()
        flag_low = flag_data['low'].min()
        flag_depth_pct = (flag_high - flag_low) / flag_high * 100
        
        # Validar profundidad del flag (10-25% típico)
        if flag_depth_pct < 8 or flag_depth_pct > 30:
            return PatternResult(
                detected=False, pattern_type=PatternType.HIGH_TIGHT_FLAG,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=flag_depth_pct, base_length=len(flag_data),
                characteristics={
                    'gain_pct': gain_pct,
                    'flag_depth_pct': flag_depth_pct
                },
                reasoning=f"Flag depth {flag_depth_pct:.1f}% outside range [8-30%]"
            )
        
        # VALIDACIÓN DE MAs: Precio debe estar sobre TODAS las MAs
        current_bar = rally_data.iloc[-1]
        mas_aligned = (
            current_price > current_bar['sma_10'] and
            current_price > current_bar['sma_20'] and
            current_price > current_bar['sma_50']
        )
        
        if not mas_aligned:
            return PatternResult(
                detected=False, pattern_type=PatternType.HIGH_TIGHT_FLAG,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=flag_depth_pct, base_length=len(flag_data),
                characteristics={
                    'gain_pct': gain_pct,
                    'flag_depth_pct': flag_depth_pct
                },
                reasoning="Price not above all MAs"
            )
        
        # VALIDACIÓN DE VOLUMEN: Rally debe tener volumen masivo
        rally_segment = rally_data.loc[rally_low_idx:]
        avg_volume_rally = rally_segment['volume'].mean()
        avg_volume_base = self.df['volume'].mean()
        volume_expansion = avg_volume_rally / avg_volume_base if avg_volume_base > 0 else 1.0
        
        # Flag debe tener volumen seco
        avg_volume_flag = flag_data['volume'].mean()
        volume_contraction = avg_volume_flag / avg_volume_rally if avg_volume_rally > 0 else 1.0
        
        # VALIDACIÓN DE TIGHTNESS en el flag
        flag_ranges = ((flag_data['high'] - flag_data['low']) / flag_data['low'] * 100).mean()
        is_tight = flag_ranges < 3.0  # Menos de 3% diario
        
        # Distancia del precio al pivot
        distance_to_pivot_pct = (flag_high - current_price) / current_price * 100
        
        # CALCULAR CONFIANZA
        confidence = 0.0
        confidence_factors = []
        
        # Factor 1: Ganancia masiva (90-150%+)
        if gain_pct >= 120:
            confidence += 0.35
            confidence_factors.append(f"Massive rally: {gain_pct:.0f}%")
        elif gain_pct >= 90:
            confidence += 0.25
            confidence_factors.append(f"Strong rally: {gain_pct:.0f}%")
        
        # Factor 2: Flag depth ideal (10-20%)
        if 10 <= flag_depth_pct <= 20:
            confidence += 0.25
            confidence_factors.append("Ideal flag depth")
        elif 8 <= flag_depth_pct <= 25:
            confidence += 0.15
            confidence_factors.append("Acceptable flag depth")
        
        # Factor 3: Volumen expansion en rally
        if volume_expansion > 1.5:
            confidence += 0.15
            confidence_factors.append("Strong volume expansion")
        
        # Factor 4: Volumen contraction en flag
        if volume_contraction < 0.7:
            confidence += 0.15
            confidence_factors.append("Volume dried up in flag")
        
        # Factor 5: Tightness
        if is_tight:
            confidence += 0.10
            confidence_factors.append("Tight flag")
        
        is_valid = confidence >= 0.6  # HTF requiere alta confianza
        
        # Calcular entry y stop
        pivot_price = flag_high
        entry_price = pivot_price + 0.10
        stop_loss = flag_low
        
        return PatternResult(
            detected=is_valid,
            pattern_type=PatternType.HIGH_TIGHT_FLAG,
            confidence=confidence,
            entry_price=entry_price if is_valid else None,
            stop_loss=stop_loss if is_valid else None,
            pivot_price=pivot_price,
            base_depth=flag_depth_pct,
            base_length=len(flag_data),
            characteristics={
                'gain_pct': gain_pct,
                'flag_depth_pct': flag_depth_pct,
                'rally_low': rally_low,
                'flag_high': flag_high,
                'flag_low': flag_low,
                'volume_expansion': volume_expansion,
                'volume_contraction': volume_contraction,
                'flag_tightness': flag_ranges
            },
            reasoning=f"High Tight Flag detected! {', '.join(confidence_factors)}" if is_valid else
                     f"HTF incomplete. Confidence: {confidence:.2f}"
        )
    
    # ========================================================================
    # PATRÓN 4: VCP (Volatility Contraction Pattern)
    # ========================================================================
    
    def detect_vcp(self, min_contractions: int = 2) -> PatternResult:
        """
        VCP: Serie de consolidaciones cada vez más tight
        
        Criterios Mark Minervini:
        - Mínimo 2-4 contracciones sucesivas
        - Cada contracción es más pequeña que la anterior
        - Volumen se reduce en cada contracción
        - T1 > T2 > T3 (depth y duration)
        - Última contracción muy tight (<10%)
        
        Returns:
            PatternResult con detección y características
        """
        if len(self.df) < 60:
            return PatternResult(
                detected=False, pattern_type=PatternType.VCP,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={}, reasoning="Insufficient data"
            )
        
        # Buscar contracciones en los últimos 100 días
        lookback = min(100, len(self.df))
        vcp_data = self.df.tail(lookback)
        
        # Identificar swings (peaks y troughs)
        swings = self._identify_swings(vcp_data)
        
        if len(swings) < 6:  # Necesitamos al menos 3 contracciones (6 swings)
            return PatternResult(
                detected=False, pattern_type=PatternType.VCP,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={}, reasoning="Insufficient swings for VCP"
            )
        
        # Analizar contracciones
        contractions = []
        for i in range(0, len(swings)-1, 2):
            if i+1 >= len(swings):
                break
            
            peak_idx = swings[i]
            trough_idx = swings[i+1]
            
            peak_price = vcp_data.loc[peak_idx, 'high']
            trough_price = vcp_data.loc[trough_idx, 'low']
            
            depth_pct = (peak_price - trough_price) / peak_price * 100
            duration = (trough_idx - peak_idx).days
            
            contractions.append({
                'peak_idx': peak_idx,
                'trough_idx': trough_idx,
                'peak_price': peak_price,
                'trough_price': trough_price,
                'depth_pct': depth_pct,
                'duration': duration
            })
        
        if len(contractions) < min_contractions:
            return PatternResult(
                detected=False, pattern_type=PatternType.VCP,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={'contractions_found': len(contractions)},
                reasoning=f"Only {len(contractions)} contractions found, need {min_contractions}"
            )
        
        # VALIDAR CONTRACCIÓN PROGRESIVA
        # Cada contracción debe ser menor que la anterior
        depths = [c['depth_pct'] for c in contractions]
        is_contracting = all(depths[i] > depths[i+1] for i in range(len(depths)-1))
        
        if not is_contracting:
            return PatternResult(
                detected=False, pattern_type=PatternType.VCP,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={
                    'contractions': contractions,
                    'depths': depths
                },
                reasoning="Contractions not progressively tighter"
            )
        
        # Última contracción debe ser muy tight (<10%)
        last_contraction = contractions[-1]
        if last_contraction['depth_pct'] > 15:
            return PatternResult(
                detected=False, pattern_type=PatternType.VCP,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=last_contraction['depth_pct'],
                base_length=0,
                characteristics={
                    'contractions': contractions,
                    'last_depth': last_contraction['depth_pct']
                },
                reasoning=f"Last contraction too deep: {last_contraction['depth_pct']:.1f}%"
            )
        
        # VALIDACIÓN DE VOLUMEN (debe contraerse)
        volume_ratios = []
        for c in contractions:
            contraction_data = vcp_data.loc[c['peak_idx']:c['trough_idx']]
            avg_vol = contraction_data['volume'].mean()
            volume_ratios.append(avg_vol)
        
        # Normalizar volúmenes
        first_vol = volume_ratios[0] if volume_ratios else 1
        normalized_vols = [v/first_vol for v in volume_ratios]
        
        volume_contracting = all(normalized_vols[i] >= normalized_vols[i+1] 
                                for i in range(len(normalized_vols)-1))
        
        # Precio actual
        current_price = vcp_data['close'].iloc[-1]
        pivot_price = contractions[-1]['peak_price']
        
        # Distancia al pivot
        distance_to_pivot_pct = (pivot_price - current_price) / current_price * 100
        
        # CALCULAR CONFIANZA
        confidence = 0.0
        confidence_factors = []
        
        # Factor 1: Número de contracciones (3-4 es ideal)
        num_contractions = len(contractions)
        if num_contractions >= 3:
            confidence += 0.25
            confidence_factors.append(f"{num_contractions} contractions")
        elif num_contractions >= 2:
            confidence += 0.15
            confidence_factors.append(f"{num_contractions} contractions")
        
        # Factor 2: Contracción progresiva clara
        depth_ratio = depths[0] / depths[-1] if depths[-1] > 0 else 1
        if depth_ratio >= 3:
            confidence += 0.25
            confidence_factors.append("Strong progressive contraction")
        elif depth_ratio >= 2:
            confidence += 0.15
            confidence_factors.append("Good progressive contraction")
        
        # Factor 3: Última contracción muy tight (<8%)
        if last_contraction['depth_pct'] < 8:
            confidence += 0.20
            confidence_factors.append("Very tight final contraction")
        elif last_contraction['depth_pct'] < 12:
            confidence += 0.10
            confidence_factors.append("Tight final contraction")
        
        # Factor 4: Volumen contracting
        if volume_contracting:
            confidence += 0.20
            confidence_factors.append("Volume contracting")
        
        # Factor 5: Cerca del pivot
        if distance_to_pivot_pct < 3:
            confidence += 0.10
            confidence_factors.append("Near pivot")
        
        is_valid = confidence >= 0.5
        
        # Calcular entry y stop
        entry_price = pivot_price + 0.10
        stop_loss = last_contraction['trough_price']
        
        total_base_length = (contractions[-1]['trough_idx'] - contractions[0]['peak_idx']).days
        
        return PatternResult(
            detected=is_valid,
            pattern_type=PatternType.VCP,
            confidence=confidence,
            entry_price=entry_price if is_valid else None,
            stop_loss=stop_loss if is_valid else None,
            pivot_price=pivot_price,
            base_depth=last_contraction['depth_pct'],
            base_length=total_base_length,
            characteristics={
                'num_contractions': num_contractions,
                'contractions': contractions,
                'depths': depths,
                'volume_ratios': normalized_vols,
                'depth_ratio': depth_ratio,
                'last_contraction_depth': last_contraction['depth_pct']
            },
            reasoning=f"VCP detected! {', '.join(confidence_factors)}" if is_valid else
                     f"VCP incomplete. Confidence: {confidence:.2f}"
        )
    
    # ========================================================================
    # POCKET PIVOT
    # ========================================================================
    
    def detect_pocket_pivot(self, lookback_days: int = 10) -> PatternResult:
        """
        Pocket Pivot: Entrada anticipada dentro de una base
        
        Criterios Gil Morales & Chris Kacher:
        - Volumen del día > volumen de TODOS los down days en últimos 10 días
        - Día verde (close > open o close > prev_close)
        - Dentro de una base establecida
        - Precio sobre key MAs (10, 20)
        
        Returns:
            PatternResult con detección y características
        """
        if len(self.df) < lookback_days + 1:
            return PatternResult(
                detected=False, pattern_type=PatternType.POCKET_PIVOT,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={}, reasoning="Insufficient data"
            )
        
        # Analizar últimos días
        recent = self.df.tail(lookback_days + 1)
        current_bar = recent.iloc[-1]
        prior_bars = recent.iloc[:-1]
        
        current_volume = current_bar['volume']
        current_close = current_bar['close']
        current_open = current_bar['open']
        prev_close = prior_bars.iloc[-1]['close']
        
        # Validar que sea día verde
        is_green = (current_close > current_open) or (current_close > prev_close)
        
        if not is_green:
            return PatternResult(
                detected=False, pattern_type=PatternType.POCKET_PIVOT,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={}, reasoning="Not a green day"
            )
        
        # Identificar down days en el lookback
        down_days = prior_bars[prior_bars['close'] < prior_bars['open']]
        
        if len(down_days) == 0:
            # No hay down days para comparar - posiblemente tendencia muy fuerte
            max_down_volume = prior_bars['volume'].mean()
        else:
            max_down_volume = down_days['volume'].max()
        
        # CRITERIO PRINCIPAL: Volumen actual > max volumen de down days
        volume_exceeds_downs = current_volume > max_down_volume
        
        if not volume_exceeds_downs:
            return PatternResult(
                detected=False, pattern_type=PatternType.POCKET_PIVOT,
                confidence=0.0, entry_price=None, stop_loss=None,
                pivot_price=None, base_depth=None, base_length=0,
                characteristics={
                    'current_volume': current_volume,
                    'max_down_volume': max_down_volume
                },
                reasoning="Volume does not exceed down days"
            )
        
        # VALIDACIONES ADICIONALES
        # 1. Precio sobre MAs clave
        above_sma10 = current_close > current_bar['sma_10']
        above_sma20 = current_close > current_bar['sma_20']
        
        # 2. Ganancia del día
        daily_gain_pct = ((current_close - current_open) / current_open * 100) if current_open > 0 else 0
        
        # 3. Relación de volumen
        volume_ratio = current_volume / max_down_volume
        avg_volume = prior_bars['volume'].mean()
        volume_vs_avg = current_volume / avg_volume if avg_volume > 0 else 1
        
        # CALCULAR CONFIANZA
        confidence = 0.0
        confidence_factors = []
        
        # Factor base: Cumple criterio principal
        confidence += 0.30
        confidence_factors.append("Volume > down days")
        
        # Factor 1: Sobre MAs
        if above_sma10 and above_sma20:
            confidence += 0.25
            confidence_factors.append("Above key MAs")
        elif above_sma10 or above_sma20:
            confidence += 0.15
            confidence_factors.append("Above one MA")
        
        # Factor 2: Volumen significativamente mayor
        if volume_ratio >= 2.0:
            confidence += 0.20
            confidence_factors.append(f"Volume {volume_ratio:.1f}x down days")
        elif volume_ratio >= 1.5:
            confidence += 0.10
            confidence_factors.append(f"Volume {volume_ratio:.1f}x down days")
        
        # Factor 3: Ganancia decent del día
        if daily_gain_pct > 2:
            confidence += 0.15
            confidence_factors.append(f"Strong gain: {daily_gain_pct:.1f}%")
        elif daily_gain_pct > 1:
            confidence += 0.10
            confidence_factors.append(f"Good gain: {daily_gain_pct:.1f}%")
        
        is_valid = confidence >= 0.5
        
        # Entry y stop
        pivot_price = current_bar['high']
        entry_price = current_close  # Entrada inmediata al detectar PP
        stop_loss = min(current_bar['low'], current_close * 0.92)  # 8% max
        
        return PatternResult(
            detected=is_valid,
            pattern_type=PatternType.POCKET_PIVOT,
            confidence=confidence,
            entry_price=entry_price if is_valid else None,
            stop_loss=stop_loss if is_valid else None,
            pivot_price=pivot_price,
            base_depth=None,
            base_length=0,
            characteristics={
                'current_volume': current_volume,
                'max_down_volume': max_down_volume,
                'volume_ratio': volume_ratio,
                'volume_vs_avg': volume_vs_avg,
                'daily_gain_pct': daily_gain_pct,
                'above_sma10': above_sma10,
                'above_sma20': above_sma20,
                'num_down_days': len(down_days)
            },
            reasoning=f"Pocket Pivot detected! {', '.join(confidence_factors)}" if is_valid else
                     f"Pocket Pivot weak. Confidence: {confidence:.2f}"
        )
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _identify_swings(self, df: pd.DataFrame, window: int = 5) -> List:
        """
        Identifica swing highs y swing lows
        
        Args:
            df: DataFrame con datos de precio
            window: Ventana para identificar swings
            
        Returns:
            Lista de índices de swings alternando peaks y troughs
        """
        swings = []
        
        for i in range(window, len(df) - window):
            current_high = df['high'].iloc[i]
            current_low = df['low'].iloc[i]
            
            # Verificar si es un swing high (peak)
            left_highs = df['high'].iloc[i-window:i]
            right_highs = df['high'].iloc[i+1:i+window+1]
            
            is_peak = (current_high > left_highs.max()) and (current_high > right_highs.max())
            
            # Verificar si es un swing low (trough)
            left_lows = df['low'].iloc[i-window:i]
            right_lows = df['low'].iloc[i+1:i+window+1]
            
            is_trough = (current_low < left_lows.min()) and (current_low < right_lows.min())
            
            if is_peak or is_trough:
                swings.append(df.index[i])
        
        return swings
    
    def get_best_pattern(self) -> Optional[PatternResult]:
        """
        Obtiene el patrón con mayor confianza
        
        Returns:
            PatternResult del mejor patrón o None si no hay
        """
        patterns = self.scan_all_patterns()
        
        if not patterns:
            return None
        
        return patterns[0]  # Ya están ordenados por confianza


def detect_base_construction(df: pd.DataFrame, 
                              min_base_days: int = 15,
                              atr_period: int = 14) -> dict:
    """
    Detecta construcción de base antes de breakout. (Bloque 6 - PRO)
    
    Criterios:
    - ATR decreciente: compresión de volatilidad.
    - Tight range: el precio oscila en un rango estrecho (<12% total).
    - Volume dry-up: el volumen cae indicando falta de presión vendedora.
    """
    if len(df) < min_base_days + atr_period:
        return {"in_base": False, "reason": "insufficient_data"}
    
    # 1. ATR decreciente = compresión de volatilidad
    # Calculamos ATR manualmente si no existe
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()
    
    atr_recent = atr.iloc[-5:].mean()
    atr_prior = atr.iloc[-20:-5].mean()
    compressing = atr_recent < atr_prior * 0.90 # 10% de compresión mínima
    
    # 2. Rango de precios comprimido en últimos N días
    recent = df.iloc[-min_base_days:]
    price_range = (recent["high"].max() - recent["low"].min()) / recent["close"].mean()
    tight_range = price_range < 0.12  # menos del 12% de rango
    
    # 3. Volume dry-up: volumen reciente < 75% del promedio
    vol_avg20 = df["volume"].iloc[-20:].mean()
    vol_avg5 = df["volume"].iloc[-5:].mean()
    volume_dry = vol_avg5 < vol_avg20 * 0.75
    
    # Pivot = máximo de la base
    pivot = recent["high"].max()
    
    in_base = compressing and tight_range
    base_days = min_base_days if in_base else 0
    
    return {
        "in_base": in_base,
        "base_days": base_days,
        "pivot": round(pivot, 2),
        "volume_dry": volume_dry,
        "near_breakout": in_base and (df["close"].iloc[-1] > pivot * 0.98),
        "atr_compression": round(atr_recent / atr_prior, 2) if atr_prior > 0 else 1.0,
        "price_range_pct": round(price_range * 100, 1),
    }
