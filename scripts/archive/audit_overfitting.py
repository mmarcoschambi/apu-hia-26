import pandas as pd
import subprocess
import plotly.graph_objects as go
import numpy as np
import argparse
import sys
import os
from datetime import datetime

# Configuración de Rangos Lógicos
ADR_RANGE = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]
RVOL_RANGE = [1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0]

def run_backtest_iteration(start_date, end_date, adr, rvol, universe_source="sqlite"):
    """
    Ejecuta una iteración del backtest con parámetros específicos.
    """
    cmd = [
        sys.executable, "daily_backtest_runner.py",
        "--start", start_date,
        "--end", end_date,
        "--min_adr", str(adr),
        "--min_rvol", str(rvol),
        "--source", universe_source,
        "--equity", "100000",
        "--max_symbols", "200",  # Limitado para velocidad en optimización
        "--sort_by", "liquidity"
    ]
    
    # Capturar salida
    try:
        # Ejecutamos proceso ocultando output masivo, solo nos importa el CSV final
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Leer resultados
        if os.path.exists("backtest_results.csv"):
            df = pd.read_csv("backtest_results.csv")
            if not df.empty and 'pnl' in df.columns:
                total_pnl = df['pnl'].sum()
                win_rate = len(df[df['pnl'] > 0]) / len(df) * 100 if len(df) > 0 else 0
                trade_count = len(df)
                
                # Calcular Profit Factor
                gross_win = df[df['pnl'] > 0]['pnl'].sum()
                gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
                profit_factor = gross_win / gross_loss if gross_loss > 0 else 0
                
                return {
                    "ADR": adr,
                    "RVOL": rvol,
                    "PnL": total_pnl,
                    "WinRate": win_rate,
                    "Trades": trade_count,
                    "PF": profit_factor
                }
    except Exception as e:
        print(f"Error en iteración ADR {adr} / RVOL {rvol}: {e}")
    
    return None

def generate_heatmap(results, title, filename):
    df_res = pd.DataFrame(results)
    
    # Pivotar para formato matriz (Heatmap)
    pivot_table = df_res.pivot(index="RVOL", columns="ADR", values="PnL")
    
    # Crear Heatmap
    fig = go.Figure(data=go.Heatmap(
        z=pivot_table.values,
        x=pivot_table.columns,
        y=pivot_table.index,
        colorscale='Viridis',
        text=np.round(pivot_table.values, 0),
        texttemplate="%{text:$.0f}",
        hoverongaps=False
    ))

    fig.update_layout(
        title=f"🛡️ Mapa de Calor: {title} (ADR vs RVOL)",
        xaxis_title="Min ADR (%)",
        yaxis_title="Min RVOL (x)",
        width=800,
        height=600
    )
    
    fig.write_html(filename)
    print(f"✅ Mapa de calor guardado en: {filename}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2023-12-31")
    parser.add_argument("--name", default="OOS_Audit")
    args = parser.parse_args()

    print(f"🚀 Iniciando Auditoría de Sobreajuste ({args.start} a {args.end})")
    print(f"📊 Espacio de búsqueda: {len(ADR_RANGE)} x {len(RVOL_RANGE)} = {len(ADR_RANGE)*len(RVOL_RANGE)} combinaciones.")
    
    results = []
    
    total_iter = len(ADR_RANGE) * len(RVOL_RANGE)
    curr_iter = 0
    
    for rvol in RVOL_RANGE:
        for adr in ADR_RANGE:
            curr_iter += 1
            print(f"[{curr_iter}/{total_iter}] Probando ADR={adr}% | RVOL={rvol}x ... ", end="", flush=True)
            
            res = run_backtest_iteration(args.start, args.end, adr, rvol)
            
            if res:
                print(f"PnL: ${res['PnL']:,.0f} (PF: {res['PF']:.2f})")
                results.append(res)
            else:
                print("Error/Sin Trades")
                results.append({"ADR": adr, "RVOL": rvol, "PnL": 0, "WinRate": 0, "Trades": 0, "PF": 0})

    # Guardar resultados crudos
    pd.DataFrame(results).to_csv(f"audit_results_{args.name}.csv", index=False)
    
    # Generar Visualización
    generate_heatmap(results, f"PnL Total - {args.name}", f"heatmap_{args.name}.html")

if __name__ == "__main__":
    main()
