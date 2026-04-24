"""Adapter para se\u00f1ales del Sistema B (preset monol\u00edtico).

Aplica dos correcciones en tiempo de ejecuci\u00f3n SIN tocar la l\u00f3gica core de B:

1. Alineaci\u00f3n Temporal: sobrescribe la fecha hist\u00f3rica del backtest con
   ``execution_date`` (hoy o la fecha operativa que se pase), de modo que
   el Router y F4 puedan cruzar sesiones con el Sistema A.

2. Inyecci\u00f3n de Riesgo: asigna stop_price y target_price din\u00e1micos cuando
   el preset no los define, usando ATR si est\u00e1 disponible, o un porcentaje
   fijo como fallback. Esto habilita el c\u00e1lculo R/R en el Risk Gate (F3).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Union

from src.integration.unified_signal import UnifiedSignal, normalize_score


class SignalValidationError(Exception):
    pass


REQUIRED_FIELDS_B = ["preset_id", "ticker", "signal_date"]

# Defaults de riesgo cuando el preset no define stop/target
DEFAULT_STOP_PCT: float = 0.05    # 5 % por debajo del entry
DEFAULT_TARGET_PCT: float = 0.15  # 15 % por encima del entry (R:R = 3:1)


def validate_signal_b(row: dict) -> None:
    for field in REQUIRED_FIELDS_B:
        if field not in row or not row.get(field):
            raise SignalValidationError(f"Missing required field: {field}")
    ticker = str(row.get("ticker", "")).strip().upper()
    if not ticker or ticker == "NAN":
        raise SignalValidationError(f"Invalid ticker: {row.get('ticker')}")
    signal_date = str(row.get("signal_date", "")).strip()
    if not signal_date:
        raise SignalValidationError(f"Invalid signal_date: {signal_date}")


def _resolve_execution_date(
    execution_date: Optional[Union[str, date, datetime]]
) -> str:
    """Devuelve la fecha operativa como string YYYY-MM-DD.

    Si no se pasa nada, usa today() (modo live/paper).
    Acepta str, date o datetime.
    """
    if execution_date is None:
        return date.today().isoformat()
    if isinstance(execution_date, datetime):
        return execution_date.date().isoformat()
    if isinstance(execution_date, date):
        return execution_date.isoformat()
    # Es string; tomamos solo YYYY-MM-DD
    return str(execution_date).strip()[:10]


def _inject_risk(
    entry_price: float,
    stop_price: Optional[float],
    target_price: Optional[float],
    atr: Optional[float],
    stop_pct: float,
    target_pct: float,
) -> tuple[float, float]:
    """Calcula stop y target si el preset no los define.

    Prioridad:
      1. Valor expl\u00edcito del preset (pasa tal cual).
      2. ATR: stop = entry - 1.5*ATR, target = entry + 3*ATR  (R:R ~2:1).
      3. % fijo fallback.
    """
    if entry_price <= 0:
        return stop_price or 0.0, target_price or 0.0

    computed_stop = stop_price
    computed_target = target_price

    if computed_stop is None or computed_stop <= 0:
        if atr and atr > 0:
            computed_stop = entry_price - 1.5 * atr
        else:
            computed_stop = entry_price * (1.0 - stop_pct)

    if computed_target is None or computed_target <= 0:
        if atr and atr > 0:
            computed_target = entry_price + 3.0 * atr
        else:
            computed_target = entry_price * (1.0 + target_pct)

    return computed_stop, computed_target


def adapt_signal_b(
    row: dict,
    preset_score_lookup: dict[str, float],
    *,
    execution_date: Optional[Union[str, date, datetime]] = None,
    stop_pct: float = DEFAULT_STOP_PCT,
    target_pct: float = DEFAULT_TARGET_PCT,
    historical_mode: bool = False,
) -> UnifiedSignal:
    """Adapta una fila cruda del Sistema B a UnifiedSignal.

    Args:
        row: dict con campos del preset (preset_id, ticker, signal_date, ...).
        preset_score_lookup: Mapa preset_id -> score raw.
        execution_date: Fecha operativa que reemplaza la fecha hist\u00f3rica del
            backtest. None -> today() (modo live/paper).
        stop_pct: Porcentaje de stop loss como fallback (0.05 = 5%).
        target_pct: Porcentaje de target como fallback (0.15 = 15%).
    """
    validate_signal_b(row)
    preset_id = str(row["preset_id"]).strip()
    raw_score = float(preset_score_lookup.get(preset_id, 0.0))

    entry_price = float(row.get("entry_price_ref", 0.0))
    atr: Optional[float] = float(row["atr"]) if row.get("atr") else None

    # --- FIX 1: Alineación Temporal ---
    # En modo histórico, usamos la fecha original del backtest (2024, etc)
    # En modo live/paper, alineamos con execution_date (hoy o fecha elegida)
    original_signal_date = str(row["signal_date"]).strip()
    if historical_mode:
        op_date = original_signal_date[:10]
    else:
        op_date = _resolve_execution_date(execution_date)

    # --- FIX 2: Inyección de Riesgo ---
    raw_stop = row.get("stop_price")
    raw_target = row.get("target_price")
    stop_val: Optional[float] = (
        float(raw_stop)
        if raw_stop is not None and str(raw_stop).strip() != ""
        else None
    )
    target_val: Optional[float] = (
        float(raw_target)
        if raw_target is not None and str(raw_target).strip() != ""
        else None
    )

    computed_stop, computed_target = _inject_risk(
        entry_price=entry_price,
        stop_price=stop_val,
        target_price=target_val,
        atr=atr,
        stop_pct=stop_pct,
        target_pct=target_pct,
    )

    stop_source = (
        "preset"
        if (stop_val is not None and stop_val > 0)
        else ("atr" if (atr and atr > 0) else "pct_fallback")
    )

    metadata = {
        "origin": "preset_pack",
        # Auditoría del fix temporal
        "original_signal_date": original_signal_date,
        "execution_date": op_date,
        "date_aligned": original_signal_date[:10] != op_date,
        # Auditoría del fix de riesgo
        "stop_source": stop_source,
        "atr_used": atr,
    }

    if historical_mode:
        metadata.update({
            "historical_plan": True,
            "price_origin": "trades_csv",
            "price_validation_mode": "historical_fill"
        })

    return UnifiedSignal(
        source_system="B",
        strategy_id=preset_id,
        ticker=str(row["ticker"]).upper(),
        timeframe="1D",
        # FIX 1: usa fecha operativa o histórica según el modo
        signal_time=op_date + "T00:00:00",
        side="long",
        entry_type="next_open",
        entry_price_ref=entry_price,
        # FIX 2: stop/target garantizados != None
        stop_price=computed_stop,
        target_price=computed_target,
        raw_score=raw_score,
        normalized_score=normalize_score(raw_score, -1.0, 1.0),
        confidence=float(row.get("confidence", 0.5)),
        risk_unit=None,
        reason_codes=str(row.get("reason_codes", "")),
        metadata=metadata,
    )


def adapt_batch_b(
    rows: list[dict],
    preset_score_lookup: dict[str, float],
    *,
    execution_date: Optional[Union[str, date, datetime]] = None,
    stop_pct: float = DEFAULT_STOP_PCT,
    target_pct: float = DEFAULT_TARGET_PCT,
    historical_mode: bool = False,
) -> tuple[list[UnifiedSignal], list[dict]]:
    """Adapta un lote de filas del Sistema B.

    Args:
        rows: Lista de dicts crudos del Sistema B.
        preset_score_lookup: Mapa preset_id -> score raw.
        execution_date: Fecha operativa común para todo el lote.
        stop_pct: Fallback de stop loss.
        target_pct: Fallback de target.
        historical_mode: Si True, modo evaluación de edge histórico.

    Returns:
        (signals_validos, descartados)
    """
    signals = []
    discarded = []
    for row in rows:
        try:
            signals.append(
                adapt_signal_b(
                    row,
                    preset_score_lookup,
                    execution_date=execution_date,
                    stop_pct=stop_pct,
                    target_pct=target_pct,
                    historical_mode=historical_mode,
                )
            )
        except SignalValidationError as e:
            discarded.append({"row": row, "error": str(e)})
        except KeyError as e:
            discarded.append({"row": row, "error": f"Missing key: {e}"})
    return signals, discarded
