#!/usr/bin/env python3
"""
mock_telegram_alerts.py - Prototipo estético interactivo para el nuevo formato de reportes
de Telegram del bot quant.

Este script es autónomo, cumple con el protocolo scratch (no modifica archivos en src/) y
permite:
1. Generar el nuevo diseño de reporte de pre-market de Telegram usando tags HTML válidos.
2. Renderizar una simulación visual en la terminal usando colores ANSI para emular la estética final.
3. Imprimir el código HTML puro de Telegram listo para ser enviado/testeado en la API oficial.
4. Simular el cálculo de Position Sizing dinámico (E25) basado en volatilidad (ATR) y extensión (SMA20).
5. Enviar un mensaje de prueba real a Telegram si las variables de entorno están presentes.

Uso:
  python scratch/mock_telegram_alerts.py
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

# Resolver la raíz del proyecto para importar configs si fuera necesario de forma segura
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Intento de cargar dotenv si está disponible para envíos reales
try:
    from dotenv import load_dotenv
    wsl_env = Path("/home/marcos/trade/momentum-v2/.env")
    if wsl_env.exists():
        load_dotenv(dotenv_path=wsl_env)
    else:
        load_dotenv()
except ImportError:
    # Parser manual robusto si no está instalado python-dotenv
    for path in [PROJECT_ROOT / ".env", Path("/home/marcos/trade/momentum-v2/.env")]:
        if path.exists():
            try:
                for line in path.read_text().splitlines():
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
            except Exception:
                pass


# =====================================================================
# SIMULACIÓN DE POSITION SIZING DINÁMICO (E25) - FIRST PRINCIPLES
# =====================================================================

def simulate_e25_sizing(
    ticker: str,
    entry_price: float,
    dist_sma20: float,
    adr_pct: float,
    atr_14: float,
    account_capital: float = 100000.0,
    risk_pct: float = 0.01  # 1% de riesgo de la cuenta por default
) -> dict:
    """
    Simula el algoritmo de sizing dynamic de producción (E25 / v2_atlas_informed).
    Calcula el factor de sizing, el stop loss adecuado por ATR y las acciones a comprar.
    """
    # Configuración de E25 (v2_atlas_informed)
    comfort = 6.76
    valley = 10.0
    mid = 15.0
    high = 25.0
    extreme_cutoff = 35.0
    max_pct = 50.0
    adr_exc = 8.0

    # 1. Calcular Sizing Factor (Factor de Penalización)
    if dist_sma20 <= comfort:
        sizing_factor = 1.0
        reason = "comfort_zone (saludable)"
    elif dist_sma20 <= valley:
        # Valle de la muerte: penalización fuerte 1.0 -> 0.3
        ratio = (dist_sma20 - comfort) / (valley - comfort)
        sizing_factor = 1.0 - (ratio * (1.0 - 0.3))
        reason = f"v2_valley_penalty (valle: dist {dist_sma20:.1f}%)"
    elif dist_sma20 <= mid:
        # Sweetspot Atlas Room: recupera tamaño 0.3 -> 0.5
        ratio = (dist_sma20 - valley) / (mid - valley)
        sizing_factor = 0.3 + (ratio * (0.5 - 0.3))
        reason = f"v2_atlas_sweetspot (recupera: dist {dist_sma20:.1f}%)"
    elif dist_sma20 <= high:
        # Extensión moderada-alta: penalización 0.5 -> 0.3
        ratio = (dist_sma20 - mid) / (high - mid)
        sizing_factor = 0.5 - (ratio * (0.5 - 0.3))
        reason = f"v2_high_ext_penalty (dist {dist_sma20:.1f}%)"
    elif dist_sma20 <= extreme_cutoff:
        # Extensión extrema: penalización 0.3 -> 0.1
        ratio = (dist_sma20 - high) / (extreme_cutoff - high)
        sizing_factor = 0.3 - (ratio * (0.3 - 0.1))
        reason = f"v2_extreme_ext_penalty (dist {dist_sma20:.1f}%)"
    else:
        # Bloqueado a menos que sea un ADR muy alto
        if adr_pct > adr_exc and dist_sma20 <= max_pct:
            sizing_factor = 0.15
            reason = "extreme_adr_exception"
        else:
            sizing_factor = 0.0
            reason = "blocked_extreme_extension"

    # 2. Calcular Stop Loss basado en ATR (ej: 1.5x ATR por debajo de la entrada)
    stop_distance_usd = atr_14 * 1.5
    stop_loss_price = entry_price - stop_distance_usd
    stop_loss_pct = (stop_distance_usd / entry_price) * 100

    # 3. Calcular riesgo monetario efectivo ajustado por E25
    raw_risk_budget = account_capital * risk_pct
    adjusted_risk_budget = raw_risk_budget * sizing_factor

    # 4. Calcular cantidad de acciones (Shares)
    if stop_distance_usd > 0 and sizing_factor > 0:
        shares = int(adjusted_risk_budget / stop_distance_usd)
        capital_allocated = shares * entry_price
        capital_allocated_pct = (capital_allocated / account_capital) * 100
    else:
        shares = 0
        capital_allocated = 0.0
        capital_allocated_pct = 0.0

    return {
        "ticker": ticker,
        "entry_price": entry_price,
        "dist_sma20": dist_sma20,
        "adr_pct": adr_pct,
        "atr_14": atr_14,
        "sizing_factor": round(sizing_factor, 2),
        "sizing_reason": reason,
        "stop_loss_price": round(stop_loss_price, 2),
        "stop_loss_pct": round(stop_loss_pct, 2),
        "shares": shares,
        "capital_allocated": round(capital_allocated, 2),
        "capital_allocated_pct": round(capital_allocated_pct, 2),
        "adjusted_risk_budget": round(adjusted_risk_budget, 2),
    }


# =====================================================================
# RENDERIZADORES DE MOCK: HTML (TELEGRAM) Y ANSI (CONSOLA)
# =====================================================================

def render_html_report(data: dict) -> str:
    """
    Genera el string HTML completo que se enviaría a Telegram.
    Soporta únicamente los tags válidos: <b>, <i>, <code>, <pre>, <a>.
    """
    # Formatear la fecha
    date_str = data["metadata"]["date"]
    close_date_str = data["metadata"]["close_date"]
    universe_size = data["metadata"]["universe_size"]

    # Semáforo e info macro
    vix = data["macro"]["vix"]
    regime_status = data["macro"]["regime_status"]
    regime_desc = data["macro"]["regime_description"]
    gamma = data["macro"]["gamma_exposure"]
    dark_pool = data["macro"]["dark_pool_pct"]
    dark_pool_desc = data["macro"]["dark_pool_desc"]

    # Construir sectores
    sector_lines = []
    for idx, sec in enumerate(data["sectors"], 1):
        flame_count = "🔥" * (4 - idx) if idx <= 3 else ""
        sector_lines.append(f"{idx}. {sec['name']} ({sec['etf']}) — Fuerza {sec['force_pct']}% {flame_count}")
    sectors_text = "\n".join(sector_lines)
    sectors_note = data["macro"]["sectors_note"]

    # Construir candidatos del día
    candidates_lines = []
    for cand in data["candidates"]:
        ticker = cand["ticker"]
        name = cand["name"]
        subsector = cand["subsector"]
        fr = cand["fr"]
        top_pct = cand["top_pct"]
        state = cand["state"]
        
        # Calcular Sizing dinámico para este candidato (First Principles)
        sizing = simulate_e25_sizing(
            ticker=ticker,
            entry_price=cand["price"],
            dist_sma20=cand["dist_sma20"],
            adr_pct=cand["adr_pct"],
            atr_14=cand.get("atr", cand["price"] * 0.04) # 4% del precio si no se provee
        )

        # Si el candidato está bloqueado por extensión
        if sizing["sizing_factor"] <= 0:
            status_line = f"⚠️ <b>Estado: {state}</b>"
            motivo_line = f"🛑 Motivo: precio extendido {cand['dist_sma20']:.2f}% sobre su media (límite sano: {comfort_limit(cand['dist_sma20'])}%). Entrar ahora es perseguir el precio."
            action_line = f"📍 A vigilar: que se enfríe hacia la media antes de re-evaluar."
            cand_body = f"{status_line}\n{motivo_line}\n{action_line}"
        else:
            status_line = f"⏳ <b>Estado: {state}</b>"
            level_line = f"🔑 Nivel clave (breakout): <b>${cand['breakout_level']:.2f}</b>"
            
            # Mostrar sizing si está en zona de advertencia (penalizado) pero no bloqueado
            if sizing["sizing_factor"] < 1.0:
                sizing_lbl = f"\n⚠️ <i>E25 Sizing Ajustado: {sizing['shares']} shares (${sizing['capital_allocated']:.2f} allocated · factor {sizing['sizing_factor']:.2f}x) debido a extensión del {cand['dist_sma20']:.1f}%</i>"
            else:
                sizing_lbl = f"\n👉 <i>E25 Sizing: {sizing['shares']} shares (${sizing['capital_allocated']:.2f} allocated)</i>"
            
            # Motivos o lo que falta
            if "rvol" in cand and cand["rvol"] >= 1.0:
                missing_line = f"✅ Interés comprador ya activo (RVOL {cand['rvol']:.2f}) — de los más cercanos a gatillar.{sizing_lbl}"
            else:
                missing_line = f"🛑 Falta: que rompa ese nivel Y que suba el interés (volumen aún bajo).{sizing_lbl}"
            cand_body = f"{status_line}\n{level_line}\n{missing_line}"

        fr_flame = "🔥" if fr >= 80 else ""
        fr_label = f" (Top {top_pct}%)" if top_pct else ""
        
        candidates_lines.append(
            f"<b>{ticker}</b> ({name}) · {subsector}\n"
            f"Fuerza Relativa: {fr}/100 {fr_flame}{fr_label}\n"
            f"{cand_body}"
        )
    candidates_text = "\n\n".join(candidates_lines)
    candidate_sector = data["metadata"]["candidate_sector"]

    # Alerta prioritaria
    alert_action = data["priority_alert"]["action"]
    alert_desc = data["priority_alert"]["description"]

    # Top Global
    global_lines = []
    for g in data["top_global"]:
        flame = "🔥" if g["fr"] >= 95 else ""
        global_lines.append(f"- {g['ticker']} ({g['sector']}) — Fuerza {g['fr']}/100 {flame}")
    global_text = "\n".join(global_lines)

    # Armado final del mensaje
    report_html = (
        f"🟢 <b>MOMENTUM SIGNALS</b> | {date_str}\n"
        f"<i>Datos al cierre del {close_date_str} · Universo: {universe_size} activos</i>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>🟢 SEMÁFORO: {regime_status}</b>\n"
        f"{regime_desc}\n\n"
        f"<b>🕵️ RASTRO INSTITUCIONAL</b>\n"
        f"Gamma Exposure de ${gamma}B actuando como piso de soporte.\n"
        f"{dark_pool}% del volumen fue compra oculta (Dark Pool) — {dark_pool_desc}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>🔥 SECTORES EN ROTACIÓN</b>\n"
        f"{sectors_text}\n\n"
        f"<i>{sectors_note}</i>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>🎯 CANDIDATOS DEL DÍA</b> — Sector {candidate_sector} 🔥\n\n"
        f"{candidates_text}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>🚨 ALERTA PRIORITARIA</b>\n"
        f"{alert_desc}\n"
        f"👉 <b>Acción:</b> {alert_action}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>🏆 TOP GLOBAL (fuera de sectores calientes)</b>\n"
        f"{global_text}\n\n"
        f"<i>💡 Nota: son los más fuertes del mercado hoy, aunque su sector aún no está en tendencia dominante. Vigilar, no priorizar.</i>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>📌 Recordatorio: \"Fuerza Relativa\" mide qué tan bien se mueve el activo vs. el resto del mercado. \"Nivel clave\" es el precio que debe romper para confirmar la señal — comprar antes de eso es anticiparse sin confirmación.</i>\n\n"
        f"<i>Reporte informativo, no es asesoría de inversión. Resultados históricos no garantizan resultados futuros.</i>"
    )
    return report_html


def comfort_limit(dist: float) -> str:
    """Helper para mostrar el límite sano simulado"""
    return "6.77"


def render_ansi_preview(html_text: str) -> str:
    """
    Convierte tags HTML básicos de Telegram a códigos de color ANSI para mostrar en consola
    y dar una previsualización estética súper interactiva.
    """
    ansi = html_text
    
    # Colores ANSI
    RESET = "\033[0m"
    BOLD = "\033[1m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Paleta premium del bot quant (MOMENTUM)
    GREEN = "\033[38;5;82m"   # Verde neón/vibrante
    ORANGE = "\033[38;5;208m" # Naranja para alertas
    CYAN = "\033[38;5;51m"    # Cyan para códigos y datos
    GRAY = "\033[38;5;245m"   # Gris para notas al pie e itálicas
    SEPARATOR = "\033[38;5;239m" # Gris oscuro para barras
    
    # Reemplazo de separador
    ansi = ansi.replace("━━━━━━━━━━━━━━━", f"{SEPARATOR}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    
    # Reemplazo de títulos y tags de formato
    # Nota: Insertamos colores ANSI manteniendo los tags HTML para evitar huérfanos
    ansi = ansi.replace("🟢 <b>MOMENTUM SIGNALS</b>", f"{GREEN}🟢 <b>MOMENTUM SIGNALS</b>{RESET}")
    ansi = ansi.replace("<b>🟢 SEMÁFORO:", f"<b>{GREEN}🟢 SEMÁFORO:")
    ansi = ansi.replace("<b>🕵️ RASTRO INSTITUCIONAL</b>", f"{GREEN}<b>🕵️ RASTRO INSTITUCIONAL</b>{RESET}")
    ansi = ansi.replace("<b>🔥 SECTORES EN ROTACIÓN</b>", f"{ORANGE}<b>🔥 SECTORES EN ROTACIÓN</b>{RESET}")
    ansi = ansi.replace("<b>🎯 CANDIDATOS DEL DÍA</b>", f"{CYAN}<b>🎯 CANDIDATOS DEL DÍA</b>{RESET}")
    ansi = ansi.replace("<b>🚨 ALERTA PRIORITARIA</b>", f"{ORANGE}<b>🚨 ALERTA PRIORITARIA</b>{RESET}")
    ansi = ansi.replace("<b>🏆 TOP GLOBAL</b>", f"{GREEN}<b>🏆 TOP GLOBAL</b>{RESET}")
    
    # Reemplazos genéricos
    # Reemplazo de <b>...</b> a BOLD
    parts = ansi.split("<b>")
    new_parts = [parts[0]]
    for p in parts[1:]:
        if "</b>" in p:
            subparts = p.split("</b>")
            new_parts.append(f"{BOLD}{subparts[0]}{RESET}" + "".join(subparts[1:]))
        else:
            new_parts.append(p)
    ansi = "".join(new_parts)

    # Reemplazo de <i>...</i> a ITALIC + GRAY
    parts = ansi.split("<i>")
    new_parts = [parts[0]]
    for p in parts[1:]:
        if "</i>" in p:
            subparts = p.split("</i>")
            new_parts.append(f"{ITALIC}{GRAY}{subparts[0]}{RESET}" + "".join(subparts[1:]))
        else:
            new_parts.append(p)
    ansi = "".join(new_parts)

    # Reemplazo de <code>...</code> a CYAN
    parts = ansi.split("<code>")
    new_parts = [parts[0]]
    for p in parts[1:]:
        if "</code>" in p:
            subparts = p.split("</code>")
            new_parts.append(f"{CYAN}{subparts[0]}{RESET}" + "".join(subparts[1:]))
        else:
            new_parts.append(p)
    ansi = "".join(new_parts)

    # Reemplazo de emoji o palabras específicas para dar más contraste
    ansi = ansi.replace("ENTORNO FAVORABLE", f"{GREEN}{BOLD}ENTORNO FAVORABLE{RESET}")
    ansi = ansi.replace("buscar breakouts", f"{GREEN}buscar breakouts{RESET}")
    ansi = ansi.replace("Consolidar — no comprar aún", f"{ORANGE}Consolidar — no comprar aún{RESET}")
    ansi = ansi.replace("Esperando ruptura", f"{CYAN}Esperando ruptura{RESET}")
    
    return ansi


# =====================================================================
# ENVÍO REAL A TELEGRAM (OPCIONAL)
# =====================================================================

def send_telegram_test(html_content: str) -> bool:
    """
    Envía el mensaje HTML formateado a los chats de Telegram configurados.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    if not bot_token:
        print("❌ Error: No se encontró TELEGRAM_BOT_TOKEN en las variables de entorno.")
        return False

    # Buscar todos los chat IDs configurados
    candidate_keys = [
        "TELEGRAM_CHAT_ID_LIVE",
        "TELEGRAM_CHAT_ID_MONITOR",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_CHAT_ID_DEMO"
    ]
    chat_ids = []
    for key in candidate_keys:
        val = os.getenv(key)
        if val and val.strip() and not val.startswith("-1009XXXX"): # Excluir mocks
            # Evitar duplicados
            c_id = val.strip()
            if c_id not in chat_ids:
                chat_ids.append(c_id)

    if not chat_ids:
        print("❌ Error: No se encontró ningún chat_id válido configurado.")
        return False

    success = False
    for chat_id in chat_ids:
        print(f"\n📡 Enviando a Telegram (Chat ID: {chat_id})...")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": html_content,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        try:
            data = urllib.parse.urlencode(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                if res_data.get("ok"):
                    print(f"✅ ¡Mensaje enviado exitosamente a Telegram (Chat ID: {chat_id})!")
                    success = True
                else:
                    print(f"❌ Error en respuesta de Telegram para {chat_id}: {res_data}")
        except Exception as e:
            print(f"❌ Error al conectar con la API de Telegram para {chat_id}: {e}")

    return success


# =====================================================================
# DATOS DE PRUEBA REALISTAS (MOCK DATABASE)
# =====================================================================

MOCK_REPORT_DATA = {
    "metadata": {
        "date": "14 Jul 2026",
        "close_date": "13/07/2026",
        "universe_size": 555,
        "candidate_sector": "Financiero"
    },
    "macro": {
        "vix": 17.16,
        "regime_status": "ENTORNO FAVORABLE",
        "regime_description": "VIX en 17.16 (zona tranquila) + acumulación institucional activa.\nMomento de <b>buscar breakouts</b>, no de esperar en el banco.",
        "gamma_exposure": 5.6,
        "dark_pool_pct": 43.8,
        "dark_pool_desc": "ligera baja vs. ayer, pero el \"smart money\" sigue posicionado, no en salida.",
        "sectors_note": "El dinero institucional está rotando fuerte hacia Financiero. Es el sector a vigilar hoy."
    },
    "sectors": [
        {"name": "Financiero", "etf": "XLF", "force_pct": 283},
        {"name": "Salud", "etf": "XLV", "force_pct": 188},
        {"name": "Utilities", "etf": "XLU", "force_pct": 146},
        {"name": "Industriales", "etf": "XLI", "force_pct": 79}
    ],
    "candidates": [
        {
            "ticker": "PYPL",
            "name": "PayPal",
            "subsector": "Fintech/Pagos",
            "price": 75.50,
            "breakout_level": 78.40,
            "dist_sma20": 8.65,    # E25 aplicará penalización fuerte (valley)
            "adr_pct": 3.25,
            "atr": 2.65,
            "fr": 89,
            "top_pct": 15,
            "state": "Consolidar — no comprar aún"
        },
        {
            "ticker": "JPM",
            "name": "JPMorgan",
            "subsector": "Banca",
            "price": 338.20,
            "breakout_level": 341.91,
            "dist_sma20": 3.12,    # E25 en zona de confort (1.0x sizing)
            "adr_pct": 1.45,
            "atr": 6.80,
            "fr": 73,
            "top_pct": None,
            "state": "Esperando ruptura"
        },
        {
            "ticker": "MS",
            "name": "Morgan Stanley",
            "subsector": "Banca de inversión",
            "price": 227.15,
            "breakout_level": 230.47,
            "dist_sma20": 4.05,    # E25 en zona de confort (1.0x sizing)
            "adr_pct": 1.85,
            "atr": 5.20,
            "fr": 62,
            "top_pct": None,
            "state": "Esperando ruptura"
        },
        {
            "ticker": "SOFI",
            "name": "SoFi Technologies",
            "subsector": "Fintech/Banca",
            "price": 19.35,
            "breakout_level": 19.74,
            "dist_sma20": 5.92,    # E25 en zona de confort (1.0x sizing)
            "adr_pct": 4.90,
            "atr": 0.85,
            "rvol": 1.13,
            "fr": 77,
            "top_pct": None,
            "state": "Esperando ruptura"
        },
        {
            "ticker": "HOOD",
            "name": "Robinhood",
            "subsector": "Brokerage",
            "price": 118.80,
            "breakout_level": 120.05,
            "dist_sma20": 6.50,    # E25 en zona de confort (1.0x sizing)
            "adr_pct": 5.10,
            "atr": 4.90,
            "fr": 93,
            "top_pct": 10,
            "state": "Esperando ruptura"
        }
    ],
    "priority_alert": {
        "description": "Sector Financiero concentra el mejor momentum del mercado hoy.",
        "action": "vigilar JPM y MS — si rompen su nivel clave <b>con volumen</b>, son los primeros en gatillar señal de entrada."
    },
    "top_global": [
        {"ticker": "PBF Energy", "sector": "Energía", "fr": 99},
        {"ticker": "VLO", "sector": "Energía", "fr": 90},
        {"ticker": "AAPL", "sector": "Tecnología", "fr": 73}
    ]
}


# =====================================================================
# EJECUCIÓN DEL MOCK INTERACTIVO
# =====================================================================

def main():
    print("=" * 60)
    print("🤖 QUANT TELEGRAM ALERTS - PROTOTYPE SYSTEM 🤖")
    print("=" * 60)
    print("Ubicación del prototipo: scratch/mock_telegram_alerts.py")
    print("Este script NO toca el código de producción y respeta el Protocolo de Entorno.")
    print("=" * 60)
    
    # 1. Generar HTML
    html_msg = render_html_report(MOCK_REPORT_DATA)
    
    # 2. Generar Previsualización ANSI
    ansi_preview = render_ansi_preview(html_msg)
    
    print("\n[!] Generando previsualización estética simulada en consola...\n")
    print(ansi_preview)
    print("\n" + "=" * 60 + "\n")
    
    # Menu interactivo
    while True:
        print("¿Qué deseas hacer ahora?")
        print("1. Imprimir código HTML de Telegram limpio (para copiar y pegar)")
        print("2. Simular cálculo de Sizing E25 detallado para candidatos del reporte")
        print("3. Enviar mensaje de prueba real a Telegram (requiere env vars)")
        print("4. Salir")
        
        try:
            choice = input("\nSelecciona una opción [1-4]: ").strip()
        except KeyboardInterrupt:
            print("\nSaliendo...")
            break
            
        if choice == "1":
            print("\n" + "-" * 30 + " TELEGRAM HTML CODE " + "-" * 30)
            print(html_msg)
            print("-" * 80 + "\n")
        
        elif choice == "2":
            print("\n📊 DETALLE DE SIMULACIÓN DE POSITION SIZING DINÁMICO (E25 / CAPITAL MOCK $100K) 📊")
            print("-" * 80)
            print(f"{'Ticker':<8} | {'Precio':<8} | {'Dist% SMA':<10} | {'ADR%':<6} | {'Sizing F.':<10} | {'Shares':<8} | {'Allocated':<12} | {'Sizing Reason'}")
            print("-" * 80)
            for cand in MOCK_REPORT_DATA["candidates"]:
                sizing = simulate_e25_sizing(
                    ticker=cand["ticker"],
                    entry_price=cand["price"],
                    dist_sma20=cand["dist_sma20"],
                    adr_pct=cand["adr_pct"],
                    atr_14=cand.get("atr", cand["price"] * 0.04)
                )
                print(f"{sizing['ticker']:<8} | ${sizing['entry_price']:<7.2f} | {sizing['dist_sma20']:<9.2f}% | {sizing['adr_pct']:<5.2f}% | {sizing['sizing_factor']:<10.2f} | {sizing['shares']:<8} | ${sizing['capital_allocated']:<10.2f} | {sizing['sizing_reason']}")
            print("-" * 80)
            print("E25 Valley Penalty: penalización fuerte (factor 0.3x) al alejarse más de 6.76% (comfort) pero sin pasar 10%.")
            print("JPM, MS, SOFI y HOOD se encuentran en zona confortable por lo que operan con sizing factor alto/normal.\n")
            
        elif choice == "3":
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID_LIVE") or os.getenv("TELEGRAM_CHAT_ID")
            
            if not bot_token or not chat_id:
                print("\n⚠️ ERROR: No se detectaron las variables de entorno para Telegram.")
                print("Para habilitar el envío real, define en tu entorno o en un archivo .env:")
                print("  TELEGRAM_BOT_TOKEN=tu_token")
                print("  TELEGRAM_CHAT_ID_LIVE=tu_chat_id")
                print("Ejecutando simulación local... (urllib call abortado por falta de credenciales)\n")
            else:
                send_telegram_test(html_msg)
                
        elif choice == "4":
            print("\nSaliendo del prototipo de alertas de Telegram. ¡Buenas operaciones!")
            break
        else:
            print("\nOpción no válida. Intente de nuevo.")


if __name__ == "__main__":
    main()
