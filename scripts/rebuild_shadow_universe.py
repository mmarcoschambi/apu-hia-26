import sys
import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.data.ticker_cache import TickerCache

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

def rebuild():
    # 1. Escanear snapshots de mayo de 2026
    paper_dir = PROJECT_ROOT / "outputs" / "paper_finviz"
    logger.info(f"Scanning snapshots in {paper_dir} for May 2026...")
    
    unique_tickers = set()
    snapshot_files = list(paper_dir.glob("2026-05-*/snapshot.json"))
    
    logger.info(f"Found {len(snapshot_files)} snapshot files to process.")
    for snap_file in sorted(snapshot_files):
        try:
            with open(snap_file, "r") as f:
                data = json.load(f)
            watchlist = data.get("watchlist_detail", {})
            if watchlist:
                unique_tickers.update(watchlist.keys())
                logger.info(f"  Processed {snap_file.parent.name}: added {len(watchlist)} candidates.")
        except Exception as e:
            logger.warning(f"  Failed to process {snap_file}: {e}")
            
    tickers_list = sorted(list(unique_tickers))
    logger.info(f"Total unique tickers found across all May 2026 snapshots: {len(tickers_list)}")
    
    if not tickers_list:
        logger.error("No tickers found to download. Exiting.")
        return
        
    # 2. Descargar y actualizar datos en lote usando TickerCache (grupos de 40)
    cache = TickerCache()
    try:
        # Descargamos desde 2025 para garantizar suficientes barras para el cálculo de SMAs (especialmente SMA200) y acelerar 5x
        success = cache.update_ohlcv_batch(tickers_list, start_date="2025-01-01", end_date="2026-06-05")
        logger.info(f"Database reconstruction completed: successfully updated {success}/{len(tickers_list)} tickers.")
    except Exception as e:
        logger.error(f"Error during batch download: {e}")
    finally:
        cache.close()

if __name__ == "__main__":
    rebuild()
