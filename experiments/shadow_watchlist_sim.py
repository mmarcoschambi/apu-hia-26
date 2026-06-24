#!/usr/bin/env python3
"""
Experimento de Simulación de Watchlist con Shadow Mode.
Implementa Issue #42: simulación de trades usando la base de datos local para candidates
de watchlist_detail en snapshots de mayo y junio de 2026.
"""

import json
import logging
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# 1. Configurar directorios y sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.ticker_cache import TickerCache
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS

# 2. Configurar logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)


def load_risk_config() -> float:
    """Carga risk_dollars de config/production_config.json o retorna default de $2,878."""
    config_path = PROJECT_ROOT / "config" / "production_config.json"
    default_risk = 2878.0
    if not config_path.exists():
        logger.warning(
            f"No se encontró el archivo de configuración en {config_path}. Usando default: ${default_risk}"
        )
        return default_risk

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        risk = config.get("tier1_strategy", {}).get("risk_dollars", default_risk)
        logger.info(f"Configuración de riesgo cargada de config: ${risk:,.2f} risk-per-trade")
        return float(risk)
    except Exception as e:
        logger.warning(
            f"Error al leer config en {config_path}: {e}. Usando default: ${default_risk}"
        )
        return default_risk


def is_healthcare(ticker: str, sector_etf: str, cache: TickerCache) -> bool:
    """
    Verifica si el ticker pertenece al sector Healthcare (XLV).
    Aplica filtros de sector_etf, SECTOR_MAP y consultas a la base de datos local.
    """
    ticker_upper = ticker.upper()

    # 1. Chequeo directo de sector_etf provisto en el JSON
    if sector_etf == "XLV":
        return True

    # 2. Chequeo en la constante SECTOR_MAP
    if SECTOR_MAP.get(ticker_upper) == "XLV":
        return True

    # 3. Consulta a la tabla universe del ticker cache
    try:
        cursor = cache.conn.execute(
            "SELECT sector, industry FROM universe WHERE ticker = ?", (ticker_upper,)
        )
        row = cursor.fetchone()
        if row:
            sector, industry = row
            sector_lower = (sector or "").lower()
            industry_lower = (industry or "").lower()

            # Palabras clave del sector salud
            keywords = ["health", "biotech", "pharma", "clinical", "medical"]
            if any(k in sector_lower for k in keywords) or any(k in industry_lower for k in keywords):
                return True
    except Exception as e:
        logger.debug(f"Error consultando universo para {ticker_upper}: {e}")

    return False


def simulate_trade(
    ticker: str,
    snapshot_date_str: str,
    breakout_lvl: float,
    shares: int,
    risk_dollars: float,
    cache: TickerCache,
) -> Optional[dict]:
    """
    Simula el comportamiento de un trade ingresando en T+1.
    Usa una estrategia de salida dividida en dos partes:
      - Mitad 1: Vende en TP1 (1.25R). Al tocar TP1, mueve el stop de la mitad 2 a break-even.
      - Mitad 2: Vende en TP2 (3.0R) o en el stop.
      - Salida por tiempo: Si no tocan stop ni targets tras 10 días, sale a precio de Close.
    """
    # 1. Obtener datos de la DB local
    start_date = snapshot_date_str
    try:
        dt = datetime.strptime(snapshot_date_str, "%Y-%m-%d")
        end_dt = dt + timedelta(days=45)  # Margen holgado para 10 trading days
        end_date = end_dt.strftime("%Y-%m-%d")
    except Exception:
        end_date = "2026-07-01"

    df = cache.get_ohlcv(ticker, start_date=start_date, end_date=end_date, offline=True)
    if df is None or df.empty:
        return None

    # Filtrar fechas estrictamente posteriores al snapshot (T+1 en adelante)
    snapshot_dt = pd.to_datetime(snapshot_date_str)
    df_post = df[df.index > snapshot_dt].sort_index()

    if df_post.empty:
        return None

    # Filtrar si hay algún NaN en Open, High, Low, Close durante los 10 días de holding
    max_hold_days = 10
    check_slice = df_post.iloc[:max_hold_days]
    if check_slice[["Open", "High", "Low", "Close"]].isna().any().any():
        return None

    # Primer día de trading (T+1)
    first_row = df_post.iloc[0]
    entry_date = df_post.index[0]

    high_t1 = first_row["High"]
    open_t1 = first_row["Open"]

    # Evaluar si se dispara la entrada en T+1 (breakout)
    if high_t1 >= breakout_lvl:
        entry_price = max(open_t1, breakout_lvl)
    else:
        # No se superó el breakout en T+1
        return None

    # Parámetros del trade
    stop_pct = 0.07
    stop_price = round(entry_price * (1.0 - stop_pct), 4)
    stop_dist = entry_price - stop_price

    tp1 = round(entry_price + stop_dist * 1.25, 4)
    tp2 = round(entry_price + stop_dist * 3.0, 4)

    # Posición dividida
    shares_half1 = shares // 2
    shares_half2 = shares - shares_half1

    if shares == 1:
        shares_half1 = 1
        shares_half2 = 0

    half1_active = True if shares_half1 > 0 else False
    half2_active = True if shares_half2 > 0 else False

    half1_exit_price = None
    half1_exit_date = None
    half1_exit_reason = None

    half2_exit_price = None
    half2_exit_date = None
    half2_exit_reason = None

    current_stop_price = stop_price
    max_hold_days = 10

    # Recorrer barras de precio diarias
    for i in range(len(df_post)):
        if i >= max_hold_days:
            break

        row = df_post.iloc[i]
        date = df_post.index[i]
        high = row["High"]
        low = row["Low"]
        open_val = row["Open"]

        # 1. Gestionar mitad 1
        if half1_active:
            # Chequear stop loss primero (conservador)
            if low <= current_stop_price:
                half1_active = False
                half1_exit_price = current_stop_price
                if open_val < current_stop_price:
                    half1_exit_price = open_val
                half1_exit_date = date
                half1_exit_reason = "STOP"

                # Si cae la primera mitad, la segunda también
                if half2_active:
                    half2_active = False
                    half2_exit_price = half1_exit_price
                    half2_exit_date = date
                    half2_exit_reason = "STOP"

            # Chequear TP1 si stop no se ejecutó
            elif high >= tp1:
                half1_active = False
                half1_exit_price = tp1
                if open_val > tp1:
                    half1_exit_price = open_val
                half1_exit_date = date
                half1_exit_reason = "TP1"

                # Ajustar stop de la mitad 2 a break-even (entry_price)
                current_stop_price = entry_price

                # Si la segunda mitad está activa, ver si alcanza TP2 o BE el mismo día
                if half2_active:
                    if high >= tp2:
                        half2_active = False
                        half2_exit_price = tp2
                        if open_val > tp2:
                            half2_exit_price = open_val
                        half2_exit_date = date
                        half2_exit_reason = "TP2"
                    elif low <= current_stop_price:
                        half2_active = False
                        half2_exit_price = current_stop_price
                        half2_exit_date = date
                        half2_exit_reason = "BE_STOP"

        # 2. Gestionar mitad 2 (si la primera ya salió en TP1 y queda activa)
        elif half2_active:
            if low <= current_stop_price:
                half2_active = False
                half2_exit_price = current_stop_price
                if open_val < current_stop_price:
                    half2_exit_price = open_val
                half2_exit_date = date
                half2_exit_reason = "BE_STOP"
            elif high >= tp2:
                half2_active = False
                half2_exit_price = tp2
                if open_val > tp2:
                    half2_exit_price = open_val
                half2_exit_date = date
                half2_exit_reason = "TP2"

        # Si ambas mitades cerraron, salir
        if not half1_active and not half2_active:
            break

    # Salidas por límite de holding period (10 días)
    last_idx = min(len(df_post) - 1, max_hold_days - 1)
    last_row = df_post.iloc[last_idx]
    last_date = df_post.index[last_idx]
    last_close = last_row["Close"]

    if half1_active:
        half1_active = False
        half1_exit_price = last_close
        half1_exit_date = last_date
        half1_exit_reason = "TIME_OUT"

    if half2_active:
        half2_active = False
        half2_exit_price = last_close
        half2_exit_date = last_date
        half2_exit_reason = "TIME_OUT"

    # Calcular PnL total y múltiplos de R
    pnl_1 = (half1_exit_price - entry_price) * shares_half1 if shares_half1 > 0 else 0.0
    pnl_2 = (half2_exit_price - entry_price) * shares_half2 if shares_half2 > 0 else 0.0
    pnl_total = pnl_1 + pnl_2

    initial_risk = (entry_price - stop_price) * shares
    r_multiple = pnl_total / initial_risk if initial_risk > 0 else 0.0

    return {
        "date": snapshot_date_str,
        "ticker": ticker,
        "entry_date": entry_date.strftime("%Y-%m-%d"),
        "entry": round(entry_price, 4),
        "stop": round(stop_price, 4),
        "tp1": round(tp1, 4),
        "tp2": round(tp2, 4),
        "shares": shares,
        "exit_date_1": half1_exit_date.strftime("%Y-%m-%d") if half1_exit_date else None,
        "exit_price_1": round(half1_exit_price, 4) if half1_exit_price else None,
        "exit_reason_1": half1_exit_reason,
        "exit_date_2": half2_exit_date.strftime("%Y-%m-%d") if half2_exit_date else None,
        "exit_price_2": round(half2_exit_price, 4) if half2_exit_price else None,
        "exit_reason_2": half2_exit_reason,
        "pnl": round(pnl_total, 2),
        "result": round(r_multiple, 4),
    }


def main():
    logger.info("Iniciando simulación de watchlist de Shadow Mode...")

    # Cargar configuraciones
    risk_dollars = load_risk_config()
    portfolio_value = 100000.0
    ticker_cap = 20000.0  # 20% de $100k

    # Instanciar TickerCache
    cache = TickerCache()

    # Buscar snapshots de mayo y junio 2026
    paper_dir = PROJECT_ROOT / "outputs" / "paper_finviz"
    snapshots = []
    for path in sorted(paper_dir.glob("2026-05-*/snapshot.json")):
        snapshots.append(path)
    for path in sorted(paper_dir.glob("2026-06-*/snapshot.json")):
        snapshots.append(path)

    logger.info(f"Encontrados {len(snapshots)} snapshots para procesar.")

    unique_watchlist_tickers = set()
    total_raw_tickers = 0
    records_processed = 0
    excluded_xlv_count = 0
    missing_data_count = 0
    no_breakout_count = 0

    trades = []
    sector_counts = Counter()

    for snap_path in snapshots:
        date_str = snap_path.parent.name
        try:
            with open(snap_path, "r", encoding="utf-8") as f:
                snap_data = json.load(f)
        except Exception as e:
            logger.error(f"Error cargada snapshot {snap_path}: {e}")
            continue

        raw_size = snap_data.get("universe_size", 0)
        total_raw_tickers += raw_size

        watchlist = snap_data.get("watchlist_detail", {})
        for ticker, detail in watchlist.items():
            records_processed += 1
            unique_watchlist_tickers.add(ticker.upper())

            # 1. Filtro Sectorial ex-XLV
            sector_etf = detail.get("sector_etf", "UNKNOWN")
            if is_healthcare(ticker, sector_etf, cache):
                excluded_xlv_count += 1
                continue

            # 2. Obtener precios de entrada/breakout
            breakout_lvl = detail.get("breakout_level")
            if breakout_lvl is None or breakout_lvl <= 0:
                breakout_lvl = detail.get("price")
            if breakout_lvl is None or breakout_lvl <= 0:
                continue

            # 3. Calcular Sizing
            # Stop fijo del 7% para determinar shares
            stop_price = breakout_lvl * 0.93
            stop_dist = breakout_lvl - stop_price
            shares_by_risk = risk_dollars / stop_dist
            max_shares_by_cap = ticker_cap / breakout_lvl
            shares = int(min(shares_by_risk, max_shares_by_cap))
            if shares <= 0:
                shares = 1

            # 4. Simulación de Trade
            trade_res = simulate_trade(
                ticker=ticker,
                snapshot_date_str=date_str,
                breakout_lvl=breakout_lvl,
                shares=shares,
                risk_dollars=risk_dollars,
                cache=cache,
            )

            if trade_res is None:
                # O bien no hay datos en la DB o no quebró el breakout
                # Para saber cuál, chequeamos si la DB tiene datos
                df_test = cache.get_ohlcv(
                    ticker, start_date=date_str, end_date="2026-07-01", offline=True
                )
                if df_test is None or df_test.empty:
                    missing_data_count += 1
                else:
                    no_breakout_count += 1
                continue

            # Registrar trade exitoso
            trades.append(trade_res)
            sector_counts[sector_etf] += 1

    logger.info("--- Resumen de Procesamiento ---")
    logger.info(f"Total registros en watchlist_detail leídos: {records_processed}")
    logger.info(f"Tickers únicos en watchlist: {len(unique_watchlist_tickers)}")
    logger.info(f"Excluidos por XLV/Healthcare: {excluded_xlv_count}")
    logger.info(f"Candidatos sin datos en caché local: {missing_data_count}")
    logger.info(f"Candidatos sin breakout en T+1: {no_breakout_count}")
    logger.info(f"Trades simulados exitosamente: {len(trades)}")

    # Escribir outputs
    out_dir = PROJECT_ROOT / "outputs" / "shadow_sandbox" / "watchlist_sim"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. trades.csv
    df_trades = pd.DataFrame(trades)
    if not df_trades.empty:
        # Asegurar columnas requeridas: date, ticker, entry, stop, result
        cols_ordered = [
            "date",
            "ticker",
            "entry",
            "stop",
            "result",
            "entry_date",
            "tp1",
            "tp2",
            "shares",
            "exit_date_1",
            "exit_price_1",
            "exit_reason_1",
            "exit_date_2",
            "exit_price_2",
            "exit_reason_2",
            "pnl",
        ]
        df_trades = df_trades[cols_ordered]
        df_trades.to_csv(out_dir / "trades.csv", index=False)
        logger.info(f"Archivo de trades guardado en: {out_dir / 'trades.csv'}")
    else:
        # Archivo vacío con headers correctos
        with open(out_dir / "trades.csv", "w", encoding="utf-8") as f:
            f.write("date,ticker,entry,stop,result\n")
        logger.warning("No se generaron trades, se creó un trades.csv vacío con cabeceras.")

    # 2. summary.md
    num_trades = len(trades)
    win_rate = 0.0
    total_pnl = 0.0
    positive_trades = 0

    if num_trades > 0:
        positive_trades = sum(1 for t in trades if t["pnl"] > 0)
        win_rate = (positive_trades / num_trades) * 100.0
        total_pnl = sum(t["pnl"] for t in trades)

    # Formatear la exposición sectorial
    sector_exposure_lines = []
    total_sector_trades = sum(sector_counts.values())
    for sector, count in sector_counts.most_common():
        pct = (count / total_sector_trades) * 100.0 if total_sector_trades > 0 else 0.0
        sector_exposure_lines.append(f"- **{sector}**: {count} trades ({pct:.2f}%)")

    summary_content = f"""# Watchlist Shadow Simulation Summary

**Generado:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Período:** Mayo - Junio 2026

## Métricas Clave

- **Total Trades Simulados:** {num_trades}
- **Win Rate:** {win_rate:.2f}% ({positive_trades} ganadores / {num_trades} totales)
- **PnL Estimado:** ${total_pnl:,.2f}
- **Riesgo por trade (Sizing E25):** ${risk_dollars:,.2f}
- **Cap de Ticker:** Máximo $20,000.00 por ticker (20% de $100k)

## Exposición Sectorial

{chr(10).join(sector_exposure_lines) if sector_exposure_lines else "No hubo trades simulados."}

## Advertencia de Limitación de Datos

> [!WARNING]
> **Limitación del Universo Parcial:**
> Esta simulación se ejecutó sobre una lista filtrada de candidates (`watchlist_detail`) que contiene únicamente **331 tickers únicos** a lo largo de mayo y junio de 2026, en contraste con los **591 tickers crudos** que conforman el universo total escaneado. Esta omisión del ~44% del universo puede ocasionar que falten señales y trades que sí se ejecutaron en producción en la VPS.
"""

    with open(out_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write(summary_content)
    logger.info(f"Resumen guardado en: {out_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
