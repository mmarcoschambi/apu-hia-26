#!/usr/bin/env python3
"""
WEEKLY KPIs & PERFORMANCE REVIEW
================================
Template para reporte semanal de paper trading:
- Resumen de performance por estrategia
- Métricas clave: Sharpe, PF, DD, win rate, frecuencia
- Alertas y recomendaciones de acción
- Seguimiento vs benchmark/shadow

Usage:
    python3 scripts/paper_weekly_review.py
    python3 scripts/paper_weekly_review.py --weeks 4
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

PAPER_CONFIG = ROOT / "config" / "paper_portfolio_config.json"
PAPER_OUTPUTS = ROOT / "outputs" / "paper_trading"


from src.paper.analytics_io import load_analytics_range


def load_portfolio_config():
    if PAPER_CONFIG.exists():
        return json.load(open(PAPER_CONFIG))
    return {}


def load_daily_reports(days=30):
    reports = []
    if not PAPER_OUTPUTS.exists():
        return reports
    for f in sorted(PAPER_OUTPUTS.glob("daily_pnl_*.json")):
        try:
            data = json.load(open(f))
            data["_file"] = f.name
            reports.append(data)
        except Exception as e:
            logger.warning(f"Failed to load {f}: {e}")
    return sorted(reports, key=lambda x: x.get("date", ""))[-days:]


def load_universe_audit_reports(days=30):
    reports = []
    snapshot_dir = PAPER_OUTPUTS / "universe_snapshots"
    if not snapshot_dir.exists():
        return reports
    today = datetime.now()
    for i in range(days):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        audit_path = snapshot_dir / date / f"universe_audit_{date}.json"
        if audit_path.exists():
            try:
                data = json.load(open(audit_path))
                data["_date"] = date
                reports.append(data)
            except Exception as e:
                logger.warning(f"Failed to load {audit_path}: {e}")
    return sorted(reports, key=lambda x: x.get("_date", ""))


def compute_universe_metrics(universe_reports):
    if not universe_reports:
        return {
            "blocked_days": 0,
            "avg_divergence_pct": 0.0,
            "max_divergence_pct": 0.0,
            "avg_tickers_count": 0,
            "total_days": 0,
        }

    blocked_days = sum(1 for r in universe_reports if not r.get("gate_passed", True))
    divergences = [r.get("divergence_pct", 0) for r in universe_reports]
    tickers = [r.get("live_size", 0) for r in universe_reports]

    return {
        "blocked_days": blocked_days,
        "avg_divergence_pct": round(sum(divergences) / len(divergences), 2)
        if divergences
        else 0.0,
        "max_divergence_pct": round(max(divergences), 2) if divergences else 0.0,
        "avg_tickers_count": round(sum(tickers) / len(tickers), 0) if tickers else 0,
        "total_days": len(universe_reports),
    }


def compute_rolling_metrics(reports, combo):
    default = {
        "sharpe": 0.0,
        "pf": 0.0,
        "win_rate": 0.0,
        "trades": 0,
        "dd": 0.0,
        "pnl_r": 0.0,
    }
    if not reports:
        return default
    trades = []
    for r in reports:
        strat = r.get("strategies", {}).get(combo, {})
        if strat:
            trades.append(strat)
    if not trades:
        return default
    total_trades = sum(t.get("fills", 0) for t in trades)
    total_pnl_r = sum(t.get("pnl_r", 0) for t in trades)
    winners = sum(1 for t in trades if t.get("pnl_r", 0) > 0)
    win_rate = winners / len(trades) if trades else 0
    return {
        "sharpe": 0.0,
        "pf": 1.0 if total_trades > 0 else 0.0,
        "win_rate": win_rate * 100,
        "trades": total_trades,
        "pnl_r": total_pnl_r,
    }


def generate_weekly_report(weeks=4):
    logger.info("=" * 70)
    logger.info("WEEKLY PERFORMANCE REVIEW")
    logger.info("=" * 70)

    config = load_portfolio_config()
    strategies = config.get("portfolio", {}).get("strategies", [])
    shadow = config.get("portfolio", {}).get("shadow", [])

    days = weeks * 7
    reports = load_daily_reports(days)

    logger.info(f"📅 Period: Last {weeks} weeks ({len(reports)} daily reports)")
    logger.info("")

    all_combos = [(s["combo"], s.get("role", "PAPER")) for s in strategies]
    all_combos += [(s["combo"], s.get("role", "SHADOW")) for s in shadow]

    rows = []
    for combo, role in all_combos:
        metrics = compute_rolling_metrics(reports, combo)
        strategy_cfg = next((s for s in strategies if s["combo"] == combo), {})
        min_trades_for_validation = int(
            strategy_cfg.get("min_trades_for_validation", 30)
        )
        sample_ready = metrics["trades"] >= min_trades_for_validation
        status = "✅" if role == "GO-PAPER" else "👁️" if role == "WATCH-PAPER" else "📊"
        logger.info(
            f"{status} {combo:<35} trades={metrics['trades']:>3}  "
            f"WR={metrics['win_rate']:>5.1f}%  PF={metrics['pf']:>4.2f}  R={metrics['pnl_r']:>+6.2f}"
        )
        if role in ["GO-PAPER", "WATCH-PAPER"] and not sample_ready:
            logger.info(
                f"   ↳ Sample insuficiente: {metrics['trades']}/{min_trades_for_validation} trades "
                f"(se evita juicio de PF/Sharpe por ahora)"
            )
        rows.append(
            {
                "combo": combo,
                "role": role,
                "trades": metrics["trades"],
                "win_rate": metrics["win_rate"],
                "pf": metrics["pf"],
                "pnl_r": metrics["pnl_r"],
                "sample_ready": sample_ready,
                "min_trades_for_validation": min_trades_for_validation,
            }
        )

    logger.info("")
    logger.info("UNIVERSE GATE METRICS:")
    universe_reports = load_universe_audit_reports(days)
    universe_metrics = compute_universe_metrics(universe_reports)
    logger.info(f"  Days analyzed: {universe_metrics['total_days']}")
    logger.info(f"  Blocked days: {universe_metrics['blocked_days']}")
    logger.info(f"  Avg divergence: {universe_metrics['avg_divergence_pct']}%")
    logger.info(f"  Max divergence: {universe_metrics['max_divergence_pct']}%")
    logger.info(f"  Avg universe size: {universe_metrics['avg_tickers_count']:.0f}")

    if universe_metrics["blocked_days"] >= 2:
        logger.warning(
            f"  🚨 ALERT: {universe_metrics['blocked_days']} days blocked - review universe source!"
        )
    if universe_metrics["max_divergence_pct"] > 15.0:
        logger.warning(
            f"  🚨 ALERT: Max divergence {universe_metrics['max_divergence_pct']}% exceeds 15% threshold!"
        )

    logger.info("")

    all_combos = [(s["combo"], s.get("role", "PAPER")) for s in strategies]
    all_combos += [(s["combo"], s.get("role", "SHADOW")) for s in shadow]

    rows = []
    for combo, role in all_combos:
        metrics = compute_rolling_metrics(reports, combo)
        strategy_cfg = next((s for s in strategies if s["combo"] == combo), {})
        min_trades_for_validation = int(
            strategy_cfg.get("min_trades_for_validation", 30)
        )
        sample_ready = metrics["trades"] >= min_trades_for_validation
        status = "✅" if role == "GO-PAPER" else "👁️" if role == "WATCH-PAPER" else "📊"
        logger.info(
            f"{status} {combo:<35} trades={metrics['trades']:>3}  "
            f"WR={metrics['win_rate']:>5.1f}%  PF={metrics['pf']:>4.2f}  R={metrics['pnl_r']:>+6.2f}"
        )
        if role in ["GO-PAPER", "WATCH-PAPER"] and not sample_ready:
            logger.info(
                f"   ↳ Sample insuficiente: {metrics['trades']}/{min_trades_for_validation} trades "
                f"(se evita juicio de PF/Sharpe por ahora)"
            )
        rows.append(
            {
                "combo": combo,
                "role": role,
                "trades": metrics["trades"],
                "win_rate": metrics["win_rate"],
                "pf": metrics["pf"],
                "pnl_r": metrics["pnl_r"],
                "sample_ready": sample_ready,
                "min_trades_for_validation": min_trades_for_validation,
            }
        )

    logger.info("")
    logger.info("ALERTS & ACTIONS:")
    for row in rows:
        if row["role"] in ["GO-PAPER", "WATCH-PAPER"] and row["sample_ready"]:
            if row["pf"] < 1.1:
                logger.warning(f"  ⚠️ {row['combo']}: PF below 1.1 threshold")
            if row["pnl_r"] < -3.0:
                logger.warning(f"  ⚠️ {row['combo']}: Negative R exceeding -3.0")

    logger.info("")
    logger.info("RECOMMENDATIONS:")
    for row in rows:
        if row["role"] == "GO-PAPER":
            if not row["sample_ready"]:
                logger.info(
                    f"  ⏳ {row['combo']}: Insufficient sample "
                    f"({row['trades']}/{row['min_trades_for_validation']} trades)"
                )
            elif row["pf"] > 1.15 and row["pnl_r"] > 0:
                logger.info(f"  ➡️  {row['combo']}: Continue - performing well")
            elif row["pf"] < 1.0:
                logger.warning(f"  ⏸️  {row['combo']}: Move to WATCH (PF < 1.0)")

    # === Analytics Summary ===
    logger.info("")
    logger.info("📊 ANALYTICS SUMMARY (from analytics_*.json)")

    today = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    analytics_list = load_analytics_range(start_date, today)

    if not analytics_list:
        logger.info("  ℹ️ No analytics data available yet")
    else:
        # Aggregate metrics
        expectancy_vals = [
            a.get("overall_quality", {}).get("expectancy", 0) for a in analytics_list
        ]
        calmar_vals = [
            a.get("overall_quality", {}).get("calmar", 0) for a in analytics_list
        ]
        sharpe_vals = [
            a.get("overall_quality", {}).get("sharpe", 0) for a in analytics_list
        ]
        pf_vals = [
            a.get("overall_quality", {}).get("profit_factor", 0) for a in analytics_list
        ]
        mdd_vals = [
            a.get("overall_quality", {}).get("max_drawdown_90d", 0)
            for a in analytics_list
        ]
        soft_ruin_vals = [
            a.get("risk_checks", {}).get("soft_ruin_30", 0) for a in analytics_list
        ]
        hard_ruin_vals = [
            a.get("risk_checks", {}).get("hard_ruin_50", 0) for a in analytics_list
        ]

        kelly_tiers = [
            a.get("position_sizing", {}).get("kelly_tier", "UNKNOWN")
            for a in analytics_list
        ]

        avg_expectancy = (
            sum(expectancy_vals) / len(expectancy_vals) if expectancy_vals else 0
        )
        avg_calmar = sum(calmar_vals) / len(calmar_vals) if calmar_vals else 0
        avg_sharpe = sum(sharpe_vals) / len(sharpe_vals) if sharpe_vals else 0
        avg_pf = sum(pf_vals) / len(pf_vals) if pf_vals else 0
        max_mdd = max(mdd_vals) if mdd_vals else 0
        avg_soft_ruin = (
            sum(soft_ruin_vals) / len(soft_ruin_vals) if soft_ruin_vals else 0
        )
        avg_hard_ruin = (
            sum(hard_ruin_vals) / len(hard_ruin_vals) if hard_ruin_vals else 0
        )

        quarter_count = kelly_tiers.count("QUARTER")
        half_count = kelly_tiers.count("HALF")

        logger.info(f"  Avg Expectancy: {avg_expectancy:+.4f} R/trade")
        logger.info(f"  Avg Calmar: {avg_calmar:.2f} | Avg Sharpe: {avg_sharpe:.2f}")
        logger.info(f"  Avg PF: {avg_pf:.2f} | Max DD (90d): {max_mdd:.1f}%")
        logger.info(
            f"  Avg Soft Ruin (30%): {avg_soft_ruin * 100:.2f}% | Hard Ruin (50%): {avg_hard_ruin * 100:.2f}%"
        )
        logger.info(f"  Kelly Tier: {half_count} HALF, {quarter_count} QUARTER")

    report = {
        "generated_at": datetime.now().isoformat(),
        "weeks_lookback": weeks,
        "days_covered": len(reports),
        "strategies": rows,
    }
    report_path = (
        PAPER_OUTPUTS / f"weekly_report_{datetime.now().strftime('%Y%m%d')}.json"
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"✅ Report saved: {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Weekly Paper Trading Review")
    parser.add_argument("--weeks", type=int, default=4, help="Weeks to review")
    args = parser.parse_args()
    generate_weekly_report(args.weeks)


if __name__ == "__main__":
    main()
