# src/data/theme_taxonomy.py — diccionario manual Capa 3
THEME_MAP = {
    # AI Infra & Semis
    "NVDA": ["AI infra", "semis"],
    "AMD":  ["AI infra", "semis"],
    "AMAT": ["semis"],       
    "TSM":  ["semis"],
    "MU":   ["semis"],       
    "STX":  ["semis"],
    "AVGO": ["AI infra", "semis"],
    "ARM":  ["semis"],
    "SMCI": ["AI infra"],
    "ON":   ["semis", "auto_semis"],
    "MCHP": ["semis"],
    "MPWR": ["semis", "power"],
    
    # Software & Cloud
    "PLTR": ["AI software", "data analytics"], 
    "AXON": ["defense tech"],
    "NET":  ["software", "cybersecurity"],    
    "ADSK": ["software", "design"],
    "MSFT": ["AI software", "cloud"],
    "GOOGL": ["AI software", "search", "cloud"],
    "META": ["AI software", "ads", "social"],
    "AMZN": ["cloud", "e-commerce"],
    "SNOW": ["data infrastructure", "software"],
    "DDOG": ["observability", "software"],
    "MDB":  ["database", "software"],
    "CRM":  ["software", "saas"],
    "NOW":  ["software", "saas"],
    
    # Cybersecurity
    "CRWD": ["cybersecurity", "software"],
    "PANW": ["cybersecurity", "software"],
    "ZS":   ["cybersecurity", "software"],
    "FTNT": ["cybersecurity", "hardware"],
    "OKTA": ["cybersecurity", "identity"],
    
    # Big Tech / Consumer Electronics
    "AAPL": ["hardware", "phones", "consumer tech"],
    "TSLA": ["EV", "AI", "energy storage"],
    
    # Fintech & Payments
    "SQ":   ["fintech", "payments"],
    "PYPL": ["fintech", "payments"],
    "HOOD": ["fintech", "brokerage"],
    "SOFI": ["fintech", "banking"],
    "MELI": ["e-commerce", "fintech"],
    "SHOP": ["e-commerce", "software"],
    
    # REITs
    "HST":  ["REITs", "hotels"],       
    "AMT":  ["REITs", "towers"],
    "PLD":  ["REITs", "logistics"],
    "CCI":  ["REITs", "towers"],
    "EQIX": ["REITs", "data centers"],
    
    # Energy / Uranium / Solar
    "CCJ":  ["uranium"],     
    "NXE":  ["uranium"],
    "XOM":  ["energy", "oil"],
    "CVX":  ["energy", "oil"],
    "FSLR": ["solar", "energy"],
    "ENPH": ["solar", "energy tech"],
    "SEDG": ["solar", "energy tech"],
    
    # Builders
    "LEN":  ["builders"],    
    "DHI":  ["builders"],
    "PHM":  ["builders"],
    
    # Crypto
    "COIN": ["crypto", "exchange"],      
    "MARA": ["crypto", "mining"],
    "MSTR": ["crypto", "bitcoin"],
    "WULF": ["crypto", "mining"],
    "RIOT": ["crypto", "mining"],
    
    # Biotech & Pharma
    "OGN":  ["pharma", "womens health"],
    "SYRE": ["biotech"],
    "RVMD": ["biotech"],
    "VRTX": ["biotech"],
    "LLY":  ["pharma", "glp1"],
    "NVO":  ["pharma", "glp1"],
    
    # Healthcare Plans
    "OSCR": ["healthcare", "managed care"],
    "CNC":  ["healthcare", "managed care"],
    "UNH":  ["healthcare", "managed care"],
    
    # Semiconductors & Foundry
    "MXL":  ["semis"],
    "INTC": ["semis", "foundry"],
    "STM":  ["semis"],
    "AXTI": ["semis", "materials"],
    "HIMX": ["semis"],
    "VSH":  ["semis"],
    "GFS":  ["semis", "foundry"],
    
    # Communication & Networking
    "AAOI": ["networking", "optics"],
    "NOK":  ["networking", "telecom"],
    "VIAV": ["networking"],
    "EXTR": ["networking"],
    "VSAT": ["networking", "satellite"],
    "ANET": ["networking", "AI infra"],
    
    # Hardware & Storage
    "SNDK": ["hardware", "storage"],
    "WDC":  ["hardware", "storage"],
    "TTMI": ["hardware", "electronics"],
    "DELL": ["hardware", "AI infra"],
    "VRT":  ["hardware", "liquid cooling", "AI infra"],
    
    # Industrials & Energy Equipment
    "BE":   ["energy tech", "fuel cells"],
    "AMSC": ["industrials", "electrical"],
    "LGN":  ["construction", "infrastructure"],
    "AESI": ["energy", "oil field services"],
    
    # Travel & Leisure
    "ABNB": ["travel", "hospitality"],
    "BKNG": ["travel", "booking"],
    "EXPE": ["travel", "booking"],
    "RCL":  ["travel", "cruises"],
    "CCL":  ["travel", "cruises"],
    
    # Consumer & Others
    "RSI":  ["consumer", "gaming"],
    "NAVN": ["software", "application"],
    "RELY": ["software", "infrastructure"],
}

def get_themes(ticker: str) -> list:
    return THEME_MAP.get(ticker, [])

TAXONOMY_VERSION = "v1.0-2026-05-12"
