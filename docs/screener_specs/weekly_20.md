Especificación del Screener: "Weekly 20%+ Gainers"
Contexto para el Dev: Necesito implementar un filtro de acciones (Stock Screener) en el sistema. El objetivo es encontrar empresas de alta liquidez que hayan tenido un movimiento alcista fuerte en la última semana. Por favor, asegúrate de que el proveedor de datos de la API financiera que usemos soporte los siguientes parámetros.

1. Condiciones de Filtrado (Filtros estrictos / Cláusula WHERE)
El sistema solo debe devolver acciones que cumplan todas estas condiciones al mismo tiempo (lógica AND):

País / Mercado: Estados Unidos (US).

Bolsas (Exchanges): Filtrado por 3 bolsas (Generalmente NYSE, NASDAQ, y AMEX. Nota para el dev: verificar cuáles 3 usamos por defecto).

Sectores: 19 sectores habilitados (Nota: Esto suele indicar que se incluyen casi todos los sectores. Si hay alguno excluido, por favor avísame para detallarlo).

Precio (Price): Estrictamente mayor a $1 USD (> 1).

Cambio en 1 Semana (Change 1W): Estrictamente mayor al 20% (> 20).

Capitalización de Mercado (Market Cap): Mayor a 1 Billón USD anglosajón, es decir, 1,000,000,000 USD (> 1,000,000,000).

Volumen Promedio de 60 Días (Avg Volume 60D): Mayor a 1 Millón de acciones (> 1,000,000).

ADR (Average Daily Range / Volatilidad diaria): Mayor al 3.5% (> 3.5).

2. Regla de Ordenamiento (Cláusula ORDER BY)
Ordenar por: Columna Change % 1W (Cambio de 1 Semana).

Dirección: Descendente (de mayor a menor ganancia, como indica la flecha hacia abajo en la tabla).

3. Datos a mostrar en la interfaz (Columnas de la tabla / Cláusula SELECT)
Una vez filtrada la lista, la tabla en el frontend debe mostrar las siguientes columnas para cada acción:

Symbol (Ticker de la acción)

Sector

Industry (Industria)

ADR % (Average Daily Range)

Pre-market Chg % (Cambio en el pre-mercado)

Change % (Cambio diario actual)

Change % 1W (Cambio de 1 semana - Columna de ordenamiento principal)

Change % 1M (Cambio de 1 mes)

Rel Volume (Volumen Relativo)

Avg Volume 60D (Volumen promedio de 60 días)

EPS dil growth Quarterly YoY (Crecimiento de beneficio por acción diluido, trimestral interanual)

Revenue growth Quarterly YoY (Crecimiento de ingresos, trimestral interanual)
