import requests
import pandas as pd
import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def fetch_gamma_data():
    """
    Scrapes DIX and GEX data from Squeezemetrics CSV.
    Returns a dict with latest values and status.
    """
    csv_url = "https://squeezemetrics.com/monitor/download/dix.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(csv_url, headers=headers, timeout=10)
        if response.status_code == 404:
            return None # Fuente no disponible hoy todavia
        response.raise_for_status()
        
        df = pd.read_csv(io.StringIO(response.text))
        if df.empty:
            return None
            
        # Standard columns: date, price, dix, gex
        latest = df.iloc[-1]
        
        return {
            "date": str(latest.get("date")),
            "dix": float(latest.get("dix", 0)),
            "gex": float(latest.get("gex", 0)),
            "price": float(latest.get("price", 0)),
            "updated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error scraping gamma data: {e}")
        return None

if __name__ == "__main__":
    data = fetch_gamma_data()
    print(data)
