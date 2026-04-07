Necesitamos implementar un filtro de acciones estilo "Momentum" basado en el proceso de Kristjan Kullamägi (Qullamaggie). El objetivo es encontrar acciones que se estén moviendo rápido, con alta volatilidad diaria y una fuerte tendencia alcista en el último mes.

1. Condiciones de Filtrado Activas (Filtros estrictos / Cláusula WHERE)
El sistema debe devolver solo las acciones que cumplan todas estas condiciones al mismo tiempo (lógica AND):

Precio Mínimo (Price): Estrictamente mayor a $1.00 USD [00:33].

Volumen en Dólares (Dollar Volume): Mayor a $1,500,000 USD (1.5 millones de dólares negociados al día) [00:33].

ADR % (Average Daily Range - Rango Diario Promedio de 20 días): Mayor a 2.2% [00:46]. Nota para el dev: El ADR debe medir la volatilidad intradía en porcentaje, idealmente calculado sobre los últimos 20 días.

Crecimiento de Precio a 1 Mes (1-Month Price Growth / Relative Strength): La acción debe estar en el Top 3% de las acciones con mayor crecimiento en el último mes [02:58]. Nota para el dev: Esto requiere que el backend pueda rankear (percentiles) el universo de acciones según su rendimiento a 30 días.

Intensidad de Tendencia (Trend Intensity): Mayor a 108 [04:53].

2. Requisito Técnico Importante (Para el Dev): "Trend Intensity"
El indicador "Trend Intensity" mencionado requiere una lógica especial. Si la API de datos no lo trae por defecto, debe calcularse así:

Mide la relación entre una Media Móvil rápida (ej. 13 días) y una Media Móvil lenta (ej. 65 días) [03:54].

Un valor de 108 significa que la media móvil rápida está al menos un 8% por encima de la media lenta [04:41].

Lógica matemática sugerida: (MA_13 / MA_65) * 100 > 108.

3. Notas Adicionales de Exclusión
ADRs (American Depositary Receipts): El autor menciona que separa las acciones extranjeras (ADRs) de las estadounidenses en listas distintas [00:15]. El desarrollador debe agregar un filtro para incluir o excluir acciones tipo "ADR" según queramos ver el mercado local de EE.UU. o empresas extranjeras.
