#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path
import logging

# Configuración de logging profesional
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("morning_workflow.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def run_step(command, description):
    logger.info(f"🚀 INICIANDO: {description}")
    try:
        # Usamos check=True para que lance excepción en error
        result = subprocess.run(command, shell=True, check=True, capture_output=False)
        logger.info(f"✅ COMPLETADO: {description}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ ERROR en {description}: {e}")
        return False
    except Exception as e:
        logger.error(f"⚠️ Error inesperado en {description}: {e}")
        return False

def main():
    root = Path(__file__).resolve().parent
    
    logger.info("=== 🌅 INICIANDO WORKFLOW MATUTINO INTEGRADO ===")

    # 1. Identificar nuevos tickers del QQQ/Russell
    run_step("python3 data/index_data_downloader.py", "Identificando nuevos tickers en índices")
    
    # 2. Descargar datos para los nuevos (si existe el archivo)
    new_tickers_file = Path("data/new_tickers.txt")
    if new_tickers_file.exists():
        with open(new_tickers_file, "r") as f:
            content = f.read().strip()
            if content:
                logger.info(f"Nuevos tickers detectados: {content}")
                run_step(f"python3 populate_market_data.py --tickers {content}", "Descargando datos históricos para nuevos tickers")
            else:
                logger.info("No hay nuevos tickers para descargar.")
    
    # --- BLOQUE DE LIMPIEZA Y CALIDAD (The "Perfect" Workflow) ---
    
    # 3. Limpiar tickers basura
    run_step("python3 purge_broken_tickers.py", "Limpiando tickers sin datos o corruptos")
    
    # 4. Reparar huecos (Gaps)
    run_step("python3 fix_gaps_detected.py", "Detectando y reparando huecos en el historial")
    
    # 5. Precomputar métricas base en SQLite
    run_step("python3 populate_precomputed_metrics.py", "Calculando métricas base en SQLite (SMA20/50, ADR)")

    # --- BLOQUE DE OPTIMIZACIÓN Y VELOCIDAD ---

    # 6. Sincronizar a PKL para máxima velocidad en Streamlit
    if Path("sync_sqlite_to_pkl.py").exists():
        run_step("python3 sync_sqlite_to_pkl.py", "Sincronizando SQLite -> PKL (Cache Streamlit)")
    
    # 7. Precomputar todos los indicadores en el Cache
    # Se corre después del sync para asegurar que los .pkl tengan todo
    run_step("python3 precompute_all_indicators.py", "Calculando indicadores técnicos avanzados")

    # 8. Optimizar Base de Datos SQLite
    run_step("python3 optimize_sqlite_indexes.py", "Optimizando índices y estructura de SQLite")

    logger.info("=== ✅ WORKFLOW COMPLETADO EXITOSAMENTE. SISTEMA LISTO PARA TRADING ===")

if __name__ == "__main__":
    main()
