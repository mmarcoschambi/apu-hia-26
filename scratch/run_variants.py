#!/usr/bin/env python3
import json
import argparse
import sys
from pathlib import Path

def check_significance(metrics_path: Path):
    if not metrics_path.exists():
        print(f"Error: {metrics_path} no existe.", file=sys.stderr)
        return None
    try:
        with open(metrics_path, "r") as f:
            metrics = json.load(f)
    except Exception as e:
        print(f"Error al leer {metrics_path}: {e}", file=sys.stderr)
        return None

    total_trades = metrics.get("total_trades", metrics.get("trades_count", 0))
    return total_trades, metrics

def main():
    parser = argparse.ArgumentParser(description="Compara variantes y valida significancia estadística.")
    parser.add_argument("metrics_files", nargs="+", help="Rutas a los archivos de métricas JSON a comparar.")
    parser.add_argument("-n", "--min-trades", type=int, default=30, help="Número mínimo de trades para significancia (default: 30).")
    args = parser.parse_args()

    results = []
    for file_str in args.metrics_files:
        path = Path(file_str)
        ret = check_significance(path)
        if ret is None:
            continue
        trades, metrics = ret
        results.append((path.name, trades, metrics))

    if not results:
        print("No se pudieron procesar métricas válidas.")
        sys.exit(1)

    print("=== Análisis de Significancia Estadística ===")
    print(f"Filtro: Mínimo de trades requerido (N) = {args.min_trades}\n")

    best_candidate = None
    best_metric = -999999.0

    for name, trades, metrics in results:
        total_return = metrics.get("total_return", 0.0)
        sharpe = metrics.get("sharpe_ratio", 0.0)
        
        status = "OK"
        if trades < args.min_trades:
            status = "⚠️ INSUFICIENTE EVIDENCIA"
        
        print(f"Variante: {name}")
        print(f"  Trades: {trades} | Retorno: {total_return}% | Sharpe: {sharpe}")
        print(f"  Estado: {status}")
        
        if trades >= args.min_trades and total_return > best_metric:
            best_metric = total_return
            best_candidate = (name, total_return, trades)
        print("-" * 40)

    if best_candidate:
        print(f"\n🏆 GANADOR: {best_candidate[0]} con Retorno de {best_candidate[1]}% ({best_candidate[2]} trades)")
    else:
        print("\n❌ GANADOR: Insuficiente evidencia, ampliar ventana.")

if __name__ == "__main__":
    main()
