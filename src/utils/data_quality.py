"""
data_quality.py - Helper centralizado para validar la calidad de datos de tickers.
"""

def calculate_data_quality(data: dict) -> tuple[str, list[str]]:
    """
    Valida la calidad de los datos del ticker.
    Retorna (status, reasons). Status: 'ok', 'warn', 'bad'.
    """
    reasons = []
    status = "ok"

    # Campos requeridos y sus nombres reales en watchlist_detail/signals
    price = data.get("price") or data.get("entry_price")
    breakout_level = data.get("breakout_level")
    rvol = data.get("rvol")
    adr = data.get("adr") or data.get("adr_pct")
    dist_sma20 = data.get("dist_sma20_pct") or data.get("dist_sma20")
    dollar_vol_m = data.get("dollar_volume_m") or data.get("dollar_vol_M")

    # 1. BAD: Datos faltantes o imposibles (impiden validar entrada)
    if price is None or not isinstance(price, (int, float)):
        reasons.append("missing_price")
        status = "bad"
    
    if breakout_level is None or not isinstance(breakout_level, (int, float)) or breakout_level <= 0:
        reasons.append("missing_breakout_level")
        status = "bad"
    
    if data.get("ma_gap_pct") == -100:
        reasons.append("default_ma_gap")
        status = "bad"

    if status == "bad":
        return status, reasons

    # 2. WARN: Datos incompletos o sospechosos (pueden ser placeholders)
    if rvol == 1.0 or rvol == 0:
        reasons.append("rvol_1.0_default")
        status = "warn"
    
    if adr == 0 or adr is None:
        reasons.append("adr_0")
        status = "warn"

    if dollar_vol_m == 0 or dollar_vol_m is None:
        reasons.append("zero_dollar_vol")
        status = "warn"
    
    if dist_sma20 == 0 and price != 0:
        reasons.append("dist_sma20_zero_suspect")
        status = "warn"

    return status, reasons


def is_monitor_eligible(data: dict) -> bool:
    """Determina si un ticker es apto para ser monitoreado en vivo."""
    status, _ = calculate_data_quality(data)
    # Solo los 'bad' se excluyen del monitor.
    # Los 'warn' se monitorean pero requieren validacion live extra para promocion.
    return status != "bad"


def is_promotable(data: dict, allow_warn: bool = False) -> bool:
    """Determina si un ticker puede ser promovido a señal activa."""
    status, _ = calculate_data_quality(data)
    if status == "ok":
        return True
    if status == "warn" and allow_warn:
        return True
    return False
