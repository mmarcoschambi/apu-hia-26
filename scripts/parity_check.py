#!/usr/bin/env python3
"""
parity_check.py - Compara tickers live vs walk-forward.

Busca señales live en `outputs/live_signals/<date>/combined.csv` y un artefacto
WF asociado a esa fecha dentro de `outputs/walkforward/*/`.

Si la paridad cae por debajo de `MIN_PARITY_PCT`, dispara Telegram.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_DIR = PROJECT_ROOT / "outputs" / "live_signals"
WF_DIR = PROJECT_ROOT / "outputs" / "walkforward"
OUT_DIR = PROJECT_ROOT / "outputs" / "parity"

sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv()
from src.utils.telegram_client import telegram_send
from src.utils.telegram_client import telegram_send


@dataclass
class ParityResult:
    date: str
    generated_at: str
    wf_run_dir: str | None
    wf_fold: int | None
    wf_oos_start: str | None
    wf_oos_end: str | None
    tickers_live: list[str]
    tickers_wf: list[str]
    common_tickers: list[str]
    common_count: int
    union_count: int
    live_count: int
    wf_count: int
    match_pct: float
    coverage_pct: float
    min_parity_pct: float
    alert_triggered: bool
    source_file: str | None
    note: str | None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _load_live_tickers(date: str) -> pd.DataFrame:
    path = LIVE_DIR / date / "combined.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _extract_tickers(df: pd.DataFrame) -> list[str]:
    if df.empty or "ticker" not in df.columns:
        return []
    tickers = (
        df["ticker"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )
    return sorted(tickers)


def _walkforward_folds(report: dict[str, Any]) -> list[dict[str, Any]]:
    folds: list[dict[str, Any]] = []
    for mode in report.get("results", []):
        mode_name = mode.get("mode")
        for fold in mode.get("folds", []):
            item = dict(fold)
            item["mode"] = mode_name
            folds.append(item)
    return folds


def _extract_report_tickers(fold: dict[str, Any]) -> list[str]:
    for key in ("oos_tickers", "tickers", "signals_tickers"):
        value = fold.get(key)
        if isinstance(value, list):
            return sorted({str(v).strip() for v in value if str(v).strip()})
    return []


def _pick_walkforward_run(
    date: str,
) -> tuple[Path | None, dict[str, Any] | None, dict[str, Any] | None]:
    if not WF_DIR.exists():
        return None, None, None

    candidates: list[tuple[datetime, Path, dict[str, Any], dict[str, Any]]] = []
    target = pd.Timestamp(date)

    for run_dir in sorted([p for p in WF_DIR.iterdir() if p.is_dir()], reverse=True):
        report_path = run_dir / "walkforward_report.json"
        if not report_path.exists():
            continue
        try:
            report = json.loads(report_path.read_text())
        except Exception:
            continue

        for fold in _walkforward_folds(report):
            oos_start = pd.to_datetime(fold.get("oos_start"), errors="coerce")
            oos_end = pd.to_datetime(fold.get("oos_end"), errors="coerce")
            if pd.isna(oos_start) or pd.isna(oos_end):
                continue
            if oos_start <= target <= oos_end:
                candidates.append(
                    (
                        datetime.fromtimestamp(report_path.stat().st_mtime),
                        run_dir,
                        report,
                        fold,
                    )
                )
                break

    if not candidates:
        return None, None, None

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, run_dir, report, fold = candidates[0]
    return run_dir, report, fold


def _find_wf_signal_file(run_dir: Path) -> Path | None:
    preferred = [
        "oos_signals.csv",
        "signals_oos.csv",
        "wf_signals.csv",
        "signals.csv",
        "trades.csv",
        "oos_trades.csv",
    ]
    for name in preferred:
        path = run_dir / name
        if path.exists():
            return path

    for path in sorted(run_dir.glob("*.csv")):
        name = path.name.lower()
        if any(key in name for key in ("signal", "trade", "oos")):
            return path
    return None


def _load_wf_tickers(
    run_dir: Path, fold: dict[str, Any] | None = None
) -> tuple[list[str], Path | None, str | None]:
    if fold is not None:
        report_tickers = _extract_report_tickers(fold)
        if report_tickers:
            return report_tickers, None, None

    signal_file = _find_wf_signal_file(run_dir)
    if signal_file is None:
        return [], None, "No WF CSV artifact with tickers found"

    df = pd.read_csv(signal_file)
    tickers = _extract_tickers(df)
    if not tickers and "ticker" not in df.columns:
        return [], signal_file, "WF CSV does not contain ticker column"
    return tickers, signal_file, None


def _build_alert(res: ParityResult) -> str:
    status = "OK" if not res.alert_triggered else "ALERTA"
    return (
        f"<b>Parity Check</b>\n"
        f"Status: {status}\n"
        f"Date: {res.date}\n"
        f"Match: {res.match_pct:.2f}%\n"
        f"Coverage: {res.coverage_pct:.2f}%\n"
        f"Live: {res.live_count} | WF: {res.wf_count} | Common: {res.common_count}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Live/WF parity checker")
    parser.add_argument("--date", required=True, help="Date to compare (YYYY-MM-DD)")
    parser.add_argument(
        "--telegram", action="store_true", help="Send alert via Telegram"
    )
    parser.add_argument("--json-only", action="store_true", help="Skip console table")
    args = parser.parse_args()

    min_parity_pct = _safe_float(os.getenv("MIN_PARITY_PCT", "80"), 80.0)

    live_df = _load_live_tickers(args.date)
    tickers_live = _extract_tickers(live_df)

    run_dir, report, fold = _pick_walkforward_run(args.date)
    note = None
    source_file = None
    tickers_wf: list[str] = []
    wf_fold = None
    wf_oos_start = None
    wf_oos_end = None

    if run_dir is not None:
        tickers_wf, source_file_path, note = _load_wf_tickers(run_dir, fold)
        source_file = str(source_file_path) if source_file_path else None
        if fold is not None:
            wf_fold = int(fold.get("fold")) if fold.get("fold") is not None else None
            wf_oos_start = str(fold.get("oos_start")) if fold.get("oos_start") else None
            wf_oos_end = str(fold.get("oos_end")) if fold.get("oos_end") else None

    live_set = set(tickers_live)
    wf_set = set(tickers_wf)
    common = sorted(live_set & wf_set)
    union = sorted(live_set | wf_set)

    common_count = len(common)
    union_count = len(union)
    live_count = len(live_set)
    wf_count = len(wf_set)
    match_pct = (common_count / union_count * 100.0) if union_count else 0.0
    coverage_pct = (common_count / live_count * 100.0) if live_count else 0.0
    alert_triggered = match_pct < min_parity_pct

    result = ParityResult(
        date=args.date,
        generated_at=datetime.now().isoformat(),
        wf_run_dir=str(run_dir) if run_dir else None,
        wf_fold=wf_fold,
        wf_oos_start=wf_oos_start,
        wf_oos_end=wf_oos_end,
        tickers_live=tickers_live,
        tickers_wf=tickers_wf,
        common_tickers=common,
        common_count=common_count,
        union_count=union_count,
        live_count=live_count,
        wf_count=wf_count,
        match_pct=match_pct,
        coverage_pct=coverage_pct,
        min_parity_pct=min_parity_pct,
        alert_triggered=alert_triggered,
        source_file=source_file,
        note=note,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{args.date}_check.json"
    out_path.write_text(json.dumps(asdict(result), indent=2, default=str))

    if not args.json_only:
        sep = "=" * 72
        print(f"\n{sep}")
        print(f"  PARITY CHECK  |  {args.date}")
        print(f"{sep}")
        print(f"  Live tickers:     {live_count}")
        print(f"  WF tickers:       {wf_count}")
        print(f"  Common:           {common_count}")
        print(f"  Match (Jaccard):  {match_pct:.2f}%")
        print(f"  Coverage live:    {coverage_pct:.2f}%")
        print(f"  Threshold:        {min_parity_pct:.2f}%")
        print(f"  WF run:           {result.wf_run_dir or 'not found'}")
        print(f"  WF source:        {source_file or 'not found'}")
        if note:
            print(f"  Note:             {note}")
        print(f"{sep}")
        if common:
            print("  Common tickers:")
            print("    " + ", ".join(common[:30]))
        print(f"\nSaved: {out_path}")

    if args.telegram and alert_triggered:
        ok = telegram_send(
            f"⚠ PARIDAD BAJA: {match_pct:.2f}%\n"
            f"Date: {args.date}\n"
            f"Live: {live_count} | WF: {wf_count} | Common: {common_count}"
        )
        print(f"Telegram: {'sent' if ok else 'failed'}")


if __name__ == "__main__":
    main()
