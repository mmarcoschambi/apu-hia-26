"""
Universe Presets
High-quality, liquid ticker lists for automated watchlist population.
Excluded: Penny stocks, low volume, OTC.
Focus: Institutional Mid-Caps (approx $2B - $20B) and high momentum names.
"""

LIQUID_MID_CAPS = [
    # Tech / Growth
    "APP", "DUOL", "PATH", "IOT", "GTLB", "HCP", "ESTC", "DT", "BILL", "MDB", "CFLT", "PCOR",
    "AFRM", "UPST", "OPEN", "RIVN", "LCID", "DKNG", "HOOD", "PLTR", "SOFI", "TOST", "COIN",
    "NET", "OKTA", "TWLO", "DOCU", "ZS", "CRWD", "DDOG", "TEAM", "WDAY", "SPLK", "ANET",
    # Semi / Hardware
    "ALAB", "COHR", "LSCC", "WOLF", "POWI", "DIOD", "SLAB", "RMBS", "ACLS", "MKSI", "AEIS",
    # Biotech / Health (Liquid)
    "VRTX", "ALNY", "BGNE", "ARGX", "TECH", "DNA", "NTRA", "EXAS", "TXG", "RGEN",
    # Consumer / Retail
    "ONON", "CROX", "DECK", "SKX", "ELF", "ULTA", "FIVE", "BOOT", "WING", "SHAK", "CAVA",
    "CELH", "MNST", "BJ", "COST",
    # Industrial / Energy
    "ETHE", "GEV", "CEG", "VST", "NRG", "PWR", "FIX", "EMR", "PH", "ETN", "CAT",
    # Crypto / Blockchain
    "MSTR", "MARA", "RIOT", "CLSK", "HUT", "BITF",
    # High Momentum 2024
    "RDDT", "ALM", "CART", "ARM", "SMCI", "NVDA", "VRT", "ANF", "GPS"
]

# Ensure uniqueness and upper case
LIQUID_MID_CAPS = sorted(list(set([x.upper() for x in LIQUID_MID_CAPS])))
