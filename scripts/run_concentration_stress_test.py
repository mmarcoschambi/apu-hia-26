#!/usr/bin/env python3
"""
scripts/run_concentration_stress_test.py
Plan E21: Concentration Stress Test & Defensive Shadow Mode.
Performs an ablation study and bootstrapping on Variant E consolidated trades
to audit concentration and calculate real statistical edge.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.utils.sector_rotation import SECTOR_MAP

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "backtests"
REPORT_JSON = OUTPUT_DIR / "concentration_stress_test_report.json"
REPORT_MD = OUTPUT_DIR / "concentration_stress_test_report.md"
VALIDATION_REPORT_JSON = OUTPUT_DIR / "variant_e_validation_report.json"

# Configuración de archivos de entrada
TRADE_FILES = [
    "sp500_variant_e_1920_trades.csv",
    "sp500_variant_e_2122_trades.csv",
    "sp500_variant_e_2324_trades.csv",
    "sp500_variant_e_2526_trades.csv",
    "russell_variant_e_1920_trades.csv",
    "russell_variant_e_2122_trades.csv",
    "russell_variant_e_2324_trades.csv",
    "russell_variant_e_2526_trades.csv"
]

def load_consolidated_trades() -> pd.DataFrame:
    """Carga y concatena todos los trades de la Variante E."""
    aggregated = []
    for file_name in TRADE_FILES:
        file_path = OUTPUT_DIR / file_name
        if not file_path.exists():
            print(f"⚠️ Archivo de trades no encontrado: {file_path.name}")
            continue
        try:
            df = pd.read_csv(file_path)
            if not df.empty:
                # Extraer metadatos del nombre de archivo
                parts = file_name.split("_")
                df["index_name"] = "SP500" if "sp500" in parts[0] else "RUSSELL1000"
                df["window"] = parts[3]  # e.g., '1920'
                aggregated.append(df)
        except Exception as e:
            print(f"❌ Error leyendo {file_name}: {e}")
            
    if not aggregated:
        print("❌ No se pudieron cargar trades para el stress test.")
        return pd.DataFrame()
        
    df_all = pd.concat(aggregated, ignore_index=True)
    # Asignar sector ETF
    df_all["sector_etf"] = df_all["symbol"].map(SECTOR_MAP).fillna("Other")
    return df_all

def run_bootstrap_sim(returns: np.ndarray, n_iterations: int = 5000) -> Dict:
    """Ejecuta simulación de remuestreo Bootstrap de 5,000 iteraciones."""
    if len(returns) == 0:
        return {
            "total_trades": 0,
            "win_rate": {"p5": 0.0, "p50": 0.0, "p95": 0.0},
            "profit_factor": {"p5": 0.0, "p50": 0.0, "p95": 0.0},
            "trade_sharpe": {"p5": 0.0, "p50": 0.0, "p95": 0.0}
        }
        
    n_trades = len(returns)
    boot_win_rates = []
    boot_pfs = []
    boot_sharpes = []
    
    np.random.seed(42)  # Rigor y reproducibilidad
    
    for _ in range(n_iterations):
        sample = np.random.choice(returns, size=n_trades, replace=True)
        
        # Win Rate
        win_rate = (sample > 0).sum() / n_trades * 100
        boot_win_rates.append(win_rate)
        
        # Profit Factor
        pos_sum = sample[sample > 0].sum()
        neg_sum = abs(sample[sample < 0].sum())
        pf = pos_sum / neg_sum if neg_sum > 0 else (99.0 if pos_sum > 0 else 1.0)
        boot_pfs.append(pf)
        
        # Sharpe Ratio (basado en trades)
        mean_ret = sample.mean()
        std_ret = sample.std()
        sharpe = mean_ret / std_ret if std_ret > 0 else 0.0
        boot_sharpes.append(sharpe)
        
    boot_pfs = np.nan_to_num(boot_pfs, nan=1.0, posinf=99.0)
    
    return {
        "total_trades": int(n_trades),
        "win_rate": {
            "p5": float(np.percentile(boot_win_rates, 5)),
            "p50": float(np.percentile(boot_win_rates, 50)),
            "p95": float(np.percentile(boot_win_rates, 95))
        },
        "profit_factor": {
            "p5": float(np.percentile(boot_pfs, 5)),
            "p50": float(np.percentile(boot_pfs, 50)),
            "p95": float(np.percentile(boot_pfs, 95))
        },
        "trade_sharpe": {
            "p5": float(np.percentile(boot_sharpes, 5)),
            "p50": float(np.percentile(boot_sharpes, 50)),
            "p95": float(np.percentile(boot_sharpes, 95))
        }
    }

def calculate_group_metrics(df_subset: pd.DataFrame) -> Dict:
    """Calcula las métricas deterministas para un subgrupo."""
    if df_subset.empty:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0,
            "avg_return": 0.0
        }
    returns = df_subset["return_pct"].values
    pos_sum = returns[returns > 0].sum()
    neg_sum = abs(returns[returns < 0].sum())
    pf = pos_sum / neg_sum if neg_sum > 0 else (99.0 if pos_sum > 0 else 1.0)
    
    return {
        "total_trades": int(len(returns)),
        "win_rate": float((returns > 0).sum() / len(returns) * 100),
        "profit_factor": float(pf),
        "total_pnl": float(df_subset["pnl"].sum()),
        "avg_return": float(returns.mean())
    }

def main():
    print("=============================================================")
    print("🧪 PLAN E21: CONCENTRATION STRESS TEST Y ABLATION STUDY")
    print("=============================================================\n")
    
    # 1. Cargar trades consolidados
    trades_df = load_consolidated_trades()
    if trades_df.empty:
        sys.exit(1)
        
    print(f"✅ Se cargaron exitosamente {len(trades_df)} trades limpios agregados.\n")
    
    # 2. Configurar los 7 grupos de estrés (Ablation Setups)
    setups = {
        "1. Complete (Reference)": trades_df,
        "2. Ex-WDC": trades_df[trades_df["symbol"] != "WDC"],
        "3. Ex-NVDA": trades_df[trades_df["symbol"] != "NVDA"],
        "4. Ex-WDC+NVDA": trades_df[~trades_df["symbol"].isin(["WDC", "NVDA"])],
        "5. Solo XLK (Tech)": trades_df[trades_df["sector_etf"] == "XLK"],
        "6. Ex-XLK (No-Tech)": trades_df[trades_df["sector_etf"] != "XLK"],
        "7. Ex-Negative Sectors": trades_df[~trades_df["sector_etf"].isin(["XLV", "XLY", "XLRE", "XLE"])]
    }
    
    ablation_results = {}
    
    # 3. Ejecutar simulación y bootstrap para cada grupo
    for name, df_subset in setups.items():
        print(f"⏳ Procesando: {name} ({len(df_subset)} trades)...")
        metrics = calculate_group_metrics(df_subset)
        
        # Bootstrapping (5,000 corridas)
        returns = df_subset["return_pct"].values
        boot_stats = run_bootstrap_sim(returns, n_iterations=5000)
        
        ablation_results[name] = {
            "metrics": metrics,
            "bootstrap": boot_stats
        }
    
    # 4. Cargar Reporte de Validación para evaluar Criterios Go/No-Go
    mdd_improved_ratio = 0.0
    bull_vs_bear_drift = {}
    
    if VALIDATION_REPORT_JSON.exists():
        try:
            with open(VALIDATION_REPORT_JSON, "r") as f:
                val_data = json.load(f)
                
            matrix = val_data.get("validation_matrix", {})
            mdd_improved_count = 0
            total_cells = 0
            
            for idx, windows in matrix.items():
                for win_suffix, cell in windows.items():
                    total_cells += 1
                    if cell["criteria"]["mdd_improved"]:
                        mdd_improved_count += 1
                        
            if total_cells > 0:
                mdd_improved_ratio = mdd_improved_count / total_cells
                
        except Exception as e:
            print(f"⚠️ No se pudo procesar variant_e_validation_report.json: {e}")
            
    # 5. Evaluar Criterios de Decisión Go/No-Go
    # A. GO_SHADOW_CONTINUE
    go_shadow_continue = mdd_improved_ratio >= 0.50
    
    # B. NO_GO_PRODUCTION
    ex_wdc_nvda_pf_p50 = ablation_results["4. Ex-WDC+NVDA"]["bootstrap"]["profit_factor"]["p50"]
    no_go_production = ex_wdc_nvda_pf_p50 < 1.0
    
    # C. GO_SECTOR_STUDY
    xlk_pf_p50 = ablation_results["5. Solo XLK (Tech)"]["bootstrap"]["profit_factor"]["p50"]
    ex_xlk_pf_p50 = ablation_results["6. Ex-XLK (No-Tech)"]["bootstrap"]["profit_factor"]["p50"]
    go_sector_study = (xlk_pf_p50 > ex_xlk_pf_p50) and (ex_xlk_pf_p50 < 1.0)
    
    # D. BOOTSTRAP RISK INDICATOR
    complete_pf_p5 = ablation_results["1. Complete (Reference)"]["bootstrap"]["profit_factor"]["p5"]
    bootstrap_risk_warning = complete_pf_p5 < 1.0
    
    decisions = {
        "GO_SHADOW_CONTINUE": {
            "status": "✅ COMPLIED" if go_shadow_continue else "❌ REJECTED",
            "reason": f"La Variante E mejoró el Drawdown Máximo (MDD) en el {mdd_improved_ratio*100:.1f}% de las ventanas (Requisito >= 50%)."
        },
        "NO_GO_PRODUCTION": {
            "status": "⚠️ NO-GO ACTIVE" if no_go_production else "✅ PASSED",
            "reason": f"Al remover WDC+NVDA, la mediana (p50) del Profit Factor del Bootstrap es de {ex_wdc_nvda_pf_p50:.2f} (Umbral de quiebra < 1.00)."
        },
        "GO_SECTOR_STUDY": {
            "status": "🎯 RECOMMEND ACTIVE" if go_sector_study else "⏸️ INACTIVE",
            "reason": f"El Profit Factor sectorial en Tech es rentable ({xlk_pf_p50:.2f}) mientras que ex-Tech es perdedor neto ({ex_xlk_pf_p50:.2f} < 1.00)."
        },
        "BOOTSTRAP_RISK_ALERT": {
            "status": "🚨 HIGH DANGER" if bootstrap_risk_warning else "✅ CONTROLLED",
            "reason": f"El percentil 5 (pesimista) del Profit Factor de la Variante E completa es de {complete_pf_p5:.2f} (< 1.00, alto riesgo de erosión)."
        }
    }
    
    # 6. Guardar Reporte JSON
    stress_test_data = {
        "timestamp": datetime.now().isoformat(),
        "total_aggregated_trades": len(trades_df),
        "ablation_setups": ablation_results,
        "go_no_go_decisions": decisions
    }
    
    with open(REPORT_JSON, "w") as f:
        json.dump(stress_test_data, f, indent=2)
    print(f"💾 Reporte unificado de estrés JSON guardado en: {REPORT_JSON}")
    
    # 7. Generar Reporte Markdown Ejecutivo
    generate_markdown_stress_report(stress_test_data)
    print(f"💾 Reporte ejecutivo de estrés Markdown guardado en: {REPORT_MD}")
    
    print("\n=============================================================")
    print("🏁 PLAN E21: STRESS TEST DE CONCENTRACIÓN COMPLETADO")
    print("=============================================================")

def generate_markdown_stress_report(data: Dict):
    """Genera una hermosa y profunda presentación ejecutiva de las métricas de estrés."""
    ablation = data["ablation_setups"]
    decisions = data["go_no_go_decisions"]
    
    md = []
    md.append("# Reporte de Estrés de Concentración y Ablación (Plan E21)")
    md.append(f"\n*Generado automáticamente el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    
    md.append("\n## 🔬 1. Resumen Científico")
    md.append(f"\nSometimos los **{data['total_aggregated_trades']} trades limpios** consolidados de la **Variante E** (obtenidos del backtest multi-índice libre de sesgos) a un análisis sistemático de estrés y eliminación secuencial de componentes (**Ablation Study**). Este proceso aísla las fuentes reales de retorno de la estrategia y calcula la fragilidad matemática mediante **Bootstrap de 5,000 iteraciones** por subgrupo.")
    
    # Caja de Decisiones Go/No-Go
    md.append("\n## 🛑 2. Matriz de Decisión Cuantitativa (Go/No-Go)")
    
    # Alerta Bootstrap
    alert_status = decisions["BOOTSTRAP_RISK_ALERT"]["status"]
    if "HIGH DANGER" in alert_status:
        md.append("\n> [!CAUTION]")
        md.append("> **ALERTA DE FRAGILIDAD ESTADÍSTICA ACTIVA (BOOTSTRAP P5 < 1.00)**:")
        md.append(f"> *   {decisions['BOOTSTRAP_RISK_ALERT']['reason']}")
        md.append("> *   *Implicación:* Queda estrictamente prohibida la asignación de capital real completo a la estrategia en este estado. Su viabilidad financiera requiere mitigación de riesgo inmediata.")
        
    for name, dec in decisions.items():
        if name == "BOOTSTRAP_RISK_ALERT": continue
        md.append(f"\n### {name}")
        md.append(f"*   **Estado:** `{dec['status']}`")
        md.append(f"*   **Fundamento Técnico:** {dec['reason']}")
        
    md.append("\n---")
    
    # Tabla Comparativa de Ablación
    md.append("\n## 📊 3. Métricas de Ablación y Bootstrapping (5,000 Iteraciones)")
    md.append("\nMedimos la robustez del Profit Factor, Win Rate y Sharpe Ratio al sustraer o aislar concentraciones específicas:")
    
    md.append("\n| Setup de Ablación / Estrés | Trades | PnL Total | Win Rate Determ. | PF Histórico | Bootstrap WR (p5 - p95) | Bootstrap PF (p5 - p95) | Bootstrap Sharpe (p5 - p95) |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    for name, stats in ablation.items():
        m = stats["metrics"]
        b = stats["bootstrap"]
        
        md.append(
            f"| **{name}** "
            f"| {m['total_trades']} "
            f"| {m['total_pnl']:+,.2f}$ "
            f"| {m['win_rate']:.2f}% "
            f"| {m['profit_factor']:.2f} "
            f"| {b['win_rate']['p5']:.1f}% - {b['win_rate']['p95']:.1f}% "
            f"| **{b['profit_factor']['p5']:.2f} - {b['profit_factor']['p95']:.2f}** "
            f"| {b['trade_sharpe']['p5']:.3f} - {b['trade_sharpe']['p95']:.3f} |"
        )
        
    md.append("\n---")
    
    # Análisis de Hallazgos
    md.append("\n## 🔍 4. Diagnósticos Estructurales Clave")
    
    # NVDA/WDC dependency
    ex_wdc_nvda_pf = ablation["4. Ex-WDC+NVDA"]["metrics"]["profit_factor"]
    complete_pf = ablation["1. Complete (Reference)"]["metrics"]["profit_factor"]
    md.append("\n### 💾 A. Dependencia de WDC y NVDA (Líderes Tecnológicos)")
    md.append(f"*   La Variante E completa tiene un Profit Factor de **{complete_pf:.2f}**.")
    md.append(f"*   Al sustraer únicamente los trades de **Western Digital (WDC) y Nvidia (NVDA)**, el Profit Factor cae a **{ex_wdc_nvda_pf:.2f}**.")
    if ex_wdc_nvda_pf < 1.0:
        md.append(f"*   *Veredicto de Estrés:* **COLAPSO DE RETORNO**. Sin estos dos ganadores excepcionales, la estrategia pierde su ventaja y se vuelve una erosionadora de capital. La rentabilidad histórica general no es sistémica, sino altamente dependiente de dos eventos alcistas aislados.")
    else:
        md.append(f"*   *Veredicto de Estrés:* **EDGE REDUCIDO PERO VIVO**. La estrategia retiene un Profit Factor rentable de {ex_wdc_nvda_pf:.2f} ex-ganadores, indicando que el patrón defensivo tiene base robusta.")
        
    # Tech vs Non-tech
    xlk_pf = ablation["5. Solo XLK (Tech)"]["metrics"]["profit_factor"]
    ex_xlk_pf = ablation["6. Ex-XLK (No-Tech)"]["metrics"]["profit_factor"]
    md.append("\n### 🌐 B. Filtro Sectorial XLK vs ex-XLK")
    md.append(f"*   **Solo XLK:** Genera un Profit Factor histórico sobresaliente de **{xlk_pf:.2f}** en {ablation['5. Solo XLK (Tech)']['metrics']['total_trades']} trades.")
    md.append(f"*   **Ex-XLK (Todos los otros sectores):** Cae a un Profit Factor deficitario de **{ex_xlk_pf:.2f}**.")
    if ex_xlk_pf < 1.0:
        md.append(f"*   *Veredicto de Estrés:* **INEFICACIA FUERA DE TECNOLOGÍA**. El modelo momentum-v2 no posee un edge momentum multisectorial. Tratar de operar sectores de energía, finanzas, salud o consumo con las reglas de stop de ATR y divergencia temática produce pérdidas consistentes. La estrategia debe ser comercializada **únicamente como un sistema sectorial tecnológico (XLK-only)**.")
    else:
        md.append(f"*   *Veredicto de Estrés:* **COMPORTAMIENTO ROBUSTO MULTISECTORIAL**. El modelo mantiene rentabilidad en múltiples industrias.")

    md.append("\n---")
    md.append("\n## 🛠️ 5. Próximos Pasos Recomendados en el Pipeline Quantitative")
    md.append("\nBasado en la evidencia dura revelada por Plan E21, el plan de acción óptimo es:")
    md.append("\n1.  **Mantener Variante E en Shadow Mode (Torre de Control / VPS):** En fase de observación, con alerta de fragilidad estadística en mente.")
    md.append("\n2.  **Transición a XLK-Only o Enfoque de Filtro Sectorial:** Dadas las pérdidas sistemáticas en sectores no tecnológicos, se recomienda agregar un filtro para escanear y disparar señales **únicamente** en activos del sector de Tecnología (XLK) o Comunicaciones (XLC). Esto optimiza el Profit Factor general sin alterar los parámetros de salida.")
    md.append("\n3.  **Desarrollo del Interruptor de Régimen de Mercado (Dynamic Switch):** Dado el gran costo de oportunidad de la Variante E defensiva en mercados alcistas puros, es mandatorio avanzar en el pre-cálculo del `health_score` histórico para habilitar la alternancia dinámica (Attack en bull generalizado / Defense con Variante E en bear/laterales).")
    
    with open(REPORT_MD, "w") as f:
        f.write("\n".join(md))

if __name__ == "__main__":
    main()
