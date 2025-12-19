# Stock Quality Filter Configuration

# ═══════════════════════════════════════════════════════════════
# FILTER THRESHOLDS
# ═══════════════════════════════════════════════════════════════

# 1. LIQUIDITY FILTER
# Minimum average daily dollar volume
# Default: $100M (institutional-grade liquidity)
# More conservative: $200M
# More aggressive: $50M
MIN_DOLLAR_VOLUME = 100_000_000  # $100M

# 2. VOLATILITY FILTER  
# Minimum ADR (Average Daily Range) percentage
# Default: 2.5% (balanced - allows most momentum stocks)
# More conservative: 4.0% (only high-volatility movers)
# More aggressive: 1.5% (includes less volatile stocks)
MIN_ADR_PCT = 2.5  # 2.5%

# Note: Original recommendation was 4%, but that's too restrictive
# Most quality stocks (AAPL, MSFT, etc) have ADR 1.5-3%
# Only highly volatile stocks (TSLA, COIN, etc) exceed 4%

# 3. TREND FILTER
# Require Price > SMA50 > SMA200 alignment
# True: Only trade stocks in confirmed uptrends
# False: Allow all trend conditions (not recommended)
REQUIRE_TREND_ALIGNMENT = True

# ═══════════════════════════════════════════════════════════════
# PRESETS
# ═══════════════════════════════════════════════════════════════

PRESET_CONSERVATIVE = {
    'min_dollar_volume': 200_000_000,  # $200M
    'min_adr_pct': 3.5,                # 3.5%
    'require_trend_alignment': True
}

PRESET_BALANCED = {
    'min_dollar_volume': 100_000_000,  # $100M (default)
    'min_adr_pct': 2.5,                # 2.5% (default)
    'require_trend_alignment': True
}

PRESET_AGGRESSIVE = {
    'min_dollar_volume': 50_000_000,   # $50M
    'min_adr_pct': 1.5,                # 1.5%
    'require_trend_alignment': True
}

PRESET_ORIGINAL_SPEC = {
    'min_dollar_volume': 100_000_000,  # $100M
    'min_adr_pct': 4.0,                # 4% (very restrictive!)
    'require_trend_alignment': True
}

# Current preset to use
CURRENT_PRESET = 'BALANCED'  # 'CONSERVATIVE', 'BALANCED', 'AGGRESSIVE', 'ORIGINAL_SPEC'
