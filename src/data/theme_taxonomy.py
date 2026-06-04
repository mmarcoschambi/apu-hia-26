# src/data/theme_taxonomy.py — Capa 3: Taxonomía Temática Versionada e Histórica (Point-in-Time)

# --- 1. TAXONOMÍA ACTUAL (2023-Presente) ---
# Incluye narrativas modernas como Inteligencia Artificial (AI infra, AI software), GLP-1 y Crypto maduro.
THEME_MAP_CURRENT = {
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

# --- 2. TAXONOMÍA HISTÓRICA 2021-2022 ---
# En este periodo la IA generativa no existía como tema bursátil (se elimina "AI infra"/"AI software" por "software"/"hardware").
# El GLP-1 y el auge masivo de obesidad médica de LLY/NVO no había explotado aún (se catalogan simplemente como "pharma").
THEME_MAP_2022 = {
    # Semis (Sin prefijo AI)
    "NVDA": ["semis"],
    "AMD":  ["semis"],
    "AMAT": ["semis"],       
    "TSM":  ["semis"],
    "MU":   ["semis"],       
    "STX":  ["semis"],
    "AVGO": ["semis"],
    "ARM":  ["semis"],
    "SMCI": ["hardware"],  # Servidores tradicionales
    "ON":   ["semis", "auto_semis"],
    "MCHP": ["semis"],
    "MPWR": ["semis", "power"],
    
    # Software & Cloud (Sin prefijo AI)
    "PLTR": ["software", "data analytics"], 
    "AXON": ["defense tech"],
    "NET":  ["software", "cybersecurity"],    
    "ADSK": ["software", "design"],
    "MSFT": ["cloud", "software"],
    "GOOGL": ["search", "cloud", "software"],
    "META": ["ads", "social", "software"],
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
    
    # Consumer Electronics & EV
    "AAPL": ["hardware", "phones", "consumer tech"],
    "TSLA": ["EV", "energy storage"],
    
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
    
    # Biotech & Pharma (Sin tag GLP-1)
    "OGN":  ["pharma", "womens health"],
    "SYRE": ["biotech"],
    "RVMD": ["biotech"],
    "VRTX": ["biotech"],
    "LLY":  ["pharma"],
    "NVO":  ["pharma"],
    
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
    "ANET": ["networking"],
    
    # Hardware & Storage
    "SNDK": ["hardware", "storage"],
    "WDC":  ["hardware", "storage"],
    "TTMI": ["hardware", "electronics"],
    "DELL": ["hardware"],
    "VRT":  ["hardware", "cooling"],
    
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

# --- 3. TAXONOMÍA HISTÓRICA 2019-2020 ---
# MSTR no era un vehículo de bitcoin (su estrategia de tesorería BTC comenzó a finales del 2020).
# PLTR y COIN no eran empresas públicas cotizadas aún.
THEME_MAP_2020 = {
    # Semis
    "NVDA": ["semis"],
    "AMD":  ["semis"],
    "AMAT": ["semis"],       
    "TSM":  ["semis"],
    "MU":   ["semis"],       
    "STX":  ["semis"],
    "AVGO": ["semis"],
    "ARM":  ["semis"],
    "SMCI": ["hardware"],
    "ON":   ["semis", "auto_semis"],
    "MCHP": ["semis"],
    "MPWR": ["semis", "power"],
    
    # Software & Cloud (SaaS en auge)
    "MSFT": ["cloud", "software"],
    "GOOGL": ["search", "cloud", "software"],
    "META": ["ads", "social", "software"],
    "AMZN": ["cloud", "e-commerce"],
    "SNOW": ["data infrastructure", "software"],
    "DDOG": ["observability", "software"],
    "MDB":  ["database", "software"],
    "CRM":  ["software", "saas"],
    "NOW":  ["software", "saas"],
    "NET":  ["software", "cybersecurity"],    
    "ADSK": ["software", "design"],
    "AXON": ["defense tech"],
    
    # Cybersecurity
    "CRWD": ["cybersecurity", "software"],
    "PANW": ["cybersecurity", "software"],
    "ZS":   ["cybersecurity", "software"],
    "FTNT": ["cybersecurity", "hardware"],
    "OKTA": ["cybersecurity", "identity"],
    
    # Consumer Electronics & EV (TSLA antes del boom masivo S&P)
    "AAPL": ["hardware", "phones", "consumer tech"],
    "TSLA": ["EV", "clean energy"],
    
    # Fintech & Payments (Crypto omitido en MSTR/SQ/etc)
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
    
    # Energy / Solar
    "XOM":  ["energy", "oil"],
    "CVX":  ["energy", "oil"],
    "FSLR": ["solar", "energy"],
    "ENPH": ["solar", "energy tech"],
    "SEDG": ["solar", "energy tech"],
    
    # Builders
    "LEN":  ["builders"],    
    "DHI":  ["builders"],
    "PHM":  ["builders"],
    
    # Crypto (En 2019-2020 MSTR era 100% software empresarial tradicional)
    "MSTR": ["software"],
    "MARA": ["crypto", "mining"],
    "RIOT": ["crypto", "mining"],
    
    # Biotech & Pharma
    "OGN":  ["pharma", "womens health"],
    "VRTX": ["biotech"],
    "LLY":  ["pharma"],
    "NVO":  ["pharma"],
    
    # Healthcare Plans
    "CNC":  ["healthcare", "managed care"],
    "UNH":  ["healthcare", "managed care"],
    
    # Semiconductors & Foundry
    "MXL":  ["semis"],
    "INTC": ["semis", "foundry"],
    "STM":  ["semis"],
    "AXTI": ["semis", "materials"],
    "HIMX": ["semis"],
    "VSH":  ["semis"],
    
    # Communication & Networking
    "AAOI": ["networking", "optics"],
    "NOK":  ["networking", "telecom"],
    "VIAV": ["networking"],
    "EXTR": ["networking"],
    "VSAT": ["networking", "satellite"],
    "ANET": ["networking"],
    
    # Hardware & Storage
    "SNDK": ["hardware", "storage"],
    "WDC":  ["hardware", "storage"],
    "TTMI": ["hardware", "electronics"],
    "DELL": ["hardware"],
    "VRT":  ["hardware", "cooling"],
    
    # Industrials & Energy Equipment
    "BE":   ["energy tech", "fuel cells"],
    "AMSC": ["industrials", "electrical"],
    "LGN":  ["construction", "infrastructure"],
    
    # Travel & Leisure
    "BKNG": ["travel", "booking"],
    "EXPE": ["travel", "booking"],
    "RCL":  ["travel", "cruises"],
    "CCL":  ["travel", "cruises"],
    
    # Consumer & Others
    "RSI":  ["consumer", "gaming"],
    "NAVN": ["software", "application"],
}

# --- 4. EXPOSITOR DE MAPA CANÓNICO Y RESOLUCIÓN DINÁMICA ---

# Mapeo por defecto de compatibilidad
THEME_MAP = THEME_MAP_CURRENT

def get_theme_map_for_date(date_obj) -> dict:
    """
    Retorna el mapa temático correspondiente al año de la fecha dada.
    """
    if date_obj is None:
        return THEME_MAP_CURRENT
        
    try:
        if isinstance(date_obj, (str, bytes)):
            # Convertir a string limpia si es bytes
            d_str = date_obj.decode('utf-8') if isinstance(date_obj, bytes) else date_obj
            year = int(d_str[:4])
        elif hasattr(date_obj, 'year'):
            year = date_obj.year
        else:
            year = int(str(date_obj)[:4])
    except Exception:
        # Fallback si el parsing falla
        return THEME_MAP_CURRENT

    if year <= 2020:
        return THEME_MAP_2020
    elif year <= 2022:
        return THEME_MAP_2022
    else:
        return THEME_MAP_CURRENT

def get_themes(ticker: str, date_obj=None) -> list:
    """
    Obtiene los temas asociados a un ticker en un punto en el tiempo específico.
    Es 100% retrocompatible con llamadas sin fecha.
    """
    theme_map = get_theme_map_for_date(date_obj)
    return theme_map.get(ticker, [])

TAXONOMY_VERSION = "v2.0-PIT-MultiYear"
