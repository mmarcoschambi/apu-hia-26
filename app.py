import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
import subprocess
import time
import sys
from pathlib import Path
import calendar
import plotly.figure_factory as ff
import random
import pickle

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.dashboard import InteractiveDashboard
from src.backtest.visualizer import BacktestVisualizer
from src.data.openbb_data import OpenBBData
from src.data.ticker_cache import TickerCache
from config.universe_presets import LIQUID_MID_CAPS

# Initialize TickerCache
ticker_cache = TickerCache()

# Función para cargar/guardar watchlist
WATCHLIST_FILE = 'config/watchlist.json'

def load_watchlist_json():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_watchlist_json(data):
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_cache_date_range():
    """
    Obtiene el rango de fechas real disponible en el cache (tanto .pkl como SQLite)
    Returns: (min_date, max_date) as datetime objects
    """
    min_date = None
    max_date = None
    
    # 1. Check SQLite Cache
    try:
        cursor = ticker_cache.conn.execute("SELECT MIN(date), MAX(date) FROM ohlcv_cache")
        sqlite_min, sqlite_max = cursor.fetchone()
        if sqlite_min and sqlite_max:
            min_date = datetime.strptime(sqlite_min, '%Y-%m-%d')
            max_date = datetime.strptime(sqlite_max, '%Y-%m-%d')
    except Exception as e:
        pass

    # 2. Check Legacy .pkl Cache
    cache_dir = 'data/cache'
    if os.path.exists(cache_dir):
        try:
            for file in os.listdir(cache_dir):
                # Only process daily data files
                if file.endswith('_daily.pkl'):
                    try:
                        with open(os.path.join(cache_dir, file), 'rb') as f:
                            data = pickle.load(f)
                            if not data.empty:
                                file_min = data.index.min()
                                file_max = data.index.max()
                                
                                if hasattr(file_min, 'to_pydatetime'):
                                    file_min = file_min.to_pydatetime()
                                if hasattr(file_max, 'to_pydatetime'):
                                    file_max = file_max.to_pydatetime()

                                if min_date is None or file_min < min_date:
                                    min_date = file_min
                                if max_date is None or file_max > max_date:
                                    max_date = file_max
                    except:
                        continue
        except:
            pass
    
    # Default fallback if nothing found
    if min_date is None or max_date is None:
        return datetime(2020, 1, 1), datetime.now()
    
    # Cap max_date to today (no future dates)
    today = datetime.now()
    if max_date > today:
        max_date = today
    
    return min_date, max_date

# Función para ejecutar el backtest con UI de progreso y parámetros de riesgo
def run_backtest_with_progress(start_date, end_date, stop_loss_pct=None, 
                               equity=100000, risk_pct=0.5, max_exp_pct=25,
                               min_mcap_b=2.0, max_mcap_b=20.0, 
                               min_vol_k=300, min_adr=1.5, min_price=5.0, min_dollar_m=15,
                               min_rvol=1.5, watchlist_path='config/watchlist.json', skip_filters=False,
                               source='file', sector=None, offline=False, max_symbols=None, sort_by='liquidity'):
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_area = st.empty()
    logs = []

    cmd = [
        "python3", "daily_backtest_runner.py",
        "--start", str(start_date),
        "--end", str(end_date),
        "--watchlist", watchlist_path,
        "--equity", str(equity),
        "--risk", str(risk_pct / 100.0),
        "--max_exp", str(max_exp_pct / 100.0),
        "--min_mcap", str(min_mcap_b * 1e9),
        "--max_mcap", str(max_mcap_b * 1e9),
        "--min_volume", str(int(min_vol_k * 1000)),
        "--min_adr", str(min_adr),
        "--min_price", str(min_price),
        "--min_dollar_vol", str(int(min_dollar_m * 1e6)),
        "--min_rvol", str(min_rvol),
        "--source", str(source)
    ]
    
    if sector:
        cmd.extend(["--sector", str(sector)])
    
    if offline:
        cmd.append("--offline")
    
    if skip_filters:
        cmd.append("--skip_filters")
    
    if stop_loss_pct is not None and stop_loss_pct > 0:
        cmd.extend(["--stop_loss", str(stop_loss_pct)])
    
    if max_symbols:
        cmd.extend(["--max_symbols", str(max_symbols)])
    
    if sort_by:
        cmd.extend(["--sort_by", str(sort_by)])
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                line = line.strip()
                if "__PROGRESS__" in line:
                    parts = line.split("__")
                    if len(parts) >= 3:
                        progress_info = parts[2].split("/") # "1/10"
                        symbol_name = parts[3] if len(parts) > 3 else ""
                        if len(progress_info) == 2:
                            current = int(progress_info[0])
                            total = int(progress_info[1])
                            progress = float(current) / float(total)
                            progress_bar.progress(progress)
                            status_text.write(f"⏳ Procesando **{symbol_name}** ({current}/{total})...")
                else:
                    logs.append(line)
                    log_text = "\n".join(logs[-10:])
                    log_area.code(log_text)
        
        if process.returncode == 0:
            progress_bar.progress(1.0)
            status_text.success("✅ Backtest completado!")
            time.sleep(1)
            st.cache_data.clear()
            return True
        else:
            status_text.error("❌ Error en la ejecución.")
            return False

    except Exception as e:
        status_text.error(f"Error inesperado: {e}")
        return False

# Configuración de la página
st.set_page_config(
    page_title="Momentum V2 - Institutional Risk Dashboard",
    page_icon="📈",
    layout="wide"
)

# Título y Descripción
st.title("📈 Momentum V2 - Institutional Risk Dashboard")

# --- Barra Lateral: Configuración y Ejecución ---
st.sidebar.header("⚙️ Configuración del Sistema")

with st.sidebar.expander("📅 Fechas y Filtros Universo", expanded=True):
    # Get actual date range from cache
    cache_min_date, cache_max_date = get_cache_date_range()
    
    # Initialize session state for dates if not exists
    if 'start_date' not in st.session_state:
        # Default to last year if available
        default_start = max(cache_min_date, cache_max_date - timedelta(days=365))
        st.session_state.start_date = default_start
    if 'end_date' not in st.session_state:
        st.session_state.end_date = cache_max_date
    
    # Show cache info
    st.info(f"📦 Datos disponibles: {cache_min_date.strftime('%Y-%m-%d')} a {cache_max_date.strftime('%Y-%m-%d')}")

    # Random Date Button
    if st.button("🎲 Rango Aleatorio (Backtest)", use_container_width=True):
        # Random start within available cache range
        days_available = (cache_max_date - cache_min_date).days
        if days_available > 365:
            # Random start between cache_min and 6 months before cache_max
            start_offset = random.randint(0, max(0, days_available - 180))
            random_start = cache_min_date + timedelta(days=start_offset)
            
            # Duration: 3 to 8 months
            duration_days = random.randint(90, 240)
            random_end = min(random_start + timedelta(days=duration_days), cache_max_date)
            
            st.session_state.start_date = random_start
            st.session_state.end_date = random_end
            st.rerun()

    run_start_date = st.date_input(
        "Fecha Inicio", 
        value=st.session_state.start_date,
        min_value=cache_min_date.date(),
        max_value=cache_max_date.date()
    )
    run_end_date = st.date_input(
        "Fecha Fin", 
        value=st.session_state.end_date,
        min_value=cache_min_date.date(),
        max_value=cache_max_date.date()
    )
    
    # Sync session state
    st.session_state.start_date = run_start_date
    st.session_state.end_date = run_end_date
    
    # Show warning if dates are outside cache range
    if run_start_date < cache_min_date.date() or run_end_date > cache_max_date.date():
        st.warning("⚠️ Fechas seleccionadas fuera del rango del cache. Se descargarán datos adicionales.")
    
    # Show days selected
    days_selected = (run_end_date - run_start_date).days
    st.caption(f"📊 Rango: {days_selected} días ({days_selected/365:.1f} años)")
    
    st.markdown("---")
    # Checkbox para forzar calidad institucional
    use_inst_quality = st.checkbox("🛡️ Modo Calidad Institucional", value=True, 
                                   help="Fuerza filtros mínimos: Mcap > $2B (sin límite superior), Precio > $5, Volumen > 300k, $Vol > $15M")
    
    # Logic to set defaults based on checkbox
    def_mcap = 2.0 if use_inst_quality else 0.5
    def_price = 5.0 if use_inst_quality else 1.0
    def_vol = 300 if use_inst_quality else 50
    def_dvol = 15 if use_inst_quality else 1
    
    st.markdown("**Filtros de Calidad**")
    c1, c2 = st.columns(2)
    in_min_mcap = c1.number_input("Min Mcap ($B)", value=def_mcap, step=0.5, disabled=use_inst_quality)
    in_max_mcap = c2.number_input("Max Mcap ($B)", value=5000.0, step=100.0, help="Default: $5T (permite mega-caps)")
    in_min_price = st.number_input("Precio Mínimo ($)", value=def_price, step=1.0, disabled=use_inst_quality)
    
    st.markdown("**Filtros de Liquidez y Volatilidad**")
    in_min_vol = st.number_input("Min Volumen Diario (k)", value=def_vol, step=50, disabled=use_inst_quality)
    in_min_dollar_m = st.number_input("Min Dollar Volume ($M)", value=def_dvol, step=5, disabled=use_inst_quality)
    in_min_adr = st.number_input("Min ADR 20 (%)", value=1.5, step=0.1, format="%.1f")
    in_min_rvol = st.number_input("Min RVOL (x)", value=1.5, step=0.1, format="%.1f", help="Relative Volume: Volumen actual vs promedio 20 días")
    
    # Stop Loss Config
    use_custom_stop = st.checkbox("Forzar Stop Loss Fijo (%)")
    stop_loss_input = 2.0
    if use_custom_stop:
        stop_loss_input = st.number_input("Stop Loss %", value=3.0, step=0.5)

    st.markdown("---")
    st.markdown("**Mantenimiento del Universo**")
    if st.button("🔄 Actualizar Universo (SQLite)", help="Descarga lista fresca de tickers (S&P500, Nasdaq, Dow)"):
        with st.spinner("Actualizando universo..."):
            ticker_cache.update_universe(force=True)
            st.success("¡Universo actualizado!")
            st.rerun()

with st.sidebar.expander("🛡️ Institutional Risk Manager", expanded=True):
    in_equity = st.number_input("Equity ($)", value=100000.0, step=10000.0)
    in_risk = st.number_input("Risk per Trade (%)", value=0.5, step=0.1, format="%.2f")
    in_max_exp = st.number_input("Max Exposure (%)", value=25.0, step=5.0)

# --- Nueva Entrada Directa de Símbolos ---
st.sidebar.markdown("---")
st.sidebar.header("🚀 Ejecución Rápida")

# Scan Mode Selection
scan_mode = st.sidebar.radio(
    "Fuente del Universo",
    ["📝 Lista Manual", "🌎 Todo el Mercado (SQLite)", "🏗️ Por Sector"],
    help="Elige qué tickers escanear"
)

selected_sector = None
if scan_mode == "🏗️ Por Sector":
    # Get available sectors from DB
    try:
        cursor = ticker_cache.conn.execute("SELECT DISTINCT sector FROM universe WHERE sector != '' ORDER BY sector")
        sectors = [row[0] for row in cursor.fetchall()]
        selected_sector = st.sidebar.selectbox("Selecciona Sector", sectors)
    except:
        st.sidebar.warning("No se pudieron cargar sectores")

direct_symbols = st.sidebar.text_area("Tu Lista (Referencia o Escaneo)", value="APP, PLTR", help="Si eliges 'Todo el Mercado', esta lista se usará para resaltar oportunidades que NO tenías en el radar.")

# Cache Check Button (Only relevant for manual list)
if scan_mode == "📝 Lista Manual" and st.sidebar.button("🔍 Verificar Cache de Símbolos", use_container_width=True):
    if direct_symbols:
        symbols_list = [s.strip().upper() for s in direct_symbols.split(',') if s.strip()]
        
        with st.sidebar:
            st.markdown("### 📦 Estado del Cache")
            
            for symbol in symbols_list:
                # Check SQLite first
                cursor = ticker_cache.conn.execute(
                    "SELECT MIN(date), MAX(date) FROM ohlcv_cache WHERE ticker = ?", (symbol,)
                )
                sqlite_res = cursor.fetchone()
                
                # Check .pkl legacy
                cache_file = f"data/cache/{symbol}_daily.pkl"
                cache_file_alt = f"data/cache/{symbol}.pkl"
                
                found = False
                if sqlite_res and sqlite_res[0]:
                    st.write(f"✅ **{symbol}**: SQLite Cache ({sqlite_res[0]} a {sqlite_res[1]})")
                    found = True
                
                if not found:
                    file_to_check = None
                    if os.path.exists(cache_file):
                        file_to_check = cache_file
                    elif os.path.exists(cache_file_alt):
                        file_to_check = cache_file_alt
                    
                    if file_to_check:
                        try:
                            with open(file_to_check, 'rb') as f:
                                data = pickle.load(f)
                                if not data.empty:
                                    min_d = data.index.min()
                                    max_d = data.index.max()
                                    st.write(f"✅ **{symbol}**: Pickle Cache ({min_d.strftime('%Y-%m-%d')} a {max_d.strftime('%Y-%m-%d')})")
                                    found = True
                        except:
                            pass
                
                if not found:
                    st.write(f"❌ **{symbol}**: Sin datos en cache")
    else:
        st.sidebar.warning("Ingresa símbolos primero")

# Offline Mode Checkbox
offline_mode = st.sidebar.checkbox("💾 Modo Offline (Solo Cache)", value=False, help="No descargar datos nuevos, usar solo lo disponible localmente.")

# Universe Size Limiter (for SQLite mode)
max_symbols_limit = None
selection_strategy = 'liquidity'  # Default

if scan_mode == "🌎 Todo el Mercado (SQLite)":
    st.sidebar.warning("⚠️ Universo completo = 5600+ tickers. Puede tardar mucho.")
    limit_universe = st.sidebar.checkbox("🎯 Limitar Universo", value=True, help="Recomendado para pruebas rápidas")
    if limit_universe:
        max_symbols_limit = st.sidebar.number_input("Máximo de Símbolos", value=500, min_value=50, max_value=5000, step=50)
        
        # Selection strategy
        st.sidebar.markdown("**Estrategia de Selección**")
        selection_strategy = st.sidebar.radio(
            "Cómo elegir símbolos:",
            ['liquidity', 'random', 'alphabetical'],
            format_func=lambda x: {
                'liquidity': '💎 Por Liquidez (recomendado)',
                'random': '🎲 Aleatorio',
                'alphabetical': '🔤 Alfabético (A-Z)'
            }[x],
            help="Liquidez = tickers con mayor volumen en dólares"
        )

if st.sidebar.button("🚀 EJECUTAR BACKTEST", use_container_width=True):
    # Validate dates
    if run_end_date > cache_max_date.date():
        st.sidebar.error(f"❌ Fecha Fin no puede ser mayor que {cache_max_date.date().strftime('%Y-%m-%d')}")
        st.stop()
    
    if run_start_date > run_end_date:
        st.sidebar.error("❌ Fecha Inicio debe ser anterior a Fecha Fin")
        st.stop()
    
    sl_val = stop_loss_input if use_custom_stop else None
    
    # Logic for source
    source_arg = "file"
    sector_arg = None
    temp_watchlist_path = 'temp_backtest_list.json'
    
    # Save manual list anyway for highlighting or usage
    manual_list = []
    if direct_symbols:
        manual_list = [s.strip().upper() for s in direct_symbols.split(',') if s.strip()]
        
        # Guardar en base de datos si son nuevos
        if len(manual_list) > 0:
            added_count = ticker_cache.add_tickers(manual_list)
            if added_count > 0:
                st.toast(f"✅ Se agregaron {added_count} nuevos tickers a la base de datos.", icon="💾")
        
        with open(temp_watchlist_path, 'w') as f:
            json.dump({"DIRECT_INPUT": manual_list}, f)
    
    if scan_mode == "🌎 Todo el Mercado (SQLite)":
        source_arg = "sqlite"
        st.sidebar.info("Escaneando todo el mercado... esto puede tardar.")
    elif scan_mode == "🏗️ Por Sector":
        source_arg = "sqlite_sector"
        sector_arg = selected_sector
        st.sidebar.info(f"Escaneando sector: {selected_sector}")
    
    # Run
    # Skip filters when using Manual List (allow any ticker regardless of mcap/volume)
    skip_fundamental_filters = (scan_mode == "📝 Lista Manual")
    
    if run_backtest_with_progress(run_start_date, run_end_date, sl_val, in_equity, in_risk, in_max_exp, 
                                  in_min_mcap, in_max_mcap, in_min_vol, in_min_adr, in_min_price, in_min_dollar_m,
                                  in_min_rvol, watchlist_path=temp_watchlist_path, skip_filters=skip_fundamental_filters, 
                                  source=source_arg, sector=sector_arg, offline=offline_mode, 
                                  max_symbols=max_symbols_limit, sort_by=selection_strategy):
        st.rerun()

st.sidebar.markdown("---")

# --- Carga de datos ---
@st.cache_data
def load_data():
    try:
        main_df = pd.DataFrame()
        partial_df = pd.DataFrame()
        
        if os.path.exists('backtest_results.csv'):
            main_df = pd.read_csv('backtest_results.csv')
            main_df['entry_date'] = pd.to_datetime(main_df['entry_date'])
            main_df['exit_date'] = pd.to_datetime(main_df['exit_date'])
            main_df['trade_type'] = 'FULL_EXIT'  # Marcar como cierre completo
        
        # Cargar salidas parciales si existen
        if os.path.exists('partial_exits.csv'):
            partial_df = pd.read_csv('partial_exits.csv')
            partial_df['entry_date'] = pd.to_datetime(partial_df['entry_date'])
            partial_df['exit_date'] = pd.to_datetime(partial_df['exit_date'])
            partial_df['trade_type'] = partial_df['phase']  # FASE_1 o FASE_2
            
            # Renombrar columnas para compatibilidad con main_df
            partial_df = partial_df.rename(columns={
                'shares_sold': 'shares',
                'pct_sold': 'exit_pct'
            })
        
        return main_df, partial_df
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df_raw, df_partial_raw = load_data()

# --- Highlight New Opportunities ---
if not df_raw.empty and os.path.exists('temp_backtest_list.json'):
    try:
        with open('temp_backtest_list.json', 'r') as f:
            data = json.load(f)
            if "DIRECT_INPUT" in data:
                manual_set = set(data["DIRECT_INPUT"])
                # Add 'source' column
                df_raw['source'] = df_raw['symbol'].apply(lambda x: '📝 Manual' if x in manual_set else '💡 Discovery')
                
                # If we have discovery items, show a notification
                discovery_count = len(df_raw[df_raw['source'] == '💡 Discovery'])
                if discovery_count > 0:
                    st.success(f"✨ ¡Se encontraron {discovery_count} oportunidades fuera de tu lista manual!")
            else:
                df_raw['source'] = 'N/A'
    except:
        pass

# --- Formulario de Filtros (Solo visualización) ---
with st.sidebar.form("filtros_form"):
    st.header("🔍 Filtros de Visualización")
    if not df_raw.empty:
        syms = ['Todos'] + sorted(df_raw['symbol'].unique().tolist())
        sig_types = ['Todos'] + sorted(df_raw['signal_type'].unique().tolist())
    else:
        syms, sig_types = ['Todos'], ['Todos']

    f_symbol = st.selectbox("Símbolo", syms)
    f_signal = st.selectbox("Señal", sig_types)
    submitted = st.form_submit_button("Actualizar Vista")

# --- MARKET HEALTH CHECK (Only show if no backtest results or user wants it) ---
# For backtesting, this shows TODAY's market conditions which is irrelevant for historical analysis
# Only useful for live trading or when no backtest results exist

show_market_health = df_raw.empty  # Only show if no backtest results

if show_market_health:
    st.header("🛡️ Market Health Check")
    st.caption("📅 Condiciones actuales del mercado (útil para trading en vivo)")
    
    try:
        from src.data.market_data import MarketDataProvider
        from src.core.market_context import MarketContext
        
        with st.spinner("Analizando condiciones del mercado..."):
            provider = MarketDataProvider()
            mc = MarketContext(provider)
            context = mc.analyze_indices()
        
        # Extract metrics
        spy_price = context.get('spy_price', 0)
        spy_ema20 = context.get('spy_ema20', 0)
        spy_above_ema20 = context.get('spy_above_ema20', False)
        breadth_improving = context.get('breadth_improving', False)
        positive_gex = context.get('positive_gex', False)
        vix_favorable = context.get('vix_favorable', True)
        sector_leaders = context.get('sector_leaders', {})
        market_favorable = context.get('market_favorable_for_longs', False)
        
        # Calculate health score
        health_score = 0
        if spy_above_ema20:
            health_score += 2
        if breadth_improving:
            health_score += 2
        if positive_gex:
            health_score += 1
        if vix_favorable:
            health_score += 1
        if sector_leaders:
            health_score += 1
        
        # Display in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "SPY Trend",
                f"${spy_price:.2f}",
                f"{((spy_price - spy_ema20) / spy_ema20 * 100):+.2f}%" if spy_ema20 else "N/A",
                delta_color="normal"
            )
            if spy_above_ema20:
                st.success("✅ Above EMA20")
            else:
                st.error("❌ Below EMA20")
        
        with col2:
            st.metric("Breadth", "Improving" if breadth_improving else "Declining")
            if breadth_improving:
                st.success("✅ Strong")
            else:
                st.warning("⚠️ Weak")
        
        with col3:
            st.metric("Volatility", "Favorable" if vix_favorable else "Elevated")
            if vix_favorable:
                st.success("✅ VIX < 20")
            else:
                st.error("⚠️ VIX High")
        
        with col4:
            st.metric("GEX", "Positive" if positive_gex else "Neutral")
            if positive_gex:
                st.success("✅ Low Vol Grind")
            else:
                st.info("⚪ Normal")
        
        # Health Score and Verdict
        st.markdown("---")
        col_score, col_verdict = st.columns([1, 2])
        
        with col_score:
            st.metric("Health Score", f"{health_score}/7", f"{(health_score/7*100):.0f}%")
            # Progress bar
            st.progress(health_score / 7)
        
        with col_verdict:
            if not market_favorable:
                st.error("❌ **NO TRADE MODE** - Market not favorable for longs")
                st.caption("Go to cash or paper trade only")
            elif health_score >= 6:
                st.success("🚀 **AGGRESSIVE MODE** - Excellent conditions")
                st.caption("Full size (2% risk), all 3 Caminos, focus on leading sectors")
            elif health_score >= 4:
                st.success("💪 **STANDARD MODE** - Good conditions")
                st.caption("Standard size (1.5-2% risk), prefer Camino 1 in leading sectors")
            else:
                st.warning("⚠️ **DEFENSIVE MODE** - Be selective")
                st.caption("Half size (0.5-1% risk), only perfect Blue Sky in top sectors")
        
        # Sector Leaders
        if sector_leaders:
            st.markdown("---")
            st.subheader("🎯 Top Sectors Today")
            top_3 = list(sector_leaders.items())[:3]
            
            col_s1, col_s2, col_s3 = st.columns(3)
            for idx, (sector, data) in enumerate(top_3):
                with [col_s1, col_s2, col_s3][idx]:
                    pct = data['change_pct']
                    st.metric(
                        f"#{idx+1} {sector}",
                        f"{data['symbol']}",
                        f"{pct:+.2f}%",
                        delta_color="normal"
                    )

    except Exception as e:
        st.error(f"Error loading market health: {e}")
        st.caption("Backtest data will still be available below")

st.markdown("---")

# Lógica Principal
if not df_raw.empty:
    # --- TABS PRINCIPALES ---
    tab_dashboard, tab_calendar, tab_live_scanner = st.tabs([
        "📊 Dashboard Backtest", 
        "📅 PnL Calendar",
        "📡 Live Market Scanner"
    ])

    # ==========================================
    # TAB 1: DASHBOARD GENERAL (Original)
    # ==========================================
    with tab_dashboard:
        df_filtered = df_raw.copy()
        if f_symbol != 'Todos': df_filtered = df_filtered[df_filtered['symbol'] == f_symbol]
        if f_signal != 'Todos': df_filtered = df_filtered[df_filtered['signal_type'] == f_signal]

        df_filtered = df_filtered.sort_values('exit_date')
        
        # Usar PnL total (incluye salidas parciales) si existe, sino calcularlo
        if 'pnl' in df_filtered.columns:
            df_filtered['Result'] = df_filtered['pnl']
        elif 'shares' in df_filtered.columns:
            df_filtered['Result'] = (df_filtered['exit_price'] - df_filtered['entry_price']) * df_filtered['shares']
        else:
            df_filtered['Result'] = 0.0
        
        # Calcular R-multiple
        if 'monetary_risk' in df_filtered.columns:
            df_filtered['r_multiple'] = df_filtered['Result'] / df_filtered['monetary_risk']
        else:
            df_filtered['r_multiple'] = 0.0

        df_filtered['Running_Capital'] = in_equity + df_filtered['Result'].cumsum()

        # --- CUSTOM METRICS SECTION ---
        st.markdown("### 📊 Performance Overview")
        
        # Calculate advanced metrics
        total_trades = len(df_filtered)
        winners = df_filtered[df_filtered['Result'] > 0]
        losers = df_filtered[df_filtered['Result'] <= 0]
        
        closed_pnl = df_filtered['Result'].sum()
        win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0.0
        
        # R-Multiples
        if 'r_multiple' in df_filtered.columns:
            total_r = df_filtered['r_multiple'].sum()
            avg_r = df_filtered['r_multiple'].mean() if total_trades > 0 else 0
        else:
            total_r = 0.0
            avg_r = 0.0
            
        # Profit Factor
        gross_win = winners['Result'].sum()
        gross_loss = abs(losers['Result'].sum())
        profit_factor = (gross_win / gross_loss) if gross_loss > 0 else 0.0
        
        # Avg Risk/Reward
        avg_win_amt = winners['Result'].mean() if not winners.empty else 0
        avg_loss_amt = abs(losers['Result'].mean()) if not losers.empty else 0
        rr_ratio = (avg_win_amt / avg_loss_amt) if avg_loss_amt > 0 else 0.0
        
        general_perf_pct = (closed_pnl / in_equity) * 100

        # Row 1
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("General Performance (%)", f"{general_perf_pct:+.2f}%")
            st.metric("Available Capital", f"${(in_equity + closed_pnl):,.2f}")
        with c2:
            st.metric("Cash - Invested Capital", f"${(in_equity + closed_pnl):,.2f}") 
            st.metric("Open Trades PnL", "$0.00") 
        with c3:
            st.metric("Closed Trades PnL", f"${closed_pnl:,.2f}", delta=f"{general_perf_pct:.1f}%")
            st.metric("Win Rate (%)", f"{win_rate:.1f}%")
        with c4:
            st.metric("Total Trades", total_trades)
            st.metric("Winners / Losers", f"{len(winners)} / {len(losers)}")

        st.markdown("---")
        
        # Row 2 (Risk Metrics)
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Risk/Reward Ratio", f"{rr_ratio:.2f}")
        d2.metric("Total R", f"{total_r:.2f}R")
        d3.metric("Profit Factor", f"{profit_factor:.2f}")
        d4.metric("Expectancy (R)", f"{avg_r:.2f}R")

        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        with col1:
            fig = px.line(df_filtered, x='exit_date', y='Running_Capital', title='Equity Curve (Real Risk Adjusted)')
            st.plotly_chart(fig, use_container_width=True, key="equity_curve_chart")
        with col2:
            if 'shares' in df_filtered.columns:
                fig = px.scatter(df_filtered, x='entry_date', y='position_value', 
                                 color='is_profitable', size='shares',
                                 title='Position Sizing Impact (Size = Shares, Y = Capital Alloc)')
                st.plotly_chart(fig, use_container_width=True, key="position_sizing_chart")

        #Tabla
        st.markdown("### 📋 Trade Log (Institutional)")
        df_disp = df_filtered.copy()
        if 'shares' in df_disp.columns:
            df_disp['days_held'] = (df_filtered['exit_date'] - df_filtered['entry_date']).dt.days
            
            cols = ['symbol', 'entry_date', 'days_held', 'signal_type', 'shares', 'position_value', 'monetary_risk', 'returns_pct', 'r_multiple', 'Result']
            
            # Add context columns if available
            if 'context_rvol' in df_disp.columns:
                cols.insert(4, 'context_rvol')  # Add after signal_type
            if 'context_trend' in df_disp.columns:
                cols.insert(5, 'context_trend')  # Add after rvol
            
            column_config = {
                "symbol": st.column_config.TextColumn("Symbol", width="small"),
                "entry_date": st.column_config.DateColumn("Entry Date", format="YYYY-MM-DD"),
                "days_held": st.column_config.NumberColumn("Days", format="%d"),
                "signal_type": st.column_config.TextColumn("Signal"),
                "context_rvol": st.column_config.NumberColumn("RVOL", format="%.2fx"),
                "context_trend": st.column_config.TextColumn("Trend", width="small"),
                "shares": st.column_config.NumberColumn("Shares", format="%.2f"),
                "position_value": st.column_config.NumberColumn("Position", format="$%.0f"),
                "monetary_risk": st.column_config.NumberColumn("Risk", format="$%.0f"),
                "returns_pct": st.column_config.NumberColumn("Return %", format="%+.2f%%",), 
                "r_multiple": st.column_config.NumberColumn("R Multiple", format="%+.2f R"),
                "Result": st.column_config.NumberColumn("P/L", format="$%.2f")
            }
            
            st.dataframe(
                df_disp[cols].sort_values('entry_date', ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
        else:
            st.dataframe(df_filtered)
        
        # --- 📊 ALL EXITS TABLE (Incluye Fase 1, 2 y 3) ---
        if not df_partial_raw.empty:
            st.markdown("---")
            st.markdown("### 📤 Detalle de Salidas Escalonadas (Todas las Fases)")
            st.caption("📊 Registro completo de cada salida: Fase 1 (Risk-Free), Fase 2 (Resistance), Fase 3 (Runner)")
            
            # Filtrar partial exits según los filtros aplicados
            df_partial_filtered = df_partial_raw.copy()
            if f_symbol != 'Todos':
                df_partial_filtered = df_partial_filtered[df_partial_filtered['symbol'] == f_symbol]
            if f_signal != 'Todos':
                df_partial_filtered = df_partial_filtered[df_partial_filtered['signal_type'] == f_signal]
            
            if not df_partial_filtered.empty:
                df_partial_disp = df_partial_filtered.copy()
                df_partial_disp['days_to_exit'] = (df_partial_disp['exit_date'] - df_partial_disp['entry_date']).dt.days
                
                partial_cols = ['symbol', 'phase', 'exit_date', 'days_to_exit', 'exit_price', 
                               'shares', 'exit_pct', 'pnl', 'return_pct', 'reason']
                
                partial_config = {
                    "symbol": st.column_config.TextColumn("Symbol", width="small"),
                    "phase": st.column_config.TextColumn("Fase", width="small"),
                    "exit_date": st.column_config.DateColumn("Exit Date", format="YYYY-MM-DD"),
                    "days_to_exit": st.column_config.NumberColumn("Days", format="%d"),
                    "exit_price": st.column_config.NumberColumn("Exit Price", format="$%.2f"),
                    "shares": st.column_config.NumberColumn("Shares Sold", format="%d"),
                    "exit_pct": st.column_config.NumberColumn("% Sold", format="%.0f%%"),
                    "pnl": st.column_config.NumberColumn("P&L", format="$%.2f"),
                    "return_pct": st.column_config.NumberColumn("Return %", format="%+.2f%%"),
                    "reason": st.column_config.TextColumn("Reason"),
                }
                
                st.dataframe(
                    df_partial_disp[partial_cols].sort_values('exit_date', ascending=False),
                    use_container_width=True,
                    hide_index=True,
                    column_config=partial_config
                )
                
                # Estadísticas rápidas de partial exits
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    total_partial_pnl = df_partial_disp['pnl'].sum()
                    st.metric("Total P&L Parciales", f"${total_partial_pnl:,.2f}")
                with col2:
                    fase1_count = len(df_partial_disp[df_partial_disp['phase'] == 'FASE_1'])
                    st.metric("Fase 1 Ejecutadas", fase1_count)
                with col3:
                    fase2_count = len(df_partial_disp[df_partial_disp['phase'] == 'FASE_2'])
                    st.metric("Fase 2 Ejecutadas", fase2_count)
                with col4:
                    avg_days = df_partial_disp['days_to_exit'].mean()
                    st.metric("Días Promedio", f"{avg_days:.1f}")
            else:
                st.info("No hay salidas parciales que coincidan con los filtros aplicados.")

        # --- 🔬 TRADE ANALYSIS SECTION ---
        st.markdown("---")
        st.header("🔬 Análisis Detallado de Operaciones")
        
        if not df_filtered.empty:
            df_analysis = df_filtered.sort_values('entry_date', ascending=False)
            trade_options = []
            trade_map = {}
            
            for idx, row in df_analysis.iterrows():
                sym = row['symbol']
                date = row['entry_date'].strftime('%Y-%m-%d')
                pnl = row['Result'] if 'Result' in row else 0
                sig_type = row.get('signal_type', 'N/A').replace('Camino.', '')
                label = f"{date} | {sym} | {sig_type} | PnL: ${pnl:,.2f}"
                trade_options.append(label)
                trade_map[label] = row
                
            selected_trade_label = st.selectbox("Selecciona una operación para analizar:", trade_options)
            
            if selected_trade_label:
                trade_data = trade_map[selected_trade_label]
                
                # --- VISUALIZATION TABS ---
                tab_static, tab_interactive = st.tabs(["📸 Gráfico Detallado (Masterclass)", "🖱️ Gráfico Interactivo"])
                
                signal_data = {
                    'camino': trade_data.get('signal_type', 'N/A'),
                    'entry_price': trade_data['entry_price'],
                    'stop_loss': trade_data.get('entry_price', 0) * 0.95,
                    'exit_price': trade_data['exit_price'],
                    'outcome': 'WIN' if trade_data.get('is_profitable') else 'LOSS',
                    'return_pct': trade_data['returns_pct'],
                    'hold_days': (trade_data['exit_date'] - trade_data['entry_date']).days,
                    'monetary_risk': trade_data.get('monetary_risk', 0)
                }

                with tab_static:
                    st.info("💡 Este gráfico muestra el ciclo de vida del trade con temporalidad ajustable.")
                    
                    # Timeframe selector
                    col_tf1, col_tf2 = st.columns([1, 3])
                    with col_tf1:
                        timeframe = st.selectbox(
                            "⏱️ Temporalidad",
                            options=["5m", "15m", "30m", "1h", "1d"],
                            index=0,  # Default to 5m
                            key=f"tf_{trade_data['symbol']}_{trade_data['entry_date'].strftime('%Y%m%d')}"
                        )
                    
                    with col_tf2:
                        entry_date_pd = pd.to_datetime(trade_data['entry_date']).tz_localize(None)
                        days_ago = (datetime.now() - entry_date_pd).days
                        
                        if days_ago > 59:
                            st.warning(f"⚠️ Trade de hace {days_ago} días. Datos intraday no disponibles en APIs gratuitas (límite ~60 días). Solo disponible: 1d")
                        else:
                            st.caption(f"📊 Mostrando velas de **{timeframe}** para análisis intraday del ciclo de vida del trade.")
                    
                    entry_date_str = trade_data['entry_date'].strftime('%Y-%m-%d')
                    
                    # Initialize dashboard engine
                    if 'dashboard_engine' not in st.session_state:
                        if os.path.exists('backtest_results.csv'):
                            st.session_state['dashboard_engine'] = InteractiveDashboard('backtest_results.csv')
                    
                    if 'dashboard_engine' in st.session_state:
                        db = st.session_state['dashboard_engine']
                        
                        with st.spinner(f"Cargando gráfico {timeframe}..."):
                            try:
                                # Use intraday chart with selected timeframe
                                if timeframe == "1d":
                                    # Use daily chart
                                    fig = db.create_trade_chart(trade_data['symbol'], entry_date_str, signal_data)
                                else:
                                    # Use intraday chart
                                    entry_date_pd = pd.to_datetime(entry_date_str).tz_localize(None)
                                    days_diff = (datetime.now() - entry_date_pd).days
                                    
                                    intraday_df = None
                                    
                                    # Try YFinance first (if <60 days)
                                    if days_diff <= 59:
                                        try:
                                            intraday_df = db.data_provider.get_intraday_data(trade_data['symbol'], interval=timeframe, days=days_diff+5)
                                        except:
                                            pass
                                    
                                    # If YFinance failed or trade too old, try OpenBB
                                    if intraday_df is None or intraday_df.empty:
                                        st.info(f"📡 Intentando obtener datos históricos intraday vía OpenBB...")
                                        try:
                                            openbb_provider = OpenBBData()
                                            # Calculate date range for OpenBB
                                            start_date = (entry_date_pd - timedelta(days=1)).strftime('%Y-%m-%d')
                                            end_date = (entry_date_pd + timedelta(days=1)).strftime('%Y-%m-%d')
                                            
                                            intraday_df = openbb_provider.get_intraday_data(
                                                symbol=trade_data['symbol'],
                                                start_date=start_date,
                                                end_date=end_date,
                                                interval=timeframe
                                            )
                                            
                                            if intraday_df is not None and not intraday_df.empty:
                                                st.success("✅ Datos históricos obtenidos exitosamente vía OpenBB!")
                                        except Exception as openbb_error:
                                            st.warning(f"⚠️ OpenBB tampoco pudo obtener datos: {openbb_error}")
                                            intraday_df = None
                                    
                                    if intraday_df is not None and not intraday_df.empty:
                                        # Filter for entry date
                                        target_day_str = entry_date_pd.strftime('%Y-%m-%d')
                                        day_data = intraday_df[intraday_df.index.strftime('%Y-%m-%d') == target_day_str].copy()
                                        
                                        if not day_data.empty:
                                            # Normalize column names (OpenBB uses lowercase, YFinance uses Title case)
                                            day_data.columns = [col.capitalize() if col.lower() in ['open', 'high', 'low', 'close', 'volume'] else col for col in day_data.columns]
                                            
                                            # Calculate VWAP
                                            day_data['TP'] = (day_data['High'] + day_data['Low'] + day_data['Close']) / 3
                                            day_data['CumVol'] = day_data['Volume'].cumsum()
                                            day_data['CumVolPrice'] = (day_data['TP'] * day_data['Volume']).cumsum()
                                            day_data['VWAP'] = day_data['CumVolPrice'] / day_data['CumVol']
                                            
                                            # Create figure
                                            fig = go.Figure()
                                            
                                            # Candlesticks
                                            fig.add_trace(go.Candlestick(
                                                x=day_data.index,
                                                open=day_data['Open'],
                                                high=day_data['High'],
                                                low=day_data['Low'],
                                                close=day_data['Close'],
                                                name=f'Price {timeframe}'
                                            ))
                                            
                                            # VWAP Line
                                            fig.add_trace(go.Scatter(
                                                x=day_data.index,
                                                y=day_data['VWAP'],
                                                mode='lines',
                                                line=dict(color='orange', width=2),
                                                name='Intraday VWAP'
                                            ))
                                            
                                            # Entry Level
                                            fig.add_hline(y=signal_data['entry_price'], line_dash="dash", 
                                                        line_color="cyan", annotation_text="Entry")
                                            
                                            # Exit Level
                                            fig.add_hline(y=signal_data['exit_price'], line_dash="dash", 
                                                        line_color="green" if signal_data['outcome'] == 'WIN' else "red", 
                                                        annotation_text="Exit")
                                            
                                            # Stop Loss
                                            fig.add_hline(y=signal_data['stop_loss'], line_dash="dot", 
                                                        line_color="red", annotation_text="Stop")
                                            
                                            fig.update_layout(
                                                title=f"<b>🔍 Ciclo de Vida del Trade - {trade_data['symbol']}</b><br><sup>{timeframe} | {target_day_str} | {signal_data['camino']}</sup>",
                                                yaxis_title="Price ($)",
                                                xaxis_title="Time",
                                                template='plotly_white',
                                                height=600,
                                                xaxis_rangeslider_visible=False
                                            )
                                        else:
                                            st.warning(f"No hay datos {timeframe} para la fecha específica {entry_date_str}.")
                                            fig = None
                                    else:
                                        st.warning(f"⚠️ No se pudieron obtener datos {timeframe}. Mostrando gráfico diario.")
                                        fig = db.create_trade_chart(trade_data['symbol'], entry_date_str, signal_data)
                                
                                if fig:
                                    st.plotly_chart(fig, use_container_width=True, key=f"intraday_chart_{trade_data['symbol']}_{entry_date_str}_{timeframe}")
                                else:
                                    st.info("Mostrando gráfico estático como respaldo...")
                                    viz = BacktestVisualizer()
                                    viz.visualize_trade(trade_data['symbol'], entry_date_str, signal_data)
                                    chart_filename = f"{trade_data['symbol']}_{entry_date_str}_{signal_data['camino']}.png"
                                    chart_path = Path("backtest_charts") / chart_filename
                                    if chart_path.exists():
                                        st.image(str(chart_path), caption=f"Análisis Técnico: {trade_data['symbol']}", use_container_width=True)
                                        
                            except Exception as e:
                                st.error(f"Error cargando gráfico: {e}")
                                st.info("Mostrando gráfico estático como respaldo...")
                                viz = BacktestVisualizer()
                                viz.visualize_trade(trade_data['symbol'], entry_date_str, signal_data)
                                chart_filename = f"{trade_data['symbol']}_{entry_date_str}_{signal_data['camino']}.png"
                                chart_path = Path("backtest_charts") / chart_filename
                                if chart_path.exists():
                                    st.image(str(chart_path), caption=f"Análisis Técnico: {trade_data['symbol']}", use_container_width=True)
                    else:
                        st.warning("Dashboard engine no disponible. Ejecuta un backtest primero.")

                with tab_interactive:
                    if 'dashboard_engine' not in st.session_state:
                         if os.path.exists('backtest_results.csv'):
                             st.session_state['dashboard_engine'] = InteractiveDashboard('backtest_results.csv')
                    
                    if 'dashboard_engine' in st.session_state:
                        db = st.session_state['dashboard_engine']
                        try:
                            fig = db.create_trade_chart(trade_data['symbol'], entry_date_str, signal_data)
                            st.plotly_chart(fig, use_container_width=True, key=f"interactive_chart_{trade_data['symbol']}_{entry_date_str}")
                        except Exception as e:
                            st.error(f"Error generando gráfico interactivo: {e}")

                # --- ANATOMÍA DEL TRADE ---
                st.markdown("### 🏫 Anatomía del Trade (Explicación Paso a Paso)")
                st.info("Esta sección desglosa la operación para que puedas mecanizar el proceso mental.")
                
                sig_type = trade_data.get('signal_type', '')
                is_reclaim = 'VWAP_RECLAIM' in sig_type
                is_blue_sky = 'BLUE_SKY' in sig_type
                
                # Card 1: El Contexto - FULL WIDTH
                st.markdown("#### 1️⃣ Selección (El 'Qué')")
                
                # Extract Context Data
                vol_raw = trade_data.get('context_vol', 0)
                vol_str = f"{vol_raw/1e6:.1f}M" if vol_raw > 1e6 else f"{vol_raw/1e3:.0f}k" if vol_raw > 0 else "N/A"
                
                trend_str = trade_data.get('context_trend', 'N/A')
                adr_val = trade_data.get('context_adr', 0)
                rvol_val = trade_data.get('context_rvol', 0)
                
                # Tooltips educativos
                rvol_status = "✅ ACEPTADO" if rvol_val >= 1.0 else "❌ RECHAZADO"
                rvol_explanation = ""
                if is_blue_sky:
                    rvol_explanation = f"Blue Sky requiere RVOL ≥ 1.5x. Valor: {rvol_val:.2f}x {'✅' if rvol_val >= 1.5 else '❌'}"
                else:
                    rvol_explanation = f"VWAP Reclaim requiere RVOL ≥ 1.0x. Valor: {rvol_val:.2f}x {'✅' if rvol_val >= 1.0 else '❌'}"
                
                trend_explanation = {
                    'Uptrend': "✅ Precio por encima de SMA20 - Momentum alcista",
                    'Weak': "⚠️ Precio cerca de SMA20 - Gestión conservadora requerida",
                    'Downtrend': "❌ Precio debajo de SMA20 - Tendencia bajista"
                }.get(trend_str, "Tendencia no definida")
                
                adr_explanation = f"Volatilidad diaria promedio: {adr_val:.1f}% - {'Alta' if adr_val > 5 else 'Media' if adr_val > 3 else 'Baja'} oportunidad de movimiento"
                
                filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
                
                with filter_col1:
                    st.metric("📊 Volumen", vol_str)
                    with st.expander("ℹ️ ¿Por qué importa?"):
                        st.write("**Liquidez institucional.** Necesitamos volumen suficiente para entradas/salidas sin slippage.")
                
                with filter_col2:
                    st.metric("🔥 RVOL", f"{rvol_val:.2f}x", delta=rvol_status)
                    with st.expander("ℹ️ ¿Por qué importa?"):
                        st.write(f"**{rvol_explanation}**")
                        st.write("RVOL = Volumen actual vs promedio 20 días. Confirma interés institucional.")
                
                with filter_col3:
                    st.metric("📈 Tendencia", trend_str)
                    with st.expander("ℹ️ ¿Por qué importa?"):
                        st.write(f"**{trend_explanation}**")
                        if trend_str == "Weak":
                            st.write("En tendencia débil operamos con **salidas escalonadas** (FASE 1→2→3) para protección de capital.")
                        else:
                            st.write("Preferimos Uptrend para maximizar probabilidad. El sistema permite Weak con gestión risk-free.")
                
                with filter_col4:
                    st.metric("⚡ ADR", f"{adr_val:.1f}%")
                    with st.expander("ℹ️ ¿Por qué importa?"):
                        st.write(f"**{adr_explanation}**")
                        st.write("Average Daily Range: Potencial de movimiento. Mínimo 3% para justificar el riesgo.")
                
                st.markdown("---")
                
                # Card 2, 3, 4 - En fila
                step2, step3, step4 = st.columns(3)
                
                with step2:
                    st.markdown("#### 2️⃣ El Patrón (El 'Por qué')")
                    if is_reclaim:
                        st.markdown("🛡️ **VWAP Reclaim:**")
                        st.write("Trampa de Osos. Las instituciones defendieron el precio en apertura débil.")
                    elif is_blue_sky:
                        st.markdown("🚀 **Blue Sky Breakout:**")
                        st.write("Rompimiento de máximos sin resistencia. Momentum puro.")
                    else:
                        st.markdown("Patrón del sistema.")

                with step3:
                    st.markdown("#### 3️⃣ La Ejecución (El 'Cómo')")
                    if is_reclaim:
                        st.markdown(f"""
                        🔫 **Trigger:** Cruce VWAP  
                        📍 **Entrada:** ${trade_data['entry_price']:.2f}  
                        🛑 **Stop:** Min Día
                        """)
                    else:
                        st.markdown(f"""
                        🔫 **Trigger:** Base Break  
                        📍 **Entrada:** ${trade_data['entry_price']:.2f}  
                        🛑 **Stop:** Estructura
                        """)

                with step4:
                    st.markdown("#### 4️⃣ El Resultado (La Nota)")
                    r_mul = trade_data.get('r_multiple', 0)
                    result_color = "green" if r_mul > 0 else "red"
                    st.markdown(f"""
                    🏆 **Retorno:** :{result_color}[{trade_data['returns_pct']:+.2f}%]  
                    ⚖️ **Ratio R:** :{result_color}[{r_mul:+.2f}R]
                    """)
                
                st.markdown("---")
                
                # --- PARTIAL EXITS BREAKDOWN (NUEVO) ---
                # Buscar salidas parciales para este trade específico
                if not df_partial_raw.empty:
                    symbol = trade_data['symbol']
                    entry_date = trade_data['entry_date']
                    
                    partial_for_trade = df_partial_raw[
                        (df_partial_raw['symbol'] == symbol) & 
                        (df_partial_raw['entry_date'] == entry_date)
                    ].sort_values('exit_date')
                    
                    if not partial_for_trade.empty:
                        # Verificar si realmente hubo salidas parciales (FASE_1 o FASE_2)
                        has_partial_exits = any(partial_for_trade['phase'].isin(['FASE_1', 'FASE_2']))
                        
                        if has_partial_exits:
                            st.markdown("### 📤 Progresión de Salidas Parciales")
                            st.success("✅ Este trade ejecutó salidas escalonadas (Fase 1, Fase 2, Fase 3) - Sistema de Risk-Free")
                        else:
                            st.markdown("### 📤 Cierre de Posición")
                            st.info("ℹ️ Este trade se cerró sin ejecutar salidas parciales (no alcanzó +1R para risk-free)")
                        
                        # Timeline visual - FULL WIDTH
                        st.markdown("#### 📊 Timeline del Trade")
                        
                        # Calcular número de columnas: Entrada + Parciales (FASE_1, FASE_2) + Final
                        partial_phases_count = len(partial_for_trade[partial_for_trade['phase'].isin(['FASE_1', 'FASE_2'])])
                        num_phases = 1 + partial_phases_count + 1  # Entrada + Parciales + Final
                        timeline_cols = st.columns(num_phases)
                        
                        # Entrada
                        with timeline_cols[0]:
                            st.markdown("##### 🟢 ENTRADA")
                            entry_metrics = {
                                "📅 Fecha": trade_data['entry_date'].strftime('%Y-%m-%d'),
                                "💵 Precio": f"${trade_data['entry_price']:.2f}",
                                "📊 Shares": trade_data.get('initial_shares', 'N/A'),
                                "🎯 R inicial": f"${trade_data.get('R_inicial', 0):.2f}",
                                "⚡ ADR": f"${trade_data.get('adr_valor', 0):.2f}"
                            }
                            for key, val in entry_metrics.items():
                                st.write(f"**{key}:** {val}")
                        
                        # Cada salida parcial (FASE_1, FASE_2)
                        partial_phases = partial_for_trade[partial_for_trade['phase'].isin(['FASE_1', 'FASE_2'])]
                        for i, (idx, partial_row) in enumerate(partial_phases.iterrows()):
                            with timeline_cols[i + 1]:
                                phase_emoji = "🔵" if partial_row['phase'] == 'FASE_1' else "🟡"
                                days_held = (partial_row['exit_date'] - partial_row['entry_date']).days
                                
                                # Explicación de la fase
                                phase_explanation = ""
                                if partial_row['phase'] == 'FASE_1':
                                    phase_explanation = "⚡ Risk-Free Conversion\n🛡️ Stop → Breakeven"
                                elif partial_row['phase'] == 'FASE_2':
                                    phase_explanation = "💎 Resistance Exit\n📊 Booking Profits"
                                
                                st.markdown(f"##### {phase_emoji} {partial_row['phase']}")
                                st.write(phase_explanation)
                                st.write(f"**📅 Fecha:** {partial_row['exit_date'].strftime('%Y-%m-%d')}")
                                st.write(f"**⏱️ Días:** {days_held}")
                                st.write(f"**💵 Precio:** ${partial_row['exit_price']:.2f}")
                                st.write(f"**📉 Vendido:** {int(partial_row['shares'])} sh ({partial_row.get('exit_pct', 0):.0f}%)")
                                pnl_color = "green" if partial_row['pnl'] > 0 else "red"
                                st.markdown(f"**💰 P&L:** :{pnl_color}[${partial_row['pnl']:.2f}]")
                                st.markdown(f"**📈 Return:** :{pnl_color}[{partial_row['return_pct']:+.2f}%]")
                        
                        # Salida Final (Runner o Cierre Normal)
                        with timeline_cols[-1]:
                            if has_partial_exits:
                                st.markdown("##### 🏁 FASE 3 (Runner)")
                                st.write("🎯 Trailing Stop")
                            else:
                                st.markdown("##### 🔴 CIERRE")
                                # Mostrar razón del cierre
                                reason = trade_data.get('reason', 'N/A').split('|')[0].strip()
                                st.write(f"⚠️ {reason}")
                            
                            st.write(f"**📅 Fecha:** {trade_data['exit_date'].strftime('%Y-%m-%d')}")
                            # Calcular días totales desde entrada hasta salida final
                            total_days_held = (trade_data['exit_date'] - trade_data['entry_date']).days
                            st.write(f"**⏱️ Total Días:** {total_days_held}")
                            st.write(f"**💵 Precio:** ${trade_data['exit_price']:.2f}")
                            final_shares = trade_data.get('shares', 0)
                            
                            if has_partial_exits:
                                st.write(f"**📉 Restante:** {int(final_shares)} sh")
                            else:
                                st.write(f"**📉 Shares:** {int(final_shares)} sh")
                            
                            # Calcular P&L del runner correctamente desde precio de entrada
                            entry_price = trade_data['entry_price']
                            exit_price = trade_data['exit_price']
                            runner_pnl = (exit_price - entry_price) * final_shares
                            runner_color = "green" if runner_pnl > 0 else "red"
                            st.markdown(f"**💰 P&L:** :{runner_color}[${runner_pnl:.2f}]")
                        
                        st.markdown("---")
                        
                        # Tabla resumen - FULL WIDTH (solo si hay salidas parciales)
                        if has_partial_exits:
                            st.markdown("#### 📋 Resumen de Ejecución")
                            
                            summary_data = []
                            total_pnl = 0
                            
                            # Solo incluir FASE_1 y FASE_2
                            partial_phases = partial_for_trade[partial_for_trade['phase'].isin(['FASE_1', 'FASE_2'])]
                            for _, row in partial_phases.iterrows():
                                trigger_short = row['reason'].split(':')[1].strip() if ':' in row['reason'] else row['reason']
                                summary_data.append({
                                    '🎯 Fase': row['phase'],
                                    '⚡ Trigger': trigger_short,
                                    '💵 Exit Price': f"${row['exit_price']:.2f}",
                                    '📊 Shares': int(row['shares']),
                                    '📉 % Sold': f"{row.get('exit_pct', 0):.0f}%",
                                    '💰 P&L': f"${row['pnl']:.2f}",
                                    '📈 Return': f"{row['return_pct']:+.2f}%"
                                })
                                total_pnl += row['pnl']
                            
                            # Agregar salida final (Fase 3 - runner)
                            entry_price = trade_data['entry_price']
                            exit_price = trade_data['exit_price']
                            final_shares = trade_data.get('shares', 0)
                            final_pnl = (exit_price - entry_price) * final_shares
                            final_trigger = trade_data.get('reason', 'N/A').split('|')[0].strip()
                            summary_data.append({
                                '🎯 Fase': 'FASE_3 (Runner)',
                                '⚡ Trigger': final_trigger,
                                '💵 Exit Price': f"${trade_data['exit_price']:.2f}",
                                '📊 Shares': int(final_shares),
                                '📉 % Sold': f"{trade_data.get('final_shares_pct', 0):.0f}%",
                                '💰 P&L': f"${final_pnl:.2f}",
                                '📈 Return': f"{trade_data['returns_pct']:+.2f}%"
                            })
                            
                            summary_df = pd.DataFrame(summary_data)
                            st.dataframe(summary_df, use_container_width=True, hide_index=True)
                        else:
                            # Trade sin parciales - mostrar solo resumen simple
                            total_pnl = 0
                            final_pnl = trade_data['pnl']  # PnL total ya está en el trade_data
                        
                        # Métricas totales - FULL WIDTH
                        st.markdown("#### 🎯 Métricas Totales")
                        col_t1, col_t2, col_t3, col_t4, col_t5 = st.columns(5)
                        with col_t1:
                            # Total P&L
                            if has_partial_exits:
                                total_result = total_pnl + final_pnl
                            else:
                                total_result = final_pnl
                            total_color = "green" if total_result > 0 else "red"
                            st.metric("💰 Total P&L", f"${total_result:.2f}", delta="Final")
                        with col_t2:
                            if has_partial_exits:
                                st.metric("📊 Parciales P&L", f"${total_pnl:.2f}", delta="Fases 1-2")
                            else:
                                st.metric("📊 Parciales P&L", "$0.00", delta="No ejecutadas")
                        with col_t3:
                            if has_partial_exits:
                                st.metric("🏃 Runner P&L", f"${final_pnl:.2f}", delta="Fase 3")
                            else:
                                st.metric("🏃 Cierre Directo", f"${final_pnl:.2f}", delta="Sin parciales")
                        with col_t4:
                            if has_partial_exits:
                                fases_ejecutadas = len(partial_for_trade[partial_for_trade['phase'].isin(['FASE_1', 'FASE_2'])])
                                st.metric("✅ Fases Ejecutadas", f"{fases_ejecutadas}/2", delta="Parciales")
                            else:
                                st.metric("✅ Fases Ejecutadas", "0/2", delta="Sin risk-free")
                        with col_t5:
                            # Recalcular R Multiple con PnL total correcto
                            R_inicial = trade_data.get('R_inicial', 1)
                            initial_shares = trade_data.get('initial_shares', trade_data.get('shares', 0))
                            total_risk = R_inicial * initial_shares
                            total_r = total_result / total_risk if total_risk > 0 else 0
                            r_color = "normal" if total_r > 0 else "inverse"
                            st.metric("⚖️ R Total", f"{total_r:+.2f}R", delta=None, delta_color=r_color)
                        
                        # Notas educativas
                        with st.expander("📚 Notas Educativas - ¿Por qué funciona este sistema?"):
                            st.markdown("""
                            ### 🛡️ Sistema de Salidas Risk-Free
                            
                            **Fase 1 (40% @ +1R o +1ADR):**
                            - ✅ Convierte el trade en inversión libre de riesgo
                            - 🔒 Stop sube a Breakeven AUTOMÁTICAMENTE
                            - 💡 Asegura ganancia mínima, nunca pierde después de aquí
                            
                            **Fase 2 (30% @ +2.5R o resistencia):**
                            - 💎 Book profits en zona de resistencia técnica
                            - 📊 Ya tienes 70% de capital recuperado + ganancias
                            
                            **Fase 3 (30% Runner con trailing stop):**
                            - 🚀 Deja correr para capturar big movers (runners)
                            - 📈 Protegido con EMA/SMA trailing stop
                            - 🛡️ Stop NUNCA baja de Breakeven
                            
                            **Resultado:** 
                            - ✅ Si sube: Maximizas ganancias
                            - ✅ Si baja: Sales con ganancia de Fase 1
                            - ❌ IMPOSIBLE perder después de Fase 1
                            """)


                st.markdown("---")

                # --- MASTERCLASS CONTEXT ---
                with st.expander("🎓 Contexto Educativo (Masterclass)", expanded=True):
                    st.markdown("### 📚 Fundamentos del Setup")
                    
                    if 'VWAP_RECLAIM' in sig_type:
                        st.markdown("#### 🛡️ VWAP Reclaim - Segunda Oportunidad")
                        
                        col_edu1, col_edu2 = st.columns(2)
                        
                        with col_edu1:
                            st.markdown("""
                            **🎯 El Concepto:**
                            
                            El VWAP Reclaim es un patrón de **recuperación institucional** después de una apertura débil.
                            
                            **¿Qué es VWAP?**
                            - Volume Weighted Average Price
                            - Precio promedio ponderado por volumen del día
                            - **Línea de batalla** entre compradores y vendedores
                            
                            **La Psicología:**
                            1. 🔻 Apertura débil (gap down o venta matutina)
                            2. 🐻 Traders minoristas venden por pánico
                            3. 🏦 Instituciones **compran la debilidad**
                            4. ✅ Precio reclaim VWAP = Instituciones ganando
                            
                            **Señal de Confirmación:**
                            - Cruce por encima de VWAP
                            - RVOL ≥ 1.0x (volumen confirmando)
                            - Stop: Low of Day (LOD)
                            """)
                        
                        with col_edu2:
                            st.markdown("""
                            **📊 Criterios de Validación:**
                            
                            ✅ **ACEPTADO si:**
                            - RVOL ≥ 1.0x (mínimo)
                            - Precio cruza VWAP de abajo hacia arriba
                            - Mercado general débil (SPY/QQQ gap down)
                            - Tendencia general: Uptrend en timeframe mayor
                            
                            ❌ **RECHAZADO si:**
                            - RVOL < 1.0x (sin instituciones)
                            - Precio ya muy por encima de VWAP
                            - Tendencia bajista en timeframe mayor
                            - Stop loss muy amplio (>5% del precio)
                            
                            **💡 Trading Edge:**
                            Este patrón funciona porque capturas el momento exacto 
                            en que las instituciones "defienden" el precio después 
                            de una trampa de osos.
                            
                            **🎲 Probabilidad:**
                            - Win Rate: ~45-55%
                            - Reward:Risk: 2:1 típico
                            - Best con mercados débiles
                            """)
                        
                    elif 'BLUE_SKY' in sig_type:
                        st.markdown("#### 🚀 Blue Sky Breakout - Momentum Puro")
                        
                        col_edu1, col_edu2 = st.columns(2)
                        
                        with col_edu1:
                            st.markdown("""
                            **🎯 El Concepto:**
                            
                            Blue Sky Breakout es un rompimiento hacia **máximos históricos** sin resistencia superior.
                            
                            **¿Por qué funciona?**
                            - No hay "bag holders" (compradores atrapados arriba)
                            - Sin resistencia = menos vendedores
                            - Momentum alcista fuerte
                            - FOMO institucional activo
                            
                            **La Anatomía:**
                            1. 📊 Base de consolidación (3-10 días)
                            2. 📈 AVWAP convergiendo con base high
                            3. 🔥 Volumen explosivo (RVOL > 1.5x)
                            4. 🚀 Breakout con convicción
                            
                            **Señal de Entrada:**
                            - Buy Stop 5¢ por encima del base high
                            - AVWAP dentro de 2% del base high
                            - Tendencia: Uptrend (precio > SMA20)
                            """)
                        
                        with col_edu2:
                            st.markdown("""
                            **📊 Criterios de Validación:**
                            
                            ✅ **ACEPTADO si:**
                            - RVOL ≥ 1.5x (instituciones activas)
                            - AVWAP cerca del base high (<2% divergencia)
                            - Tendencia: Uptrend confirmado
                            - ADR ≥ 3% (volatilidad suficiente)
                            - Base bien formada (3+ días)
                            
                            ❌ **RECHAZADO si:**
                            - RVOL < 1.5x (sin volumen = trampa)
                            - AVWAP muy por encima del precio actual
                            - Tendencia: Weak o Downtrend
                            - ADR < 3% (poco potencial)
                            
                            **💡 Trading Edge:**
                            Este patrón captura el inicio de movimientos impulsivos
                            cuando instituciones entran masivamente en un stock 
                            que "rompe techos".
                            
                            **🎲 Probabilidad:**
                            - Win Rate: ~40-50%
                            - Reward:Risk: 3:1+ en runners
                            - Best con mercados alcistas
                            """)
                    else:
                        st.info("Selecciona un trade con señal VWAP_RECLAIM o BLUE_SKY para ver el contexto educativo completo.")
                    
                    # Glosario común
                    st.markdown("---")
                    st.markdown("#### 📖 Glosario de Términos")
                    
                    glossary_col1, glossary_col2, glossary_col3 = st.columns(3)
                    
                    with glossary_col1:
                        st.markdown("""
                        **RVOL (Relative Volume):**
                        - Volumen actual vs promedio 20 días
                        - 1.0x = volumen normal
                        - >1.5x = instituciones activas
                        - <1.0x = poco interés
                        """)
                        
                    with glossary_col2:
                        st.markdown("""
                        **ADR (Average Daily Range):**
                        - Rango diario promedio en %
                        - Mide volatilidad
                        - >5% = Alta volatilidad
                        - 3-5% = Media (ideal)
                        - <3% = Baja (poco potencial)
                        """)
                    
                    with glossary_col3:
                        st.markdown("""
                        **R (Risk Multiple):**
                        - Retorno vs riesgo inicial
                        - 1R = ganaste tu riesgo inicial
                        - 2R = ganaste 2x tu riesgo
                        - -1R = perdiste tu stop completo
                        - Objetivo: >2R promedio
                        """)

    # ==========================================
    # TAB 2: PnL CALENDAR (NEW)
    # ==========================================
    with tab_calendar:
        st.header("📅 PnL Calendar & Monthly Analysis")
        
        df_cal = df_raw.copy()
        if 'shares' in df_cal.columns:
            df_cal['Result'] = (df_cal['exit_price'] - df_cal['entry_price']) * df_cal['shares']
            
            # --- DATE SELECTION ---
            # Calculate Monthly PnLs for the Selector
            df_cal['month_key'] = df_cal['exit_date'].dt.to_period('M')
            monthly_agg = df_cal.groupby('month_key')['Result'].sum().sort_index(ascending=False)
            
            month_options = []
            month_map = {}
            for period, pnl in monthly_agg.items():
                start_of_month = period.start_time.date()
                pnl_str = f"+${pnl:,.0f}" if pnl >= 0 else f"-${abs(pnl):,.0f}"
                label = f"{start_of_month.strftime('%B %Y')} ({pnl_str})"
                month_options.append(label)
                month_map[label] = start_of_month

            col_sel1, col_sel2 = st.columns([1, 2])
            with col_sel1:
                if month_options:
                    selected_month_label = st.selectbox("📅 Seleccionar Mes", month_options)
                    selected_date = month_map[selected_month_label]
                else:
                    selected_date = datetime.now().date().replace(day=1)
                    st.warning("No hay datos mensuales disponibles.")
            
            # Filter Month
            sel_month_start = selected_date # Already 1st of month

            # Safe logic for next month first day
            if sel_month_start.month == 12:
                next_month = sel_month_start.replace(year=sel_month_start.year+1, month=1, day=1)
            else:
                next_month = sel_month_start.replace(month=sel_month_start.month+1, day=1)
            
            sel_month_end = next_month - timedelta(days=1)
            
            monthly_trades = df_cal[(df_cal['exit_date'].dt.date >= sel_month_start) & 
                                  (df_cal['exit_date'].dt.date <= sel_month_end)]
            monthly_pnl = monthly_trades['Result'].sum()
            
            with col_sel2:
                # Generate Calendar Grid with Interactive Buttons and Custom Styling
                cal = calendar.Calendar(firstweekday=6) # Sunday start
                month_days = cal.monthdayscalendar(selected_date.year, selected_date.month)
                
                st.markdown(f"### 🗓️ {selected_date.strftime('%B %Y')}")
                
                # Initialize selected_day in session state
                if 'selected_day' not in st.session_state:
                    st.session_state.selected_day = selected_date
                
                # Custom CSS for calendar styling
                st.markdown("""
                <style>
                .cal-day-header {
                    text-align: center;
                    font-weight: bold;
                    font-size: 11px;
                    color: #666;
                    padding: 5px;
                    background: #f0f2f6;
                    border-radius: 5px;
                    margin-bottom: 5px;
                }
                /* Override Streamlit button styles for calendar */
                div[data-testid="column"] > div > div > button {
                    font-size: 13px !important;
                    padding: 10px 5px !important;
                    min-height: 70px !important;
                    white-space: pre-wrap !important;
                    border-radius: 8px !important;
                    font-weight: 500 !important;
                }
                /* Win buttons (primary) - Green theme */
                div[data-testid="column"] > div > div > button[kind="primary"] {
                    background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%) !important;
                    color: #155724 !important;
                    border: 2px solid #b1dfbb !important;
                }
                div[data-testid="column"] > div > div > button[kind="primary"]:hover {
                    background: linear-gradient(135deg, #c3e6cb 0%, #b1dfbb 100%) !important;
                    border-color: #28a745 !important;
                    transform: scale(1.05) !important;
                    box-shadow: 0 4px 8px rgba(40, 167, 69, 0.3) !important;
                }
                /* Loss buttons (secondary) - Red theme */
                div[data-testid="column"] > div > div > button[kind="secondary"] {
                    background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%) !important;
                    color: #721c24 !important;
                    border: 2px solid #f1b0b7 !important;
                }
                div[data-testid="column"] > div > div > button[kind="secondary"]:hover {
                    background: linear-gradient(135deg, #f5c6cb 0%, #f1b0b7 100%) !important;
                    border-color: #dc3545 !important;
                    transform: scale(1.05) !important;
                    box-shadow: 0 4px 8px rgba(220, 53, 69, 0.3) !important;
                }
                /* Neutral days (tertiary) - Gray theme */
                div[data-testid="column"] > div > div > button[kind="tertiary"] {
                    background: #ffffff !important;
                    color: #495057 !important;
                    border: 1px solid #dee2e6 !important;
                }
                div[data-testid="column"] > div > div > button[kind="tertiary"]:hover {
                    background: #f8f9fa !important;
                    border-color: #adb5bd !important;
                    transform: scale(1.02) !important;
                }
                </style>
                """, unsafe_allow_html=True)
                
                days_header = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
                
                # Display calendar header
                header_cols = st.columns(7)
                for idx, day_name in enumerate(days_header):
                    with header_cols[idx]:
                        st.markdown(f'<div class="cal-day-header">{day_name}</div>', unsafe_allow_html=True)
                
                month_pnl_total = 0
                
                # Display calendar grid with interactive buttons
                for week in month_days:
                    week_cols = st.columns(7)
                    for idx, day in enumerate(week):
                        with week_cols[idx]:
                            if day == 0:
                                st.write("")  # Empty cell
                            else:
                                # Find PnL for this day
                                current_dt = datetime(selected_date.year, selected_date.month, day).date()
                                day_trades = df_cal[df_cal['exit_date'].dt.date == current_dt]
                                
                                pnl_val = day_trades['Result'].sum() if not day_trades.empty else 0
                                
                                pnl_str = ""
                                button_type = "tertiary"  # neutral/no trades
                                
                                if pnl_val > 0: 
                                    pnl_str = f"+${pnl_val:,.0f}"
                                    month_pnl_total += pnl_val
                                    button_type = "primary"  # Green for wins
                                elif pnl_val < 0: 
                                    pnl_str = f"-${abs(pnl_val):,.0f}"
                                    month_pnl_total += pnl_val
                                    button_type = "secondary"  # Red for losses
                                
                                # Button label with day and PnL
                                label = f"**{day}**\n{pnl_str}" if pnl_str else f"{day}"
                                
                                # Highlight selected day
                                is_selected = (current_dt == st.session_state.get('selected_day', selected_date))
                                
                                # Create button for each day
                                if st.button(label, key=f"day_{selected_date.year}_{selected_date.month}_{day}", 
                                           type=button_type, use_container_width=True):
                                    st.session_state.selected_day = current_dt
                
                if monthly_trades.empty:
                    st.caption("No trades closed this month.")
                else:
                    # Display monthly summary with color
                    col_metric1, col_metric2 = st.columns(2)
                    with col_metric1:
                        pnl_delta = "📈" if month_pnl_total >= 0 else "📉"
                        st.metric("Monthly PnL", f"${month_pnl_total:,.2f}", 
                                delta=f"{pnl_delta} {len(monthly_trades)} Trades",
                                delta_color="normal" if month_pnl_total >= 0 else "inverse")
                    with col_metric2:
                        win_trades = monthly_trades[monthly_trades['Result'] > 0]
                        win_rate = len(win_trades) / len(monthly_trades) * 100 if len(monthly_trades) > 0 else 0
                        st.metric("Win Rate", f"{win_rate:.1f}%", 
                                delta=f"{len(win_trades)}W / {len(monthly_trades)-len(win_trades)}L")

            st.markdown("---")
            
            # --- DAILY DETAIL VIEW ---
            # Use the selected day from session state
            display_date = st.session_state.get('selected_day', selected_date)
            st.subheader(f"📆 Daily Snapshot: {display_date.strftime('%Y-%m-%d')}")
            
            # A. REALIZED PNL (Closed Today)
            realized_today = df_cal[df_cal['exit_date'].dt.date == display_date]
            
            # B. ACTIVE POSITIONS (Active Today)
            active_today = df_cal[(df_cal['entry_date'].dt.date <= display_date) & 
                                (df_cal['exit_date'].dt.date > display_date)].copy()
            
            c_d1, c_d2 = st.columns([2, 1])
            
            with c_d1:
                combined_rows = []
                # Realized
                for _, row in realized_today.iterrows():
                    combined_rows.append({
                        'Sym': row['symbol'], 'Pos': 0, 'Last': row['exit_price'],
                        'PosAvg': row['entry_price'], '$Real': row['Result'], '$Value': 0.0, 'Type': 'Closed'
                    })
                # Active
                for _, row in active_today.iterrows():
                    combined_rows.append({
                        'Sym': row['symbol'], 'Pos': row['shares'], 'Last': row['entry_price'], # Proxy
                        'PosAvg': row['entry_price'], '$Real': 0.0, '$Value': row['shares'] * row['entry_price'], 'Type': 'Open'
                    })
                
                df_day_view = pd.DataFrame(combined_rows)
                
                if not df_day_view.empty:
                    st.dataframe(
                        df_day_view,
                        column_config={
                            "Sym": st.column_config.TextColumn("Sym", width="small"),
                            "Pos": st.column_config.NumberColumn("Pos", format="%.0f"),
                            "Last": st.column_config.NumberColumn("Last (Ref)", format="$%.2f"),
                            "PosAvg": st.column_config.NumberColumn("PosAvg", format="$%.2f"),
                            "$Real": st.column_config.NumberColumn("$Real PnL", format="$%.2f"),
                            "$Value": st.column_config.NumberColumn("$Alloc Value", format="$%.2f"),
                        },
                        use_container_width=True, hide_index=True
                    )
                    total_realized = df_day_view['$Real'].sum()
                    st.markdown(f"**Total Realized Today:** :green[${total_realized:,.2f}]" if total_realized >= 0 else f"**Total Realized Today:** :red[${total_realized:,.2f}]")
                else:
                    st.info("No activity recorded for this date.")

            with c_d2:
                if not active_today.empty:
                    fig_pie = px.pie(active_today, values='position_value', names='symbol', 
                                   title=f"Portfolio Allocation ({display_date.strftime('%b %d')})", hole=0.4)
                    st.plotly_chart(fig_pie, use_container_width=True, key=f"portfolio_pie_{display_date.strftime('%Y%m%d')}")
                else:
                    st.info("No open positions.")

            # --- MONTHLY EQUITY CURVE ---
            st.markdown("---")
            st.subheader(f"📈 Monthly Performance: {selected_date.strftime('%B %Y')}")
            
            if not monthly_trades.empty:
                monthly_trades = monthly_trades.sort_values('exit_date')
                monthly_trades['cum_pnl'] = monthly_trades['Result'].cumsum()
                fig_equity = px.area(monthly_trades, x='exit_date', y='cum_pnl',
                                   title=f"Realized PnL Curve - {selected_date.strftime('%B')}",
                                   labels={'cum_pnl': 'Cumulative PnL ($)', 'exit_date': 'Date'})
                st.plotly_chart(fig_equity, use_container_width=True, key=f"monthly_equity_{selected_date.strftime('%Y%m')}")
            else:
                st.info("No trades closed in this month.")
        else:
            st.warning("Run backtest to see Calendar data.")
    
    # ==========================================
    # TAB 3: LIVE MARKET SCANNER
    # ==========================================
    with tab_live_scanner:
        st.header("📡 Live Market Scanner")
        st.caption("🔴 Condiciones del mercado en TIEMPO REAL (no histórico)")
        
        try:
            from src.data.market_data import MarketDataProvider
            from src.core.market_context import MarketContext
            
            with st.spinner("Analizando condiciones del mercado..."):
                provider = MarketDataProvider()
                mc = MarketContext(provider)
                context = mc.analyze_indices()
            
            # Extract metrics
            spy_price = context.get('spy_price', 0)
            spy_ema20 = context.get('spy_ema20', 0)
            spy_above_ema20 = context.get('spy_above_ema20', False)
            breadth_improving = context.get('breadth_improving', False)
            positive_gex = context.get('positive_gex', False)
            vix_favorable = context.get('vix_favorable', True)
            sector_leaders = context.get('sector_leaders', {})
            market_favorable = context.get('market_favorable_for_longs', False)
            
            # Calculate health score
            health_score = 0
            if spy_above_ema20:
                health_score += 2
            if breadth_improving:
                health_score += 2
            if positive_gex:
                health_score += 1
            if vix_favorable:
                health_score += 1
            if sector_leaders:
                health_score += 1
            
            # Display in columns
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "SPY Trend",
                    f"${spy_price:.2f}",
                    f"{((spy_price - spy_ema20) / spy_ema20 * 100):+.2f}%" if spy_ema20 else "N/A",
                    delta_color="normal"
                )
                if spy_above_ema20:
                    st.success("✅ Above EMA20")
                else:
                    st.error("❌ Below EMA20")
            
            with col2:
                st.metric("Breadth", "Improving" if breadth_improving else "Declining")
                if breadth_improving:
                    st.success("✅ Strong")
                else:
                    st.warning("⚠️ Weak")
            
            with col3:
                st.metric("Volatility", "Favorable" if vix_favorable else "Elevated")
                if vix_favorable:
                    st.success("✅ VIX < 20")
                else:
                    st.error("⚠️ VIX High")
            
            with col4:
                st.metric("GEX", "Positive" if positive_gex else "Neutral")
                if positive_gex:
                    st.success("✅ Low Vol Grind")
                else:
                    st.info("⚪ Normal")
            
            # Health Score and Verdict
            st.markdown("---")
            col_score, col_verdict = st.columns([1, 2])
            
            with col_score:
                st.metric("Health Score", f"{health_score}/7", f"{(health_score/7*100):.0f}%")
                st.progress(health_score / 7)
            
            with col_verdict:
                if not market_favorable:
                    st.error("❌ **NO TRADE MODE** - Market not favorable for longs")
                    st.caption("Go to cash or paper trade only")
                elif health_score >= 6:
                    st.success("🚀 **AGGRESSIVE MODE** - Excellent conditions")
                    st.caption("Full size (2% risk), all 3 Caminos, focus on leading sectors")
                elif health_score >= 4:
                    st.success("💪 **STANDARD MODE** - Good conditions")
                    st.caption("Standard size (1.5-2% risk), prefer Camino 1 in leading sectors")
                else:
                    st.warning("⚠️ **DEFENSIVE MODE** - Be selective")
                    st.caption("Half size (0.5-1% risk), only perfect Blue Sky in top sectors")
            
            # Sector Leaders
            if sector_leaders:
                st.markdown("---")
                st.subheader("🎯 Top Performing Sectors (Today)")
                
                st.info("💡 **Trading Tip**: Focus on leading sectors for mejor probabilidad de éxito. Evita sectores débiles.")
                
                # Top 3 in columns
                top_3 = list(sector_leaders.items())[:3]
                col_s1, col_s2, col_s3 = st.columns(3)
                for idx, (sector, data) in enumerate(top_3):
                    with [col_s1, col_s2, col_s3][idx]:
                        pct = data['change_pct']
                        st.metric(
                            f"#{idx+1} {sector}",
                            f"{data['symbol']}",
                            f"{pct:+.2f}%",
                            delta_color="normal"
                        )
                
                # Full sector table
                st.markdown("### 📊 All Sectors Performance")
                sector_df = pd.DataFrame([
                    {
                        'Sector': sector,
                        'ETF': data['symbol'],
                        'Change %': data['change_pct'],
                        'Trend': '🟢 Strong' if data['change_pct'] > 0.5 else '🟡 Neutral' if data['change_pct'] > 0 else '🔴 Weak'
                    }
                    for sector, data in sector_leaders.items()
                ]).sort_values('Change %', ascending=False)
                
                st.dataframe(
                    sector_df,
                    column_config={
                        "Change %": st.column_config.NumberColumn("Change %", format="%.2f%%"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                # Action recommendations
                st.markdown("---")
                st.subheader("🎯 Recommended Actions")
                
                top_sector = list(sector_leaders.items())[0]
                worst_sector = list(sector_leaders.items())[-1]
                
                col_rec1, col_rec2 = st.columns(2)
                with col_rec1:
                    st.success(f"**✅ FOCUS ON**: {top_sector[0]}")
                    st.caption(f"Leading with {top_sector[1]['change_pct']:+.2f}%. Busca setups en este sector.")
                
                with col_rec2:
                    st.error(f"**❌ AVOID**: {worst_sector[0]}")
                    st.caption(f"Lagging with {worst_sector[1]['change_pct']:+.2f}%. Skip este sector hoy.")

        except Exception as e:
            st.error(f"Error loading market health: {e}")
            st.caption("Intenta recargar la página")

else:
    st.info("👋 Bienvenido. Configura los parámetros de riesgo a la izquierda y pulsa 'EJECUTAR BACKTEST'.")
