from src.integration.unified_signal import UnifiedSignal, normalize_score


class SignalValidationError(Exception):
    pass


REQUIRED_FIELDS_A = ["ticker", "signal_price"]


def validate_signal_a(row: dict) -> None:
    for field in REQUIRED_FIELDS_A:
        if field not in row or not row.get(field):
            raise SignalValidationError(f"Missing required field: {field}")
    ticker = str(row.get("ticker", "")).strip().upper()
    if not ticker or ticker == "NAN":
        raise SignalValidationError(f"Invalid ticker: {row.get('ticker')}")
    signal_price = row.get("signal_price")
    try:
        signal_price = float(signal_price)
        if signal_price <= 0:
            raise SignalValidationError(f"Invalid signal_price: {signal_price}")
    except (ValueError, TypeError):
        raise SignalValidationError(f"Invalid signal_price: {signal_price}")


def adapt_signal_a(row: dict) -> UnifiedSignal:
    validate_signal_a(row)
    raw_score = float(row.get("entry_score", row.get("score", 0.0)))
    strategy_id = str(row.get("combo_name", row.get("combo", "unknown")))
    signal_time = str(row.get("signal_time", row.get("signal_date", "")))
    ticker = str(row.get("ticker", "")).upper()
    entry_price_ref = float(row.get("signal_price", 0.0))
    stop_price = row.get("stop_price")
    if stop_price is not None:
        stop_price = float(stop_price)
    target_price = row.get("tp1") or row.get("target_price")
    if target_price is not None:
        target_price = float(target_price)
    risk_unit = row.get("risk_$", row.get("risk_unit"))
    if risk_unit is not None:
        risk_unit = float(risk_unit)
    return UnifiedSignal(
        source_system="A",
        strategy_id=strategy_id,
        ticker=ticker,
        timeframe=str(row.get("timeframe", "1D")),
        signal_time=signal_time,
        side=str(row.get("side", "long")).lower(),
        entry_type="next_open",
        entry_price_ref=entry_price_ref,
        stop_price=stop_price,
        target_price=target_price,
        raw_score=raw_score,
        normalized_score=normalize_score(raw_score, 0.0, 100.0),
        confidence=float(row.get("confidence", 0.5)),
        risk_unit=risk_unit,
        reason_codes=str(row.get("reason_codes", "")),
        metadata={"origin": "combo_pipeline"},
    )


def adapt_batch_a(rows: list[dict]) -> tuple[list[UnifiedSignal], list[dict]]:
    signals = []
    discarded = []
    for row in rows:
        try:
            signals.append(adapt_signal_a(row))
        except SignalValidationError as e:
            discarded.append({"row": row, "error": str(e)})
        except KeyError as e:
            discarded.append({"row": row, "error": f"Missing key: {e}"})
    return signals, discarded
