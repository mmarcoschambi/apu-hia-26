#!/usr/bin/env python3
"""
DAILY TRADING WORKFLOW - Complete Pre-Market to Post-Market
Flujo completo automatizado para tu rutina diaria de trading

Usage:
    python daily_workflow.py pre-market      # Pre-market scan (antes de 9:30 AM)
    python daily_workflow.py market-open     # Market open check (9:30-10:00 AM)
    python daily_workflow.py mid-day         # Mid-day review (12:00 PM)
    python daily_workflow.py market-close    # EOD review (después de 4:00 PM)
    python daily_workflow.py full            # Run all steps automatically
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime, time as dt_time
import time as time_module

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from live_trading_scanner import LiveTradingScanner, load_watchlist_from_file
from position_tracker import PositionTracker


class DailyWorkflow:
    """Workflow automatizado para trading diario"""
    
    def __init__(self):
        self.scanner = LiveTradingScanner()
        self.tracker = PositionTracker()
        self.watchlist = load_watchlist_from_file()
        
    def pre_market_routine(self):
        """Rutina Pre-Market (antes de 9:30 AM)"""
        print("\n" + "="*80)
        print("🌅 PRE-MARKET ROUTINE")
        print("="*80 + "\n")
        
        # Step 1: Scan for new setups
        print("📍 STEP 1: Scanning for new setups...")
        print("-" * 80)
        setups = self.scanner.scan_watchlist(self.watchlist)
        
        if setups:
            print("\n✅ Setups found! Review and place orders.")
            self._show_order_placement_guide(setups)
        else:
            print("\n⏸️  No new setups today. Focus on existing positions.")
        
        # Step 2: Review existing positions
        print("\n" + "="*80)
        print("📍 STEP 2: Review existing positions")
        print("-" * 80 + "\n")
        self.tracker.show_dashboard()
        
        # Step 3: Action plan
        print("="*80)
        print("📋 PRE-MARKET ACTION PLAN")
        print("="*80)
        print("1. ✅ Place any BUY STOP orders from scan")
        print("2. ✅ Verify stop losses on existing positions")
        print("3. ✅ Set alerts for MANUAL_WATCH setups")
        print("4. ✅ Review market context (SPY/QQQ)")
        print("5. ✅ Be ready at 9:30 AM for executions")
        print("="*80 + "\n")
    
    def market_open_check(self):
        """Market Open Check (9:30-10:00 AM)"""
        print("\n" + "="*80)
        print("🔔 MARKET OPEN CHECK")
        print("="*80 + "\n")
        
        # Update positions
        print("📍 Updating current prices...")
        self.tracker.update_prices()
        
        # Show dashboard
        self.tracker.show_dashboard()
        
        print("="*80)
        print("⚡ MARKET OPEN ACTIONS")
        print("="*80)
        print("1. ✅ Check if any BUY STOP orders filled")
        print("2. ✅ Watch MANUAL setups for VWAP reclaim")
        print("3. ✅ Monitor for flush + recovery patterns")
        print("4. ✅ Cancel unfilled orders by 10:30 AM if no trigger")
        print("="*80 + "\n")
    
    def mid_day_review(self):
        """Mid-Day Review (12:00 PM)"""
        print("\n" + "="*80)
        print("☀️ MID-DAY REVIEW")
        print("="*80 + "\n")
        
        # Update positions
        self.tracker.update_prices()
        self.tracker.show_dashboard()
        
        print("="*80)
        print("🎯 MID-DAY CHECKLIST")
        print("="*80)
        print("1. ✅ Any positions in profit? Consider partial exit")
        print("2. ✅ Any positions near stop? Prepare mentally")
        print("3. ✅ Any MANUAL setups developed? Entry/pass decision")
        print("4. ✅ Cancel any unfilled BUY STOP orders")
        print("="*80 + "\n")
    
    def market_close_review(self):
        """Market Close Review (después de 4:00 PM)"""
        print("\n" + "="*80)
        print("🌆 END OF DAY REVIEW")
        print("="*80 + "\n")
        
        # Update final prices
        print("📍 Updating final prices...")
        self.tracker.update_prices()
        
        # Show dashboard
        self.tracker.show_dashboard()
        
        # Show recent closed trades
        print("\n" + "="*80)
        print("📍 Recent Closed Trades")
        print("="*80 + "\n")
        self.tracker.show_closed_trades(last_n=5)
        
        # Journal prompts
        print("="*80)
        print("📝 TRADING JOURNAL PROMPTS")
        print("="*80)
        print("1. What setups did I see today?")
        print("2. What did I execute and why?")
        print("3. What did I pass on and why?")
        print("4. How did I manage emotions?")
        print("5. What will I do differently tomorrow?")
        print("="*80 + "\n")
        
        # Prep for tomorrow
        print("="*80)
        print("🔮 PREP FOR TOMORROW")
        print("="*80)
        print("1. ✅ Review/update watchlist if needed")
        print("2. ✅ Note any patterns forming")
        print("3. ✅ Set calendar reminder for pre-market scan")
        print("4. ✅ Rest - mental capital is everything")
        print("="*80 + "\n")
    
    def full_workflow(self):
        """Execute full workflow with time-based automation"""
        print("\n" + "="*80)
        print("🤖 AUTOMATED DAILY WORKFLOW")
        print("="*80 + "\n")
        print("Running based on current time...")
        
        now = datetime.now().time()
        
        # Pre-market: before 9:30 AM
        pre_market_time = dt_time(9, 30)
        market_open_time = dt_time(10, 0)
        mid_day_time = dt_time(12, 0)
        market_close_time = dt_time(16, 0)
        
        if now < pre_market_time:
            print("⏰ Time for PRE-MARKET routine\n")
            self.pre_market_routine()
            
        elif pre_market_time <= now < market_open_time:
            print("⏰ Time for MARKET OPEN check\n")
            self.market_open_check()
            
        elif market_open_time <= now < mid_day_time:
            print("⏰ Time for MID-DAY review\n")
            self.mid_day_review()
            
        elif now >= market_close_time:
            print("⏰ Time for MARKET CLOSE review\n")
            self.market_close_review()
            
        else:
            print("⏰ Market hours - focus on execution\n")
            self.tracker.update_prices()
            self.tracker.show_dashboard()
    
    def _show_order_placement_guide(self, setups):
        """Quick guide for order placement"""
        buy_stops = [s for s in setups if s['signal'].action == 'BUY_STOP']
        
        if not buy_stops:
            return
        
        print("\n" + "="*80)
        print("📝 ORDER PLACEMENT GUIDE")
        print("="*80 + "\n")
        
        for setup in buy_stops:
            signal = setup['signal']
            symbol = setup['symbol']
            
            print(f"🔹 {symbol}")
            print(f"   Order Type: BUY STOP LIMIT")
            print(f"   Stop Price: ${signal.entry_price:.2f}")
            print(f"   Limit Price: ${signal.entry_price + 0.50:.2f} (add slippage)")
            print(f"   Stop Loss: ${signal.stop_loss:.2f}")
            print(f"   Duration: Day Order (cancel at 10:30 AM if not filled)")
            print()

    def run_validation(self) -> None:
        """Rutina de Validacion de Stress Testing y Robustez (Issue #11)"""
        print("\n" + "="*80)
        print("🛡️  STRATEGY VALIDATION & STRESS TESTING")
        print("="*80 + "\n")
        
        print("📍 Cargando parametros del modelo activo (production_config.json)...")
        import json
        import pandas as pd
        
        prod_config_path = Path("config/production_config.json")
        if not prod_config_path.exists():
            print("❌ Archivo config/production_config.json no encontrado.")
            return
            
        try:
            with open(prod_config_path, "r") as f:
                prod_cfg = json.load(f)
        except Exception as e:
            print(f"❌ Error al cargar production_config.json: {e}")
            return
            
        # Extraer parametros relevantes para el backtest
        t2_cfg = prod_cfg.get("tier2_filters", {})
        t1_cfg = prod_cfg.get("tier1_strategy", {})
        t3_cfg = prod_cfg.get("tier3_fixed", {})
        
        # Mapear parametros al motor de backtest
        params = {
            "max_dist_sma20": t2_cfg.get("max_dist_sma20", 8.94),
            "min_rvol": t2_cfg.get("min_rvol", 0.91),
            "min_adr": t2_cfg.get("min_adr", 1.97),
            "tp1_r": t1_cfg.get("tp1_r", 1.25),
            "tp2_r": t1_cfg.get("tp2_r", 3.0),
            "risk_dollars": 2878.0,
        }
        
        # Activar E25 si esta configurado
        if t3_cfg.get("use_dynamic_extension_sizing", False):
            params["use_dynamic_extension_sizing"] = True
            params["dynamic_extension_sizing"] = t3_cfg.get("dynamic_extension_sizing", {})
            
        print("📍 Preparando universo para simulacion...")
        # Usar tickers de la watchlist, limitados a 15 para velocidad de ejecucion diaria
        tickers = [t.upper() for t in self.watchlist if t.strip()]
        if not tickers:
            # Fallback a tickers de alta liquidez si la watchlist esta vacia
            tickers = ["AAPL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "GOOGL", "JPM", "XOM", "UNH", "AMD", "LLY", "V", "PG", "JNJ"]
            
        if len(tickers) > 15:
            tickers = tickers[:15]
            
        print(f"   Universo seleccionado ({len(tickers)} activos): {', '.join(tickers)}")
        
        # Fechas del stress test (ultimos 2 anos para robustez)
        test_dates = ("2023-01-01", "2024-12-31")
        print(f"   Rango de fechas: {test_dates[0]} a {test_dates[1]}")
        
        print("\n🔥 Ejecutando StressTestSuite...")
        try:
            from src.validation.stress_testing import StressTestSuite
            from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
            
            suite = StressTestSuite(engine_class=AdvancedVectorBTEngine)
            
            results = suite.run_full_stress_test(
                params=params,
                universe=tickers,
                test_dates=test_dates,
                verbose=True
            )
            
            # Guardar reporte de stress
            output_dir = Path("outputs/backtests")
            output_dir.mkdir(parents=True, exist_ok=True)
            report_path = output_dir / "daily_workflow_stress_report.json"
            
            import dataclasses
            import numpy as np
            
            def make_serializable(obj):
                if isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_serializable(x) for x in obj]
                elif isinstance(obj, tuple):
                    return tuple(make_serializable(x) for x in obj)
                elif isinstance(obj, np.bool_):
                    return bool(obj)
                elif isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return make_serializable(obj.tolist())
                else:
                    return obj
            
            with open(report_path, "w") as f:
                if dataclasses.is_dataclass(results):
                    res_dict = dataclasses.asdict(results)
                elif hasattr(results, "__dict__"):
                    res_dict = {k: v for k, v in results.__dict__.items() if not k.startswith("_")}
                else:
                    res_dict = results
                json.dump(make_serializable(res_dict), f, indent=2)
                
            print(f"\n✅ Reporte de Stress Test guardado en: {report_path}")
            
            # Calcular e imprimir metricas de robustez sobre el baseline
            print("\n🛡️  Calculando Robustness Metrics...")
            # Inicializar baseline engine para calcular la curva de equidad
            engine = AdvancedVectorBTEngine(
                universe=tickers,
                start_date=test_dates[0],
                end_date=test_dates[1],
                **params
            )
            engine.load_data()
            baseline_res = engine.run_backtest()
            
            # Generar reporte de robustez
            from src.validation.robustness_metrics import calculate_comprehensive_robustness_report
            equity_curve = pd.Series(baseline_res.get("equity", []))
            
            if len(equity_curve) == 0 and "equity_df" in baseline_res:
                equity_curve = baseline_res["equity_df"]["equity"]
                    
            if len(equity_curve) >= 30:
                backtest_result = {
                    "equity_curve": equity_curve,
                    "trades_df": pd.DataFrame(baseline_res.get("trades", [])),
                    "sharpe_ratio": baseline_res.get("sharpe_ratio", 0.0),
                    "max_drawdown_pct": abs(baseline_res.get("max_drawdown", 0.0)),
                    "total_trades": len(baseline_res.get("trades", [])),
                    "win_rate_pct": baseline_res.get("win_rate", 0.0),
                    "profit_factor": baseline_res.get("profit_factor", 0.0),
                }
                robustness_report = calculate_comprehensive_robustness_report(backtest_result)
                
                robustness_path = output_dir / "daily_workflow_robustness_report.json"
                with open(robustness_path, "w") as f:
                    json.dump(make_serializable(robustness_report), f, indent=2)
                    
                print(f"✅ Reporte de Robustez guardado en: {robustness_path}")
                print(f"   • Sortino: {robustness_report['risk_adjusted']['sortino']:.2f}")
                print(f"   • Omega: {robustness_report['risk_adjusted']['omega']:.2f}")
                print(f"   • Calmar: {robustness_report['risk_adjusted']['calmar']:.2f}")
                print(f"   • Probabilidad de Perdida: {robustness_report['probability_of_loss']*100:.1f}%")
            else:
                print("⚠️  La curva de equidad del baseline es demasiado corta para calcular metricas de robustez.")
                
        except Exception as e:
            print(f"❌ Error durante la validacion: {e}")
            import traceback
            traceback.print_exc()
        print("\n" + "="*80 + "\n")



def main():
    parser = argparse.ArgumentParser(description='Daily Trading Workflow')
    parser.add_argument('routine', choices=['pre-market', 'market-open', 'mid-day', 'market-close', 'validate', 'full'],
                       help='Which routine to run')
    
    args = parser.parse_args()
    
    workflow = DailyWorkflow()
    
    routines = {
        'pre-market': workflow.pre_market_routine,
        'market-open': workflow.market_open_check,
        'mid-day': workflow.mid_day_review,
        'market-close': workflow.market_close_review,
        'validate': workflow.run_validation,
        'full': workflow.full_workflow
    }
    
    routines[args.routine]()


if __name__ == "__main__":
    main()
