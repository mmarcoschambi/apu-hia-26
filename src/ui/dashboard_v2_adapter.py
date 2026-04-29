"""
dashboard_v2_adapter.py
=======================
Adapter de lectura para Dashboard 2.0 basado en artefactos del pipeline
integrado A+B y del scanner multi-combo.

El dashboard consume archivos ya generados; no recalcula lógica de negocio.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pandas as pd


class DashboardV2Adapter:
    """Carga artefactos live/historical y del master universe para Streamlit."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir or Path(__file__).resolve().parents[2])
        self.integration_root = self.base_dir / "outputs" / "integration"
        self.live_signals_root = self.base_dir / "outputs" / "live_signals"
        self.universe_csv_path = self.base_dir / "data" / "stable_universe.csv"
        self.universe_meta_path = self.base_dir / "data" / "stable_universe.meta.json"
        self.snapshot_root = self.base_dir / "outputs" / "paper_trading" / "universe_snapshots"

    def list_integration_runs(self, mode: str) -> list[str]:
        run = self.load_integration_run(mode=mode, date=None)
        run_date = str(run.get("run_date") or "latest")
        return [run_date]

    def list_combo_scan_runs(self) -> list[str]:
        if not self.live_signals_root.exists():
            return []
        runs = [path.name for path in self.live_signals_root.iterdir() if path.is_dir()]
        return sorted(runs, reverse=True)

    def load_integration_run(self, mode: str, date: Optional[str] = None) -> Dict[str, Any]:
        mode = mode.lower().strip()
        if mode not in {"live", "historical"}:
            raise ValueError(f"Unsupported mode: {mode}")

        run_dir = self.integration_root / mode
        files = {
            "signals_f1": run_dir / "signals_f1.jsonl",
            "signals_f1_csv": run_dir / "signals_f1.csv",
            "routed_f2": run_dir / "routed_f2.jsonl",
            "routed_f2_csv": run_dir / "routed_f2.csv",
            "plan_f3": run_dir / "plan_f3.jsonl",
            "plan_f3_csv": run_dir / "plan_f3.csv",
            "phase3_summary": run_dir / "phase3_summary.json",
            "router_summary": run_dir / "router_summary.json",
            "edge_report": run_dir / "edge_gate_report.json",
            "edge_metrics": run_dir / "edge_metrics.csv",
            "edge_metrics_by_strategy": run_dir / "edge_metrics_by_strategy.csv",
            "promotion_decisions": run_dir / "promotion_decisions.csv",
            "risk_rejected": run_dir / "risk_rejected.csv",
        }
        warnings = [f"Missing {key}: {path.name}" for key, path in files.items() if not path.exists()]

        unified_df = self._normalize_integration_df(self._load_table(files["signals_f1"], files["signals_f1_csv"]))
        routed_df = self._normalize_integration_df(self._load_table(files["routed_f2"], files["routed_f2_csv"]))
        execution_df = self._normalize_integration_df(self._load_table(files["plan_f3"], files["plan_f3_csv"]))
        risk_rejected_df = self._normalize_integration_df(self._load_csv(files["risk_rejected"]))
        edge_metrics_df = self._normalize_integration_df(self._load_csv(files["edge_metrics"]))
        edge_by_strategy_df = self._normalize_integration_df(self._load_csv(files["edge_metrics_by_strategy"]))
        promotions_df = self._normalize_integration_df(self._load_csv(files["promotion_decisions"]))

        phase3_summary = self._load_json(files["phase3_summary"])
        router_summary = self._load_json(files["router_summary"])
        edge_report = self._load_json(files["edge_report"])

        run_date = self._detect_run_date(unified_df, execution_df, phase3_summary, edge_report)

        return {
            "mode": mode,
            "run_dir": run_dir,
            "run_date": date or run_date,
            "warnings": warnings,
            "files": files,
            "unified_signals_df": unified_df,
            "routed_signals_df": routed_df,
            "execution_plan_df": execution_df,
            "risk_rejected_df": risk_rejected_df,
            "phase3_summary": phase3_summary,
            "router_summary": router_summary,
            "edge_report": edge_report,
            "edge_metrics_df": edge_metrics_df,
            "edge_metrics_by_strategy_df": edge_by_strategy_df,
            "promotion_decisions_df": promotions_df,
            "status": {
                "f1": not unified_df.empty,
                "f2": not routed_df.empty,
                "f3": bool(phase3_summary) or not execution_df.empty,
                "f4": bool(edge_report),
            },
        }

    def load_combo_scan_run(self, date: Optional[str] = None) -> Dict[str, Any]:
        run_date = date or (self.list_combo_scan_runs()[0] if self.list_combo_scan_runs() else None)
        if not run_date:
            return {
                "run_date": None,
                "run_dir": None,
                "warnings": ["No combo scan runs found"],
                "combo_scan_summary": {},
                "combo_signals_df": pd.DataFrame(),
                "agent_tables": {},
            }

        run_dir = self.live_signals_root / run_date
        run_summary_path = run_dir / "run_summary.json"
        combined_path = run_dir / "combined.csv"

        warnings = []
        if not run_summary_path.exists():
            warnings.append("Missing run_summary.json")
        if not combined_path.exists():
            warnings.append("Missing combined.csv")

        combined_df = self._normalize_combo_df(self._load_csv(combined_path))
        agent_tables: Dict[str, pd.DataFrame] = {}
        for csv_path in sorted(run_dir.glob("*.csv")):
            if csv_path.name == "combined.csv":
                continue
            agent_tables[csv_path.stem] = self._normalize_combo_df(self._load_csv(csv_path))

        return {
            "run_date": run_date,
            "run_dir": run_dir,
            "warnings": warnings,
            "combo_scan_summary": self._load_json(run_summary_path),
            "combo_signals_df": combined_df,
            "agent_tables": agent_tables,
        }

    def load_universe_snapshot(self) -> Dict[str, Any]:
        warnings = []
        universe_df = self._load_csv(self.universe_csv_path)
        if universe_df.empty and self.universe_csv_path.exists():
            universe_df = self._load_csv_with_header_fallback(self.universe_csv_path)
        if not self.universe_csv_path.exists():
            warnings.append("Missing stable_universe.csv")
        if not self.universe_meta_path.exists():
            warnings.append("Missing stable_universe.meta.json")

        snapshot_dates = []
        if self.snapshot_root.exists():
            snapshot_dates = sorted([path.name for path in self.snapshot_root.iterdir() if path.is_dir()], reverse=True)

        return {
            "stable_universe_df": universe_df,
            "stable_universe_meta": self._load_json(self.universe_meta_path),
            "snapshot_dates": snapshot_dates,
            "latest_snapshot_date": snapshot_dates[0] if snapshot_dates else None,
            "warnings": warnings,
        }

    def _normalize_integration_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        renamed = df.rename(
            columns={
                "symbol": "ticker",
                "router_reason_code": "router_reason",
                "entry_score": "normalized_score",
            }
        ).copy()
        for column in [
            "source_system",
            "strategy_id",
            "ticker",
            "signal_time",
            "trade_date",
            "entry_price_ref",
            "hydrated_price_source",
            "router_reason",
            "shares",
            "notional_usd",
            "metadata",
        ]:
            if column not in renamed.columns:
                renamed[column] = None

        renamed["metadata"] = renamed["metadata"].apply(self._normalize_metadata)
        metadata_fields = renamed["metadata"].apply(pd.Series).add_prefix("meta_")
        renamed = pd.concat([renamed, metadata_fields], axis=1)

        if "meta_hydrated_price_source" in renamed.columns and "hydrated_price_source" in renamed.columns:
            renamed["hydrated_price_source"] = renamed["hydrated_price_source"].fillna(renamed["meta_hydrated_price_source"])

        for column in ["signal_time", "trade_date"]:
            if column in renamed.columns:
                renamed[column] = pd.to_datetime(renamed[column], errors="coerce")

        return renamed

    def _normalize_combo_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        renamed = df.rename(
            columns={
                "agent": "agent_name",
                "combo": "combo_name",
            }
        ).copy()
        for column in [
            "agent_name",
            "combo_name",
            "ticker",
            "signal_date",
            "entry_score",
            "screener_score",
            "screener_reason",
            "pattern_signal",
            "tier2_filter",
            "entry_price",
            "rs_percentile",
            "rs_ret",
        ]:
            if column not in renamed.columns:
                renamed[column] = None

        if "signal_date" in renamed.columns:
            renamed["signal_date"] = pd.to_datetime(renamed["signal_date"], errors="coerce")

        return renamed

    def _detect_run_date(
        self,
        unified_df: pd.DataFrame,
        execution_df: pd.DataFrame,
        phase3_summary: Dict[str, Any],
        edge_report: Dict[str, Any],
    ) -> Optional[str]:
        for df, column in ((execution_df, "trade_date"), (unified_df, "signal_time")):
            if not df.empty and column in df.columns:
                values = df[column].dropna()
                if not values.empty:
                    return values.max().date().isoformat()

        preflight = edge_report.get("preflight", {})
        if preflight.get("common_date_end"):
            return str(preflight["common_date_end"])

        execution_date = phase3_summary.get("execution_date")
        return str(execution_date) if execution_date else None

    def _load_table(self, jsonl_path: Path, csv_path: Path) -> pd.DataFrame:
        if jsonl_path.exists():
            return self._load_jsonl(jsonl_path)
        return self._load_csv(csv_path)

    def _load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _load_jsonl(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        rows: list[Dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    rows.append(json.loads(line))
        except Exception:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    def _load_csv(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()

    def _load_csv_with_header_fallback(self, path: Path) -> pd.DataFrame:
        try:
            rows = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception:
            return pd.DataFrame()
        if not rows:
            return pd.DataFrame()
        if rows[0].lower() == "ticker":
            return pd.DataFrame({"ticker": rows[1:]})
        return pd.DataFrame({"ticker": rows})

    def _normalize_metadata(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {"raw_metadata": value}
        return {}


def get_dashboard_v2_adapter() -> DashboardV2Adapter:
    """Factory simple para mantener simetría con el adapter legacy."""
    return DashboardV2Adapter()
