# Proposal: feat(telegram): Redesign pre-market brief with narrative format and real UTF-8 emojis

## Intent
### Propósito
Rediseñar el reporte pre-market de Telegram (`build_telegram_brief` en `src/utils/terminal_gui.py`) para reemplazar el formato técnico/operativo actual por un formato narrativo human-friendly con secciones claras, lenguaje accesible y emojis UTF-8 reales (eliminando los placeholders `[U+XXXX]` y tokens `[OK]`/`[WARN]`).

El nuevo formato debe seguir esta estructura de secciones:
1. **Header**: MOMENTUM SIGNALS + fecha + universo
2. **Semáforo de entorno**: Resumen ejecutivo del régimen (favorable/cautela/bloqueado) con VIX interpretado
3. **Rastro Institucional**: Gamma Exposure + Dark Pool (DIX) con interpretación narrativa
4. **Sectores en Rotación**: Top 4 sectores calientes con RS% y nombre en español
5. **Candidatos del Día**: Agrupados por sector caliente, con RS, estado narrativo (Consolidar/Esperando ruptura/Trigger listo), nivel de breakout, motivo, y acción sugerida
6. **Alerta Prioritaria**: Call-to-action claro del sector/ticker más relevante
7. **Top Global**: Mejores RS fuera de sectores calientes, con nota de vigilar
8. **Footer**: Disclaimer + explicación de métricas clave

### Acceptance Criteria
- [ ] Emojis UTF-8 reales en todo el mensaje (sin placeholders `[U+XXXX]`, `[OK]`, `[WARN]`, `[BOLT]`, etc.)
- [ ] Las 8 secciones del formato narrativo generadas desde los datos existentes del snapshot
- [ ] Estado de cada candidato en lenguaje natural: 'Consolidar - no comprar aún' / 'Esperando ruptura' / 'Trigger listo'
- [ ] Motivo del estado explicado (ej: 'precio extendido X% sobre su media, límite sano: Y%')
- [ ] Interpretación narrativa del VIX (no solo el número)
- [ ] Interpretación narrativa del Gamma/DIX (no solo valores crudos)
- [ ] Formato HTML compatible con Telegram parse_mode=HTML
- [ ] Tests pytest para `build_telegram_brief` verificando estructura y contenido de cada sección
- [ ] Ruff limpio sobre archivos modificados
- [ ] Commit con formato: [Telegram] Redesign pre-market brief with narrative format. Fixes #<N>

### Baseline a no degradar
N/A (feature aditiva, no toca backtest core).

### Módulos sensibles
N/A (no modifica `src/backtest/` ni `src/data/`).

### Módulo objetivo de la inspección
`src/utils/terminal_gui.py` (función `build_telegram_brief`) y `tests/test_telegram_brief.py`

### Referencia de formato objetivo
\\\html
<b>MOMENTUM SIGNALS</b> | 14 Jul 2026
<i>Datos al cierre del 13/07 · Universo: 555 activos</i>

<b>🚦 SEMÁFORO: ENTORNO FAVORABLE</b>
VIX en 17.16 (zona tranquila) + acumulación institucional activa.
Momento de <b>buscar breakouts</b>, no de esperar en el banco.

<b>🏛 RASTRO INSTITUCIONAL</b>
Gamma Exposure de \.6B actuando como piso de soporte.
43.8% del volumen fue compra oculta (Dark Pool) → ligera baja vs. ayer, pero el smart money sigue posicionado.

<b>📊 SECTORES EN ROTACIÓN</b>
1. Financiero (XLF) → Fuerza 283% 🔥
2. Salud (XLV) → Fuerza 188% 🔥
3. Utilities (XLU) → Fuerza 146% 📈
4. Industriales (XLI) → Fuerza 79%

<b>🎯 CANDIDATOS DEL DÍA</b> → Sector Financiero 🔥

<b>PYPL</b> (PayPal) → Fintech/Pagos
Fuerza Relativa: 89/100 🔥 (Top 15%)
⏸ <b>Estado: Consolidar → no comprar aún</b>
→ Motivo: precio extendido 8.65% sobre su media (límite sano: 6.77%).
→ A vigilar: que se enfríe hacia la media antes de re-evaluar.

<b>🚨 ALERTA PRIORITARIA</b>
Sector Financiero concentra el mejor momentum del mercado hoy.
→ <b>Acción:</b> vigilar JPM y MS → si rompen su nivel clave <b>con volumen</b>, son los primeros en gatillar señal de entrada.

<b>🏆 TOP GLOBAL (fuera de sectores calientes)</b>
- PBF Energy → Fuerza 99/100 🔥
- VLO (Energía) → Fuerza 90/100

<i>Reporte informativo, no es asesoría de inversión.</i>
\\\

### Notas técnicas para el agente
- Los datos de VIX, Gamma, DIX ya están disponibles en el snapshot vía `fetch_gamma_data()` y `breadth`
- Los sectores calientes se obtienen de `_build_hot_sectors()`
- Los candidatos y su estado (extendido/breakout/trigger) ya se calculan en `_estado_simple()`
- Los emojis deben ser UTF-8 directos en el source (como hace `scripts/finviz_live_promoter.py`), NO placeholders
- En VPS Linux no hay problema de encoding. Para Windows console, `telegram_client.py` envía vía HTTP (sin problema de stdout encoding)

## Context
URL: https://github.com/mmarcoschambi/swing-momentum-v1/issues/67
Labels: feat
