import json
import os

def load_watchlist():
    json_path = os.path.join(os.path.dirname(__file__), 'watchlist.json')
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        # Fallback if file doesn't exist
        return {
            "MOMENTUM": ['RDDT', 'PLTR', 'MSTR'],
            "TECH": ['AAPL', 'NVDA', 'TSLA', 'META', 'GOOGL'],
            "VOLATILITY": ['SMCI', 'CEG', 'COIN'],
            "ENERGY": ['CEG', 'NEE']
        }

_data = load_watchlist()

MOMENTUM = _data.get('MOMENTUM', [])
TECH = _data.get('TECH', [])
VOLATILITY = _data.get('VOLATILITY', [])
ENERGY = _data.get('ENERGY', [])

# Combined Default Watchlist
DEFAULT_WATCHLIST = list(set(MOMENTUM + TECH + VOLATILITY + ENERGY))