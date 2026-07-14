# Manual de Usuario de Trading — Momentum-v2 Playbook

> *Basado en los setups extraídos del canal de trading del grupo y enriquecidos con respaldo teórico de «Cómo ganar dinero en acciones» de William J. O'Neil. Cada setup refleja decisiones reales de traders en tiempo de mercado.*

---

## Filosofía y Marco Operativo del Grupo (ATR-051)

Antes de describir cada setup individual, es imprescindible entender el marco metodológico que los rige. El grupo opera bajo una síntesis de tres escuelas: **CAN SLIM** (William J. O'Neil), **VCP y gestión de riesgo** (Mark Minervini) y **Episodic Pivots** (Kristjan Qullamaggie). Cristianara resume la filosofía operativa: *«Nosotros seguimos la gestión de RISK que hace Minervini o Qullamaggie»*. El horizonte temporal preferido es el swing trading de 3 a 15 días, ajustable según el entorno de mercado.

**Marco de gestión de riesgo:**

- Riesgo máximo del 1% de la cuenta por posición: *«que el stop de la operación no supere el 1% de tu cuenta»* (Cristianara).
- ADR mínimo del 3% como filtro de entrada: *«por eso es mejor buscar ADR mayor a 3»* (Cristianara).
- Cierre de parciales del 33% en cada TP. Sistema de R-múltiplos: salida parcial a 2R, segunda salida a 4R.
- Position sizing calculado en función del stop loss y el ADR: *«El Size se calcula con el SL y el ADR»* (Cristianara).
- No aumentar tamaño cuando el precio está extendido: *«no es correcto aumentar size cuando está extendido, se aumenta size cuando la acción está rompiendo bases»* (Ricky).
- Como alternativa de opciones: LONG CALLS con 30 DTE.
- Salida anticipada si el precio pierde el VWAP antes de que se active el stop formal.
- Trailing stop o stop profit si el precio pierde momentum en H1 y la EMA de 10/20.

O'Neil fundamenta este marco psicológico en el *Capítulo 1*:

> «Todas estas acciones vitales son completamente contrarias a la naturaleza humana. El mercado de valores es la naturaleza humana y la psicología de la multitud en exhibición diaria, además de la ley de la oferta y la demanda en el trabajo.»

---

## Indicadores y Herramientas del Sistema (ATR-052 y ATR-055)

El grupo emplea un conjunto estandarizado de indicadores técnicos y plataformas. Conocer estas herramientas es prerequisito para interpretar correctamente cualquier setup de este manual.

**Indicadores técnicos:**

El **AVWAP** (Anchored VWAP) se ancla en puntos de referencia donde hubo alto volumen: earnings, IPO o máximos relevantes. Pueden usarse múltiples AVWAPs simultáneamente conforme la tendencia madura. La **DEMA** (Double EMA) de 10 y 20 periodos actúa como soporte dinámico de momentum, tal como Qullamaggie la describe. La **EMA 200** filtra la tendencia mayor. El **Vol Trigger** señala expansión de volatilidad de mercado. El **Vol Buzz** de TC2000 detecta volumen anómalo para screening de swings. El **IV Rank** cuantifica la volatilidad implícita en opciones. El **Call Wall / Put Wall** son niveles donde se concentra volumen masivo de opciones call y put, definiendo rangos de mercado.

**Plataformas:** Deepvue (datos fundamentales: EPS, ventas, ranking de industria), TC2000 (Vol Buzz y análisis técnico), Thinkorswim/DAS Pro (ejecución), Briefing.com (catalizadores y noticias), Seeking Alpha (análisis fundamental), MarketSmith IBD (screening CAN SLIM), Tradytics (análisis cuantitativo), TraderSync (journaling), TradingView (AVWAP/VWAP) y Fewmoredays.io (enciclopedia Qullamaggie).


O'Neil enmarca estas herramientas en el *Capítulo 2* y el *Capítulo 16*:

> «Los gráficos son su hoja de ruta de inversión. En casi todos los campos, existen herramientas para ayudar a evaluar correctamente las condiciones actuales. El historial de precio y volumen se registra en gráficos para ayudar a los inversores.»

Cristianara sintetiza el principio de dominio progresivo: *«Aprende primero Swing en largos, hasta que lo domines. Domina 1 sola cosa y le vas metiendo más»*. El grupo también enfatiza auditar el sistema propio con datos reales: win rate, máxima racha de stops consecutivos y stop máximo ajustado al size.

---

## Patrones de Salida del Sistema (ATR-053)

El grupo tiene ocho patrones de salida documentados que operan en paralelo al sistema de entradas:

1. **Pérdida de momentum en H1:** cierre parcial si el precio pierde la EMA de 10/20 en timeframe horario.
2. **Pérdida de AVWAP:** salida progresiva si el precio rompe debajo del AVWAP de referencia.
3. **R-múltiplo:** salida parcial al alcanzar 2R, segunda salida a 4R.
4. **Gap down post-earnings:** cierre total inmediato.
5. **Stop profit / trailing stop:** herramienta de gestión activa de ganancia acumulada.
6. **Reducción pre-earnings:** reducir exposición o cerrar antes de resultados trimestrales.
7. **AVWAP de tendencia como stop dinámico:** usar el AVWAP de tendencia como nivel mínimo de stop.
8. **Parciales al 33% por TP:** regla estándar del grupo.

O'Neil condensa estos principios en el *Capítulo 10* y el *Capítulo 11*:


> «Debe aprender a vender siempre acciones rápidamente cuando tienes una pequeña pérdida. Me gusta seguir una proporción de 3 a 1 entre dónde vender y obtener ganancias y dónde reducir las pérdidas.»

---

## Análisis de Mercado y Rotación Sectorial


### Lectura de los Índices Principales (ATR-038)

El grupo monitorea continuamente cuatro ETFs como termómetro del mercado: **QQQ** (Nasdaq 100), **SPY** (S&P 500), **IWM** (Russell 2000) y **FFTY** (Innovator IBD 50). El FFTY es el proxy directo del universo growth/momentum: cuando está por debajo de la DEMA 10 y cerca de la DEMA 20, la metodología exige reducir exposición. El QQQ testeando la DEMA 10 define el nivel crítico de soporte en el índice líder. Ricky identifica el breakout del IWM como señal de amplitud de mercado positiva.

O'Neil es taxativo en el *Capítulo 9*:

> «La mejor manera de determinar la dirección del mercado es mirar cuidadosamente, seguir, interpretar y comprender los gráficos diarios de los tres o cuatro principales promedios generales del mercado.»

### Rotación Software vs. Semiconductores (ATR-024)


Ricky documenta la correlación entre el sector software (IGV) y el sector semiconductores (SMH): cuando esta correlación se rompe, indica rotación de capital entre sectores. La falta de definición en SMH y AVGO sin confirmación técnica señaló cautela en el sector semi. El análisis de fuerza relativa entre sectores anticipa hacia dónde fluye el capital institucional.

El *Capítulo 9* respalda este análisis:


> «Los inversores diligentes cavan otro nivel más. Quieren saber no sólo cuántos patrocinadores institucionales tiene una acción, si ese número ha aumentado constantemente en los últimos trimestres.»


### Identificación de Temas Sectoriales (ATR-054)

El grupo organiza su watchlist por temas de momentum activos. Los temas identificados durante el período analizado son: energía limpia/nuclear (NNE, SMR, OKLO, CEG, TLN), IA y semiconductores (ALAB, NVDA, ARM, AVGO), China plays (PDD, NIO, JD), computación cuántica (IONQ, QUBT), proxies de crypto (MSTR/BTC), eVTOL (ACHR) y biotech (NVAX, BNTX, SANA). Ricky identifica el tema China como *«HOT theme»* en ese momento, aunque advierte que el catalizador macro por sí solo no fue suficiente para recomendar compras agresivas.

O'Neil documenta este enfoque en el *Capítulo 15*:

> «Selección de los mejores temas de mercado, sectores e industria Grupos. Cuando estos grupos comienzan a acumularse, sabes que estás cerca del final. La rotación entre temas es clave para identificar oportunidades.»

---

## Estrategias de Momentum

### VST — Episodic Pivot por Catalizador Fundamental (ATR-001)

VST presentó un movimiento explosivo descrito como *«explotó VST, se sostuvo»*, clasificado por Ricky como un Episodic Pivot o breakout impulsado por noticias. La entrada se produjo tras la difusión del catalizador en el canal #catalizadores del grupo. Ricky confirma la tesis: *«Si VST viene con catalizador»*. En términos de gestión, no se documentó stop loss específico para este trade; el marco general del grupo aplica: máximo 1% de riesgo por posición y parciales del 33% en cada TP.


O'Neil describe exactamente este tipo de entrada en el *Capítulo 5 — N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos*:

> «Buscar empresas que hayan desarrollado nuevos productos importantes o servicios, o que se hayan beneficiado de una nueva administración o condiciones industriales sustancialmente mejoradas. Entonces compre sus acciones cuando están emergiendo de patrones de consolidación de precios sólidos.»

### LTH — Respeto de Medias Móviles como Soporte Dinámico (ATR-002)

LTH fue destacada en la watchlist diaria por bpo28, quien observó: *«Vaya forma de respetar las medias que ha mostrado»*. El precio mantenía las medias móviles (EMA/SMA) como soporte dinámico, señal de tendencia alcista saludable según la metodología Minervini/Growth. No se especificó gestión de riesgo individual para este setup.

El *Capítulo 2 — Cómo leer gráficos como un profesional* respalda este análisis:

> «En un gráfico semanal, la rigidez se define como pequeñas variaciones de precio de mayor a menor durante la semana, con precios de varias semanas consecutivas cerrando sin cambios o muy cerca del cierre de la semana anterior. Si el patrón base tiene una amplia dispersion...»

### ALAB — Doble Suelo con Ruptura del AVWAP de Máximos (ATR-003)


ALAB (Astera Labs, semiconductores para IA) desarrolló un patrón de doble suelo identificado por kiliaitor: *«Parece que ha hecho un doble suelo y puede romper hacia arriba»*. Cristianara confirmó el setup añadiéndolo a su watchlist. La confirmación de entrada llegó cuando river_trades reportó: *«$ALAB en buen punto de compra, rompiendo el vwap de máximos»*. La doble validación —patrón estructural más ruptura del AVWAP anclado a máximos— define el punto de entrada de alta probabilidad.

El *Capítulo 2 — Reconocer un patrón de precios de doble fondo* documenta este patrón con precisión:

> «Un patrón de precios de 'doble fondo' se parece a la letra 'W'. Este patrón tampoco ocurre con tanta frecuencia como la taza con asa, pero aún ocurre con frecuencia. Por lo general, es importante que el segundo mínimo de la W coincida con el nivel de precios...»

### NNE — VCP con Ruptura del AVWAP de IPO (ATR-004)

NNE (Nano Nuclear Energy, sector uranio) presentó una configuración que Cristianara describió como *«un VCP brutal»* en el gráfico diario. El VCP (Volatility Contraction Pattern) de Minervini implica contracciones progresivas de rango antes de la ruptura. La entrada se ejecutó cuando el precio recuperó el VWAP diario y posteriormente rompió el AVWAP de IPO. bpo28 confirmó la calidad del movimiento: *«De lo poco que vi con volumen duro. Esa NNE y poco más»*. La gestión de riesgo fue ejemplar: Ricky reportó *«NNE que cae un 13% es un 1% de la cuenta»*, demostrando un position sizing inversamente proporcional al ADR del activo.


El *Capítulo 2 — Características básicas del área del mango de una taza* conecta con la lógica del VCP:

> «La formación del área del mango generalmente toma más de una o dos semanas y tiene una tendencia a la baja del precio o 'sacudida' (donde el precio cae por debajo de un punto bajo anterior en el mango), generalmente cerca del final de su movimiento de precios descendente.»

### PDD — Catalizador Macro China con Tolerancia a la Volatilidad (ATR-005)

PDD se posicionó como play de momentum sobre el tema China a partir de un catalizador de estímulos del gobierno chino. Ricky confirmó: *«Por cierto muy buena entrada en $PDD»* y reveló que la tesis se basó en el catalizador enviado en el canal la noche anterior. La gestión de esta posición difiere de un swing estándar: Ricky advirtió que mantenerla meses requiere aceptar la volatilidad inherente al riesgo geopolítico del sector.

El *Capítulo 5 — N = Nuevas condiciones industriales* valida este tipo de entrada:


> «Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio importante que se vende rápidamente y hace que las ganancias se aceleren... Las nuevas condiciones de la industria también pueden tener un efecto positivo.»

### GEV — Gestión Conservadora ante Evento de Earnings (ATR-006)

GEV (GE Vernova) presentó un evento binario de resultados trimestrales. La estrategia del grupo fue mantener únicamente *«poco size»* en la posición, con un plan de salida explícito: *«Si $GEV abre gap down, cerraremos»*. Ale tenía posición activa en GEV desde antes. Esta gestión —reducir tamaño ante eventos inciertos y definir trigger de salida anticipadamente— es el estándar del grupo para gestión de riesgo de earnings.

El *Capítulo 10 — Cuando debe vender y eliminar todas las pérdidas* respalda esta disciplina:

> «Debes aprender a vender siempre acciones rápidamente cuando tienes una pequeña pérdida en lugar de esperar y esperar que regresen.»

### OKLO — Position Sizing por ADR Extremo (ATR-007)

OKLO (energía nuclear) mostró un movimiento de +37% en sesión, con un ADR de 13.46% y un volumen de 26 millones de dólares diarios. Ricky fue explícito sobre el tamaño de posición: *«Después tampoco vas a ir con mucho size en $OKLO que tiene 13,46% de ADR»*. La regla del grupo es clara: el size completo se utiliza únicamente en el punto de ruptura de la base, nunca cuando el precio ya se ha extendido. Ricky lo resume: *«no es correcto aumentar size cuando está extendido, se aumenta size cuando la acción está rompiendo bases»*.

El *Capítulo 12 — Administración del dinero* y el *Capítulo 6 — Oferta y Demanda* respaldan este principio:


> «Las acciones de pequeña capitalización serán sustancialmente más volátil, tanto al alza como a la baja. Las empresas que están recomprando sus acciones... se prefieren.»


### SHOP — Ruptura de Trendline en Pre-Market (ATR-008)

Ale identificó la señal en pre-mercado: *«$SHOP quebrando trendline en pre»*. La rotura de la línea de tendencia bajista con volumen en el pre-market define el punto pivote de entrada. Ale mantuvo la convicción alcista durante la sesión. El tipo de señal —ruptura de trendline— exige confirmación de volumen, aunque en pre-market el volumen es menor y la confirmación definitiva ocurre al abrir la sesión regular.

El *Capítulo 2 — Encuentre puntos de pivote* conecta directamente:

> «Cuando una acción forma un patrón de gráfico de taza con asa adecuado y luego carga a través de un punto de compra alcista... el volumen del día debería aumentar al menos un 40% al 50% por encima de lo normal.»

### PLTR — Episodic Pivot Post-Earnings con Parciales al 50% (ATR-009)

PLTR presentó el caso de Episodic Pivot más documentado del playbook. Ricky clasificó el movimiento directamente: *«$PLTR Episodic»*. Kingluis confirmó el catalizador: *«como que $PLTR reporto bien, esta 11% arriba para el día»*. La gestión de salida fue por parciales: Ale reportó *«cierro el 50 de $PLTR»*, tomando la mitad de la posición en un punto de extensión. En este caso el grupo usó el 50% en lugar del 33% estándar, ajustando la salida a la magnitud del movimiento.

El *Capítulo 2 — Las banderas altas y apretadas son raras* contextualiza históricamente el patrón:

> «Bethlehem Steel en 1915 es nuestro primer ejemplo potente de bandera alta y ajustada y sirvió como precedente histórico perfecto para banderas altas y ajustadas posteriores como Syntex, Rollins, Simmonds Precision, Yahoo! y Taser.»

### ZM — Shakeout con Test del AVWAP de Earnings (ATR-010)

Ale identificó el patrón en ZM: *«$ZM genera un shakeout testeando el avwap de earnings»*. Un shakeout rompe brevemente un soporte para recuperarse rápidamente, limpiando stops débiles. La combinación shakeout + test del AVWAP anclado a earnings define una zona de entrada de alta probabilidad: el precio ha limpiado el papel débil y el AVWAP actúa como soporte de demanda institucional.

O'Neil describe este comportamiento en el *Capítulo 2 — Características básicas del área del mango de una taza*:

> «La formación del área del mango... tiene una tendencia a la baja del precio o 'sacudida' (donde el precio cae por debajo de un punto bajo anterior), generalmente cerca del final de su movimiento de precios descendente. El volumen puede secarse notablemente cerca de los mínimos.»

### CEG — Episodic Pivot por Adquisición y Gap Risk (ATR-011)

CEG (Constellation Energy) generó dos dinámicas distintas. Primero, Ricky lamentó no haber capturado el Episodic Pivot inicial: *«Se me escapó el EP en $CEG»*. Luego, un catalizador de adquisición relanzó el movimiento: *«$CEG ha cerrado una adquisición y viene bastante»*. Ale confirmó la recuperación técnica del VWAP. La lección clave del setup fue el gap risk: Ricky reportó que VST, CRDO y CEG abrieron con gap por debajo de sus stops overnight, generando pérdidas no controladas —riesgo inherente del swing trading con posiciones nocturnas.

El *Capítulo 5 — N = Nuevas condiciones industriales* valida el catalizador de adquisición:

> «Buscar empresas que hayan desarrollado nuevos productos importantes o servicios, o que se hayan beneficiado de una nueva administración o condiciones industriales sustancialmente mejoradas.»

### CROX — AVWAP de Earnings como Zona de Decisión (ATR-012)

Ale identificó que CROX se encontraba *«justo en el AVWAP de los earnings»* y describió al precio como *«luchando con el avwap de earnings»*. Esta lucha del precio contra el AVWAP define una zona de decisión técnica: la superación con cierre por encima confirmaría la continuación alcista; el rechazo invalidaría la tesis. No se detalló gestión de riesgo específica para este setup.


El *Capítulo 2 — Cómo leer gráficos como un profesional* fundamenta el concepto de niveles de oferta y demanda:


> «Los gráficos registran el rendimiento real de los precios de miles de acciones. Los cambios de precios son el resultado de la oferta y la demanda diarias... Los inversores que se entrenan para descifrar los movimientos de precios en los gráficos tienen una enorme ventaja.»

### IONQ — Sistema de TP Escalonados en Computación Cuántica (ATR-013)

IONQ (computación cuántica) alcanzó el primer objetivo de toma de ganancias. Ricky confirmó: *«$IONQ ya nos ha tocado el primer TP!»*. Al alcanzar el primer TP, el sistema del grupo prescribe: cerrar el 33% de la posición y ajustar el stop a breakeven o al siguiente nivel de soporte. IONQ se operó como parte del tema cuántico junto con QUBT, reforzando la tesis sectorial.

El *Capítulo 11 — Cuándo vender y tomar sus ganancias* y el *Capítulo 10* respaldan la gestión escalonada:

> «Me gusta seguir una proporción de 3 a 1 entre dónde vender y obtener ganancias y dónde reducir las pérdidas. Si toma ganancias del 20% al 25%, reduzca sus pérdidas al 7% o al 8%.»

### SMR — God Candle como Señal de Aceleración de Momentum (ATR-014)


SMR (NuScale Power, energía nuclear modular) generó lo que Ricky llamó una *«God Candle»*: una vela de gran tamaño (estructura similar a un marubozu) que señala presión compradora extrema y aceleración del momentum. Este tipo de vela ocurre típicamente tras un catalizador o en el punto de escape de una base. El tema nuclear/energía limpia brindaba el contexto sectorial favorable.

El *Capítulo 2 — Las pistas de gran volumen son valiosas* conecta con este patrón:

> «Casi todas las bases correctas mostrarán una disminución drástica del volumen durante una o dos semanas en la parte inferior del patrón de la base... Cuando el precio de las acciones sube, desea ver un aumento en el volumen.»

### RDDT — VCP de Alta Calidad (ATR-015)

Cristianara identificó el VCP de RDDT con entusiasmo: *«Ese VCP de RDDT ES HERMOSO»*. El Volatility Contraction Pattern de Minervini requiere contracciones progresivas y decrecientes del rango de precio, acompañadas de volumen decreciente, indicando acumulación institucional. La entrada se produce en la ruptura del último punto de contracción con expansión de volumen.

El *Capítulo 2 — Conceptos básicos de lectura de gráficos* fundamenta este patrón:

> «Los patrones de gráficos, o 'bases', son simplemente áreas de corrección y consolidación de precios después de un avance de precios anterior. Debe diagnosticar si los movimientos de precios y volúmenes son normales o anormales.»

### GSHD — VCP Brutal en Base de Acumulación (ATR-016)

GSHD fue descrita por Cristianara como *«también es hermosa, ese VCP es brutal»*. Otro VCP de alta calidad donde la estructura de contracción de volatilidad sugiere acumulación institucional previa al breakout. Las múltiples contracciones sucesivas indican una base de construcción sólida.

El *Capítulo 2 — Los patrones constructivos tienen áreas de precios ajustados* respalda la lectura:

> «También debería haber al menos algunas áreas estrechas en los patrones de precios de las acciones en acumulación. La rigidez se define como pequeñas variaciones de precio de mayor a menor durante la semana.»

### NVAX — VCP Identificado Temprano en Sesión (ATR-017)

Cristianara identificó el VCP de NVAX (Novavax) *«temprano»* en la sesión: *«NVAX la mandé temprano, lindo VCP»*. La ventaja de identificar el patrón antes de la ruptura es la posibilidad de preparar la entrada, calcular el riesgo exacto y dimensionar correctamente la posición antes de que el precio se mueva.


El *Capítulo 2 — La historia se repite* contextualiza el reconocimiento anticipado de patrones:

> «Las fortunas las hacen todos los años aquellos que se toman el tiempo para aprender a interpretar los gráficos correctamente. Los patrones de precios de las grandes acciones del pasado pueden servir como modelos para sus selecciones futuras.»

### XYZ — Envolvente Alcista en M15 con VWAP Reclaim (ATR-018)

Ale describió este setup intradía compuesto: *«Si $XYZ deja envolvente en M15 junto con el vwap reclaim, me parece una buena posición»*. Dos confirmaciones simultáneas: (1) patrón de vela envolvente alcista en timeframe de 15 minutos y (2) VWAP Reclaim —recuperación del precio por encima del VWAP. La convergencia de ambas señales define el punto de entrada, con el stop colocado bajo el VWAP recién recuperado para optimizar el ratio riesgo/beneficio.

El *Capítulo 2 — Encuentre puntos de pivote* respalda la búsqueda de la entrada óptima:

> «Su objetivo no es comprar al precio más barato o cercano al mínimo, sino comenzar a comprar exactamente en el momento adecuado, cuando sus posibilidades de éxito sean mayores. Debe aprender a esperar a que una acción suba y negociar en su punto de compra.»

### CRWV — Doble Suelo con Ruptura de Canal Bajista (ATR-019)


morae_0 articuló la tesis: *«CRWV puede tener una explosión de amplitud; marcó doble suelo hoy y rompió canal bajista»*. El setup combinó dos patrones de reversión: el doble suelo como patrón de cambio de tendencia y la ruptura del canal bajista como confirmación directional. La coincidencia de ambos patrones refuerza significativamente la probabilidad del movimiento alcista.

El *Capítulo 2 — Reconocer un patrón de precios de doble fondo* describe el patrón W:

> «Un patrón de precios de 'doble fondo' se parece a la letra 'W'. Por lo general, es importante que el segundo mínimo de la W coincida con el nivel de precios del primer mínimo o, como en casi todos los casos, lo socave claramente.»

### HIMS — Ruptura de Trendline con Exigencia de Volumen (ATR-020)

river_trades condicionó la entrada a HIMS a una doble confirmación: *«Si HIMS rompe el trendline con volumen quizá le entre»*. La ruptura de la línea de tendencia bajista es la señal técnica; el volumen por encima de la media es la validación. Sin expansión de volumen, la ruptura no se ejecuta. Esta disciplina evita señales falsas y entradas en trampas alcistas.

El *Capítulo 6 — S = Oferta y Demanda* es taxativo:

> «Cuando una acción sale de un área de consolidación de precios, el volumen de negociación debe ser al menos un 40% o un 50% superior al normal. En muchos casos, aumentará un 100% o mucho más durante el día.»

### MSTR / BTC — Proxy Crypto y Gestión de Volatilidad Extrema (ATR-022)

Ale documentó la correlación entre MSTR y Bitcoin: *«$MSTR se había adelantado a la suba de $BTC hasta más arriba de que ATH»*, lo que convirtió a MSTR en un proxy adelantado de Bitcoin. La reversión posterior fue severa: -40% desde máximos. Ricky señaló la correlación sectorial en la corrección: MSTR, CORZ, WULF cayeron juntos con SOFI y TSLA. El sector cripto exige gestión de tamaño conservadora dado el riesgo de volatilidad extrema.


El *Capítulo 9 — M = Dirección del mercado* respalda el análisis de correlaciones:


> «Se deben verificar varios promedios en los puntos de inflexión del mercado para ver si hay divergencias significativas.»


### OPEN — Setup Bien Temporizado con TP Alcanzado Rápidamente (ATR-023)

Ricky reportó: *«Entramos en $OPEN en la comunidad privada y ya cerca del 1er TP»*. La velocidad con la que el precio se aproximó al primer objetivo indica un setup bien temporizado donde la entrada coincidió con el inicio del movimiento. La gestión sigue la regla estándar: posición dividida en tercios, cerrar el primero al alcanzar el primer TP.

El *Capítulo 11 — Cuándo vender y tomar sus ganancias* respalda las salidas escalonadas:

> «Me gusta seguir una proporción de 3 a 1 entre dónde vender y obtener ganancias y dónde reducir las pérdidas. Si toma ganancias del 20% al 25%, reduzca sus pérdidas al 7% o al 8%.»

### APP — Setup de Swing con Catalizador de Adquisición (ATR-025)

Ricky identificó APP (AppLovin) como *«un buen setup para swing»*. Sin embargo, la ejecución no funcionó: *«$APP termina cerrando -»*. Posteriormente, Cristianara añadió una capa fundamental: el interés de APP en adquirir TikTok, un catalizador corporativo que podría generar un nuevo Episodic Pivot en el futuro. Este setup ilustra que incluso setups técnicamente válidos pueden fallar, y que los catalizadores corporativos pueden reactivar una tesis.

El *Capítulo 5 — N = Nuevas condiciones* contextualiza el catalizador:

> «Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio importante que se vende rápidamente.»


### TLN — Recent IPO Setup (ATR-026)

TLN (Talen Energy) fue presentado por Ricky como un estudio de caso de Recent IPO: *«Revisar el estudio de $TLN Recent IPO en #daily-focus no tiene mala pinta»*. Las Recent IPOs son acciones recién listadas que, tras un período de consolidación post-IPO, pueden generar movimientos explosivos cuando fundamentos fuertes se alinean con una estructura técnica correcta.

El *Capítulo 5 — Excelentes oportunidades en acciones nuevas* es explícito:

> «Los inversionistas alertas deberían tener una forma de realizar un seguimiento de todas las nuevas emisiones de acciones que han surgido en los últimos 10 años. Algunas de estas empresas más nuevas estarán entre las más impresionantes del próximo año o dos.»


### QUBT — Liderazgo en el Tema de Computación Cuántica (ATR-027)

QUBT (Quantum Computing) fue señalado por Ricky como *«una muy buena oportunidad»* dentro del tema cuántico. Eltradino también seguía el ticker. La clave del setup es sectorial: cuando QUBT e IONQ muestran fortaleza simultánea, el tema tiene validez como grupo, lo que reduce el riesgo de que el movimiento sea específico a un solo ticker.

El *Capítulo 7 — L = Líder o rezagado* respalda el análisis de grupo:

> «Se necesitan las acciones de uno, dos o tres principales en un grupo industrial fuerte. Las grandes acciones en el mercado alcista se multiplicaron por cinco, seis y siete antes de llegar al tope.»

### BFLY — Catalizador por Asociación Sectorial (ATR-028)


BFLY fue compartido por Eltradino como idea de trading. Ricky vinculó el setup con un catalizador de noticias del sector: *«Si, tiene noticia hoy $RGTI»*, utilizando la correlación dentro del tema para reforzar la tesis. La noticia fundamental de un ticker relacionado puede actuar como catalizador indirecto para otros del mismo sector.

El *Capítulo 5 — N = Nuevas condiciones de la industria* fundamenta este enfoque:

> «Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio, nueva administración, o nuevas condiciones de la industria.»

### HOOD — Rebote en Media Móvil con Gap Risk Documentado (ATR-029)

HOOD (Robinhood) generó múltiples dinámicas durante el período. Ricky reportó una caída de -8% en posición abierta: *«La cartera seguirá estando en máximos $HOOD cayendo un -8% ahora»*. darksalsa identificó la oportunidad de rebote: *«buen rebote de $HOOD en la media»*, usando la media móvil como soporte dinámico de entrada. Posteriormente, un gap de -7% after-hours por exclusión del S&P 500 demostró el gap risk en acciones de esta naturaleza. HOOD se recuperó finalmente con un +7.38%.

El *Capítulo 7 — Encontrar nuevos líderes durante las correcciones del mercado* respalda el rebote en media:

> «Las acciones de crecimiento más deseables normalmente corrigen de 1½ a 2½ veces los promedios generales del mercado. Las que menos caen son normalmente sus mejores selecciones.»

### DOCS — Reducción de 50% en Posición Extendida (ATR-030)


Ale reportó la gestión activa de DOCS (Doximity): *«Reduzco 50% en $DOCS»*. El cierre del 50% en lugar del 33% estándar indica que el precio se había extendido significativamente o que el trader evaluó mayor cautela en ese momento. Esta flexibilidad en el porcentaje de parciales es parte de la gestión activa: la regla del 33% es la base, pero puede ajustarse según el contexto del precio.

El *Capítulo 11 — Cuándo vender y tomar sus ganancias* respalda la toma progresiva de beneficios:

> «Debe aprender a vender sus errores mientras la pérdida aún sea pequeña y observar sus mejores selecciones para ver si se convierten en grandes ganadores. Si posee una cartera, venda primero las de peor desempeño.»

### SERV — Excepción al 1% de Riesgo por Posición (ATR-031)


SERV generó un impacto del 3.5% de la cuenta, por encima del 1% objetivo del grupo. Ricky lo documentó como excepción o caso de estudio: la combinación de ADR alto con un ajuste de position sizing imperfecto amplió el impacto. La lección es que el cálculo del size debe ser riguroso en cada operación, especialmente en tickers de alta volatilidad. El marco del grupo establece el 1% como máximo; cualquier desvío debe ser consciente y justificado.

El *Capítulo 10* cita a Bernard Baruch en un principio aplicable directamente a este caso:

> «Bernard Baruch lo dijo mejor: 'Si un especulador tiene razón la mitad de las veces, está alcanzando un buen promedio. Pero acertar 3 o 4 veces de cada 10 debería rendir una fortuna si tiene el sentido común de reducir sus pérdidas rápidamente'.»

### LQDA — Fuerza Relativa como Precursor del Breakout (ATR-032)

darksalsa articuló la tesis de LQDA con claridad: *«Me gusta $LQDA, a ver si deja un buen breakout hoy. Ha estado mostrando mucha fuerza relativa»*. La fuerza relativa —outperformance del precio de LQDA respecto al mercado general— es el indicador adelantado. Los líderes del mercado muestran RS superior antes de sus mayores movimientos, cuando el mercado general aún no ha confirmado la dirección.

El *Capítulo 7 — L = Líder o rezagado* describe el indicador RS:


> «La calificación RS patentada mide el rendimiento del precio de una acción frente al resto del mercado. A cada acción se le asigna una calificación de 1 a 99. La calificación RS promedio de las acciones con mejor desempeño antes de sus mayores incrementos fue de 87.»

### TEM — Reconocimiento de Patrón Repetido (ATR-033)

Ricky identificó TEM señalando: *«$TEM está en un setup parecido al de hace días en otro activo»*. El reconocimiento de patrones recurrentes —la misma estructura técnica en distintos tickers o momentos— es parte central de la metodología cuantitativa del grupo. Identificar el patrón antes de la ruptura permite preparar la entrada con antelación.

El *Capítulo 2 — La historia se repite* fundamenta este enfoque:

> «La historia se repite. Cuantos más patrones históricos conozca y llegue a reconocer, más dinero podrá ganar en los mercados futuros.»

### SOFI — EPS +266% como Catalizador de Growth Investing (ATR-034)

Ricky describió SOFI con entusiasmo: *«$SOFI es buenísima y encima viene con unos resultados explosivos EPS +266% Sales crecimiento»*. Un crecimiento de ganancias del 266% supera con creces el umbral mínimo de CAN SLIM. La estructura técnica favorable más el catalizador fundamental explosivo definen el setup ideal de growth investing. Ale reportó una corrección posterior: *«Le dieron duro a $SOFI»*, ilustrando que incluso con fundamentos sólidos el timing de salida es crítico.


El *Capítulo 3 — C = Ganancias trimestrales grandes* establece el estándar:

> «Las ganancias por acción trimestrales actuales deberían aumentar un porcentaje importante, del 25% al 50% como mínimo. Las mejores empresas pueden mostrar ganancias del 100% para 500% o más.»

### VKTX — Reversión de Pre-Market: Riesgo de Entrar Fuera del RTH (ATR-035)


VKTX ilustró uno de los riesgos más documentados del pre-market: Ricky reportó *«+24% arriba $VKTX»* en pre-mercado, seguido de *«$VKTX de llegar a estar un +24 en pre market a caer un -5%»* al abrir el mercado regular. La reversión extrema de +24% a -5% demuestra que los movimientos de pre-market no tienen confirmación de volumen ni liquidez suficiente. La metodología del grupo prioriza entradas durante RTH.

El *Capítulo 9 — M = Dirección del mercado* contextualiza este comportamiento:

> «En los mercados bajistas, las acciones suelen abrir fuertes y cerrar débiles. En los mercados alcistas, tienden a abrir débiles y cerrar fuertes.»

### ACHR — Momentum Imparable en el Tema eVTOL (ATR-036)

ACHR (Archer Aviation, eVTOL) fue seguido por Eltradino desde el inicio del tema sectorial: *«os acordáis de la que comenté de EVTOL? $ACHR»*. El momentum fue tan fuerte que el trader reportó: *«$ACHR imparable, no me deja salir/vender»*, señal de aceleración vertical donde la demanda supera cualquier intento de salida parcial. Posteriormente, Ricky incluyó ACHR en la lista de tickers afectados negativamente por earnings.

El *Capítulo 6 — S = Oferta y Demanda* describe este fenómeno:

> «Cuando una acción está a la baja, normalmente desea ver que el volumen se agota. Cuando el precio de las acciones sube, en la mayoría de las situaciones desea ver un aumento en el volumen.»

### BBAI — Acuerdo Corporativo con Palantir en el Tema AI (ATR-037)


kriptopepino identificó la tesis: *«$BBAI empresa de AI ha firmado un acuerdo con PALANTIR y lleva momentum»*. El acuerdo corporativo con Palantir —un líder reconocido en el sector— genera sinergia y validación del negocio de BBAI. La combinación de catalizador corporativo específico más contexto sectorial de IA define el setup.


El *Capítulo 5 — N = Nuevas condiciones de la industria* valida el catalizador:

> «Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio importante... Nuevas condiciones de la industria.»

### LUNR — Ejecución Disciplinada del Stop Loss (ATR-039)

Kingluis reportó la salida sin ambigüedad: *«$LUNR me saco en el primer SL»*. El setup falló y el stop loss se ejecutó en el primer nivel predefinido, protegiendo el capital. Esta ejecución disciplinada —sin esperar una recuperación que puede no llegar— es el pilar de la metodología del grupo. Aceptar pérdidas pequeñas rápidamente es parte del sistema, no una excepción.

El *Capítulo 10 — Cuando debe vender y eliminar todas las pérdidas* es la regla más citada del libro:

> «La primera regla para el inversionista individual altamente exitoso es siempre acortar y limitar cada pérdida. Debe comprender que el precio de las acciones cae por debajo del precio que pagó. Cada punto aumenta la posibilidad de que se equivoque.»

### SANA — Movimiento en After-Hours como Anticipación de Gap (ATR-040)

boy__plunger reportó: *«Buen after de $SANA»* para SANA (Sana Biotechnology). Los movimientos significativos en after-hours pueden anticipar gaps alcistas al abrir la sesión siguiente y generar oportunidades de Episodic Pivot. El monitoreo del after-hours forma parte del proceso de preparación diaria del grupo.

El *Capítulo 2 — Cómo leer gráficos como un profesional* fundamenta la lectura de estos movimientos:

> «Los cambios de precios son el resultado de la oferta y la demanda diarias en el mercado de subastas más grande del mundo. Los gráficos pueden decirle cuándo una acción no está actuando correctamente.»

### GLXY — Salida Anticipada por Pérdida del VWAP (ATR-041)

Ricky documentó su gestión proactiva de GLXY: *«GLXY la estoy vigilando, igual cierro antes del stop si veo que no termina de aguantar el vwap»*. El VWAP funciona aquí como indicador de salida dinámico: si el precio no sostiene el VWAP como soporte, la tesis del trade se deteriora y el trader cierra la posición antes de que el stop loss formal sea alcanzado. Esta técnica reduce pérdidas al anticipar el deterioro de la acción del precio.

El *Capítulo 10* respalda esta gestión proactiva:


> «Debe aprender a vender siempre acciones rápidamente cuando tienes una pequeña pérdida en lugar de esperar y esperar que regresen. Es su trabajo estar en sintonía con el mercado.»

### BNTX — Stop Sweep: La Disyuntiva del Stop Ajustado (ATR-042)

panxo documentó la frustración del stop sweep: *«BNTX barrió mi stop y luego se recuperó, esto AM»*. El precio rompió el stop loss para recuperarse inmediatamente, generando una pérdida realizada evitable con un stop más amplio. Cristianara contextualizó la metodología de stops ajustados: *«Él busca stops más ajustados, lo que implica que la acción necesita moverse un menor porcentaje para alcanzar el target»*. Stops ajustados permiten mayor tamaño de posición y mejor ratio riesgo/beneficio, pero incrementan la probabilidad de ser eliminated por ruido de mercado.

El *Capítulo 2 — Características básicas del área del mango de una taza* describe exactamente el shakeout:

> «La formación del área del mango generalmente toma más de una o dos semanas y tiene una tendencia a la baja del precio o 'sacudida' donde el precio cae por debajo de un punto bajo anterior en el mango.»

### SCCO / TW / CVNA — Diversificación por Sectores en Cartera (ATR-043)

Ale mencionó sus posiciones activas: *«$SCCO $TW $CVNA llevo yo»*. TW fue descrita como *«Hermosa»*. CVNA (Carvana) es un clásico de growth/momentum. La distribución entre sectores distintos —materiales básicos (SCCO), servicios financieros (TW) y comercio electrónico/autos (CVNA)— reduce la correlación de la cartera y el riesgo de que un evento sectorial afecte todas las posiciones simultáneamente.


El *Capítulo 12 — Administración del dinero* respalda la diversificación controlada:


> «Como inversionista individual que posee 5, 10 o 20 acciones, no tiene una desventaja de gran tamaño. Algunas de sus acciones pueden caer sustancialmente.»

### NVDA / ARM — Posicionamiento en los Líderes de Semiconductores (ATR-044)

Ricky ejecutó la tesis sectorial con precisión: *«nos hemos posicionado en $NVDA $ARM con la estructura correcta»*. ARM mostró liderazgo relativo con un +3.5% antes que NVDA. La confirmación llegó con: *«$ARM volando»*, señalando aceleración del momentum en el líder relativo. Posicionar en los dos líderes del sector maximiza la exposición al tema con gestión controlada.


El *Capítulo 7 — L = Líder o rezagado* prescribe exactamente esto:

> «Debe comprar las empresas realmente grandes, aquellas que lideran sus industrias y son las número uno en sus campos. Busque a los líderes genuinos y evite los rezagados.»

### DJT — Play Especulativo con Cautela de Tamaño (ATR-045)

Ricky observó: *«También hay que observar $DJT Trump Media & Technology como posible play»*. DJT es un play de momentum político/especulativo cuya naturaleza exige una gestión de tamaño más conservadora que los setups técnicos estándar. El seguimiento fue observacional, priorizando la cautela.

El *Capítulo 7 — L = Líder o rezagado* advierte sobre el perfil de estos activos:

> «Se necesitan las acciones de uno, dos o tres principales en un grupo industrial fuerte. Las grandes acciones pueden tener un crecimiento increíble, mientras que otros en el paquete pueden apenas moverse.»

### INSG — Caso de Estudio para el Timing de Entrada Óptimo (ATR-046)

Ricky recomendó: *«Recomiendo leer el post sobre $INSG en #daily-focus para entender cuando es óptimo entrar en una posición»*. INSG funciona como caso de estudio pedagógico sobre el punto pivote exacto de entrada, posiblemente vinculado a un breakout de base o a un pullback técnico al soporte.

El *Capítulo 2 — Cómo usar correctamente la fuerza del precio relativo* define el concepto:

> «No basta con comprar acciones que muestren la fortaleza de precio relativa más alta. Debería comprar acciones que están formándose mejor que el mercado general cuando están comenzando a emerger de períodos sólidos de construcción de bases.»


### CLLS — Ganancia del 17% en Swing Trade (ATR-047)

Ricky reportó un resultado concreto: *«Ya sacándole un 17% a $CLLS»*. Una ganancia del 17% representa aproximadamente 2 a 4R dependiendo del stop loss utilizado, lo que ilustra cómo un sistema con pérdidas promedio pequeñas y ganancias de múltiplos de R genera rentabilidad compuesta sostenible.

El *Capítulo 10 — El método de Bernard Baruch* fundamenta la matemática del sistema:

> «Baruch: 'Si un especulador tiene razón la mitad de las veces, está alcanzando un buen promedio. Incluso acertar 3 o 4 veces de cada 10 debería rendir una fortuna a una persona si reduce las pérdidas rápidamente'.»


### ROOT — Convicción en la Tesis de Largo Plazo (ATR-048)


ron_smt expresó convicción sobre ROOT (Root Inc., insurtech): *«Siempre te tuve fe $ROOT»*. La posición fue mantenida a pesar de altibajos, con la tesis de que los fundamentos o la estructura técnica la respaldaban. Esta actitud —dar tiempo a los ganadores potenciales— se contrasta con la disciplina de cortar los perdedores rápido.

El *Capítulo 7 — Cómo separar a los líderes de los rezagados* establece el criterio:

> «Si posee una cartera de acciones, debe aprender a vender primero las de peor desempeño y conservar las mejores un poco más. Observe sus mejores selecciones para ver si se convierten en grandes ganadores.»

### MELI — Líder Latinoamericano de Growth (ATR-049)


MELI (MercadoLibre) fue referenciado en el contexto de discusión general como ticker de referencia de growth. Como líder latinoamericano en su categoría, cumple la condición de ser el número uno en su mercado geográfico/vertical, que es exactamente lo que CAN SLIM prioriza.

El *Capítulo 7 — L = Líder o rezagado* resume el criterio de selección:

> «La calificación RS promedio de las acciones con mejor desempeño antes de sus mayores incrementos fue de 87. Busque a los líderes genuinos y evite los rezagados.»


---

## Estrategias de Swing Trading

### MMM — Rechazo por ADR Insuficiente (ATR-021)

panxo consultó sobre MMM. La respuesta de Ricky fue directa: *«$MMM no me gusta, 1.75 de ADR»*. Un ADR de 1.75% está por debajo del umbral mínimo del grupo (3%). La lógica es que con una volatilidad tan reducida, el potencial de ganancia es insuficiente para justificar el riesgo del trade. Este filtro de ADR elimina las acciones que no tienen el dinamismo necesario para generar rendimientos compatibles con la metodología.

El *Capítulo 3 — C = Ganancias trimestrales grandes* respalda el perfil requerido:

> «Tres de cada cuatro grandes ganadores del mercado en el pasado fueron acciones de crecimiento... Las acciones que seleccione deben mostrar un aumento porcentual importante en las ganancias por acción trimestrales actuales.»

---

## Setups Sin Respaldo Académico Directo

### JNVR — Oportunidad Perdida (ATR-050)

Estrategia de campo sin respaldo académico directo.

Kingluis reportó: *«esta se nos escapó $JNVR»*. Este registro no documenta un trade ejecutado sino una oportunidad de trading perdida donde el setup se desarrolló sin participación del grupo. Las oportunidades perdidas son utilizadas como lección pedagógica para mejorar los procesos de screening y ejecución. No existe un patrón técnico ni fundamento defensible extraído del intercambio, razón por la cual este setup no tiene respaldo teórico asignable.

---

*Fin del Manual de Usuario de Trading — Momentum-v2 Playbook*
*55 setups documentados | 54/55 con respaldo teórico de «Cómo ganar dinero en acciones» (William J. O'Neil) | 1 setup sin patrón defensible (ATR-050)*
ENDOFMA
