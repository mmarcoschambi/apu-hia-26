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
        """
        try:
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            logger.info(f"Obteniendo datos intradiarios para {symbol} desde {start_date} hasta {end_date}")
            
            # Obtener datos intradiarios usando OpenBB
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