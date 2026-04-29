Preset "21EMA"
Contexto para el Dev: Este es un filtro personalizado (Custom Screener) para identificar acciones con condiciones específicas de tendencia y volatilidad. Por favor, asegúrate de implementar la siguiente lógica de filtrado exacto en el backend/API.

1. Configuración General de la Búsqueda
Límite de resultados (Limit): 500 (El slider superior marca este límite máximo de acciones a devolver).

Modo de Escaneo: Solo aplicar los filtros seleccionados (checkboxes activados).

2. Condiciones de Filtrado Activas (Cláusula WHERE / Lógica AND)
El sistema debe devolver solo los activos que cumplan todas estas condiciones simultáneamente:

A. Información Básica (Basic Info)

Market Cap (Capitalización de Mercado): Mayor o igual a 1 Billón USD (>= 1,000,000,000).

Volumen Promedio de 50 Días (50d Vol): Mayor o igual a 1 Millón de acciones (>= 1,000,000).

Exclusión de Sector: Se debe excluir el sector Salud. Lógica: Sector != 'Healthcare' (o usar NOT IN ('Healthcare')).

B. Distancia de Medias Móviles (Distance from MA)
(Nota importante para el dev: Los valores tienen un sufijo "(R)". Asegúrate de verificar en la documentación de la API financiera si esta métrica "R" hace referencia a un porcentaje directo, a un valor absoluto en dólares, o a un múltiplo de riesgo como el ATR. Debes programar el cálculo de la distancia basándote en esa métrica).

Distancia a la EMA de 21 días (21EMA Dist): El valor debe estar estrictamente entre -0.50 y 1.00. Lógica: >= -0.50 AND <= 1.00.

Distancia a la SMA de 50 días (50SMA Dist): El valor debe estar estrictamente entre 0.00 y 3.00. Lógica: >= 0.00 AND <= 3.00 (esto implica que el precio actual debe estar igual o por encima de su media móvil de 50 días).

C. Volatilidad (Volatility)

ADR % (Average Daily Range): El valor debe estar estrictamente entre 3.50% y 10.00%. Lógica: >= 3.5 AND <= 10.0.

3. Filtros Inactivos (Ignorar en la consulta)
Para mayor claridad, el desarrollador no debe aplicar condiciones sobre:

Return & Changes % (Daily Ret, Weekly Ret, Chg from Open).

Filter by 21EMA Low Dist.

Filter by 52W High Dist.

Un consejo rápido:
El parámetro de distancia a las medias móviles (EMA y SMA) medido en unidades "(R)" es muy específico de ciertas estrategias de trading. Tu programador probablemente te preguntará qué significa esa "R" matemáticamente para poder calcularlo si la API no lo trae por defecto (por ejemplo, ¿es un porcentaje respecto al precio actual o es un múltiplo ATR?). Es bueno que lo tengas claro para cuando te consulte.
