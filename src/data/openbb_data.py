from openbb import obb
import pandas as pd
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class OpenBBData:
    """
    Clase para obtener datos de mercado usando OpenBB
    """
    
    def __init__(self):
        self.obb = obb
    
    def get_historical_data(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: Optional[str] = None,
        interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        Obtener datos históricos de un símbolo usando OpenBB
        """
        try:
            if end_date is None:
                end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            
            logger.info(f"Obteniendo datos para {symbol} desde {start_date} hasta {end_date}")
            
            # Obtener datos históricos usando OpenBB
            result = obb.equity.price.historical(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval
            )
            
            if result and hasattr(result, 'to_df'):
                df = result.to_df()
                if not df.empty:
                    # Asegurar que el índice sea datetime
                    df.index = pd.to_datetime(df.index)
                    return df
                else:
                    logger.warning(f"No se encontraron datos para {symbol}")
                    return None
            else:
                logger.warning(f"No se encontraron datos para {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo datos para {symbol}: {str(e)}")
            return None
    
    def get_intraday_data(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: Optional[str] = None,
        interval: str = "5m"
    ) -> Optional[pd.DataFrame]:
        """
        Obtener datos intradiarios de un símbolo usando OpenBB
        Si el intervalo no es soportado nativamente (ej: 5m), se descarga 1m y se resamplea.
        """
        try:
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            logger.info(f"Obteniendo datos intradiarios para {symbol} desde {start_date} hasta {end_date}")
            
            # Determine supported interval and resampling need
            # OpenBB v4+ validation often only supports 1m or 1d for historical
            fetch_interval = interval
            should_resample = False
            
            if interval not in ["1m", "1d"]:
                fetch_interval = "1m"
                should_resample = True
            
            # Obtener datos intradiarios usando OpenBB
            result = obb.equity.price.historical(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=fetch_interval
            )
            
            if result and hasattr(result, 'to_df'):
                df = result.to_df()
                if not df.empty:
                    # Asegurar que el índice sea datetime
                    df.index = pd.to_datetime(df.index)
                    
                    # Resample if needed
                    if should_resample:
                        # Convert interval format (e.g., "5m" -> "5min")
                        # Pandas understands "min" or "T" for minutes
                        resample_rule = interval.replace("m", "min") if "m" in interval else interval
                        
                        # Define aggregation logic
                        agg_dict = {
                            'open': 'first',
                            'high': 'max',
                            'low': 'min',
                            'close': 'last',
                            'volume': 'sum'
                        }
                        # Only include columns that exist
                        agg_dict = {k: v for k, v in agg_dict.items() if k in df.columns}
                        
                        df = df.resample(resample_rule).agg(agg_dict).dropna()

                    return df
                else:
                    logger.warning(f"No se encontraron datos intradiarios para {symbol}")
                    return None
            else:
                logger.warning(f"No se encontraron datos intradiarios para {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo datos intradiarios para {symbol}: {str(e)}")
            return None

    def get_multiple_timeframes(
        self, 
        symbol: str, 
        daily_start: str, 
        intraday_start: str,
        lookback_period: str = "3mo"
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        Obtener datos en múltiples timeframes para un símbolo
        """
        # Datos diarios
        daily_data = self.get_historical_data(
            symbol=symbol,
            start_date=daily_start,
            interval="1d"
        )
        
        # Datos intradiarios
        intraday_data = self.get_intraday_data(
            symbol=symbol,
            start_date=intraday_start,
            interval="5m"
        )
        
        # Datos de lookback para cálculos adicionales
        lookback_data = self.get_historical_data(
            symbol=symbol,
            start_date=self._calculate_lookback_start(lookback_period),
            interval="1d"
        )
        
        return daily_data, intraday_data, lookback_data
    
    def _calculate_lookback_start(self, period: str) -> str:
        """
        Calcular fecha de inicio basada en periodo de lookback
        """
        end_date = datetime.now()
        if period == "1y":
            start_date = end_date - timedelta(days=365)
        elif period == "3mo":
            start_date = end_date - timedelta(days=90)
        elif period == "6mo":
            start_date = end_date - timedelta(days=180)
        else:
            start_date = end_date - timedelta(days=90)  # default a 3 meses
            
        return start_date.strftime('%Y-%m-%d')