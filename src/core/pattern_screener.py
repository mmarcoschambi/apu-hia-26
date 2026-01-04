"""
Pattern-Based Screener Integration
====================================
Integra el Pattern Detection Engine con el screener institucional
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import logging

from src.indicators.pattern_detection import PatternDetectionEngine, PatternType, PatternResult
from src.core.screener import InstitutionalScreener

logger = logging.getLogger(__name__)


class PatternScreener:
    """
    Screener mejorado con detección de patrones institucionales
    """
    
    def __init__(self, 
                 adr_threshold: float = 1.5,
                 min_price: float = 5.0,
                 min_avg_vol: int = 300000,
                 min_dollar_vol: float = 15000000.0,
                 min_rvol: float = 1.5,
                 enable_patterns: bool = True):
        """
        Args:
            enable_patterns: Si False, solo usa screener básico
        """
        # Screener base
        self.base_screener = InstitutionalScreener(
            adr_threshold=adr_threshold,
            min_price=min_price,
            min_avg_vol=min_avg_vol,
            min_dollar_vol=min_dollar_vol,
            min_rvol=min_rvol
        )
        
        self.enable_patterns = enable_patterns
    
    def scan(self, symbol: str, df: pd.DataFrame, spy_df: pd.DataFrame, 
             date: pd.Timestamp) -> Optional[Dict]:
        """
        Escanea símbolo con detección de patrones
        
        Returns:
            Dict con información de setup + patrón detectado
        """
        # Primero aplicar screener base
        base_result, rejection_reason = self.base_screener.scan_verbose(
            symbol, df, spy_df, date
        )
        
        if not base_result:
            return None
        
        # Si patterns están deshabilitados, retornar resultado base
        if not self.enable_patterns:
            return base_result
        
        # Aplicar Pattern Detection
        try:
            # Preparar datos hasta la fecha actual
            hist_data = df.loc[:date].tail(200)
            
            if len(hist_data) < 50:
                logger.debug(f"{symbol}: Insufficient history for pattern detection")
                return base_result
            
            # Detectar patrones
            engine = PatternDetectionEngine(symbol, hist_data)
            patterns = engine.scan_all_patterns()
            
            if not patterns:
                # No patterns detected - usar resultado base
                base_result['pattern_detected'] = False
                base_result['pattern_type'] = 'SIMPLE_BREAKOUT'
                return base_result
            
            # Usar el mejor patrón (mayor confianza)
            best_pattern = patterns[0]
            
            # Enriquecer resultado con información del patrón
            enriched_result = base_result.copy()
            enriched_result['pattern_detected'] = True
            enriched_result['pattern_type'] = best_pattern.pattern_type.value
            enriched_result['pattern_confidence'] = best_pattern.confidence
            enriched_result['pattern_entry'] = best_pattern.entry_price
            enriched_result['pattern_stop'] = best_pattern.stop_loss
            enriched_result['pattern_pivot'] = best_pattern.pivot_price
            enriched_result['pattern_depth'] = best_pattern.base_depth
            enriched_result['pattern_length'] = best_pattern.base_length
            enriched_result['pattern_characteristics'] = best_pattern.characteristics
            enriched_result['pattern_reasoning'] = best_pattern.reasoning
            
            # Usar entry del patrón si disponible
            if best_pattern.entry_price:
                enriched_result['entry_trigger'] = best_pattern.entry_price
            
            if best_pattern.stop_loss:
                enriched_result['stop_loss'] = best_pattern.stop_loss
            
            logger.info(f"✅ {symbol}: {best_pattern.pattern_type.value} "
                       f"(confidence: {best_pattern.confidence:.2f})")
            
            return enriched_result
            
        except Exception as e:
            logger.error(f"Error in pattern detection for {symbol}: {e}")
            return base_result
    
    def get_pattern_summary(self, symbol: str, df: pd.DataFrame, 
                           date: pd.Timestamp) -> List[PatternResult]:
        """
        Obtiene resumen de todos los patrones detectados
        
        Args:
            symbol: Ticker
            df: DataFrame histórico
            date: Fecha de análisis
            
        Returns:
            Lista de todos los PatternResult detectados
        """
        hist_data = df.loc[:date].tail(200)
        
        if len(hist_data) < 50:
            return []
        
        engine = PatternDetectionEngine(symbol, hist_data)
        patterns = engine.scan_all_patterns()
        
        return patterns


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def scan_watchlist_with_patterns(symbols: List[str], 
                                 start_date: str,
                                 end_date: str,
                                 min_pattern_confidence: float = 0.5) -> pd.DataFrame:
    """
    Escanea watchlist completo con detección de patrones
    
    Args:
        symbols: Lista de símbolos
        start_date: Fecha inicio
        end_date: Fecha fin
        min_pattern_confidence: Confianza mínima para incluir patrón
        
    Returns:
        DataFrame con resultados
    """
    from openbb import obb
    
    results = []
    
    screener = PatternScreener(enable_patterns=True)
    
    # Cargar SPY para relative strength
    try:
        spy_data = obb.equity.price.historical(
            symbol='SPY',
            start_date=start_date,
            provider='yfinance'
        ).to_df()
    except:
        spy_data = pd.DataFrame()
    
    for symbol in symbols:
        try:
            # Cargar datos
            data = obb.equity.price.historical(
                symbol=symbol,
                start_date=start_date,
                provider='yfinance'
            ).to_df()
            
            if data.empty:
                continue
            
            # Escanear última fecha
            last_date = pd.to_datetime(end_date)
            if last_date not in data.index:
                last_date = data.index[-1]
            
            result = screener.scan(symbol, data, spy_data, last_date)
            
            if result and result.get('pattern_detected'):
                pattern_conf = result.get('pattern_confidence', 0)
                if pattern_conf >= min_pattern_confidence:
                    results.append(result)
                    
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            continue
    
    if not results:
        return pd.DataFrame()
    
    df = pd.DataFrame(results)
    
    # Ordenar por confianza de patrón
    if 'pattern_confidence' in df.columns:
        df = df.sort_values('pattern_confidence', ascending=False)
    
    return df


def export_pattern_analysis(symbol: str, df: pd.DataFrame, 
                            output_file: str = 'pattern_analysis.txt'):
    """
    Exporta análisis detallado de patrones a archivo de texto
    
    Args:
        symbol: Ticker
        df: DataFrame con datos históricos
        output_file: Archivo de salida
    """
    engine = PatternDetectionEngine(symbol, df)
    patterns = engine.scan_all_patterns()
    
    with open(output_file, 'w') as f:
        f.write(f"PATTERN ANALYSIS REPORT\n")
        f.write(f"={'='*60}\n")
        f.write(f"Symbol: {symbol}\n")
        f.write(f"Analysis Date: {df.index[-1]}\n")
        f.write(f"Price: ${df['Close'].iloc[-1]:.2f}\n")
        f.write(f"\n")
        
        if not patterns:
            f.write("No institutional patterns detected.\n")
            return
        
        f.write(f"PATTERNS DETECTED: {len(patterns)}\n")
        f.write(f"{'-'*60}\n\n")
        
        for i, pattern in enumerate(patterns, 1):
            f.write(f"{i}. {pattern.pattern_type.value}\n")
            f.write(f"   Confidence: {pattern.confidence:.1%}\n")
            f.write(f"   Reasoning: {pattern.reasoning}\n")
            
            if pattern.entry_price:
                f.write(f"   Entry: ${pattern.entry_price:.2f}\n")
            if pattern.stop_loss:
                f.write(f"   Stop: ${pattern.stop_loss:.2f}\n")
                risk_pct = ((pattern.entry_price - pattern.stop_loss) / pattern.entry_price * 100) if pattern.entry_price else 0
                f.write(f"   Risk: {risk_pct:.1f}%\n")
            
            if pattern.base_depth:
                f.write(f"   Base Depth: {pattern.base_depth:.1f}%\n")
            if pattern.base_length > 0:
                f.write(f"   Base Length: {pattern.base_length} days\n")
            
            # Características específicas del patrón
            if pattern.characteristics:
                f.write(f"   Characteristics:\n")
                for key, value in pattern.characteristics.items():
                    if isinstance(value, (int, float)):
                        if isinstance(value, float):
                            f.write(f"     - {key}: {value:.2f}\n")
                        else:
                            f.write(f"     - {key}: {value}\n")
            
            f.write(f"\n")
    
    logger.info(f"Pattern analysis exported to {output_file}")
