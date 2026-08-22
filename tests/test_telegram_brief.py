"""Tests TDD para el rediseño narrativo del brief de Telegram (Issue #67).

Verifica estructura y contenido de las 8 secciones narrativas, uso de emojis
UTF-8 reales (sin placeholders), estados en lenguaje natural y HTML válido
para Telegram (parse_mode=HTML).
"""

import re
from unittest.mock import patch

import pytest

from src.utils.terminal_gui import build_telegram_brief

# ── Fixtures de datos ────────────────────────────────────────────────────────

GAMMA_DATA = {"date": "2026-07-14", "price": 6450.0, "dix": 0.438, "gex": 6.0e9}

HOT_SECTORS = [
    {"sector_etf": "XLF", "rank": 1, "rs": 2.83, "strength": "+283%", "tradeable": True},
    {"sector_etf": "XLV", "rank": 2, "rs": 1.88, "strength": "+188%", "tradeable": True},
    {"sector_etf": "XLU", "rank": 3, "rs": 1.46, "strength": "+146%", "tradeable": True},
    {"sector_etf": "XLI", "rank": 4, "rs": 0.79, "strength": "+79%", "tradeable": False},
]


def _candidato_base(**overrides):
    """Candidato genérico que pasa el gate de calidad de datos como 'ok'."""
    base = {
        "price": 78.9,
        "breakout_level": 72.5,
        "rs_pct": 89,
        "score": 89,
        "proximity_score": 70,
        "breakout": False,
        "ma_stack": True,
        "dist_sma20_pct": 8.65,
        "max_dist_sma20": 6.77,
        "rvol": 1.2,
        "adr": 2.1,
        "dollar_volume_m": 250.5,
        "sector_etf": "XLF",
        "waiting_for": "OK",
        "primary_reason": "Extendido de SMA20",
        "reasons": ["Extendido de SMA20"],
        "themes": ["Fintech"],
    }
    base.update(overrides)
    return base


def make_snapshot(breadth_overrides=None, regime_ok=True):
    """Snapshot realista fresco por llamada (evita mutaciones entre tests)."""
    breadth = {
        "vix": 17.16,
        "new_highs": 120,
        "new_lows": 40,
        "advances": 300,
        "declines": 180,
        "verdict": "GREEN",
        "sample_size": 505,
        "put_call": 0.85,
        "data_status": "OK",
    }
    if breadth_overrides:
        breadth.update(breadth_overrides)

    return {
        "date": "2026-07-14",
        "data_as_of": "2026-07-13",
        "regime_ok": regime_ok,
        "signals": [],
        "universe_size": 555,
        "scanner_universe_count": 555,
        "breadth": breadth,
        "watchlist_detail": {
            # Extendido sobre su media -> 'Consolidar - no comprar aún'
            "PYPL": _candidato_base(),
            # Breakout listo, sin bloqueos -> 'Trigger listo'
            "JPM": _candidato_base(
                price=208.7,
                breakout_level=210.4,
                rs_pct=92,
                proximity_score=95,
                breakout=True,
                dist_sma20_pct=3.1,
                rvol=1.4,
                waiting_for="OK",
                primary_reason="OK",
                reasons=[],
            ),
            # Sin ruptura todavía -> 'Esperando ruptura'
            "BAC": _candidato_base(
                price=44.1,
                breakout_level=45.8,
                rs_pct=84,
                proximity_score=88,
                breakout=False,
                dist_sma20_pct=2.4,
                rvol=1.3,
                waiting_for="breakout",
                primary_reason="Falta breakout",
                reasons=["Falta breakout"],
            ),
            # Fuera de sectores calientes (XLE) -> aparece en Top Global
            "PBF": _candidato_base(
                price=28.4,
                breakout_level=29.7,
                rs_pct=99,
                proximity_score=60,
                breakout=True,
                dist_sma20_pct=4.2,
                rvol=1.5,
                sector_etf="XLE",
                themes=["Energía"],
            ),
        },
    }


def construir_brief(snapshot, gamma=None):
    """Ejecuta build_telegram_brief con dependencias externas mockeadas.

    Retorna (texto, botones) del brief generado.
    """
    datos_gamma = dict(gamma) if gamma else dict(GAMMA_DATA)
    with (
        patch(
            "src.utils.terminal_gui.fetch_gamma_data",
            return_value=datos_gamma,
        ),
        patch(
            "src.utils.terminal_gui._build_hot_sectors",
            return_value=[dict(s) for s in HOT_SECTORS],
        ),
        patch(
            "src.utils.terminal_gui.get_ticker_sector_mapping",
            return_value={},
        ),
    ):
        texto, botones = build_telegram_brief(snapshot)
    return texto, botones


# ── Constantes de verificación ───────────────────────────────────────────────

PLACEHOLDER_RE = re.compile(r"\[(U\+|OK|WARN|BOLT)[^\]]*\]")
TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)")
TELEGRAM_ALLOWED_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "span", "a", "code", "pre", "blockquote", "tg-spoiler",
}


@pytest.fixture(name="brief")
def fixture_brief():
    """Brief narrativo estándar para la mayoría de los tests."""
    return construir_brief(make_snapshot())


# ── Criterio 1: emojis UTF-8 reales, cero placeholders ──────────────────────


def test_no_placeholder_tokens_en_texto_ni_botones(brief):
    texto, botones = brief
    completo = texto + "".join(
        b["text"] for fila in botones for b in fila
    )
    coincidencias = PLACEHOLDER_RE.findall(completo)
    assert not coincidencias, f"Placeholders encontrados: {coincidencias[:5]}"


def test_emojis_reales_presentes_por_seccion(brief):
    texto, _ = brief
    for emoji in ("🚀", "🚦", "🏛", "📊", "🎯", "🚨", "🏆"):
        assert emoji in texto, f"Falta el emoji real {emoji} en el brief"


# ── Sección 1: Header ────────────────────────────────────────────────────────


def test_header_momentum_signals_con_fecha_y_universo(brief):
    texto, _ = brief
    assert "MOMENTUM SIGNALS" in texto
    assert "2026-07-14" in texto
    assert "Universo" in texto
    assert "555" in texto


# ── Sección 2: Semáforo de entorno ───────────────────────────────────────────


def test_semaforo_favorable_con_interpretacion_narrativa_del_vix(brief):
    texto, _ = brief
    assert "SEMÁFORO" in texto
    assert "ENTORNO FAVORABLE" in texto
    # El número del VIX debe venir acompañado de interpretación narrativa
    assert "17.16" in texto
    assert "tranquil" in texto.lower()


def test_semaforo_bloqueado_cuando_regime_fail():
    texto, _ = construir_brief(make_snapshot(regime_ok=False))
    assert "ENTORNO BLOQUEADO" in texto


def test_semaforo_bloqueado_narra_proteccion():
    texto, _ = construir_brief(
        make_snapshot(breadth_overrides={"vix": 33.4}, regime_ok=False)
    )
    assert "33.4" in texto
    # Narrativa, no solo número: pide prudencia/esperar
    assert any(
        palabra in texto.lower()
        for palabra in ("panico", "pánico", "proteg", "esperar")
    )


def test_semaforo_cautela_con_vix_elevado():
    texto, _ = construir_brief(
        make_snapshot(breadth_overrides={"vix": 24.5})
    )
    assert "CAUTELA" in texto
    assert "24.5" in texto


# ── Sección 3: Rastro Institucional ──────────────────────────────────────────


def test_rastro_institucional_narra_gex_como_soporte(brief):
    texto, _ = brief
    assert "RASTRO INSTITUCIONAL" in texto
    # GEX positivo narrado como piso de soporte (no solo valor crudo)
    assert "$6.0B" in texto
    assert "soporte" in texto.lower()


def test_rastro_institucional_narra_dix_dark_pool(brief):
    texto, _ = brief
    assert "43.8%" in texto
    assert "Dark Pool" in texto
    # Interpretación narrativa del DIX (acumulación institucional)
    assert any(
        palabra in texto.lower()
        for palabra in ("acumulacion", "acumulación", "smart money", "compra oculta")
    )


def test_rastro_gex_negativo_narra_resistencia():
    # Variante con GEX negativo: la narrativa cambia de piso a techo/resistencia
    texto, _ = construir_brief(
        make_snapshot(),
        gamma={"date": "2026-07-14", "price": 6400.0, "dix": 0.25, "gex": -2.0e9},
    )
    assert "RASTRO INSTITUCIONAL" in texto
    assert "-$2.0B" in texto or "$-2.0B" in texto
    assert any(
        palabra in texto.lower()
        for palabra in ("techo", "resistencia", "volatilidad")
    )
    # DIX bajo: compra oculta floja
    assert "25.0%" in texto


# ── Sección 4: Sectores en Rotación ─────────────────────────────────────────


def test_sectores_rotacion_top4_con_nombres_espanol(brief):
    texto, _ = brief
    assert "SECTORES EN ROTACIÓN" in texto
    for etf, nombre in (
        ("XLF", "Financieras"),
        ("XLV", "Salud"),
        ("XLU", "Utilities"),
        ("XLI", "Industriales"),
    ):
        assert etf in texto, f"Falta el ETF {etf}"
        assert nombre in texto, f"Falta el nombre en español: {nombre}"
    # Fuerza relativa del sector líder expresada en %
    assert "283%" in texto


# ── Sección 5: Candidatos del Día ────────────────────────────────────────────


def test_candidatos_agrupados_en_sector_caliente_con_rs(brief):
    texto, _ = brief
    assert "CANDIDATOS DEL DÍA" in texto
    # Agrupados bajo el sector caliente líder
    assert "Financieras" in texto
    for ticker in ("PYPL", "JPM", "BAC"):
        assert ticker in texto, f"Falta el candidato {ticker}"
    # Nivel de ruptura visible
    assert "72.50" in texto


def test_candidato_estados_en_lenguaje_natural(brief):
    texto, _ = brief
    assert "Consolidar - no comprar aún" in texto
    assert "Esperando ruptura" in texto
    assert "Trigger listo" in texto


def test_candidatos_excluye_sectores_no_calientes(brief):
    texto, _ = brief
    seccion_candidatos = texto[
        texto.index("CANDIDATOS DEL DÍA"):texto.index("ALERTA PRIORITARIA")
    ]
    # PBF pertenece a XLE (no caliente): vive solo en Top Global
    assert "PBF" not in seccion_candidatos


def test_motivo_estado_explicado_con_numeros(brief):
    texto, _ = brief
    # Motivo del estado extendido con números: extensión y límite sano
    assert "extendido 8.65%" in texto
    assert "límite sano: 6.77%" in texto


# ── Criterio nuevo: mini-línea de aprendizaje 'Objetivo' por candidato ──────


def _bloque_candidato(texto: str, ticker: str) -> str:
    """Extrae el fragmento del brief correspondiente a un solo candidato.

    Parámetros: texto (brief completo), ticker (símbolo buscado).
    Retorna: substring desde la viñeta del candidato hasta la siguiente.
    """
    seccion = texto[texto.index("CANDIDATOS DEL DÍA"):texto.index("ALERTA PRIORITARIA")]
    inicio = seccion.index(f"• <b>{ticker}</b>")
    siguiente = seccion.find("• <b>", inicio + len(f"• <b>{ticker}</b>"))
    fin = siguiente if siguiente != -1 else len(seccion)
    return seccion[inicio:fin]


def test_objetivo_en_trigger_listo_con_nivel_y_rvol(brief):
    texto, _ = brief
    bloque = _bloque_candidato(texto, "JPM")  # Trigger listo
    assert "→ 🎯 <b>Objetivo:</b>" in bloque
    assert "Breakout de 210.40" in bloque
    assert "RVOL &gt; 1.20" in bloque
    assert "alta convicción" in bloque


def test_objetivo_en_esperando_ruptura_con_nivel_y_rvol(brief):
    texto, _ = brief
    bloque = _bloque_candidato(texto, "BAC")  # Esperando ruptura
    assert "→ 🎯 <b>Objetivo:</b>" in bloque
    assert "Breakout de 45.80" in bloque
    assert "RVOL &gt; 1.20" in bloque
    assert "alta convicción" in bloque


def test_objetivo_reemplaza_accion_sugerida_en_estados_de_ruptura(brief):
    texto, _ = brief
    for ticker in ("JPM", "BAC"):
        bloque = _bloque_candidato(texto, ticker)
        # La línea Objetivo subsume la acción operativa previa
        assert "Acción sugerida" not in bloque


def test_consolidar_mantiene_enfriamiento_sin_linea_objetivo(brief):
    texto, _ = brief
    bloque = _bloque_candidato(texto, "PYPL")  # Consolidar - no comprar aún
    # Extendido: nada que romper todavía, conserva su guía de enfriamiento
    assert "Objetivo:" not in bloque
    assert "→ Acción sugerida:" in bloque
    assert "Esperar que se enfríe hacia la media antes de re-evaluar" in bloque


def test_umbral_rvol_alta_conviccion_constante_nombrada():
    from src.utils.terminal_gui import HIGH_CONVICTION_RVOL

    assert isinstance(HIGH_CONVICTION_RVOL, float)
    assert HIGH_CONVICTION_RVOL == pytest.approx(1.20)


# ── Sección 6: Alerta Prioritaria ────────────────────────────────────────────


def test_alerta_prioritaria_call_to_action(brief):
    texto, _ = brief
    assert "ALERTA PRIORITARIA" in texto
    texto_lower = texto.lower()
    # Call-to-action claro: qué vigilar y condición de entrada
    assert "vigilar" in texto_lower or "accion" in texto_lower or "acción" in texto_lower
    assert "volumen" in texto_lower


# ── Sección 7: Top Global ────────────────────────────────────────────────────


def test_top_global_fuera_de_sectores_calientes(brief):
    texto, _ = brief
    assert "TOP GLOBAL" in texto
    # PBF pertenece a XLE, que NO está entre los sectores calientes del fixture
    assert "PBF" in texto
    assert "99" in texto
    # Nota de vigilar presente
    assert "vigilar" in texto.lower()


# ── Sección 8: Footer ────────────────────────────────────────────────────────


def test_footer_disclaimer_y_metricas_explicadas(brief):
    texto, _ = brief
    cola = texto[texto.rindex("TOP GLOBAL"):]
    assert "no es asesoria" in cola.lower() or "no es asesoría" in cola.lower()
    # Explicación de métricas clave
    assert "RS" in cola or "Fuerza Relativa" in cola
    assert "RVOL" in cola


# ── Criterio 7: HTML compatible con Telegram parse_mode=HTML ────────────────


def test_html_solo_usa_tags_permitidas_por_telegram(brief):
    texto, _ = brief
    for _, tag in TAG_RE.findall(texto):
        assert tag in TELEGRAM_ALLOWED_TAGS, f"Tag HTML no permitida: <{tag}>"


def test_html_tags_balanceados(brief):
    texto, _ = brief
    conteo: dict = {}
    for cierre, tag in TAG_RE.findall(texto):
        clave = f"</{tag}>" if cierre else f"<{tag}>"
        conteo[clave] = conteo.get(clave, 0) + 1
    for tag in {t for _, t in TAG_RE.findall(texto)}:
        assert conteo.get(f"<{tag}>", 0) == conteo.get(f"</{tag}>", 0), (
            f"Tag <{tag}> desbalanceada"
        )


# ── Contrato de retorno preservado para callers existentes ──────────────────


def test_contrato_retorno_tupla_str_list(brief):
    texto, botones = brief
    assert isinstance(texto, str)
    assert isinstance(botones, list)
    for fila in botones:
        assert isinstance(fila, list)
        for boton in fila:
            assert "text" in boton
            assert "callback_data" in boton


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
