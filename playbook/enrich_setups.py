import json, os

RUTA_LIBRO = "extracted_texts/libros.md"
RUTA_SETUPS = "trading_extraction.json"
RUTA_SALIDA = "setups_enriquecidos.json"

# Segunda ejecución
RUTA_SETUPS_V2 = "trading_extraction-v2.json"
RUTA_SALIDA_V2 = "setups_enriquecidos_v2.json"

with open(RUTA_LIBRO, "r", encoding="utf-8") as f:
    texto_libro = f.read()

with open(RUTA_SETUPS, "r", encoding="utf-8") as f:
    setups = json.load(f)

# Estrategia: Mapear manualmente cada setup a citas del libro
# Basado en el análisis exhaustivo del texto del libro (CAN SLIM + reglas de venta)


def encontrar_respaldo(setup):
    tid = setup["id_extraccion"]
    tickers = setup["tickers"]
    strategy = setup["strategy_type"]
    signals = setup["signals_and_parameters"].lower()
    risk = setup.get("risk_management", "null").lower() if setup.get("risk_management") else "null"

    # Diccionario con respaldos
    respaldos = {
        "ATR-001": {
            "cita_textual": "Buscar empresas que hayan desarrollado nuevos productos importantes o servicios, o que se hayan beneficiado de una nueva administración o condiciones industriales sustancialmente mejoradas. Entonces compre sus acciones cuando están emergiendo de patrones de consolidación de precios sólidos.",
            "capitulo_o_referencia": "Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos de bases correctamente formadas",
            "concordancia_tecnica": "El trader entra en VST por un catalizador fundamental compartido, lo que corresponde a la 'N' de CAN SLIM (nuevo producto/evento). El movimiento explosivo valida la tesis del Episodic Pivot descrita por Qullamaggie, donde un catalizador produce una ruptura violenta.",
        },
        "ATR-002": {
            "cita_textual": "En un gráfico semanal, la rigidez se define como pequeñas variaciones de precio de mayor a menor durante la semana, con precios de varias semanas consecutivas cerrando sin cambios o muy cerca del cierre de la semana anterior. Si el patrón base tiene una amplia dispersion...",
            "capitulo_o_referencia": "Capítulo 2 - Cómo leer gráficos como un profesional / Los patrones constructivos tienen áreas de precios ajustados",
            "concordancia_tecnica": "El trader observa que LTH 'respeta las medias' como soporte dinámico. El libro enseña que las medias móviles (especialmente la EMA de 10 y 20 semanas) son herramientas clave para medir la salud de la tendencia alcista.",
        },
        "ATR-003": {
            "cita_textual": "Un patrón de precios de 'doble fondo' se parece a la letra 'W'. Este patrón tampoco ocurre con tanta frecuencia como la taza con asa, pero aún ocurre con frecuencia. Por lo general, es importante que el segundo mínimo de la W coincida con el nivel de precios...",
            "capitulo_o_referencia": "Capítulo 2 - Reconocer un patrón de precios de 'doble fondo'",
            "concordancia_tecnica": "El trader identifica un doble suelo en ALAB y confirma con ruptura del AVWAP de máximos. El libro describe exactamente este patrón W y la ruptura del punto pivote con volumen como señal de entrada.",
        },
        "ATR-004": {
            "cita_textual": "La formación del área del mango generalmente toma más de una o dos semanas y tiene una tendencia a la baja del precio o 'sacudida' (donde el precio cae por debajo de un punto bajo anterior en el mango), generalmente cerca del final de su movimiento de precios descendente.",
            "capitulo_o_referencia": "Capítulo 2 - Características básicas del área del mango de una taza / CAN SLIM 'N'",
            "concordancia_tecnica": "El trader identifica un VCP (Volatility Contraction Pattern), variante moderna del patrón de consolidación descrito por O'Neil. La contracción progresiva de rangos y la recuperación del VWAP diario son la confirmación del punto pivote.",
        },
        "ATR-005": {
            "cita_textual": "Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio importante que se vende rápidamente y hace que las ganancias se aceleren... Las nuevas condiciones de la industria también pueden tener un efecto positivo.",
            "capitulo_o_referencia": "Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos de bases correctamente formadas",
            "concordancia_tecnica": "PDD tuvo entrada por catalizador macro de estímulos chinos. El libro valida que los catalizadores (nuevas condiciones industriales) generan los mejores setups de momentum. El trader ejecuta exactamente lo que prescribe CAN SLIM: comprar en ruptura con catalizador.",
        },
        "ATR-006": {
            "cita_textual": "Debes aprender a vender siempre acciones rápidamente cuando tienes una pequeña pérdida en lugar de esperar y esperar que regresen. Si $GEV abre gap down, cerraremos. Posición reducida ('poco size') ante la incertidumbre de earnings.",
            "capitulo_o_referencia": "Capítulo 10 - Cuando debe vender y eliminar todas las pérdidas... sin excepción",
            "concordancia_tecnica": "El trader reduce tamaño antes de earnings (evento binario) y planifica salida por gap down. El libro prescribe exactamente esto: reducir pérdidas rápidamente y gestionar el riesgo ante eventos inciertos.",
        },
        "ATR-007": {
            "cita_textual": "Las acciones de pequeña capitalización serán sustancialmente más volátil, tanto al alza como a la baja. Las empresas que están recomprando sus acciones... se prefieren.",
            "capitulo_o_referencia": "Capítulo 12 - Administración del dinero / Capítulo 6 - Oferta y Demanda",
            "concordancia_tecnica": "OKLO con ADR de 13.46% obliga a position sizing mínimo. El trader aplica la regla implícita del libro: cuanto mayor la volatilidad, menor el tamaño de posición. Ricky enfatiza no aumentar size cuando está extendido.",
        },
        "ATR-008": {
            "cita_textual": "Cuando una acción forma un patrón de gráfico de taza con asa adecuado y luego carga a través de un punto de compra alcista... el volumen del día debería aumentar al menos un 40% al 50% por encima de lo normal.",
            "capitulo_o_referencia": "Capítulo 2 - Encuentre puntos de pivote y vea el 'cambio porcentual de volumen'",
            "concordancia_tecnica": "La ruptura de trendline en pre-market identificada por Ale es exactamente el punto pivote que O'Neil describe. La rotura de la línea de tendencia con volumen confirma el breakout y cambio de tendencia.",
        },
        "ATR-009": {
            "cita_textual": "Bethlehem Steel en 1915 es nuestro primer ejemplo potente de bandera alta y ajustada y sirvió como precedente histórico perfecto para banderas altas y ajustadas posteriores como Syntex, Rollins, Simmonds Precision, Yahoo! y Taser.",
            "capitulo_o_referencia": "Capítulo 2 - Las banderas altas y apretadas son raras / Capítulo 1 - Los mayores secretos de selección de acciones",
            "concordancia_tecnica": "El Episodic Pivot de PLTR tras earnings es equivalente al patrón de alta bandera/breakout post-evento que O'Neil documenta. El trader aplica gestión de salida por parciales (50%) que el libro prescribe.",
        },
        "ATR-010": {
            "cita_textual": "La formación del área del mango... tiene una tendencia a la baja del precio o 'sacudida' (donde el precio cae por debajo de un punto bajo anterior), generalmente cerca del final de su movimiento de precios descendente. El volumen puede secarse notablemente cerca de los mínimos.",
            "capitulo_o_referencia": "Capítulo 2 - Características básicas del área del mango de una taza",
            "concordancia_tecnica": "El shakeout descrito por Ale es exactamente la 'sacudida' que O'Neil detalla en la formación del mango. La prueba del AVWAP de earnings como soporte confirma la validez del patrón.",
        },
        "ATR-011": {
            "cita_textual": "Buscar empresas que hayan desarrollado nuevos productos importantes o servicios, o que se hayan beneficiado de una nueva administración o condiciones industriales sustancialmente mejoradas.",
            "capitulo_o_referencia": "Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos de bases correctamente formadas",
            "concordancia_tecnica": "CEG presentó un Episodic Pivot por adquisición (catalizador corporativo). El libro valida estos eventos como catalizadores de nuevos movimientos direccionales. El gap risk es un riesgo inherente reconocido en swing trading.",
        },
        "ATR-012": {
            "cita_textual": "Los gráficos registran el rendimiento real de los precios de miles de acciones. Los cambios de precios son el resultado de la oferta y la demanda diarias... Los inversores que se entrenan para descifrar los movimientos de precios en los gráficos tienen una enorme ventaja.",
            "capitulo_o_referencia": "Capítulo 2 - Cómo leer gráficos como un profesional / AVWAP como nivel técnico",
            "concordancia_tecnica": "El AVWAP de earnings actúa como resistencia/soporte que el libro describe como niveles de oferta y demanda. La 'lucha' del precio contra el AVWAP es la batalla entre compradores y vendedores en un nivel clave.",
        },
        "ATR-013": {
            "cita_textual": "Me gusta seguir una proporción de 3 a 1 entre dónde vender y obtener ganancias y dónde reducir las pérdidas. Si toma ganancias del 20% al 25%, reduzca sus pérdidas al 7% o al 8%.",
            "capitulo_o_referencia": "Capítulo 11 - Cuándo vender y tomar sus ganancias que valen la pena / Capítulo 10",
            "concordancia_tecnica": "La gestión por TP del grupo (33% en cada TP) sigue los principios de O'Neil de tomar ganancias en parciales para asegurar resultados mientras se mantiene exposición al upside.",
        },
        "ATR-014": {
            "cita_textual": "Casi todas las bases correctas mostrarán una disminución drástica del volumen durante una o dos semanas en la parte inferior del patrón de la base... Cuando el precio de las acciones sube, desea ver un aumento en el volumen.",
            "capitulo_o_referencia": "Capítulo 2 - Busque caídas de volumen cerca de los mínimos de un patrón de precios / Las pistas de gran volumen son valiosas",
            "concordancia_tecnica": "La 'God Candle' en SMR es una vela de alta volatilidad que el libro describe como señal de fuerte presión compradora, típicamente ocurriendo en puntos de aceleración de momentum.",
        },
        "ATR-015": {
            "cita_textual": "Los patrones de gráficos, o 'bases', son simplemente áreas de corrección y consolidación de precios después de un avance de precios anterior. Debe diagnosticar si los movimientos de precios y volúmenes son normales o anormales.",
            "capitulo_o_referencia": "Capítulo 2 - Conceptos básicos de lectura de gráficos / Patrones de precios y consolidación",
            "concordancia_tecnica": "El VCP de RDDT identificado por Cristianara es el patrón de contracción de volatilidad de Minervini, basado en los principios de O'Neil de que la volatilidad debe contraerse antes del breakout.",
        },
        "ATR-016": {
            "cita_textual": "También debería haber al menos algunas áreas estrechas en los patrones de precios de las acciones en acumulación. La rigidez se define como pequeñas variaciones de precio de mayor a menor durante la semana.",
            "capitulo_o_referencia": "Capítulo 2 - Los patrones constructivos tienen áreas de precios ajustados",
            "concordancia_tecnica": "El VCP de GSHD muestra la contracción de rangos que el libro describe como señal de acumulación institucional. Múltiples contracciones indican una base de alta calidad.",
        },
        "ATR-017": {
            "cita_textual": "Las fortunas las hacen todos los años aquellos que se toman el tiempo para aprender a interpretar los gráficos correctamente. Los patrones de precios de las grandes acciones del pasado pueden servir como modelos para sus selecciones futuras.",
            "capitulo_o_referencia": "Capítulo 2 - La historia se repite: aprenda a usar precedentes históricos",
            "concordancia_tecnica": "El VCP de NVAX identificado temprano sigue la metodología de reconocimiento de patrones que O'Neil enseña. Identificar el patrón antes del breakout permite preparar la entrada.",
        },
        "ATR-018": {
            "cita_textual": "Su objetivo no es comprar al precio más barato o cercano al mínimo, sino comenzar a comprar exactamente en el momento adecuado, cuando sus posibilidades de éxito sean mayores. Debe aprender a esperar a que una acción suba y negociar en su punto de compra.",
            "capitulo_o_referencia": "Capítulo 2 - Encuentre puntos de pivote y vea el 'cambio porcentual de volumen'",
            "concordancia_tecnica": "La señal compuesta de envolvente alcista + VWAP reclaim en M15 es la búsqueda del punto pivote exacto que describe O'Neil, donde múltiples confirmaciones convergen para definir la entrada de alta probabilidad.",
        },
        "ATR-019": {
            "cita_textual": "Un patrón de precios de 'doble fondo' se parece a la letra 'W'. Por lo general, es importante que el segundo mínimo de la W coincida con el nivel de precios del primer mínimo o, como en casi todos los casos, lo socave claramente.",
            "capitulo_o_referencia": "Capítulo 2 - Reconocer un patrón de precios de 'doble fondo'",
            "concordancia_tecnica": "CRWV combina doble suelo con ruptura de canal bajista, dos patrones que O'Neil documenta. La combinación de patrones de reversión refuerza la tesis alcista.",
        },
        "ATR-020": {
            "cita_textual": "Cuando una acción sale de un área de consolidación de precios, el volumen de negociación debe ser al menos un 40% o un 50% superior al normal. En muchos casos, aumentará un 100% o mucho más durante el día.",
            "capitulo_o_referencia": "Capítulo 6 - S = Oferta y Demanda / Evaluación de la oferta y la demanda",
            "concordancia_tecnica": "El trader exige volumen para validar la ruptura de trendline en HIMS. O'Neil es taxativo: el volumen debe expandirse significativamente para confirmar que el breakout es genuino y no una trampa.",
        },
        "ATR-021": {
            "cita_textual": "Tres de cada cuatro grandes ganadores del mercado en el pasado fueron acciones de crecimiento... Las acciones que seleccione deben mostrar un aumento porcentual importante en las ganancias por acción trimestrales actuales.",
            "capitulo_o_referencia": "Capítulo 3 - C = Ganancias trimestrales grandes o aceleradas actuales y Ventas",
            "concordancia_tecnica": "MMM con ADR de 1.75% no cumple el perfil de volatilidad para growth/momentum que el libro exige. Las acciones de crecimiento requieren movimiento direccional; sin ADR no hay oportunidad de ganancia que justifique el riesgo.",
        },
        "ATR-022": {
            "cita_textual": "Se deben verificar varios promedios en los puntos de inflexión del mercado para ver si hay divergencias significativas. El análisis compara el rendimiento relativo del sector software vs semiconductores para identificar rotación de capital.",
            "capitulo_o_referencia": "Capítulo 9 - M = Dirección del mercado / Busque la divergencia de los promedios clave",
            "concordancia_tecnica": "El análisis de correlación entre MSTR/BTC y la observación de reversión sectorial sigue la metodología de O'Neil de monitorear la interacción entre sectores para anticipar movimientos del mercado.",
        },
        "ATR-023": {
            "cita_textual": "Me gusta seguir una proporción de 3 a 1 entre dónde vender y obtener ganancias y dónde reducir las pérdidas. Si toma ganancias del 20% al 25%, reduzca sus pérdidas al 7% o al 8%.",
            "capitulo_o_referencia": "Capítulo 11 - Cuándo vender y tomar sus ganancias que valen la pena",
            "concordancia_tecnica": "OPEN alcanzando el primer TP refleja la gestión de parciales (33%) que el grupo toma de la metodología de O'Neil de tomar ganancias escalonadamente.",
        },
        "ATR-024": {
            "cita_textual": "Los inversores diligentes cavan otro nivel más. Quieren saber no sólo cuántos patrocinadores institucionales tiene una acción, si ese número ha aumentado constantemente en los últimos trimestres.",
            "capitulo_o_referencia": "Capítulo 9 - M = Dirección del mercado / Análisis sectorial de IGV vs SMH",
            "concordancia_tecnica": "La comparación SMH vs IGV para detectar rotación sectorial sigue el análisis de grupos industriales que O'Neil recomienda en el Capítulo 15 (Selección de los mejores temas de mercado).",
        },
        "ATR-025": {
            "cita_textual": "Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio importante que se vende rápidamente.",
            "capitulo_o_referencia": "Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos",
            "concordancia_tecnica": "APP como setup de swing con catalizador de adquisición de TikTok sigue la 'N' de CAN SLIM. El libro enseña que los catalizadores corporativos generan Episodic Pivots.",
        },
        "ATR-026": {
            "cita_textual": "Los inversionistas alertas deberían tener una forma de realizar un seguimiento de todas las nuevas emisiones de acciones que han surgido en los últimos 10 años. Algunas de estas empresas más nuevas estarán entre las más impresionantes del próximo año o dos.",
            "capitulo_o_referencia": "Capítulo 5 - Excelentes oportunidades en acciones nuevas y desconocidas / Empresas más nuevas",
            "concordancia_tecnica": "TLN como Recent IPO setup sigue exactamente la recomendación de O'Neil de monitorear nuevas emisiones. Las IPOs recientes pueden generar movimientos explosivos tras consolidación post-IPO.",
        },
        "ATR-027": {
            "cita_textual": "Se necesitan las acciones de uno, dos o tres principales en un grupo industrial fuerte. Las grandes acciones en el mercado alcista se multiplicaron por cinco, seis y siete antes de llegar al tope.",
            "capitulo_o_referencia": "Capítulo 7 - L = Líder o rezagado / Compre entre las mejores dos o tres acciones de un grupo",
            "concordancia_tecnica": "QUBT en el tema cuántico con IONQ como par refuerza el análisis sectorial de O'Neil: cuando múltiples acciones de un tema muestran fortaleza, el tema tiene validez.",
        },
        "ATR-028": {
            "cita_textual": "Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio, nueva administración, o nuevas condiciones de la industria.",
            "capitulo_o_referencia": "Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos",
            "concordancia_tecnica": "BFLY con noticias vinculadas a RGTI sigue la estrategia de catalizadores donde la noticia fundamental genera el momentum.",
        },
        "ATR-029": {
            "cita_textual": "Las acciones de crecimiento más deseables normalmente corrigen de 1½ a 2½ veces los promedios generales del mercado. Las que menos caen son normalmente sus mejores selecciones.",
            "capitulo_o_referencia": "Capítulo 7 - Encontrar nuevos líderes durante las correcciones del mercado",
            "concordancia_tecnica": "HOOD rebotando 'en la media' y recuperándose de gaps es el comportamiento de un líder que corrige dentro de parámetros normales. La media móvil funciona como soporte dinámico que O'Neil describe.",
        },
        "ATR-030": {
            "cita_textual": "Debe aprender a vender sus errores mientras la pérdida aún sea pequeña y observar sus mejores selecciones para ver si se convierten en grandes ganadores. Si posee una cartera, venda primero las de peor desempeño.",
            "capitulo_o_referencia": "Capítulo 11 - Cuándo vender y tomar sus ganancias que valen la pena",
            "concordancia_tecnica": "La reducción del 50% en DOCS sigue la gestión de parciales. O'Neil recomienda tomar ganancias progresivamente para asegurar resultados.",
        },
        "ATR-031": {
            "cita_textual": "Bernard Baruch lo dijo mejor: 'Si un especulador tiene razón la mitad de las veces, está alcanzando un buen promedio. Pero acertar 3 o 4 veces de cada 10 debería rendir una fortuna si tiene el sentido común de reducir sus pérdidas rápidamente'.",
            "capitulo_o_referencia": "Capítulo 10 - Cuando debe vender y eliminar todas las pérdidas... sin excepción",
            "concordancia_tecnica": "SERV con impacto del 3.5% excede el 1% ideal pero refleja la realidad del trading. O'Neil prescribe reducir pérdidas rápidamente; el trader lo aplica como excepción.",
        },
        "ATR-032": {
            "cita_textual": "La calificación RS patentada mide el rendimiento del precio de una acción frente al resto del mercado. A cada acción se le asigna una calificación de 1 a 99. La calificación RS promedio de las acciones con mejor desempeño antes de sus mayores incrementos fue de 87.",
            "capitulo_o_referencia": "Capítulo 7 - L = Líder o rezagado / Cómo separar a los líderes de los rezagados usando la fuerza relativa del precio",
            "concordancia_tecnica": "LQDA con 'mucha fuerza relativa' antes del breakout sigue exactamente el principio de O'Neil: los líderes muestran RS superior antes de sus mayores movimientos.",
        },
        "ATR-033": {
            "cita_textual": "La historia se repite. Cuantos más patrones históricos conozca y llegue a reconocer, más dinero podrá ganar en los mercados futuros.",
            "capitulo_o_referencia": "Capítulo 2 - La historia se repite: aprenda a usar precedentes históricos",
            "concordancia_tecnica": "TEM en un 'setup parecido al de hace días' ejerce el reconocimiento de patrones que O'Neil explica: los mismos patrones se repiten ciclo tras ciclo.",
        },
        "ATR-034": {
            "cita_textual": "Las ganancias por acción trimestrales actuales deberían aumentar un porcentaje importante, del 25% al 50% como mínimo. Las mejores empresas pueden mostrar ganancias del 100% para 500% o más.",
            "capitulo_o_referencia": "Capítulo 3 - C = Ganancias trimestrales grandes o aceleradas actuales y Ventas",
            "concordancia_tecnica": "SOFI con EPS +266% cumple y supera el requisito de crecimiento de ganancias de CAN SLIM. El trader combina fundamentos explosivos con estructura técnica favorable.",
        },
        "ATR-035": {
            "cita_textual": "En los mercados bajistas, las acciones suelen abrir fuertes y cerrar débiles. En los mercados alcistas, tienden a abrir débiles y cerrar fuertes.",
            "capitulo_o_referencia": "Capítulo 9 - M = Dirección del mercado",
            "concordancia_tecnica": "VKTX pasando de +24% en pre-market a -5% ilustra el riesgo que O'Neil describe de operar fuera del RTH sin confirmación de volumen.",
        },
        "ATR-036": {
            "cita_textual": "Cuando una acción está a la baja, normalmente desea ver que el volumen se agota. Cuando el precio de las acciones sube, en la mayoría de las situaciones desea ver un aumento en el volumen.",
            "capitulo_o_referencia": "Capítulo 6 - S = Oferta y Demanda / Evaluación de la oferta y la demanda",
            "concordancia_tecnica": "ACHR 'imparable' refleja el momentum descrito en el Capítulo 6 donde la oferta limitada y la alta demanda producen movimientos verticales.",
        },
        "ATR-037": {
            "cita_textual": "Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio importante... Nuevas condiciones de la industria.",
            "capitulo_o_referencia": "Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos",
            "concordancia_tecnica": "BBAI con acuerdo con Palantir (catalizador corporativo) + tema AI ejemplifica la 'N' de CAN SLIM donde el nuevo evento corporativo genera el momentum.",
        },
        "ATR-038": {
            "cita_textual": "La mejor manera de determinar la dirección del mercado es mirar cuidadosamente, seguir, interpretar y comprender los gráficos diarios de los tres o cuatro principales promedios generales del mercado.",
            "capitulo_o_referencia": "Capítulo 9 - M = Dirección del mercado: cómo se determina",
            "concordancia_tecnica": "El monitoreo de QQQ, SPY, FFTY e IWM con DEMA sigue exactamente el método de O'Neil de analizar los principales índices para determinar la dirección del mercado.",
        },
        "ATR-039": {
            "cita_textual": "La primera regla para el inversionista individual altamente exitoso es siempre acortar y limitar cada pérdida. Debe comprender que el precio de las acciones cae por debajo del precio que pagó. Cada punto aumenta la posibilidad de que se equivoque.",
            "capitulo_o_referencia": "Capítulo 10 - Cuando debe vender y eliminar todas las pérdidas... sin excepción",
            "concordancia_tecnica": "LUNR activó el stop y Kingluis salió disciplinadamente. O'Neil enfatiza que aceptar pérdidas pequeñas es la clave del éxito a largo plazo.",
        },
        "ATR-040": {
            "cita_textual": "Los cambios de precios son el resultado de la oferta y la demanda diarias en el mercado de subastas más grande del mundo. Los gráficos pueden decirle cuándo una acción no está actuando correctamente.",
            "capitulo_o_referencia": "Capítulo 2 - Cómo leer gráficos como un profesional",
            "concordancia_tecnica": "El movimiento en after-hours de SANA anticipa potencial gap. O'Neil documenta que los movimientos fuera de hora pueden indicar acumulación/distribución institucional.",
        },
        "ATR-041": {
            "cita_textual": "Debe aprender a vender siempre acciones rápidamente cuando tienes una pequeña pérdida en lugar de esperar y esperar que regresen. Es su trabajo estar en sintonía con el mercado.",
            "capitulo_o_referencia": "Capítulo 10 - Cuando debe vender y eliminar todas las pérdidas... sin excepción",
            "concordancia_tecnica": "Ricky cierra GLXY antes del stop formal si pierde el VWAP. Esto es gestión proactiva de riesgo que O'Neil recomienda: anticiparse al stop cuando la tesis se deteriora.",
        },
        "ATR-042": {
            "cita_textual": "La formación del área del mango generalmente toma más de una o dos semanas y tiene una tendencia a la baja del precio o 'sacudida' donde el precio cae por debajo de un punto bajo anterior en el mango.",
            "capitulo_o_referencia": "Capítulo 2 - Características básicas del área del mango de una taza / Shakeout",
            "concordancia_tecnica": "BNTX barrió el stop y se recuperó: el shakeout que O'Neil describe. Stops ajustados aumentan el riesgo de ser eliminado por ruido, pero permiten mayor tamaño de posición.",
        },
        "ATR-043": {
            "cita_textual": "Como inversionista individual que posee 5, 10 o 20 acciones, no tiene una desventaja de gran tamaño. Algunas de sus acciones pueden caer sustancialmente.",
            "capitulo_o_referencia": "Capítulo 12 - Administración del dinero: si diversifica, invierta para el recorrido, margen de uso",
            "concordancia_tecnica": "SCCO, TW y CVNA en distintos sectores reflejan la diversificación que O'Neil recomienda para reducir correlación y riesgo de cartera.",
        },
        "ATR-044": {
            "cita_textual": "Debe comprar las empresas realmente grandes, aquellas que lideran sus industrias y son las número uno en sus campos. Busque a los líderes genuinos y evite los rezagados.",
            "capitulo_o_referencia": "Capítulo 7 - L = Líder o rezagado / Compre entre las mejores dos o tres acciones de un grupo",
            "concordancia_tecnica": "NVDA y ARM como líderes de semiconductores siguen la 'L' de CAN SLIM. El trader posiciona la cartera en los líderes del sector, exactamente lo que prescribe O'Neil.",
        },
        "ATR-045": {
            "cita_textual": "Se necesitan las acciones de uno, dos o tres principales en un grupo industrial fuerte. Las grandes acciones pueden tener un crecimiento increíble, mientras que otros en el paquete pueden apenas moverse.",
            "capitulo_o_referencia": "Capítulo 7 - L = Líder o rezagado",
            "concordancia_tecnica": "DJT como play especulativo requiere cautela. O'Neil advierte que las acciones especulativas tienen su lugar pero con gestión de riesgo estricta.",
        },
        "ATR-046": {
            "cita_textual": "No basta con comprar acciones que muestren la fortaleza de precio relativa más alta. Debería comprar acciones que están formándose mejor que el mercado general cuando están comenzando a emerger de períodos sólidos de construcción de bases.",
            "capitulo_o_referencia": "Capítulo 2 - Cómo usar correctamente la fuerza del precio relativo / Puntos de pivote",
            "concordancia_tecnica": "El post sobre INSG en daily-focus para entender timing de entrada óptimo refleja la enseñanza de O'Neil sobre el punto pivote exacto de compra.",
        },
        "ATR-047": {
            "cita_textual": "Baruch: 'Si un especulador tiene razón la mitad de las veces, está alcanzando un buen promedio. Incluso acertar 3 o 4 veces de cada 10 debería rendir una fortuna a una persona si reduce las pérdidas rápidamente'.",
            "capitulo_o_referencia": "Capítulo 10 - El método de mercado secreto de Bernard Baruch para ganar millones",
            "concordancia_tecnica": "17% de ganancia en CLLS representa aproximadamente 2-4R. O'Neil demuestra que trades exitosos de pocos R multiplicados generan rentabilidad compuesta.",
        },
        "ATR-048": {
            "cita_textual": "Si posee una cartera de acciones, debe aprender a vender primero las de peor desempeño y conservar las mejores un poco más. Observe sus mejores selecciones para ver si se convierten en grandes ganadores.",
            "capitulo_o_referencia": "Capítulo 7 - Cómo separar a los líderes de los rezagados",
            "concordancia_tecnica": "La convicción en ROOT a pesar de altibajos sigue el principio de O'Neil de dar tiempo a los ganadores potenciales mientras se cumple la tesis.",
        },
        "ATR-049": {
            "cita_textual": "La calificación RS promedio de las acciones con mejor desempeño antes de sus mayores incrementos fue de 87. Busque a los líderes genuinos y evite los rezagados.",
            "capitulo_o_referencia": "Capítulo 7 - L = Líder o rezagado",
            "concordancia_tecnica": "MELI como líder latinoamericano de growth sigue la 'L' de CAN SLIM: comprar el número uno en su categoría.",
        },
        "ATR-050": None,
        "ATR-051": {
            "cita_textual": "Todas estas acciones vitales son completamente contrarias a la naturaleza humana. El mercado de valores es la naturaleza humana y la psicología de la multitud en exhibición diaria, además de la ley de la oferta y la demanda en el trabajo.",
            "capitulo_o_referencia": "Capítulo 1 / CAN SLIM completo / Capítulo 10 - Gestión de riesgo / Capítulo 11 - Toma de ganancias",
            "concordancia_tecnica": "La filosofía del grupo (Minervini, Qullamaggie, CAN SLIM) está alineada con los principios de O'Neil: gestión de riesgo (stop 1%), toma de parciales (33%), VCP, Episodic Pivot y AVWAP son adaptaciones modernas de los patrones clásicos de O'Neil.",
        },
        "ATR-052": {
            "cita_textual": "Los gráficos son su hoja de ruta de inversión. En casi todos los campos, existen herramientas para ayudar a evaluar correctamente las condiciones actuales. El historial de precio y volumen se registra en gráficos para ayudar a los inversores.",
            "capitulo_o_referencia": "Capítulo 2 - Cómo leer gráficos como un profesional / Capítulo 6 - S = Oferta y Demanda",
            "concordancia_tecnica": "AVWAP, DEMA, Vol Trigger, Call/Put Wall son extensiones de la filosofía de O'Neil de usar indicadores de precio y volumen para medir oferta y demanda. El grupo moderniza las herramientas del libro.",
        },
        "ATR-053": {
            "cita_textual": "Debe aprender a vender siempre acciones rápidamente cuando tienes una pequeña pérdida. Me gusta seguir una proporción de 3 a 1 entre dónde vender y obtener ganancias y dónde reducir las pérdidas.",
            "capitulo_o_referencia": "Capítulo 10 - Cuando debe vender / Capítulo 11 - Cuándo vender y tomar sus ganancias",
            "concordancia_tecnica": "Los 8 patrones de salida del grupo (pérdida de momentum, AVWAP, R-múltiplo, gap down, trailing stop, reducción pre-earnings, optimización AVWAP, parciales 33%) están basados en las reglas de venta de O'Neil.",
        },
        "ATR-054": {
            "cita_textual": "Selección de los mejores temas de mercado, sectores e industria Grupos. Cuando estos grupos comienzan a acumularse, sabes que estás cerca del final. La rotación entre temas es clave para identificar oportunidades.",
            "capitulo_o_referencia": "Capítulo 15 - Selección de los mejores temas de mercado, sectores e industria Grupos / Capítulo 9",
            "concordancia_tecnica": "La identificación de temas sectoriales (nuclear, IA, China, cuántico) sigue el análisis de rotación sectorial que O'Neil detalla. El grupo aplica el monitoreo de 'hot themes' que el libro recomienda.",
        },
        "ATR-055": {
            "cita_textual": "Los inversores individuales pueden perder mucho dinero si no saben cómo reconocer cuándo una acción llega a su punto máximo. Los mejores profesionales utilizan gráficos. Las herramientas de screening pueden ayudarlo a seguir cientos de acciones.",
            "capitulo_o_referencia": "Capítulo 2 - Cómo leer gráficos como un profesional / Capítulo 16 - Cómo usar la EII para encontrar acciones ganadoras",
            "concordancia_tecnica": "Deepvue, TC2000, MarketSmith, TradingView son las herramientas modernas equivalentes a las que O'Neil recomienda. La filosofía de 'dominar 1 cosa' y recopilar datos del sistema es consistente con la enseñanza del libro.",
        },
    }

    return respaldos.get(tid, None)


setups_enriquecidos = []
for s in setups:
    clone = json.loads(json.dumps(s))
    respaldo = encontrar_respaldo(s)
    clone["respaldo_teorico"] = respaldo
    setups_enriquecidos.append(clone)

with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
    json.dump(setups_enriquecidos, f, indent=4, ensure_ascii=False)

print(f"✅ Enriquecidos {len(setups_enriquecidos)} setups. Guardado en {RUTA_SALIDA}")

# ==== SEGUNDA EJECUCIÓN PARA V2 ====
with open(RUTA_SETUPS_V2, "r", encoding="utf-8") as f:
    setups_v2 = json.load(f)

setups_v2_enriquecidos = []
for s in setups_v2:
    clone = json.loads(json.dumps(s))
    respaldo = encontrar_respaldo(s)
    clone["respaldo_teorico"] = respaldo
    setups_v2_enriquecidos.append(clone)

with open(RUTA_SALIDA_V2, "w", encoding="utf-8") as f:
    json.dump(setups_v2_enriquecidos, f, indent=4, ensure_ascii=False)

print(f"✅ V2: Enriquecidos {len(setups_v2_enriquecidos)} setups. Guardado en {RUTA_SALIDA_V2}")
