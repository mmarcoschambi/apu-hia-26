#!/usr/bin/env python3
"""Daily analysis for live signal validation.

Reads the official live alert register from `outputs/live_signals/<date>/combined.csv`,
enriches it with snapshot/audit context and forward returns from `data/ticker_cache.db`,
then writes per-day and aggregate research outputs.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.theme_taxonomy import get_themes
from src.data.ticker_cache import TickerCache
from src.utils.sector_rotation import get_ticker_sector_mapping

logger = logging.getLogger(__name__)

LIVE_ROOT = PROJECT_ROOT / "outputs" / "live_signals"
FINVIZ_ROOT = PROJECT_ROOT / "outputs" / "paper_finviz"
ANALYSIS_ROOT = PROJECT_ROOT / "outputs" / "live_signal_analysis"
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"

HORIZONS = (1, 3, 5, 10, 20)
EXTENDED_DIST_THRESHOLD = 8.0
_EMPTY_BLOCKER_VALUES = {"", "ok", "clean", "passed", "none", "n/a", "na", "null", "nan"}


def today_ny() -> str:
    try:
        import pytz

        tz = pytz.timezone("America/New_York")
        return datetime.now(tz).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return None


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return {}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return pd.DataFrame()


def load_inputs(date: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    combined = _read_csv(LIVE_ROOT / date / "combined.csv")
    rejection = _read_csv(LIVE_ROOT / date / "rejection_audit.csv")
    snapshot = _read_json(FINVIZ_ROOT / date / "snapshot.json")
    return combined, rejection, snapshot


def _snapshot_lookup(snapshot: dict) -> dict[str, dict]:
    if not snapshot:
        return {}

    lookup: dict[str, dict] = {}

    watchlist = snapshot.get("watchlist_detail")
    if isinstance(watchlist, dict):
        for ticker, detail in watchlist.items():
            if isinstance(detail, dict):
                lookup[str(ticker).upper()] = detail

    for key in ("signals", "top_candidates"):
        items = snapshot.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("ticker"):
                    lookup[str(item["ticker"]).upper()] = {
                        **lookup.get(str(item["ticker"]).upper(), {}),
                        **item,
                    }

    return lookup


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, float) and math.isnan(value):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return "" if text in _EMPTY_BLOCKER_VALUES else text


def infer_signal_quality(row: pd.Series) -> str:
    blocker_value = _first_non_empty(
        row.get("snapshot_blocker"),
        row.get("snapshot_waiting_for"),
        row.get("primary_reason"),
        row.get("waiting_for"),
        row.get("tier2_filter"),
        row.get("reason"),
    )
    blocker_text = _normalize_text(blocker_value)

    if any(token in blocker_text for token in ("ma stack", "sma50", "sma200", "stack")):
        return "ma_stack_broken"

    dist = _safe_float(row.get("dist_sma20"))
    if dist is not None and dist >= EXTENDED_DIST_THRESHOLD:
        return "extended"

    breakout = _safe_float(row.get("breakout_level"))
    price = (
        _safe_float(row.get("trigger_price"))
        or _safe_float(row.get("entry_price"))
        or _safe_float(row.get("price"))
    )
    if breakout is not None and price is not None:
        if price >= breakout and any(
            word in blocker_text for word in ("breakout", "trigger", "price", "waiting")
        ):
            return "breakout_resolved"

    status = str(
        _first_non_empty(row.get("data_quality_status"), row.get("signal_quality"), "ok")
    ).lower()
    if status in {"ok", "clean", "passed"} and not blocker_text:
        return "clean"

    return "other"


def _normalize_detail(detail: dict | None) -> dict:
    detail = detail or {}
    return {
        "snapshot_waiting_for": _first_non_empty(
            detail.get("waiting_for"),
            detail.get("snapshot_waiting_for"),
            detail.get("status"),
        ),
        "snapshot_blocker": _first_non_empty(
            detail.get("primary_reason"),
            detail.get("blocker"),
            detail.get("snapshot_blocker"),
            detail.get("reason"),
        ),
        "snapshot_score": _safe_float(detail.get("score")),
        "snapshot_theme": _first_non_empty(detail.get("theme"), detail.get("themes")),
        "snapshot_sector_etf": _first_non_empty(detail.get("sector_etf"), detail.get("sector")),
        "snapshot_breakout_level": _safe_float(detail.get("breakout_level")),
        "snapshot_avg_volume_20d": _safe_float(detail.get("avg_volume_20d")),
    }


def _to_theme_string(ticker: str, snapshot_theme: Any = None) -> str | None:
    if snapshot_theme:
        if isinstance(snapshot_theme, list):
            return ", ".join(str(item) for item in snapshot_theme if item)
        return str(snapshot_theme)
    themes = get_themes(ticker)
    return ", ".join(themes) if themes else None


def _df_to_markdown_safe(df: pd.DataFrame) -> str:
    if df.empty:
        return ""

    cols = list(df.columns)
    rows = [
        ["" if pd.isna(val) else str(val) for val in row]
        for row in df.itertuples(index=False, name=None)
    ]
    widths = [len(str(col)) for col in cols]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def fmt_row(values: list[str]) -> str:
        return "| " + " | ".join(values[i].ljust(widths[i]) for i in range(len(values))) + " |"

    header = fmt_row([str(col) for col in cols])
    sep = "| " + " | ".join("-" * widths[i] for i in range(len(cols))) + " |"
    body = [fmt_row(row) for row in rows]
    return "\n".join([header, sep, *body])


def _as_day(value: str | datetime) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def compute_forward_metrics(
    history: pd.DataFrame, signal_date: str, trigger_price: float
) -> dict[str, float]:
    metrics = {f"forward_return_{h}d": np.nan for h in HORIZONS}
    metrics["max_favorable_excursion"] = np.nan
    metrics["max_adverse_excursion"] = np.nan

    if history is None or history.empty or trigger_price is None or trigger_price <= 0:
        return metrics

    if not isinstance(history.index, pd.DatetimeIndex):
        history = history.copy()
        history.index = pd.to_datetime(history.index)

    rename_map = {}
    for src, dst in (
        ("open", "Open"),
        ("high", "High"),
        ("low", "Low"),
        ("close", "Close"),
        ("volume", "Volume"),
    ):
        if src in history.columns and dst not in history.columns:
            rename_map[src] = dst
    if rename_map:
        history = history.rename(columns=rename_map)

    history = history.sort_index()
    signal_ts = _as_day(signal_date)
    future = history.loc[history.index > signal_ts]
    if future.empty:
        return metrics

    for horizon in HORIZONS:
        if len(future) >= horizon:
            close = _safe_float(
                future.iloc[horizon - 1].get("Close", future.iloc[horizon - 1].get("close"))
            )
            if close is not None and trigger_price:
                metrics[f"forward_return_{horizon}d"] = close / trigger_price - 1.0

    max_window = future.iloc[: max(HORIZONS)]
    if not max_window.empty:
        hi = pd.to_numeric(max_window.get("High", max_window.get("high")), errors="coerce").max()
        lo = pd.to_numeric(max_window.get("Low", max_window.get("low")), errors="coerce").min()
        if pd.notna(hi):
            metrics["max_favorable_excursion"] = float(hi) / trigger_price - 1.0
        if pd.notna(lo):
            metrics["max_adverse_excursion"] = float(lo) / trigger_price - 1.0

    return metrics


def _merge_audit(df: pd.DataFrame, audit: pd.DataFrame) -> pd.DataFrame:
    if df.empty or audit.empty or "ticker" not in df.columns or "ticker" not in audit.columns:
        return df

    cols = [
        c
        for c in ("ticker", "status", "eligible", "reason", "price", "breakout_level", "live_rvol")
        if c in audit.columns
    ]
    audit_small = audit[cols].copy()
    audit_small = audit_small.drop_duplicates(subset=["ticker"], keep="last")
    audit_small = audit_small.rename(
        columns={
            "status": "audit_status",
            "eligible": "audit_eligible",
            "reason": "audit_reason",
            "price": "audit_price",
            "breakout_level": "audit_breakout_level",
            "live_rvol": "audit_live_rvol",
        }
    )
    return df.merge(audit_small, on="ticker", how="left")


def enrich_signals(
    date: str,
    combined: pd.DataFrame,
    rejection: pd.DataFrame,
    snapshot: dict,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    if combined.empty:
        return combined.copy()

    enriched = combined.copy()
    if "ticker" not in enriched.columns:
        raise ValueError("combined.csv must contain a ticker column")

    enriched["ticker"] = enriched["ticker"].astype(str).str.upper()

    snapshot_lookup = _snapshot_lookup(snapshot)
    enriched = _merge_audit(enriched, rejection)

    try:
        cache = TickerCache(db_path=str(db_path))
    except Exception as exc:
        logger.warning("Could not initialize ticker cache at %s: %s", db_path, exc)
        cache = None
    sector_map = get_ticker_sector_mapping(enriched["ticker"].tolist())

    rows: list[dict[str, Any]] = []
    for _, row in enriched.iterrows():
        ticker = str(row["ticker"]).upper()
        detail = _normalize_detail(snapshot_lookup.get(ticker))

        trigger_price = _safe_float(
            _first_non_empty(
                row.get("trigger_price"),
                row.get("entry_price"),
                row.get("price"),
                detail.get("snapshot_price"),
            )
        )
        breakout_level = _safe_float(
            _first_non_empty(
                row.get("breakout_level"),
                detail.get("snapshot_breakout_level"),
                row.get("audit_breakout_level"),
            )
        )
        live_rvol = _safe_float(
            _first_non_empty(
                row.get("live_rvol"),
                row.get("rvol"),
                row.get("audit_live_rvol"),
                detail.get("snapshot_rvol"),
            )
        )
        dist_sma20 = _safe_float(
            _first_non_empty(row.get("dist_sma20"), row.get("dist_sma20_pct"), row.get("dist20"))
        )

        history = None
        if cache is not None:
            try:
                end_date = (pd.Timestamp(date) + timedelta(days=max(HORIZONS) * 4)).strftime(
                    "%Y-%m-%d"
                )
                history = cache.get_ohlcv(ticker, date, end_date, offline=True)
            except Exception as exc:
                logger.debug("Could not load OHLCV for %s: %s", ticker, exc)

        forward = compute_forward_metrics(history, date, trigger_price or 0)

        snapshot_waiting_for = _first_non_empty(
            row.get("snapshot_waiting_for"),
            row.get("waiting_for"),
            detail.get("snapshot_waiting_for"),
            row.get("audit_status"),
        )
        snapshot_blocker = _first_non_empty(
            row.get("snapshot_blocker"),
            row.get("primary_reason"),
            detail.get("snapshot_blocker"),
            row.get("audit_reason"),
        )

        signal_quality = infer_signal_quality(
            pd.Series(
                {
                    **row.to_dict(),
                    "trigger_price": trigger_price,
                    "breakout_level": breakout_level,
                    "dist_sma20": dist_sma20,
                    "snapshot_waiting_for": snapshot_waiting_for,
                    "snapshot_blocker": snapshot_blocker,
                }
            )
        )

        rows.append(
            {
                **row.to_dict(),
                "signal_quality": signal_quality,
                "trigger_price": trigger_price,
                "breakout_level": breakout_level,
                "live_rvol": live_rvol,
                "dist_sma20": dist_sma20,
                "sector_etf": _first_non_empty(
                    row.get("sector_etf"), detail.get("snapshot_sector_etf"), sector_map.get(ticker)
                ),
                "theme": _to_theme_string(
                    ticker, _first_non_empty(row.get("theme"), detail.get("snapshot_theme"))
                ),
                "snapshot_waiting_for": snapshot_waiting_for,
                "snapshot_blocker": snapshot_blocker,
                **forward,
            }
        )

    result = pd.DataFrame(rows)
    if "signal_date" not in result.columns:
        result["signal_date"] = date
    return result


def _win_rate(series: pd.Series) -> float:
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return float("nan")
    return float((series > 0).mean())


def _summarize_returns(df: pd.DataFrame) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "signals": int(len(df)),
        "unique_tickers": int(df["ticker"].nunique()) if "ticker" in df.columns else 0,
        "quality_counts": df["signal_quality"].value_counts(dropna=False).to_dict()
        if "signal_quality" in df.columns
        else {},
        "blocker_counts": df["snapshot_blocker"].fillna("NA").value_counts().head(25).to_dict()
        if "snapshot_blocker" in df.columns
        else {},
        "sector_counts": df["sector_etf"].fillna("NA").value_counts().head(25).to_dict()
        if "sector_etf" in df.columns
        else {},
        "theme_counts": df["theme"].fillna("NA").value_counts().head(25).to_dict()
        if "theme" in df.columns
        else {},
    }

    for horizon in HORIZONS:
        col = f"forward_return_{horizon}d"
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            summary[col] = {
                "win_rate": _win_rate(series),
                "avg_return": float(series.mean(skipna=True))
                if not series.dropna().empty
                else None,
                "median_return": float(series.median(skipna=True))
                if not series.dropna().empty
                else None,
                "positive": int((series > 0).sum(skipna=True)),
                "available": int(series.notna().sum()),
            }

    for quality, grp in df.groupby("signal_quality", dropna=False):
        key = str(quality)
        series = pd.to_numeric(
            grp.get("forward_return_5d", pd.Series(dtype=float)), errors="coerce"
        )
        summary.setdefault("by_quality", {})[key] = {
            "signals": int(len(grp)),
            "win_rate_5d": _win_rate(series),
            "avg_5d": float(series.mean(skipna=True)) if not series.dropna().empty else None,
            "median_5d": float(series.median(skipna=True)) if not series.dropna().empty else None,
        }

    for column in ("sector_etf", "theme", "snapshot_blocker"):
        if column in df.columns:
            grouped = {}
            for value, grp in df.groupby(df[column].fillna("NA"), dropna=False):
                series = pd.to_numeric(
                    grp.get("forward_return_5d", pd.Series(dtype=float)), errors="coerce"
                )
                grouped[str(value)] = {
                    "signals": int(len(grp)),
                    "win_rate_5d": _win_rate(series),
                    "avg_5d": float(series.mean(skipna=True))
                    if not series.dropna().empty
                    else None,
                }
            summary[f"by_{column}"] = grouped

    return summary


def _render_report(date: str, df: pd.DataFrame, summary: dict[str, Any]) -> str:
    lines = [
        f"# Live Signal Analysis - {date}",
        "",
        f"Signals: {summary.get('signals', 0)}",
        f"Unique tickers: {summary.get('unique_tickers', 0)}",
        "",
    ]

    lines.append("## Quality")
    for quality, stats in summary.get("by_quality", {}).items():
        wr = stats.get("win_rate_5d")
        if wr is not None and not pd.isna(wr):
            lines.append(f"- {quality}: {stats['signals']} | win rate 5d={wr:.2%}")
        else:
            lines.append(f"- {quality}: {stats['signals']}")

    lines.append("")
    lines.append("## Horizons")
    for horizon in HORIZONS:
        stats = summary.get(f"forward_return_{horizon}d", {})
        if stats:
            wr = stats.get("win_rate")
            avg = stats.get("avg_return")
            med = stats.get("median_return")
            if (
                wr is not None
                and avg is not None
                and med is not None
                and not any(pd.isna(x) for x in (wr, avg, med))
            ):
                lines.append(f"- {horizon}d: win={wr:.2%} avg={avg:.2%} med={med:.2%}")
            else:
                lines.append(f"- {horizon}d: insufficient data")

    if not df.empty:
        lines.append("")
        lines.append("## Top Rows")
        preview_cols = [
            c
            for c in [
                "ticker",
                "signal_quality",
                "trigger_price",
                "breakout_level",
                "live_rvol",
                "dist_sma20",
                "forward_return_5d",
            ]
            if c in df.columns
        ]
        lines.append(_df_to_markdown_safe(df[preview_cols].head(20)))

    return "\n".join(lines)


def _build_aggregate() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not ANALYSIS_ROOT.exists():
        return pd.DataFrame()

    for day_dir in sorted(ANALYSIS_ROOT.iterdir()):
        if not day_dir.is_dir() or day_dir.name == "aggregate":
            continue
        path = day_dir / "live_signal_returns.csv"
        if path.exists():
            frame = _read_csv(path)
            if not frame.empty:
                frame["analysis_date"] = day_dir.name
                frames.append(frame)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _write_outputs(date: str, df: pd.DataFrame, summary: dict[str, Any]) -> None:
    day_dir = ANALYSIS_ROOT / date
    day_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(day_dir / "live_signal_returns.csv", index=False)
    (day_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (day_dir / "report.md").write_text(_render_report(date, df, summary))


def _write_aggregate() -> None:
    aggregate = _build_aggregate()
    agg_dir = ANALYSIS_ROOT / "aggregate"
    agg_dir.mkdir(parents=True, exist_ok=True)

    if aggregate.empty:
        (agg_dir / "summary.json").write_text(json.dumps({"signals": 0}, indent=2))
        return

    aggregate.to_csv(agg_dir / "live_signal_returns_all.csv", index=False)
    summary = _summarize_returns(aggregate)
    (agg_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (agg_dir / "report.md").write_text(_render_report("aggregate", aggregate, summary))


def analyze_date(date: str) -> pd.DataFrame:
    combined, rejection, snapshot = load_inputs(date)
    if combined.empty:
        logger.info("No combined.csv found for %s", date)
        return pd.DataFrame()

    enriched = enrich_signals(date, combined, rejection, snapshot)
    summary = _summarize_returns(enriched)
    _write_outputs(date, enriched, summary)
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze live signal quality and forward returns")
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD")
    parser.add_argument(
        "--aggregate-only", action="store_true", help="Only rebuild aggregate outputs"
    )
    parser.add_argument(
        "--skip-aggregate", action="store_true", help="Do not rebuild aggregate outputs"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if not args.aggregate_only:
        date = args.date or today_ny()
        analyze_date(date)

    if not args.skip_aggregate:
        _write_aggregate()


if __name__ == "__main__":
    main()
