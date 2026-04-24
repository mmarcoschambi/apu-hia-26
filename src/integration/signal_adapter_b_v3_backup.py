from src.integration.unified_signal import UnifiedSignal, normalize_score


class SignalValidationError(Exception):
    pass


REQUIRED_FIELDS_B = ["preset_id", "ticker", "signal_date"]


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


def adapt_signal_b(row: dict, preset_score_lookup: dict[str, float]) -> UnifiedSignal:
    validate_signal_b(row)
    preset_id = str(row["preset_id"]).strip()
    raw_score = float(preset_score_lookup.get(preset_id, 0.0))
    return UnifiedSignal(
        source_system="B",
        strategy_id=preset_id,
        ticker=str(row["ticker"]).upper(),
        timeframe="1D",
        signal_time=str(row["signal_date"]).strip() + "T00:00:00",
        side="long",
        entry_type="next_open",
        entry_price_ref=float(row.get("entry_price_ref", 0.0)),
        stop_price=None,
        target_price=None,
        raw_score=raw_score,
        normalized_score=normalize_score(raw_score, -1.0, 1.0),
        confidence=float(row.get("confidence", 0.5)),
        risk_unit=None,
        reason_codes=str(row.get("reason_codes", "")),
        metadata={"origin": "preset_pack"},
    )


def adapt_batch_b(
    rows: list[dict], preset_score_lookup: dict[str, float]
) -> tuple[list[UnifiedSignal], list[dict]]:
    signals = []
    discarded = []
    for row in rows:
        try:
            signals.append(adapt_signal_b(row, preset_score_lookup))
        except SignalValidationError as e:
            discarded.append({"row": row, "error": str(e)})
        except KeyError as e:
            discarded.append({"row": row, "error": f"Missing key: {e}"})
    return signals, discarded
