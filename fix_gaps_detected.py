import pandas as pd
import subprocess
import argparse
import sys
from pathlib import Path

def fix_gaps(year, years_to_download=2):
    report_file = f"gaps_report_{year}.csv"
    
    if not Path(report_file).exists():
        print(f"❌ No se encontró el reporte {report_file}. Ejecuta audit_data_gaps.py primero.")
        return

    print(f"📂 Leyendo reporte: {report_file}")
    try:
        df = pd.read_csv(report_file)
    except Exception as e:
        print(f"❌ Error leyendo CSV: {e}")
        return

    if df.empty:
        print("✅ El reporte está vacío. No hay gaps que arreglar.")
        return

    # Obtener tickers únicos que tienen gaps
    problem_tickers = df['Ticker'].unique().tolist()
    
    print(f"🔍 Encontrados {len(problem_tickers)} tickers únicos con problemas en {year}.")
    print(f"📋 Ejemplo: {', '.join(problem_tickers[:10])} ...")
    
    print(f"\n⚠️  ESTRATEGIA DE REPARACIÓN:")
    print(f"   Se re-descargarán los últimos {years_to_download} años completos para estos tickers.")
    print(f"   Esto rellenará los huecos automáticamente.")
    
    # Auto-confirmación para fluidez en entornos CLI, o input
    # confirm = input(f"¿Proceder con la reparación de {len(problem_tickers)} tickers? (s/n): ")
    # if confirm.lower() != 's':
    #     print("Cancelado.")
    #     return

    print(f"\n🚀 Iniciando reparación...")
    
    # Procesar en lotes de 20 para no saturar la consola ni la API
    batch_size = 20
    total_batches = (len(problem_tickers) + batch_size - 1) // batch_size
    
    for i in range(0, len(problem_tickers), batch_size):
        batch = problem_tickers[i:i+batch_size]
        current_batch = (i // batch_size) + 1
        
        print(f"\n🔄 Lote {current_batch}/{total_batches}: Reparando {len(batch)} tickers...")
        print(f"   Target: {', '.join(batch)}")
        
        # Llamamos a populate_historical_openbb.py forzando la actualización
        # --no-skip es importante para que sobreescriba lo que ya existe
        cmd = [
            sys.executable, 
            "populate_historical_openbb.py", 
            "--tickers"
        ] + batch + [
            "--years", str(years_to_download),
            "--no-skip"  # Forzar re-descarga
        ]
        
        try:
            # Ejecutar y esperar
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Error en este lote: {e}")
            # No detenemos el script, seguimos con el siguiente lote
        except KeyboardInterrupt:
            print("\n🛑 Interrumpido por usuario.")
            sys.exit()

    print("\n" + "="*60)
    print("✅ PROCESO DE REPARACIÓN TERMINADO")
    print("="*60)
    print(f"💡 PASO FINAL: Vuelve a ejecutar 'python3 audit_data_gaps.py --year {year}'")
    print("   para confirmar que la lista de gaps se ha reducido a cero (o casi cero).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Arreglar gaps detectados en reporte')
    parser.add_argument('--year', type=int, default=2025, help='Año del reporte a procesar (ej: 2025)')
    parser.add_argument('--history', type=int, default=2, help='Años de historia a re-descargar (default: 2)')
    args = parser.parse_args()
    
    fix_gaps(args.year, args.history)
