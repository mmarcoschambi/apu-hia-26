
import os
import pandas as pd
import numpy as np
import logging
import json
from datetime import datetime
from pathlib import Path
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DEL EXPERIMENTO ---
EXP_NAME = "EXP-010_Dynamic_ADR_Stop"
OUTPUT_DIR = Path("outputs/experiments") / EXP_NAME
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Universo y Fechas (Walk-Forward Folds)
FOLDS = [
    {"name": "2022", "start": "2022-01-01", "end": "2022-12-31"},
    {"name": "2023", "start": "2023-01-01", "end": "2023-12-31"},
    {"name": "2024", "start": "2024-01-01", "end": "2024-12-31"},
    {"name": "2025", "start": "2025-01-01", "end": "2025-05-01"},
]

# Variantes del experimento
VARIANTS = {
    "A_baseline": {"stop_mode": 0, "max_stop_pct": 0.08, "sizing_mode": 0},
    "B1_cristian_fixed_risk": {"stop_mode": 1, "adr_stop_fraction": 0.5, "max_stop_pct": 0.08, "sizing_mode": 0},
    "B2_cristian_adaptive": {"stop_mode": 1, "adr_stop_fraction": 0.5, "max_stop_pct": 0.08, "sizing_mode": 1},
    "B3_cristian_reject_lt2": {"stop_mode": 4, "adr_stop_fraction": 0.5, "reject_stop_below_pct": 0.02, "max_stop_pct": 0.08, "sizing_mode": 0},
    "C_atr15": {"stop_mode": 2, "max_stop_pct": 0.08, "sizing_mode": 0},
    "D_floor2": {"stop_mode": 3, "adr_stop_fraction": 0.5, "adr_stop_floor_pct": 0.02, "max_stop_pct": 0.08, "sizing_mode": 0},
    "E_floor3": {"stop_mode": 3, "adr_stop_fraction": 0.5, "adr_stop_floor_pct": 0.03, "max_stop_pct": 0.08, "sizing_mode": 0},
}

# Parámetros base comunes
BASE_PARAMS = {
    "initial_capital": 100000,
    "risk_dollars": 500,
    "max_exposure_pct": 0.50, # More exposure for the test
    "tp1_r": 1.25,
    "tp2_r": 3.0,
    "tp1_pct": 0.33,
    "tp2_pct": 0.33,
    "runner_pct": 0.34,
    "fee_rate": 0.001,
    "slippage_rate": 0.001,
    "use_trailing_stop": True,
    "be_threshold_r": 1.0,
    "signal_type": "pocket_pivot",
    "pp_vol_mult": 0.8, # More permissive
    "min_rvol": 0.5, # Relaxed
    "min_adr": 1.0, # Relaxed
}

def run_experiment():
    results = []
    
    # Cargar universo completo de la DB
    universe_path = Path("config/db_tickers.txt")
    if universe_path.exists():
        with open(universe_path, 'r') as f:
            universe = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        universe = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "META", "GOOGL", "AMZN", "NFLX", "PLTR"]

    logger.info(f"🧪 Starting experiment {EXP_NAME} with {len(universe)} tickers")

    for fold in FOLDS:
        logger.info(f"--- Fold: {fold['name']} ({fold['start']} to {fold['end']}) ---")
        
        for v_name, v_params in VARIANTS.items():
            logger.info(f"   Running Variant: {v_name}")
            
            # Unir parámetros
            params = {**BASE_PARAMS, **v_params}
            
            try:
                engine = AdvancedVectorBTEngine(
                    universe=universe,
                    start_date=fold['start'],
                    end_date=fold['end'],
                    **params
                )
                
                # Ejecutar backtest
                stats = engine.run_backtest()
                
                # Extraer métricas clave de stats (más robusto)
                trades_df = stats.get('trades_df')
                equity_curve = stats.get('equity_curve')
                
                if trades_df is not None and len(trades_df) > 0:
                    wr = stats.get('win_rate', 0) * 100
                    pf = stats.get('profit_factor', 0)
                    total_trades = len(trades_df)
                    phantom_stops = trades_df['is_phantom_stop'].sum() if 'is_phantom_stop' in trades_df.columns else 0
                    stop_trades = trades_df[trades_df['exit_phase'] == 'STOP']
                    phantom_pct = (phantom_stops / len(stop_trades)) * 100 if len(stop_trades) > 0 else 0
                    
                    # Missing metrics
                    winners = trades_df[trades_df['pnl'] > 0]
                    losers = trades_df[trades_df['pnl'] < 0]
                    avg_winner = winners['pnl'].mean() if len(winners) > 0 else 0
                    avg_loser = losers['pnl'].mean() if len(losers) > 0 else 0
                    
                    # Avg holding (exit_day_idx - entry_day_idx)
                    trades_df['holding_days'] = trades_df['day_idx'] - trades_df['entry_day_idx']
                    avg_holding = trades_df['holding_days'].mean()
                    
                    # Segmentación por ADR
                    trades_df['adr_segment'] = pd.cut(
                        trades_df['context_adr'],
                        bins=[0, 3, 5, 8, 100],
                        labels=['ADR < 3%', 'ADR 3-5%', 'ADR 5-8%', 'ADR > 8%']
                    )
                    
                    segment_stats = {}
                    for seg in ['ADR < 3%', 'ADR 3-5%', 'ADR 5-8%', 'ADR > 8%']:
                        seg_trades = trades_df[trades_df['adr_segment'] == seg]
                        if len(seg_trades) > 0:
                            seg_wr = (seg_trades['pnl'] > 0).mean() * 100
                            seg_pos = seg_trades[seg_trades['pnl'] > 0]
                            seg_neg = seg_trades[seg_trades['pnl'] < 0]
                            seg_pf = seg_pos['pnl'].sum() / abs(seg_neg['pnl'].sum()) if len(seg_neg) > 0 else 99.0
                            segment_stats[seg] = {
                                "wr": round(seg_wr, 1), 
                                "pf": round(seg_pf, 2), 
                                "count": len(seg_trades),
                                "phantom_pct": round((seg_trades['is_phantom_stop'].sum() / len(seg_trades[seg_trades['exit_phase'] == 'STOP'])) * 100, 1) if len(seg_trades[seg_trades['exit_phase'] == 'STOP']) > 0 else 0
                            }

                    fold_result = {
                        "fold": fold['name'],
                        "variant": v_name,
                        "win_rate": round(wr, 1),
                        "profit_factor": round(pf, 2),
                        "trades": total_trades,
                        "phantom_pct": round(phantom_pct, 1),
                        "final_equity": round(equity_curve.iloc[-1], 2) if equity_curve is not None and len(equity_curve) > 0 else 100000,
                        "max_drawdown": round(stats.get('max_drawdown', 0) * 100, 2),
                        "sharpe": round(stats.get('sharpe_ratio', 0), 2),
                        "avg_stop_dist": round(trades_df['stop_dist_pct'].mean() * 100, 2) if 'stop_dist_pct' in trades_df.columns else 0.0,
                        "avg_winner": round(avg_winner, 2),
                        "avg_loser": round(avg_loser, 2),
                        "avg_holding": round(avg_holding, 1),
                        "segment_stats": segment_stats
                    }
                    
                    # Guardar trades de esta variante
                    trades_filename = f"trades_{fold['name']}_{v_name}.csv"
                    trades_df.to_csv(OUTPUT_DIR / trades_filename, index=False)
                else:
                    fold_result = {
                        "fold": fold['name'],
                        "variant": v_name,
                        "win_rate": 0.0,
                        "profit_factor": 0.0,
                        "trades": 0,
                        "phantom_stops": 0,
                        "phantom_pct": 0.0,
                        "final_equity": 100000.0,
                        "max_drawdown": 0.0,
                        "sharpe": 0.0,
                        "avg_stop_dist": 0.0,
                        "segment_stats": {}
                    }
                
                results.append(fold_result)
                logger.info(f"      Result: Trades={fold_result['trades']}, WR={fold_result['win_rate']:.1f}%, PF={fold_result['profit_factor']:.2f}, Phantom={fold_result['phantom_pct']:.1f}%")
                
            except Exception as e:
                logger.error(f"      Error in {v_name} on {fold['name']}: {e}")
                import traceback
                logger.error(traceback.format_exc())

    # Generar Reporte Final
    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_DIR / "summary_results.csv", index=False)
    
    # Pivotar para comparación fácil
    pivot_wr = results_df.pivot(index="fold", columns="variant", values="win_rate")
    pivot_pf = results_df.pivot(index="fold", columns="variant", values="profit_factor")
    pivot_phantom = results_df.pivot(index="fold", columns="variant", values="phantom_pct")
    pivot_stop_dist = results_df.pivot(index="fold", columns="variant", values="avg_stop_dist")
    pivot_sharpe = results_df.pivot(index="fold", columns="variant", values="sharpe")
    pivot_max_dd = results_df.pivot(index="fold", columns="variant", values="max_drawdown")
    
    logger.info("\n" + "="*30)
    logger.info("WIN RATE COMPARISON")
    logger.info("\n" + pivot_wr.to_string())
    
    logger.info("\n" + "="*30)
    logger.info("PROFIT FACTOR COMPARISON")
    logger.info("\n" + pivot_pf.to_string())

    logger.info("\n" + "="*30)
    logger.info("PHANTOM STOP COMPARISON (%)")
    logger.info("\n" + pivot_phantom.to_string())

    logger.info("\n" + "="*30)
    logger.info("SHARPE RATIO COMPARISON")
    logger.info("\n" + pivot_sharpe.to_string())

    logger.info("\n" + "="*30)
    logger.info("MAX DRAWDOWN COMPARISON (%)")
    logger.info("\n" + pivot_max_dd.to_string())

    logger.info("\n" + "="*30)
    logger.info("AVG STOP DISTANCE COMPARISON (%)")
    logger.info("\n" + pivot_stop_dist.to_string())
    
    # Save JSON report
    report = {
        "timestamp": datetime.now().isoformat(),
        "experiment": EXP_NAME,
        "results": results
    }
    with open(OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
        json.dump(report, f, indent=4)

if __name__ == "__main__":
    run_experiment()
