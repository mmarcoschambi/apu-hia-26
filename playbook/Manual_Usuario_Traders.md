# Manual de Usuario de Trading — Momentum-v2 Playbook

> *Basado en los setups extraídos del canal de trading del grupo y enriquecidos
> con respaldo teórico de «Cómo ganar dinero en acciones» de William J. O'Neil.
> Cada setup refleja decisiones reales de traders en tiempo de mercado.*

---

## Marco Operativo, Indicadores y Sistema

### ATR-051 — Filosofía y Sistema General del Grupo

Filosofía del grupo basada en CAN SLIM, Minervini, Qullamaggie y Dan Zanger. Cristianara: 'Nosotros seguimos la gestión de RISK que hace Minervini o Qullamaggie'. Estilo principal: Swing Trading de 3 a 15 días. Cristianara: 'de 3 a 15 días más o menos, depende del mercado, si es un mercado de los buenos, se puede aguantar un poco más, pero vamos tomando parciales'. Señales de entrada principales: (1) AVWAP Reclaim - recuperación del AVWAP como señal de continuación alcista, (2) Pullback al VWAP/AVWAP con volumen - retroceso a zona de soporte dinámico con confirmación de volumen, (3) VCP (Volatility Contraction Pattern) - contracción progresiva de rangos de precio, entrada en breakout del último contracción, (4) Pocket Pivot - señal de entrada dentro de una base antes del breakout, (5) Episodic Pivot - gap o movimiento explosivo tras evento/catalizador, (6) Shakeout + recuperación AVWAP - limpieza de stops débiles seguida de recuperación, (7) Breakout de trendline con volumen, (8) Breakout de energía limpia con catalizador. Ricky: 'Por eso el growth con momentum es lo óptimo para el swing'.

**Gestión de riesgo:** Marco de gestión de riesgo del grupo: (1) Máximo 1% de riesgo por posición - Cristianara: 'que el stop de la operación no supere el 1% de tu cuenta'. (2) ADR mínimo de 3% para considerar entradas - Cristianara: 'por eso es mejor buscar ADR mayor a 3'. (3) Cierre de parciales en 33% por cada TP - 'Normalmente cerramos el 33% en cada TP'. (4) Sistema de R-múltiplos para salidas - Ricky: 'cuanto hayas ganado un 2R de tu riesgo sales con un parcial, en 4R otro'. (5) Position sizing basado en ADR y Stop Loss - Cristianara: 'El Size se calcula con el SL y el ADR'. Ricky: 'lo mejor es controlar el size por STOP y ADR'. (6) No aumentar size cuando la acción está extendida - Ricky: 'no es correcto aumentar size cuando está extendido, se aumenta size cuando la acción está rompiendo bases'. (7) Opciones: LONG CALLS con 30 DTE como alternativa - Cristianara: 'con LONG CALLS también funciona 30dte'. (8) Dos stops por posición (uno cerca, otro bajo AVWAP) - Cristianara: 'Yo puse 2 stops, uno cerca y otro debajo del AVWAP de máximos'. (9) Salida anticipada si se pierde el VWAP - Ricky: 'igual cierro antes del stop si veo que no termina de aguantar el vwap'. (10) Stop Profit o trailing stop en momentum - Ricky: 'Podrías cerrar algún parcial en stop profit si pierde el momentum en 1H. Que pierda la EMA de 10, 20'.

> Todas estas acciones vitales son completamente contrarias a la naturaleza humana. El mercado de valores es la naturaleza humana y la psicología de la multitud en exhibición diaria, además de la ley de la oferta y la demanda en el trabajo.
>
> — *Capítulo 1 / CAN SLIM completo / Capítulo 10 - Gestión de riesgo / Capítulo 11 - Toma de ganancias*

*Concordancia técnica:* La filosofía del grupo (Minervini, Qullamaggie, CAN SLIM) está alineada con los principios de O'Neil: gestión de riesgo (stop 1%), toma de parciales (33%), VCP, Episodic Pivot y AVWAP son adaptaciones modernas de los patrones clásicos de O'Neil.

---

### ATR-052 — Indicadores Técnicos del Sistema

Uso de indicadores técnicos del grupo: (1) AVWAP (Anchored VWAP) - anclado a puntos de referencia como earnings, IPO, máximos con alto volumen. Cristianara: 'el AVWAP lo anclas en un punto de referencia donde hubo alto volumen'. Se usan múltiples AVWAPs conforme la tendencia se desarrolla. (2) DEMA (Double EMA) - Ricky: 'Qullamaggie habla sobre la DEMA, cuando habla de respetar el momentum'. La DEMA de 10 y 20 periodos como soportes dinámicos. (3) EMA 200 como filtro de tendencia mayor - yuniormentado: 'La de 200 está sobre $56'. (4) Vol Trigger como indicador de volatilidad del mercado - Ricky: 'También a comentar que seguimos cerrando por encima del Vol Trigger'. (5) Vol Buzz (TC2000) como screening de volumen anómalo - Ricky: 'Para hacer una compra swing mira el Vol Buzz de TC2000'. (6) IV Rank para medir volatilidad implícita. (7) Call Wall / Put Wall como niveles de opciones - Cristianara: 'El Call Wall y el Put Wall son niveles donde se concentra un gran volumen de opciones call y put'.

> Los gráficos son su hoja de ruta de inversión. En casi todos los campos, existen herramientas para ayudar a evaluar correctamente las condiciones actuales. El historial de precio y volumen se registra en gráficos para ayudar a los inversores.
>
> — *Capítulo 2 - Cómo leer gráficos como un profesional / Capítulo 6 - S = Oferta y Demanda*

*Concordancia técnica:* AVWAP, DEMA, Vol Trigger, Call/Put Wall son extensiones de la filosofía de O'Neil de usar indicadores de precio y volumen para medir oferta y demanda. El grupo moderniza las herramientas del libro.

---

### ATR-053 — Patrones de Salida del Sistema

Patrones de salida identificados en el chat: (1) Salida por pérdida de momentum - Ricky: 'Podrías cerrar algún parcial en stop profit si pierde el momentum en 1H. Que pierda la EMA de 10,20'. (2) Salida por pérdida de AVWAP - Cristianara: 'lo que pierda los avwap ire [cortando]'. (3) Salida por R-múltiplo - Ricky: 'cuanto hayas ganado un 2R de tu riesgo sales con un parcial, en 4R otro'. (4) Salida por gap down post-earnings - Ricky: 'Si $GEV abre gap down, cerraremos'. (5) Stop Profit / trailing stop - toninavarro: 'lo que hago es poner stop profit'. (6) Reducción de exposición antes de earnings - river_trades: 'creo que voy a reducir exposición o incluso cerrar antes de los resultados'. (7) Optimización de stop usando AVWAP de tendencia - Cristianara: 'Usa el AVWAP de la tendencia por lo menos'. (8) Cierre de parciales en 33% por TP - Cristianara/Ricky: 'Normalmente cerramos el 33% en cada TP'.

> Debe aprender a vender siempre acciones rápidamente cuando tienes una pequeña pérdida. Me gusta seguir una proporción de 3 a 1 entre dónde vender y obtener ganancias y dónde reducir las pérdidas.
>
> — *Capítulo 10 - Cuando debe vender / Capítulo 11 - Cuándo vender y tomar sus ganancias*

*Concordancia técnica:* Los 8 patrones de salida del grupo (pérdida de momentum, AVWAP, R-múltiplo, gap down, trailing stop, reducción pre-earnings, optimización AVWAP, parciales 33%) están basados en las reglas de venta de O'Neil.

---

### ATR-054 — Temas Sectoriales — Thematic Momentum

Identificación de temas sectoriales (thematic momentum): (1) Energía limpia/nuclear - Ricky: 'Que bonitos los breakouts de energía limpia'. Incluye: NNE, SMR, OKLO, CEG, TLN. (2) IA/Semiconductores - ALAB, NVDA, ARM, AVGO. (3) China plays - PDD, NIO, JD. Ricky: 'China ahora mismo es un HOT theme'. (4) Computación cuántica - IONQ, QUBT. (5) Crypto proxy - MSTR correlacionado con BTC. (6) eVTOL - ACHR. (7) Biotech - NVAX, BNTX, SANA. La rotación entre temas es clave para identificar oportunidades.

**Gestión de riesgo:** Ricky advierte sobre China: 'no recomendaría comprar Chinas' a pesar del momentum, debido al riesgo de corrección. 'Los recientes catalizadores de China creo que [no son suficientes]'.

> Selección de los mejores temas de mercado, sectores e industria Grupos. Cuando estos grupos comienzan a acumularse, sabes que estás cerca del final. La rotación entre temas es clave para identificar oportunidades.
>
> — *Capítulo 15 - Selección de los mejores temas de mercado, sectores e industria Grupos / Capítulo 9*

*Concordancia técnica:* La identificación de temas sectoriales (nuclear, IA, China, cuántico) sigue el análisis de rotación sectorial que O'Neil detalla. El grupo aplica el monitoreo de 'hot themes' que el libro recomienda.

---

### ATR-055 — Herramientas de Screening y Plataformas

Herramientas de screening y análisis utilizadas: (1) Deepvue - Ricky: 'Deepvue es más para los datos de la empresa (EPS, Ventas, Ranking de industria, Sector)'. (2) TC2000 - para Vol Buzz, screening de volumen, análisis técnico. (3) TOS (Thinkorswim) - plataforma de trading con DAS Pro. (4) Briefing.com - noticias y catalizadores. (5) Seeking Alpha - análisis fundamental. (6) MarketSmith (IBD) - screening CAN SLIM. (7) Tradytics - análisis cuantitativo. (8) TraderSync - journaling y tracking de trades. (9) TradingView - para AVWAP/VWAP y análisis técnico. (10) Fewmoredays.io - enciclopedia de Qullamaggie. Cristianara recomienda: 'Aprende primero Swing en largos, hasta que lo domines. Domina 1 sola cosa y le vas metiendo más'.

**Gestión de riesgo:** Cristianara enfatiza la importancia de recopilar datos del sistema: 'revisar si el sistema funciona, cuál es su win rate, cuántos stops seguidos puede tener'. Ricky: 'Calcular cuál podría ser tu stop max por posición y ajustas con el size que le metas'.

> Los inversores individuales pueden perder mucho dinero si no saben cómo reconocer cuándo una acción llega a su punto máximo. Los mejores profesionales utilizan gráficos. Las herramientas de screening pueden ayudarlo a seguir cientos de acciones.
>
> — *Capítulo 2 - Cómo leer gráficos como un profesional / Capítulo 16 - Cómo usar la EII para encontrar acciones ganadoras*

*Concordancia técnica:* Deepvue, TC2000, MarketSmith, TradingView son las herramientas modernas equivalentes a las que O'Neil recomienda. La filosofía de 'dominar 1 cosa' y recopilar datos del sistema es consistente con la enseñanza del libro.

---

## Estrategias de Momentum

### ATR-001 — VST

Entrada impulsada por catalizador fundamental. VST presentó un movimiento explosivo ('explotó VST, se sostuvo') sugeriendo un Episodic Pivot o breakout con impulso de noticias. Ricky confirma: 'Si VST viene con catalizador'. El catalizador fue compartido previamente en el canal #catalizadores.

**Gestión de riesgo:** No se detalla stop loss ni tamaño de posición específico para VST en este trade. Sin embargo, el marco general del grupo indica riesgo máximo del 1% de la cuenta por operación y cierre de parciales en niveles de TP predefinidos (33% en cada TP).

> Buscar empresas que hayan desarrollado nuevos productos importantes o servicios, o que se hayan beneficiado de una nueva administración o condiciones industriales sustancialmente mejoradas. Entonces compre sus acciones cuando están emergiendo de patrones de consolidación de precios sólidos.
>
> — *Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos de bases correctamente formadas*

*Concordancia técnica:* El trader entra en VST por un catalizador fundamental compartido, lo que corresponde a la 'N' de CAN SLIM (nuevo producto/evento). El movimiento explosivo valida la tesis del Episodic Pivot descrita por Qullamaggie, donde un catalizador produce una ruptura violenta.

---

### ATR-002 — LTH

LTH destacada en la watchlist del día. El trader bpo28 señala: 'Vaya forma de respetar las medias que ha mostrado', indicando que el precio está respetando las medias móviles (EMA/SMA) como soporte dinámico, lo cual es una señal de tendencia alcista saludable según la metodología Minervini/Growth.

> En un gráfico semanal, la rigidez se define como pequeñas variaciones de precio de mayor a menor durante la semana, con precios de varias semanas consecutivas cerrando sin cambios o muy cerca del cierre de la semana anterior. Si el patrón base tiene una amplia dispersion...
>
> — *Capítulo 2 - Cómo leer gráficos como un profesional / Los patrones constructivos tienen áreas de precios ajustados*

*Concordancia técnica:* El trader observa que LTH 'respeta las medias' como soporte dinámico. El libro enseña que las medias móviles (especialmente la EMA de 10 y 20 semanas) son herramientas clave para medir la salud de la tendencia alcista.

---

### ATR-003 — ALAB

ALAB (Astera Labs, semiconductores para IA) mostró un patrón de doble suelo con posible ruptura alcista. kiliaitor identificó: 'Parece que ha hecho un doble suelo y puede romper hacia arriba'. Cristianara confirmó: 'Esa ALAB me gusta ahi' y la añadió a su watchlist. Posteriormente, river_trades señaló: '$ALAB en buen punto de compra, rompiendo el vwap de máximos', confirmando entrada en ruptura del AVWAP anclado a máximos. Ricky menciona '$ALAB' como seguimiento del setup.

> Un patrón de precios de 'doble fondo' se parece a la letra 'W'. Este patrón tampoco ocurre con tanta frecuencia como la taza con asa, pero aún ocurre con frecuencia. Por lo general, es importante que el segundo mínimo de la W coincida con el nivel de precios...
>
> — *Capítulo 2 - Reconocer un patrón de precios de 'doble fondo'*

*Concordancia técnica:* El trader identifica un doble suelo en ALAB y confirma con ruptura del AVWAP de máximos. El libro describe exactamente este patrón W y la ruptura del punto pivote con volumen como señal de entrada.

---

### ATR-004 — NNE

NNE (Nano Nuclear Energy) - Sector uranio caliente. Cristianara identifica: 'NNE en diario tiene un VCP brutal' (Volatility Contraction Pattern). Entrada técnica: 'entramos cuando recuperó el VWAP diario'. Cristianara también reporta: 'NNE rompió el AVWAP de IPO'. El patrón VCP con ruptura del AVWAP de IPO y recuperación del VWAP diario sirvieron como confirmaciones de entrada. bpo28 confirma: 'De lo poco que vi con volumen duro. Esa NNE y poco más'.

**Gestión de riesgo:** Ricky reporta: 'NNE que cae un 13% es un 1% de la cuenta', demostrando que el tamaño de posición se ajustó según el ADR/volatilidad para limitar el riesgo al 1% de la cuenta. Esto implica position sizing inversamente proporcional al ADR del activo.

> La formación del área del mango generalmente toma más de una o dos semanas y tiene una tendencia a la baja del precio o 'sacudida' (donde el precio cae por debajo de un punto bajo anterior en el mango), generalmente cerca del final de su movimiento de precios descendente.
>
> — *Capítulo 2 - Características básicas del área del mango de una taza / CAN SLIM 'N'*

*Concordancia técnica:* El trader identifica un VCP (Volatility Contraction Pattern), variante moderna del patrón de consolidación descrito por O'Neil. La contracción progresiva de rangos y la recuperación del VWAP diario son la confirmación del punto pivote.

---

### ATR-005 — PDD

Ricky confirma: 'Por cierto muy buena entrada en $PDD' y revela que la entrada fue impulsada por un catalizador de China: 'lo enviamos esta noche el catalizador de China, por eso entramos en NIO'. El setup combina la metodología de breakout con catalizador macro (estímulos chino). PDD se posicionó como play de momentum sobre el tema China.

**Gestión de riesgo:** Ricky advierte sobre la gestión de PDD a medio plazo: 'Todo esto hablo según mi perspectiva si pretendéis mantener $PDD meses y aceptáis la volatilidad'. Sugiere que la posición requiere tolerancia a la volatilidad dada la naturaleza del catalizador geopolítico.

> Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio importante que se vende rápidamente y hace que las ganancias se aceleren... Las nuevas condiciones de la industria también pueden tener un efecto positivo.
>
> — *Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos de bases correctamente formadas*

*Concordancia técnica:* PDD tuvo entrada por catalizador macro de estímulos chinos. El libro valida que los catalizadores (nuevas condiciones industriales) generan los mejores setups de momentum. El trader ejecuta exactamente lo que prescribe CAN SLIM: comprar en ruptura con catalizador.

---

### ATR-006 — GEV

GEV (GE Vernova) - Play de resultados/earnings. Ricky indica: 'Hoy presenta resultados nuestra querida $GEV, al tener poco size en ella y algo de margen hemos querido mantener'. La estrategia fue mantener posición pequeña antes de earnings. Plan de salida definido: 'Si $GEV abre gap down, cerraremos'. Ale confirma que entró en GEV previamente.

**Gestión de riesgo:** Posición reducida ('poco size') ante la incertidumbre de earnings. Plan de stop loss claro: cierre total si gap down al abrir. Ricky también menciona: 'al tener poco size en ella y algo de margen hemos querido mantener', indicando gestión conservadora del riesgo ante evento binario.

> Debes aprender a vender siempre acciones rápidamente cuando tienes una pequeña pérdida en lugar de esperar y esperar que regresen. Si $GEV abre gap down, cerraremos. Posición reducida ('poco size') ante la incertidumbre de earnings.
>
> — *Capítulo 10 - Cuando debe vender y eliminar todas las pérdidas... sin excepción*

*Concordancia técnica:* El trader reduce tamaño antes de earnings (evento binario) y planifica salida por gap down. El libro prescribe exactamente esto: reducir pérdidas rápidamente y gestionar el riesgo ante eventos inciertos.

---

### ATR-007 — OKLO

OKLO (energía nuclear) mostró un movimiento explosivo de +37%. Ricky advierte sobre su volatilidad: 'Después tampoco vas a ir con mucho size en $OKLO que tiene 13,46% de ADR'. El ADR extremo requiere ajuste de tamaño. OKLO mueve '26 Millones de $ al día' en volumen. inma_._ entró el día anterior cuando la mencionó en el chat. Kingluis comparte que es tema de una masterclass posterior.

**Gestión de riesgo:** ADR de 13.46% implica position size muy reducido. Ricky enfatiza: 'no es correcto aumentar size cuando está extendido, se aumenta size cuando la acción está rompiendo bases'. La lógica es: entrar con size completo en el punto de breakout de la base, no después de que ya se haya extendido.

> Las acciones de pequeña capitalización serán sustancialmente más volátil, tanto al alza como a la baja. Las empresas que están recomprando sus acciones... se prefieren.
>
> — *Capítulo 12 - Administración del dinero / Capítulo 6 - Oferta y Demanda*

*Concordancia técnica:* OKLO con ADR de 13.46% obliga a position sizing mínimo. El trader aplica la regla implícita del libro: cuanto mayor la volatilidad, menor el tamaño de posición. Ricky enfatiza no aumentar size cuando está extendido.

---

### ATR-008 — SHOP

Ale identifica: '$SHOP quebrando trendline en pre', señalando una ruptura de línea de tendencia en pre-mercado. Esto constituye una señal de entrada tipo breakout donde la rotura de la trendline con volumen confirma el cambio de tendencia. Posteriormente Ale reitera: '$SHOP me gusta', manteniendo la convicción alcista.

> Cuando una acción forma un patrón de gráfico de taza con asa adecuado y luego carga a través de un punto de compra alcista... el volumen del día debería aumentar al menos un 40% al 50% por encima de lo normal.
>
> — *Capítulo 2 - Encuentre puntos de pivote y vea el 'cambio porcentual de volumen'*

*Concordancia técnica:* La ruptura de trendline en pre-market identificada por Ale es exactamente el punto pivote que O'Neil describe. La rotura de la línea de tendencia con volumen confirma el breakout y cambio de tendencia.

---

### ATR-009 — PLTR

PLTR mostró un Episodic Pivot tras resultados: '$PLTR Episodic'. Ricky clasifica el movimiento como Episodic Pivot, que es un patrón de Qullamaggie donde el precio hace un gap o movimiento explosivo impulsado por un evento (earnings). Kingluis confirma: 'como que $PLTR reporto bien, esta 11% arriba para el día'. Posteriormente, Ale cierra parcial: 'cierro el 50 de $PLTR', tomando ganancias en mitad de la posición.

**Gestión de riesgo:** Gestión de salida por parciales: cierre del 50% de la posición en un nivel de toma de ganancias, siguiendo la filosofía del grupo de ir tomando parciales (33% en cada TP o en este caso 50%).

> Bethlehem Steel en 1915 es nuestro primer ejemplo potente de bandera alta y ajustada y sirvió como precedente histórico perfecto para banderas altas y ajustadas posteriores como Syntex, Rollins, Simmonds Precision, Yahoo! y Taser.
>
> — *Capítulo 2 - Las banderas altas y apretadas son raras / Capítulo 1 - Los mayores secretos de selección de acciones*

*Concordancia técnica:* El Episodic Pivot de PLTR tras earnings es equivalente al patrón de alta bandera/breakout post-evento que O'Neil documenta. El trader aplica gestión de salida por parciales (50%) que el libro prescribe.

---

### ATR-010 — ZM

Ale identifica: '$ZM genera un shakeout testeando el avwap de [earnings]'. Un shakeout es un patrón donde el precio rompe brevemente un soporte para luego recuperarse rápidamente, limpiando stops débiles antes de continuar alcista. La prueba del AVWAP anclado a earnings sirve como zona de soporte clave. La combinación shakeout + test AVWAP genera una señal de entrada con alta probabilidad según la metodología del grupo.

> La formación del área del mango... tiene una tendencia a la baja del precio o 'sacudida' (donde el precio cae por debajo de un punto bajo anterior), generalmente cerca del final de su movimiento de precios descendente. El volumen puede secarse notablemente cerca de los mínimos.
>
> — *Capítulo 2 - Características básicas del área del mango de una taza*

*Concordancia técnica:* El shakeout descrito por Ale es exactamente la 'sacudida' que O'Neil detalla en la formación del mango. La prueba del AVWAP de earnings como soporte confirma la validez del patrón.

---

### ATR-011 — CEG

CEG (Constellation Energy) - Ricky menciona: 'Se me escapó el EP (Episodic Pivot) en $CEG'. Posteriormente, CEG presenta catalizador de adquisición: '$CEG ha cerrado una adquisición y viene bastante'. Ale señala recuperación técnica: '$CEG recuperó el VWAP' y 'mucha vola $CEG hoy'. Ricky reporta gaps bajo sus stops: '$VST $CRDO $CEG abiertas con un gap por debajo de mis stops'.

**Gestión de riesgo:** Ricky menciona haber tenido posiciones con gap por debajo de sus stops, lo que generó pérdidas no controladas (gap risk). Esto es un riesgo inherente en swing trading con stops overnight.

> Buscar empresas que hayan desarrollado nuevos productos importantes o servicios, o que se hayan beneficiado de una nueva administración o condiciones industriales sustancialmente mejoradas.
>
> — *Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos de bases correctamente formadas*

*Concordancia técnica:* CEG presentó un Episodic Pivot por adquisición (catalizador corporativo). El libro valida estos eventos como catalizadores de nuevos movimientos direccionales. El gap risk es un riesgo inherente reconocido en swing trading.

---

### ATR-012 — CROX

Ale identifica: '$CROX esta justo en el AVWAP de los earnings'. El AVWAP anclado al evento de earnings sirve como nivel técnico clave. Cuando el precio testa este nivel, puede actuar como soporte o resistencia. Ale confirma: 'Esta luchando con el avwap de earnings', indicando que el precio está en una zona de decisión técnica donde la superación del AVWAP confirmaría la continuación alcista.

> Los gráficos registran el rendimiento real de los precios de miles de acciones. Los cambios de precios son el resultado de la oferta y la demanda diarias... Los inversores que se entrenan para descifrar los movimientos de precios en los gráficos tienen una enorme ventaja.
>
> — *Capítulo 2 - Cómo leer gráficos como un profesional / AVWAP como nivel técnico*

*Concordancia técnica:* El AVWAP de earnings actúa como resistencia/soporte que el libro describe como niveles de oferta y demanda. La 'lucha' del precio contra el AVWAP es la batalla entre compradores y vendedores en un nivel clave.

---

### ATR-013 — IONQ

IONQ (computación cuántica) - Ricky confirma: '$IONQ ya nos ha tocado el primer TP!', indicando que la posición alcanzó el primer objetivo de toma de ganancias. Ricky también menciona: '$IONQ También va' en contexto de momentum en el sector cuántico junto con QUBT.

**Gestión de riesgo:** La gestión de TP sigue la regla del grupo: cerrar 33% de la posición en cada TP predefinido. Al alcanzar el primer TP, se cierra un tercio de la posición y se ajusta el stop a breakeven o al siguiente nivel de soporte.

> Me gusta seguir una proporción de 3 a 1 entre dónde vender y obtener ganancias y dónde reducir las pérdidas. Si toma ganancias del 20% al 25%, reduzca sus pérdidas al 7% o al 8%.
>
> — *Capítulo 11 - Cuándo vender y tomar sus ganancias que valen la pena / Capítulo 10*

*Concordancia técnica:* La gestión por TP del grupo (33% en cada TP) sigue los principios de O'Neil de tomar ganancias en parciales para asegurar resultados mientras se mantiene exposición al upside.

---

### ATR-014 — SMR

Ricky reporta: 'God Candle $SMR'. Una 'God Candle' es una vela de gran tamaño (marubozu o similar) que indica un movimiento direccional masivo con presión compradora extrema. Generalmente ocurre tras un catalizador o en un punto de aceleración de momentum. SMR (NuScale Power, energía nuclear modular pequeña) se beneficia del tema nuclear/energía limpia.

> Casi todas las bases correctas mostrarán una disminución drástica del volumen durante una o dos semanas en la parte inferior del patrón de la base... Cuando el precio de las acciones sube, desea ver un aumento en el volumen.
>
> — *Capítulo 2 - Busque caídas de volumen cerca de los mínimos de un patrón de precios / Las pistas de gran volumen son valiosas*

*Concordancia técnica:* La 'God Candle' en SMR es una vela de alta volatilidad que el libro describe como señal de fuerte presión compradora, típicamente ocurriendo en puntos de aceleración de momentum.

---

### ATR-015 — RDDT

Cristianara identifica: 'Ese VCP de RDDT ES HERMOSO'. VCP (Volatility Contraction Pattern) es un patrón de Mark Minervini donde la volatilidad del precio se contrae progresivamente en una base antes de un breakout. La contracción decreciente indica acumulación institucional. La entrada se produce en la ruptura del último contracción con volumen.

> Los patrones de gráficos, o 'bases', son simplemente áreas de corrección y consolidación de precios después de un avance de precios anterior. Debe diagnosticar si los movimientos de precios y volúmenes son normales o anormales.
>
> — *Capítulo 2 - Conceptos básicos de lectura de gráficos / Patrones de precios y consolidación*

*Concordancia técnica:* El VCP de RDDT identificado por Cristianara es el patrón de contracción de volatilidad de Minervini, basado en los principios de O'Neil de que la volatilidad debe contraerse antes del breakout.

---

### ATR-016 — GSHD

Cristianara identifica: 'GSHD también es hermosa, ese VCP es brutal'. Otro VCP (Volatility Contraction Pattern) de alta calidad. La estructura de contracción de volatilidad en GSHD sugiere una base de acumulación antes de un potencial breakout con volumen.

> También debería haber al menos algunas áreas estrechas en los patrones de precios de las acciones en acumulación. La rigidez se define como pequeñas variaciones de precio de mayor a menor durante la semana.
>
> — *Capítulo 2 - Los patrones constructivos tienen áreas de precios ajustados*

*Concordancia técnica:* El VCP de GSHD muestra la contracción de rangos que el libro describe como señal de acumulación institucional. Múltiples contracciones indican una base de alta calidad.

---

### ATR-017 — NVAX

Cristianara identifica: 'NVAX la mandé temprano, lindo VCP'. VCP en NVAX (Novavax) identificado temprano en la sesión. El patrón VCP implica contracción progresiva de rangos de precio con volúmenes decrecientes, seguido de un breakout con expansión de volumen.

> Las fortunas las hacen todos los años aquellos que se toman el tiempo para aprender a interpretar los gráficos correctamente. Los patrones de precios de las grandes acciones del pasado pueden servir como modelos para sus selecciones futuras.
>
> — *Capítulo 2 - La historia se repite: aprenda a usar precedentes históricos*

*Concordancia técnica:* El VCP de NVAX identificado temprano sigue la metodología de reconocimiento de patrones que O'Neil enseña. Identificar el patrón antes del breakout permite preparar la entrada.

---

### ATR-018 — XYZ

Ale describe un setup intradía: 'Si $XYZ deja envolvente en M15 junto con el vwap reclaim, me parece una buena posición'. Señal compuesta: (1) patrón de vela envolvente alcista en timeframe de 15 minutos, (2) recuperación del VWAP (VWAP Reclaim). La confirmación dual de patrón de velas + reclaim del VWAP genera una señal de entrada de alta probabilidad para trade intradía.

**Gestión de riesgo:** Ale menciona 'un buen [riesgo]' en contexto de que el setup ofrece un buen risk-reward ratio gracias a la proximidad del stop al VWAP recién recuperado.

> Su objetivo no es comprar al precio más barato o cercano al mínimo, sino comenzar a comprar exactamente en el momento adecuado, cuando sus posibilidades de éxito sean mayores. Debe aprender a esperar a que una acción suba y negociar en su punto de compra.
>
> — *Capítulo 2 - Encuentre puntos de pivote y vea el 'cambio porcentual de volumen'*

*Concordancia técnica:* La señal compuesta de envolvente alcista + VWAP reclaim en M15 es la búsqueda del punto pivote exacto que describe O'Neil, donde múltiples confirmaciones convergen para definir la entrada de alta probabilidad.

---

### ATR-019 — CRWV

morae_0 identifica: 'CRWV puede tener una explosión de amplitud; marcó doble suelo hoy y rompió canal bajista'. Señal compuesta: (1) doble suelo como patrón de reversión, (2) ruptura de canal bajista como confirmación de cambio de tendencia. La combinación de ambos patrones refuerza la tesis alcista.

> Un patrón de precios de 'doble fondo' se parece a la letra 'W'. Por lo general, es importante que el segundo mínimo de la W coincida con el nivel de precios del primer mínimo o, como en casi todos los casos, lo socave claramente.
>
> — *Capítulo 2 - Reconocer un patrón de precios de 'doble fondo'*

*Concordancia técnica:* CRWV combina doble suelo con ruptura de canal bajista, dos patrones que O'Neil documenta. La combinación de patrones de reversión refuerza la tesis alcista.

---

### ATR-020 — HIMS

river_trades plantea: 'Si HIMS rompe el trendline con volumen quizá le entre'. La señal de entrada requiere: (1) ruptura de línea de tendencia bajista, (2) confirmación de volumen por encima de la media. La confirmación de volumen es esencial para validar el breakout y evitar señales falsas.

> Cuando una acción sale de un área de consolidación de precios, el volumen de negociación debe ser al menos un 40% o un 50% superior al normal. En muchos casos, aumentará un 100% o mucho más durante el día.
>
> — *Capítulo 6 - S = Oferta y Demanda / Evaluación de la oferta y la demanda*

*Concordancia técnica:* El trader exige volumen para validar la ruptura de trendline en HIMS. O'Neil es taxativo: el volumen debe expandirse significativamente para confirmar que el breakout es genuino y no una trampa.

---

### ATR-022 — MSTR / BTC

Ale nota la correlación crypto: '$MSTR se había adelantado a la suba de $BTC hasta más arriba de que ATH'. MSTR como proxy de Bitcoin mostró liderazgo alcista antes del ATH de BTC. Sin embargo, la reversión fue severa: '$MSTR -40% desde el máximo reciente'. Ricky reporta: 'Crypto devolviéndose $MSTR CORZ WULF y también SOFI TSLA', mostrando la correlación sectorial en la corrección.

**Gestión de riesgo:** La caída del 40% desde máximos demuestra el riesgo de volatilidad extrema en activos correlacionados con crypto. Se requiere gestión de tamaño conservadora dada la alta volatilidad del sector.

> Se deben verificar varios promedios en los puntos de inflexión del mercado para ver si hay divergencias significativas. El análisis compara el rendimiento relativo del sector software vs semiconductores para identificar rotación de capital.
>
> — *Capítulo 9 - M = Dirección del mercado / Busque la divergencia de los promedios clave*

*Concordancia técnica:* El análisis de correlación entre MSTR/BTC y la observación de reversión sectorial sigue la metodología de O'Neil de monitorear la interacción entre sectores para anticipar movimientos del mercado.

---

### ATR-023 — OPEN

Ricky confirma: 'Entramos en $OPEN en la comunidad privada y ya cerca del 1er [TP]'. OPEN (Opendoor Technologies) alcanzó casi el primer take profit poco después de la entrada, indicando un setup bien temporizado. El ticker también fue mencionado previamente como oportunidad.

**Gestión de riesgo:** Gestión por TPs: posición dividida en tercios (33% cada TP), cerca de alcanzar el primer objetivo.

> Me gusta seguir una proporción de 3 a 1 entre dónde vender y obtener ganancias y dónde reducir las pérdidas. Si toma ganancias del 20% al 25%, reduzca sus pérdidas al 7% o al 8%.
>
> — *Capítulo 11 - Cuándo vender y tomar sus ganancias que valen la pena*

*Concordancia técnica:* OPEN alcanzando el primer TP refleja la gestión de parciales (33%) que el grupo toma de la metodología de O'Neil de tomar ganancias escalonadamente.

---

### ATR-024 — SMH / IGV / AVGO

Ricky observa una rotación sectorial: 'Correlacion Software $IGV vs Semiconductores $SMH, Break the [correlation]'. El análisis compara el rendimiento relativo del sector software (IGV) vs semiconductores (SMH) para identificar rotación de capital. También señala: 'Observa lo choppy que está $SMH' y '$AVGO sin [confirmación]'. La falta de definición en SMH y AVGO sugiere cautela en el sector semi.

> Los inversores diligentes cavan otro nivel más. Quieren saber no sólo cuántos patrocinadores institucionales tiene una acción, si ese número ha aumentado constantemente en los últimos trimestres.
>
> — *Capítulo 9 - M = Dirección del mercado / Análisis sectorial de IGV vs SMH*

*Concordancia técnica:* La comparación SMH vs IGV para detectar rotación sectorial sigue el análisis de grupos industriales que O'Neil recomienda en el Capítulo 15 (Selección de los mejores temas de mercado).

---

### ATR-025 — APP

Ricky identifica: '$APP es un buen setup para [swing]'. APP (AppLovin) mostró un setup técnico válido. Sin embargo, la ejecución fue problemática: '$APP termina cerrando -' indicando que el trade no funcionó. Cristianara después menciona un catalizador fundamental: 'interés de $APP en adquirir TikTok', que podría generar un nuevo Episodic Pivot.

> Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio importante que se vende rápidamente.
>
> — *Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos*

*Concordancia técnica:* APP como setup de swing con catalizador de adquisición de TikTok sigue la 'N' de CAN SLIM. El libro enseña que los catalizadores corporativos generan Episodic Pivots.

---

### ATR-026 — TLN

Ricky recomienda: 'Revisar el estudio de $TLN Recent IPO en #daily-focus no tiene [mala pinta]'. TLN (Talen Energy) como Recent IPO setup. Las Recent IPOs son un patrón específico donde acciones recién listadas con fundamentos fuertes pueden generar movimientos explosivos tras un período de consolidación post-IPO.

> Los inversionistas alertas deberían tener una forma de realizar un seguimiento de todas las nuevas emisiones de acciones que han surgido en los últimos 10 años. Algunas de estas empresas más nuevas estarán entre las más impresionantes del próximo año o dos.
>
> — *Capítulo 5 - Excelentes oportunidades en acciones nuevas y desconocidas / Empresas más nuevas*

*Concordancia técnica:* TLN como Recent IPO setup sigue exactamente la recomendación de O'Neil de monitorear nuevas emisiones. Las IPOs recientes pueden generar movimientos explosivos tras consolidación post-IPO.

---

### ATR-027 — QUBT

Ricky menciona: '$QUBT sigue siendo una muy buena [oportunidad]'. QUBT (Quantum Computing) como play de momentum en el tema cuántico. Eltradino también lo sigue. El sector cuántico mostró momentum continuo durante el período analizado, junto con IONQ.

> Se necesitan las acciones de uno, dos o tres principales en un grupo industrial fuerte. Las grandes acciones en el mercado alcista se multiplicaron por cinco, seis y siete antes de llegar al tope.
>
> — *Capítulo 7 - L = Líder o rezagado / Compre entre las mejores dos o tres acciones de un grupo*

*Concordancia técnica:* QUBT en el tema cuántico con IONQ como par refuerza el análisis sectorial de O'Neil: cuando múltiples acciones de un tema muestran fortaleza, el tema tiene validez.

---

### ATR-028 — BFLY

Eltradino menciona: 'la que puse $BFLY'. BFLY fue compartido como idea de trading en el chat. Ricky añade: 'Si, tiene noticia hoy $RGTI', vinculando el setup con un catalizador de noticias.

> Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio, nueva administración, o nuevas condiciones de la industria.
>
> — *Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos*

*Concordancia técnica:* BFLY con noticias vinculadas a RGTI sigue la estrategia de catalizadores donde la noticia fundamental genera el momentum.

---

### ATR-029 — HOOD

Múltiples interacciones con HOOD: Ricky reporta: 'La cartera seguirá estando en máximos $HOOD cayendo un -8% ahora'. darksalsa identifica: 'buen rebote de $HOOD en la media', señalando un pullback a la media móvil como oportunidad de entrada. Posteriormente, HOOD sufre otro gap: 'No S&P 500 inclusion for Robinhood. Stock drops -7% after hours'. Ricky finalmente reporta: '$HOOD +7,38%' en recuperación.

**Gestión de riesgo:** Los gaps de -7% y -8% representan riesgo significativo en swing trading. El rebote 'en la media' implica uso de la media móvil como nivel de soporte dinámico para entradas.

> Las acciones de crecimiento más deseables normalmente corrigen de 1½ a 2½ veces los promedios generales del mercado. Las que menos caen son normalmente sus mejores selecciones.
>
> — *Capítulo 7 - Encontrar nuevos líderes durante las correcciones del mercado*

*Concordancia técnica:* HOOD rebotando 'en la media' y recuperándose de gaps es el comportamiento de un líder que corrige dentro de parámetros normales. La media móvil funciona como soporte dinámico que O'Neil describe.

---

### ATR-030 — DOCS

Ale reporta: 'Reduzco 50% en $DOCS'. Cierre de la mitad de la posición en DOCS (Doximity), tomando ganancias parciales. La reducción del 50% sugiere que el trade ya ha generado ganancias suficientes para asegurar parcialmente el resultado, pero mantiene exposición al upside potencial.

**Gestión de riesgo:** Gestión de parciales: cierre del 50% (en lugar del 33% estándar) sugiere mayor cautela o que el precio se ha extendido significativamente desde el punto de entrada.

> Debe aprender a vender sus errores mientras la pérdida aún sea pequeña y observar sus mejores selecciones para ver si se convierten en grandes ganadores. Si posee una cartera, venda primero las de peor desempeño.
>
> — *Capítulo 11 - Cuándo vender y tomar sus ganancias que valen la pena*

*Concordancia técnica:* La reducción del 50% en DOCS sigue la gestión de parciales. O'Neil recomienda tomar ganancias progresivamente para asegurar resultados.

---

### ATR-031 — SERV

Ricky reporta riesgo controlado: '$SERV un 3.5%' de la cuenta. Aunque SERV tuvo un movimiento adverso significativo, el riesgo por posición se mantuvo dentro del marco del grupo. La combinación de ADR alto con position sizing apropiado limitó el impacto en la cartera.

**Gestión de riesgo:** Impacto del 3.5% de la cuenta en SERV, superior al 1% objetivo. Ricky lo menciona como excepción o lección, ya que el ideal es máximo 1% de riesgo por posición.

> Bernard Baruch lo dijo mejor: 'Si un especulador tiene razón la mitad de las veces, está alcanzando un buen promedio. Pero acertar 3 o 4 veces de cada 10 debería rendir una fortuna si tiene el sentido común de reducir sus pérdidas rápidamente'.
>
> — *Capítulo 10 - Cuando debe vender y eliminar todas las pérdidas... sin excepción*

*Concordancia técnica:* SERV con impacto del 3.5% excede el 1% ideal pero refleja la realidad del trading. O'Neil prescribe reducir pérdidas rápidamente; el trader lo aplica como excepción.

---

### ATR-032 — LQDA

darksalsa identifica: 'Me gusta $LQDA, a ver si deja un buen breakout hoy. Ha estado mostrando mucha fuerza relativa'. Señal compuesta: (1) fuerza relativa vs mercado, (2) potencial breakout al alza. La fuerza relativa es un concepto clave de Minervini donde una acción outperforma el mercado general antes de un breakout.

> La calificación RS patentada mide el rendimiento del precio de una acción frente al resto del mercado. A cada acción se le asigna una calificación de 1 a 99. La calificación RS promedio de las acciones con mejor desempeño antes de sus mayores incrementos fue de 87.
>
> — *Capítulo 7 - L = Líder o rezagado / Cómo separar a los líderes de los rezagados usando la fuerza relativa del precio*

*Concordancia técnica:* LQDA con 'mucha fuerza relativa' antes del breakout sigue exactamente el principio de O'Neil: los líderes muestran RS superior antes de sus mayores movimientos.

---

### ATR-033 — TEM

Ricky identifica: '$TEM está en un setup parecido al de hace días en [otro activo]'. Reconocimiento de patrón repetido donde TEM muestra una configuración técnica similar a un setup previo exitoso. La identificación de patrones recurrentes es parte de la metodología cuantitativa del grupo.

> La historia se repite. Cuantos más patrones históricos conozca y llegue a reconocer, más dinero podrá ganar en los mercados futuros.
>
> — *Capítulo 2 - La historia se repite: aprenda a usar precedentes históricos*

*Concordancia técnica:* TEM en un 'setup parecido al de hace días' ejerce el reconocimiento de patrones que O'Neil explica: los mismos patrones se repiten ciclo tras ciclo.

---

### ATR-034 — SOFI

Ricky destaca: '$SOFI es buenísima y encima viene con unos resultados explosivos EPS +266% Sales [crecimiento]'. El crecimiento fundamental explosivo (EPS +266%) combinado con una estructura técnica favorable genera un setup de Growth Investing. Ale reporta después: 'Le dieron duro a $SOFI', indicando corrección posterior.

> Las ganancias por acción trimestrales actuales deberían aumentar un porcentaje importante, del 25% al 50% como mínimo. Las mejores empresas pueden mostrar ganancias del 100% para 500% o más.
>
> — *Capítulo 3 - C = Ganancias trimestrales grandes o aceleradas actuales y Ventas*

*Concordancia técnica:* SOFI con EPS +266% cumple y supera el requisito de crecimiento de ganancias de CAN SLIM. El trader combina fundamentos explosivos con estructura técnica favorable.

---

### ATR-035 — VKTX

Ricky reporta la volatilidad de VKTX: '+24% arriba $VKTX' en pre-market, seguido de '$VKTX de llegar a estar un +24 en pre market a caer un -5%'. Este es un ejemplo extremo de la diferencia entre el movimiento de pre-market y la sesión regular, ilustrando el riesgo de entrar en pre-market sin confirmación.

**Gestión de riesgo:** La reversión de +24% a -5% demuestra el peligro de ejecutar entradas en pre-market. La metodología del grupo prioriza entradas durante RTH (Regular Trading Hours) con confirmación de volumen.

> En los mercados bajistas, las acciones suelen abrir fuertes y cerrar débiles. En los mercados alcistas, tienden a abrir débiles y cerrar fuertes.
>
> — *Capítulo 9 - M = Dirección del mercado*

*Concordancia técnica:* VKTX pasando de +24% en pre-market a -5% ilustra el riesgo que O'Neil describe de operar fuera del RTH sin confirmación de volumen.

---

### ATR-036 — ACHR

Eltradino sigue ACHR (Archer Aviation, eVTOL): 'os acordáis de la que comenté de EVTOL? $ACHR'. Posteriormente: '$ACHR imparable, no me deja [salir/vender]'. El momentum fuerte impide salir parcialmente, lo que es tanto positivo (ganancias acumuladas) como un riesgo (necesidad de gestionar la salida). Ricky incluye ACHR en la lista de earnings: '$DELL $SOUN $ACHR $RKLB' a la baja.

> Cuando una acción está a la baja, normalmente desea ver que el volumen se agota. Cuando el precio de las acciones sube, en la mayoría de las situaciones desea ver un aumento en el volumen.
>
> — *Capítulo 6 - S = Oferta y Demanda / Evaluación de la oferta y la demanda*

*Concordancia técnica:* ACHR 'imparable' refleja el momentum descrito en el Capítulo 6 donde la oferta limitada y la alta demanda producen movimientos verticales.

---

### ATR-037 — BBAI

kriptopepino identifica: '$BBAI empresa de AI ha firmado un acuerdo con PALANTIR y lleva [momentum]'. Catalizador fundamental: acuerdo con Palantir que genera sinergia en el tema de IA. El catalizador corporativo combinado con el tema sectorial AI genera una tesis de momentum.

> Se necesita algo nuevo para producir un avance sorprendente en el precio de una acción. Eso puede ser un nuevo producto o servicio importante... Nuevas condiciones de la industria.
>
> — *Capítulo 5 - N = Empresas más nuevas, nuevos productos, nueva administración, nuevos máximos*

*Concordancia técnica:* BBAI con acuerdo con Palantir (catalizador corporativo) + tema AI ejemplifica la 'N' de CAN SLIM donde el nuevo evento corporativo genera el momentum.

---

### ATR-038 — QQQ / SPY / FFTY / IWM

Múltiples referencias a ETFs como indicadores de mercado: Ale señala '$QQQ test DEMA10' (DEMA de 10 períodos como soporte dinámico). '$FFTY debajo de la DEMA 10 y casi de la 20' (FFTY = Innovator IBD 50, indicador de momentum growth). '$SPY cerca de [soporte/resistencia]'. Ricky identifica '$IWM Rompemos' (Russels 2000 breakout). inversornovat0 toma 'Long $QQQ'. El FFTY como proxy del estilo Growth/Minervini es un indicador clave.

> La mejor manera de determinar la dirección del mercado es mirar cuidadosamente, seguir, interpretar y comprender los gráficos diarios de los tres o cuatro principales promedios generales del mercado.
>
> — *Capítulo 9 - M = Dirección del mercado: cómo se determina*

*Concordancia técnica:* El monitoreo de QQQ, SPY, FFTY e IWM con DEMA sigue exactamente el método de O'Neil de analizar los principales índices para determinar la dirección del mercado.

---

### ATR-039 — LUNR

Kingluis reporta: '$LUNR me saco en el primer SL'. LUNR (Intuitive Machines) activó el stop loss en la primera oportunidad, indicando que el setup falló. La ejecución disciplinada del stop loss es un pilar de la metodología del grupo.

**Gestión de riesgo:** Ejecución disciplinada de stop loss. El trade falló y se salió automáticamente, protegiendo el capital. Esto es consistente con la filosofía de gestión de riesgo del grupo: aceptar las pérdidas pequeñas como parte del sistema.

> La primera regla para el inversionista individual altamente exitoso es siempre acortar y limitar cada pérdida. Debe comprender que el precio de las acciones cae por debajo del precio que pagó. Cada punto aumenta la posibilidad de que se equivoque.
>
> — *Capítulo 10 - Cuando debe vender y eliminar todas las pérdidas... sin excepción*

*Concordancia técnica:* LUNR activó el stop y Kingluis salió disciplinadamente. O'Neil enfatiza que aceptar pérdidas pequeñas es la clave del éxito a largo plazo.

---

### ATR-040 — SANA

boy__plunger reporta: 'Buen after de $SANA'. Movimiento significativo en after-hours para SANA (Sana Biotechnology). Los movimientos en after-hours pueden anticipar gaps al día siguiente y generar oportunidades de Episodic Pivots.

> Los cambios de precios son el resultado de la oferta y la demanda diarias en el mercado de subastas más grande del mundo. Los gráficos pueden decirle cuándo una acción no está actuando correctamente.
>
> — *Capítulo 2 - Cómo leer gráficos como un profesional*

*Concordancia técnica:* El movimiento en after-hours de SANA anticipa potencial gap. O'Neil documenta que los movimientos fuera de hora pueden indicar acumulación/distribución institucional.

---

### ATR-041 — GLXY

Ricky monitorea: 'GLXY la estoy vigilando, igual cierro antes del stop si veo que no termina de aguantar el vwap'. Gestión proactiva de la posición: si el precio no sostiene el VWAP como soporte, se cierra antes de que el stop loss formal sea alcanzado. El VWAP funciona como indicador de salida dinámico.

**Gestión de riesgo:** Salida anticipada basada en pérdida del VWAP como soporte, antes de que se active el stop loss formal. Esto es una técnica de gestión activa para reducir pérdidas cuando la acción del precio deteriora la tesis del trade.

> Debe aprender a vender siempre acciones rápidamente cuando tienes una pequeña pérdida en lugar de esperar y esperar que regresen. Es su trabajo estar en sintonía con el mercado.
>
> — *Capítulo 10 - Cuando debe vender y eliminar todas las pérdidas... sin excepción*

*Concordancia técnica:* Ricky cierra GLXY antes del stop formal si pierde el VWAP. Esto es gestión proactiva de riesgo que O'Neil recomienda: anticiparse al stop cuando la tesis se deteriora.

---

### ATR-042 — BNTX

panxo reporta: 'BNTX barrió mi stop y luego se recuperó, esto AM'. Un caso de stop sweep (o shakeout) donde el precio rompe el stop loss para luego recuperarse, generando una pérdida realizada que se habría evitado con un stop más amplio. Esto genera la disyuntiva entre stops ajustados (más tamaño) vs stops amplios (más riesgo por trade).

**Gestión de riesgo:** Cristianara comenta sobre este tema: 'Él busca stops más ajustados, lo que implica que la acción necesita moverse un menor porcentaje para [alcanzar el target]'. Stops ajustados permiten mayor tamaño de posición pero incrementan la probabilidad de ser stopped out por ruido.

> La formación del área del mango generalmente toma más de una o dos semanas y tiene una tendencia a la baja del precio o 'sacudida' donde el precio cae por debajo de un punto bajo anterior en el mango.
>
> — *Capítulo 2 - Características básicas del área del mango de una taza / Shakeout*

*Concordancia técnica:* BNTX barrió el stop y se recuperó: el shakeout que O'Neil describe. Stops ajustados aumentan el riesgo de ser eliminado por ruido, pero permiten mayor tamaño de posición.

---

### ATR-043 — SCCO / TW / CVNA

Ale menciona sus posiciones: '$SCCO $TW $CVNA llevo yo'. Múltiples posiciones abiertas en tickers de distintos sectores. Destaca '$TW' como 'Hermosa' y '$SCCO' como posición activa. CVNA (Carvana) es un clásico growth/momentum stock. La diversificación entre sectores reduce la correlación de la cartera.

> Como inversionista individual que posee 5, 10 o 20 acciones, no tiene una desventaja de gran tamaño. Algunas de sus acciones pueden caer sustancialmente.
>
> — *Capítulo 12 - Administración del dinero: si diversifica, invierta para el recorrido, margen de uso*

*Concordancia técnica:* SCCO, TW y CVNA en distintos sectores reflejan la diversificación que O'Neil recomienda para reducir correlación y riesgo de cartera.

---

### ATR-044 — NVDA / ARM

Ricky posiciona la cartera: 'nos hemos posicionado en $NVDA $ARM con la estructura [correcta]'. Entrada conjunta en los dos líderes de semiconductores con enfoque en la estructura del gráfico (bases, breakouts). Ricky confirma: 'Si, $ARM +3.5% $NVDA'. ARM muestra liderazgo relativo. Posteriormente: '$ARM volando' confirma aceleración del momentum.

> Debe comprar las empresas realmente grandes, aquellas que lideran sus industrias y son las número uno en sus campos. Busque a los líderes genuinos y evite los rezagados.
>
> — *Capítulo 7 - L = Líder o rezagado / Compre entre las mejores dos o tres acciones de un grupo*

*Concordancia técnica:* NVDA y ARM como líderes de semiconductores siguen la 'L' de CAN SLIM. El trader posiciona la cartera en los líderes del sector, exactamente lo que prescribe O'Neil.

---

### ATR-045 — DJT

Ricky observa: 'También hay que observar $DJT Trump Media & Technology como [posible play]'. DJT como play de momentum político/especulativo. La naturaleza especulativa del ticker requiere cautela extra en el tamaño de posición.

> Se necesitan las acciones de uno, dos o tres principales en un grupo industrial fuerte. Las grandes acciones pueden tener un crecimiento increíble, mientras que otros en el paquete pueden apenas moverse.
>
> — *Capítulo 7 - L = Líder o rezagado*

*Concordancia técnica:* DJT como play especulativo requiere cautela. O'Neil advierte que las acciones especulativas tienen su lugar pero con gestión de riesgo estricta.

---

### ATR-046 — INSG

Ricky recomienda: 'Recomiendo leer el post sobre $INSG en #daily-focus para entender cuando es óptimo entrar en una [posición]'. INSG como caso de estudio para el timing de entrada óptimo, posiblemente relacionado con un breakout de base o pullback a soporte.

> No basta con comprar acciones que muestren la fortaleza de precio relativa más alta. Debería comprar acciones que están formándose mejor que el mercado general cuando están comenzando a emerger de períodos sólidos de construcción de bases.
>
> — *Capítulo 2 - Cómo usar correctamente la fuerza del precio relativo / Puntos de pivote*

*Concordancia técnica:* El post sobre INSG en daily-focus para entender timing de entrada óptimo refleja la enseñanza de O'Neil sobre el punto pivote exacto de compra.

---

### ATR-047 — CLLS

Ricky reporta: 'Ya sacándole un 17% a $CLLS'. Trade exitoso con ganancia del 17%, lo cual representa aproximadamente 2-4R dependiendo del stop loss utilizado. El porcentaje de ganancia sugiere un swing trade exitoso con holding de varios días.

> Baruch: 'Si un especulador tiene razón la mitad de las veces, está alcanzando un buen promedio. Incluso acertar 3 o 4 veces de cada 10 debería rendir una fortuna a una persona si reduce las pérdidas rápidamente'.
>
> — *Capítulo 10 - El método de mercado secreto de Bernard Baruch para ganar millones*

*Concordancia técnica:* 17% de ganancia en CLLS representa aproximadamente 2-4R. O'Neil demuestra que trades exitosos de pocos R multiplicados generan rentabilidad compuesta.

---

### ATR-048 — ROOT

ron_smt muestra convicción: 'Siempre te tuve fe $ROOT'. ROOT (Root Inc., insurtech) como posición mantenida con convicción a pesar de posibles altibajos. La fe en el ticker sugiere que los fundamentos o la estructura técnica soportan la tesis de inversión.

> Si posee una cartera de acciones, debe aprender a vender primero las de peor desempeño y conservar las mejores un poco más. Observe sus mejores selecciones para ver si se convierten en grandes ganadores.
>
> — *Capítulo 7 - Cómo separar a los líderes de los rezagados*

*Concordancia técnica:* La convicción en ROOT a pesar de altibajos sigue el principio de O'Neil de dar tiempo a los ganadores potenciales mientras se cumple la tesis.

---

### ATR-049 — MELI

Mencionado en el contexto de la discusión general como ticker de referencia. Mercado Libre como líder latinoamericano con estructura de growth.

> La calificación RS promedio de las acciones con mejor desempeño antes de sus mayores incrementos fue de 87. Busque a los líderes genuinos y evite los rezagados.
>
> — *Capítulo 7 - L = Líder o rezagado*

*Concordancia técnica:* MELI como líder latinoamericano de growth sigue la 'L' de CAN SLIM: comprar el número uno en su categoría.

---

### ATR-050 — JNVR

Kingluis reporta: 'esta se nos escapó $JNVR'. Oportunidad de trading perdida donde el setup se ejecutó sin ellos. Las oportunidades perdidas son parte del trading y el grupo las usa como lección para mejorar el proceso de screening y ejecución.

*Estrategia de campo sin respaldo académico directo.*

---

## Estrategias de Swing Trading

### ATR-021 — MMM

panxo pregunta sobre MMM. Ricky rechaza el setup: '$MMM no me gusta, 1.75 de ADR'. Un ADR (Average Daily Range) de 1.75% es demasiado bajo para la metodología del grupo, que busca ADR mayor a 3% para garantizar suficiente movimiento intradía que justifique el riesgo del trade. La falta de volatilidad elimina el interés.

**Gestión de riesgo:** Filtro de ADR mínimo de 3% como requisito para considerar un trade. Un ADR bajo implica que el potencial de ganancia es insuficiente en relación al riesgo asumido.

> Tres de cada cuatro grandes ganadores del mercado en el pasado fueron acciones de crecimiento... Las acciones que seleccione deben mostrar un aumento porcentual importante en las ganancias por acción trimestrales actuales.
>
> — *Capítulo 3 - C = Ganancias trimestrales grandes o aceleradas actuales y Ventas*

*Concordancia técnica:* MMM con ADR de 1.75% no cumple el perfil de volatilidad para growth/momentum que el libro exige. Las acciones de crecimiento requieren movimiento direccional; sin ADR no hay oportunidad de ganancia que justifique el riesgo.

---

---

*Manual generado a partir de 55 setups documentados. 54/55 con respaldo teórico
de «Cómo ganar dinero en acciones» (William J. O'Neil). El setup ATR-050 (JNVR)
no cuenta con patrón defensible: observación de oportunidad perdida sin setup ejecutable.*