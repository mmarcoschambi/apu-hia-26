# Solución: Datos Incorrectos de yFinance

## Problema Identificado

yFinance devuelve datos **ajustados por splits y dividendos** históricos que no reflejan los precios reales de trading. Por ejemplo, para DIS en junio 2018:

### Datos Incorrectos (yFinance ajustados):
```
2018-06-14: Close = 103.33
2018-06-15: Close = 103.42
```

### Datos Correctos (OpenBB sin ajustar):
```
2018-06-14: Close = 108.75
2018-06-15: Close = 108.85
```

## Solución Implementada

### 1. Modificación en `src/data/ticker_cache.py`

Se actualizó el método `get_ohlcv()` para:
- Usar OpenBB cuando `DATA_SOURCE = "openbb"` en settings
- Especificar columnas en INSERT para evitar conflictos con tabla expandida
- Mantener compatibilidad con yfinance como fallback

### 2. Configuración

El sistema ya está configurado en `config/settings.py`:
```python
DATA_SOURCE = "openbb"
OPENBB_PROVIDER = "yfinance"
```

OpenBB con provider "yfinance" usa la API de Yahoo pero sin aplicar ajustes históricos.

## Verificación

```bash
# Test datos correctos
python3 -c "
from src.data.ticker_cache import TickerCache
cache = TickerCache()
df = cache.get_ohlcv('DIS', '2018-06-13', '2018-06-20')
print(df)
cache.close()
"
```

## Cache Existente

El cache actual tiene 12M+ registros con datos incorrectos de yfinance ajustados.

### Opciones:

1. **Regeneración Automática** (Recomendado):
   - Los datos se regenerarán automáticamente cuando se ejecuten backtests
   - No requiere acción manual
   - Los nuevos datos se descargan correctamente de OpenBB

2. **Limpieza Manual** (Opcional):
   ```bash
   # Limpiar cache completo (tarda varios minutos)
   python3 << 'EOF'
   import sqlite3
   conn = sqlite3.connect('data/ticker_cache.db')
   conn.execute('DELETE FROM ohlcv_cache')
   conn.commit()
   conn.close()
   print('Cache limpiado')
   EOF
   ```

3. **Limpieza Selectiva** (Recomendado para testing):
   ```bash
   # Limpiar solo tickers específicos
   python3 << 'EOF'
   import sqlite3
   conn = sqlite3.connect('data/ticker_cache.db')
   tickers = ['DIS', 'AAPL', 'TSLA']  # Agregar tickers necesarios
   for ticker in tickers:
       conn.execute('DELETE FROM ohlcv_cache WHERE ticker = ?', (ticker,))
   conn.commit()
   conn.close()
   print(f'Cache limpiado para {len(tickers)} tickers')
   EOF
   ```

## Impacto

✅ **Backtests futuros**: Usarán datos correctos de OpenBB
✅ **Gráficos Streamlit**: Ya usan datos correctos (por eso se veían bien)
⚠️ **Cache existente**: Contiene datos incorrectos hasta que se regenere

## Limpieza del Cache

Se ha creado un script de utilidad: `clear_corrupted_cache.py`

### Uso:

```bash
# Limpiar ticker específico
python3 clear_corrupted_cache.py DIS AAPL TSLA

# Limpiar y re-descargar con fechas específicas
python3 clear_corrupted_cache.py DIS --refetch --start 2018-01-01 --end 2024-12-31

# Limpiar todo el cache (⚠️ tarda varios minutos)
python3 clear_corrupted_cache.py --all
```

## Próximos Pasos

1. Limpiar cache de tickers que vas a analizar:
   ```bash
   python3 clear_corrupted_cache.py DIS --refetch
   ```

2. Ejecutar backtests - los datos se descargarán automáticamente de OpenBB

3. El dashboard mostrará datos correctos

## Notas Técnicas

- OpenBB con provider "yfinance" descarga precios nominales (sin ajustar)
- Los datos ajustados son útiles para análisis de retornos a largo plazo
- Para trading, se necesitan precios nominales (los correctos)
- El sistema ahora usa precios nominales correctamente
