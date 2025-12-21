import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import os
import subprocess
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.dashboard import InteractiveDashboard
from config.universe_presets import LIQUID_MID_CAPS

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

# Función para ejecutar el backtest con UI de progreso y parámetros de riesgo
def run_backtest_with_progress(start_date, end_date, stop_loss_pct=None, 
                               equity=100000, risk_pct=0.5, max_exp_pct=25,
                               min_mcap_b=2.0, max_mcap_b=20.0, 
                               min_vol_k=300, min_adr=1.5, min_price=5.0, min_dollar_m=15,
                               watchlist_path='config/watchlist.json', skip_filters=False):
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
        "--min_dollar_vol", str(int(min_dollar_m * 1e6))
    ]
    
    if skip_filters:
        cmd.append("--skip_filters")
    
    if stop_loss_pct is not None and stop_loss_pct > 0:
        cmd.extend(["--stop_loss", str(stop_loss_pct)])
    
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
    run_start_date = st.date_input("Fecha Inicio", value=datetime(2024, 1, 1))
    run_end_date = st.date_input("Fecha Fin", value=datetime.now())
    
    st.markdown("---")
    # Checkbox para forzar calidad institucional
    use_inst_quality = st.checkbox("🛡️ Modo Calidad Institucional", value=True, help="Fuerza filtros mínimos: Mcap > 2B, Precio > $5, Volumen > 300k, $Vol > 15M")
    
    # Logic to set defaults based on checkbox
    def_mcap = 2.0 if use_inst_quality else 0.5
    def_price = 5.0 if use_inst_quality else 1.0
    def_vol = 300 if use_inst_quality else 50
    def_dvol = 15 if use_inst_quality else 1
    
    st.markdown("**Filtros de Calidad**")
    c1, c2 = st.columns(2)
    in_min_mcap = c1.number_input("Min Mcap ($B)", value=def_mcap, step=0.5, disabled=use_inst_quality)
    in_max_mcap = c2.number_input("Max Mcap ($B)", value=20.0, step=1.0)
    in_min_price = st.number_input("Precio Mínimo ($)", value=def_price, step=1.0, disabled=use_inst_quality)
    
    st.markdown("**Filtros de Liquidez y Volatilidad**")
    in_min_vol = st.number_input("Min Volumen Diario (k)", value=def_vol, step=50, disabled=use_inst_quality)
    in_min_dollar_m = st.number_input("Min Dollar Volume ($M)", value=def_dvol, step=5, disabled=use_inst_quality)
    in_min_adr = st.number_input("Min ADR 20 (%)", value=1.5, step=0.1, format="%.1f")
    
    # Stop Loss Config
    use_custom_stop = st.checkbox("Forzar Stop Loss Fijo (%)")
    stop_loss_input = 2.0
    if use_custom_stop:
        stop_loss_input = st.number_input("Stop Loss %", value=3.0, step=0.5)

with st.sidebar.expander("🛡️ Institutional Risk Manager", expanded=True):
    in_equity = st.number_input("Equity ($)", value=100000.0, step=10000.0)
    in_risk = st.number_input("Risk per Trade (%)", value=0.5, step=0.1, format="%.2f")
    in_max_exp = st.number_input("Max Exposure (%)", value=25.0, step=5.0)

# --- Nueva Entrada Directa de Símbolos ---
st.sidebar.markdown("---")
st.sidebar.header("🚀 Ejecución Rápida")
direct_symbols = st.sidebar.text_area("Símbolos a Testear (separados por coma)", value="APP, PLTR", help="Escribe los tickers que quieras probar, ej: AAPL, TSLA, NVDA")

if st.sidebar.button("🚀 EJECUTAR BACKTEST", use_container_width=True):
    sl_val = stop_loss_input if use_custom_stop else None
    
    # Crear lista temporal basada en la entrada directa
    if direct_symbols:
        symbols_list = [s.strip().upper() for s in direct_symbols.split(',') if s.strip()]
        temp_watchlist_path = 'temp_backtest_list.json'
        with open(temp_watchlist_path, 'w') as f:
            json.dump({"DIRECT_INPUT": symbols_list}, f)
        
        if run_backtest_with_progress(run_start_date, run_end_date, sl_val, in_equity, in_risk, in_max_exp, 
                                      in_min_mcap, in_max_mcap, in_min_vol, in_min_adr, in_min_price, in_min_dollar_m,
                                      watchlist_path=temp_watchlist_path, skip_filters=True):
            st.rerun()
    else:
        st.sidebar.error("Escribe al menos un símbolo para testear.")

st.sidebar.markdown("---")

# --- Carga de datos ---
@st.cache_data
def load_data():
    try:
        if os.path.exists('backtest_results.csv'):
            df = pd.read_csv('backtest_results.csv')
            df['entry_date'] = pd.to_datetime(df['entry_date'])
            df['exit_date'] = pd.to_datetime(df['exit_date'])
            return df
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

df_raw = load_data()

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

# Lógica Principal
if not df_raw.empty:
    df_filtered = df_raw.copy()
    if f_symbol != 'Todos': df_filtered = df_filtered[df_filtered['symbol'] == f_symbol]
    if f_signal != 'Todos': df_filtered = df_filtered[df_filtered['signal_type'] == f_signal]

    df_filtered = df_filtered.sort_values('exit_date')
    
    if 'shares' in df_filtered.columns:
        df_filtered['Result'] = (df_filtered['exit_price'] - df_filtered['entry_price']) * df_filtered['shares']
        # Ajuste para PnL parciales
        df_filtered['Result'] = df_filtered['position_value'] * (df_filtered['returns_pct'] / 100)
        
        if 'monetary_risk' in df_filtered.columns:
            df_filtered['r_multiple'] = df_filtered['Result'] / df_filtered['monetary_risk']
        else:
            df_filtered['r_multiple'] = 0.0
    else:
        df_filtered['Result'] = 0.0
        df_filtered['r_multiple'] = 0.0

    df_filtered['Running_Capital'] = in_equity + df_filtered['Result'].cumsum()

    # Métricas
    total_trades = len(df_filtered)
    winners = df_filtered[df_filtered['Result'] > 0]
    losers = df_filtered[df_filtered['Result'] <= 0]
    win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
    closed_pnl = df_filtered['Result'].sum()
    
    # UI
    st.markdown("### 📊 Performance Institucional")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equity Final", f"${(in_equity + closed_pnl):,.2f}")
    c2.metric("Total PnL", f"${closed_pnl:,.2f}", delta=f"{(closed_pnl/in_equity)*100:.1f}%")
    c3.metric("Win Rate", f"{win_rate:.1f}%")
    c4.metric("Trades", total_trades)

    c5, c6, c7, c8 = st.columns(4)
    avg_risk = df_filtered['monetary_risk'].mean() if 'monetary_risk' in df_filtered.columns else 0
    c5.metric("Avg Risk per Trade", f"${avg_risk:,.0f}")
    c6.metric("Total R", f"{df_filtered['r_multiple'].sum():.1f}R")
    c7.metric("Expectancy", f"{df_filtered['r_multiple'].mean() if total_trades > 0 else 0:.2f}R")
    
    gross_loss = abs(losers['Result'].sum())
    profit_factor = (winners['Result'].sum() / gross_loss) if gross_loss > 0 else 0.0
    c8.metric("Profit Factor", f"{profit_factor:.2f}")

    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    with col1:
        fig = px.line(df_filtered, x='exit_date', y='Running_Capital', title='Equity Curve (Real Risk Adjusted)')
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        if 'shares' in df_filtered.columns:
            fig = px.scatter(df_filtered, x='entry_date', y='position_value', 
                             color='is_profitable', size='shares',
                             title='Position Sizing Impact (Size = Shares, Y = Capital Alloc)')
            st.plotly_chart(fig, use_container_width=True)

    #Tabla
    st.markdown("### 📋 Trade Log (Institutional)")
    df_disp = df_filtered.copy()
    if 'shares' in df_disp.columns:
        # Calculate days held
        df_disp['days_held'] = (df_filtered['exit_date'] - df_filtered['entry_date']).dt.days
        
        cols = ['symbol', 'entry_date', 'days_held', 'signal_type', 'shares', 'position_value', 'monetary_risk', 'returns_pct', 'r_multiple', 'Result']
        
        # Usar column_config para formatear sin perder tipos numéricos
        st.dataframe(
            df_disp[cols].sort_values('entry_date', ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "symbol": st.column_config.TextColumn("Symbol", width="small"),
                "entry_date": st.column_config.DateColumn("Entry Date", format="YYYY-MM-DD"),
                "days_held": st.column_config.NumberColumn("Days", format="%d"),
                "signal_type": st.column_config.TextColumn("Signal"),
                "shares": st.column_config.NumberColumn("Shares", format="%.2f"),
                "position_value": st.column_config.NumberColumn("Position", format="$%,.0f"),
                "monetary_risk": st.column_config.NumberColumn("Risk", format="$%,.0f"),
                "returns_pct": st.column_config.NumberColumn("Return %", format="%+.2f%%"),
                "r_multiple": st.column_config.NumberColumn("R Multiple", format="%+.2f R"),
                "Result": st.column_config.NumberColumn("P/L", format="$%,.2f")
            }
        )
    else:
        st.dataframe(df_filtered)

    # --- 🔬 TRADE ANALYSIS SECTION ---
    st.markdown("---")
    st.header("🔬 Análisis Detallado de Operaciones")
    
    if not df_filtered.empty:
        # Create a selection list
        df_analysis = df_filtered.sort_values('entry_date', ascending=False)
        trade_options = []
        trade_map = {}
        
        for idx, row in df_analysis.iterrows():
            sym = row['symbol']
            date = row['entry_date'].strftime('%Y-%m-%d')
            pnl = row['Result'] if 'Result' in row else 0
            label = f"{date} | {sym} | PnL: ${pnl:,.2f}"
            trade_options.append(label)
            trade_map[label] = row
            
        selected_trade_label = st.selectbox("Selecciona una operación para analizar:", trade_options)
        
        if selected_trade_label:
            trade_data = trade_map[selected_trade_label]
            
            # Init Dashboard Logic (Lazy load)
            if 'dashboard_engine' not in st.session_state:
                 # Ensure results file exists or use df directly if we could modify dashboard.py, 
                 # but for now we rely on the CSV being there from the run
                 if os.path.exists('backtest_results.csv'):
                     st.session_state['dashboard_engine'] = InteractiveDashboard('backtest_results.csv')
                 else:
                     st.warning("⚠️ No se encontró backtest_results.csv")
            
            if 'dashboard_engine' in st.session_state:
                db = st.session_state['dashboard_engine']
                
                # Prepare signal data for chart
                signal_data = {
                    'camino': trade_data.get('signal_type', 'N/A'),
                    'entry_price': trade_data['entry_price'],
                    'stop_loss': trade_data.get('entry_price', 0) * 0.95, # Fallback if not saved
                    'exit_price': trade_data['exit_price'],
                    'outcome': 'WIN' if trade_data.get('is_profitable') else 'LOSS',
                    'return_pct': trade_data['returns_pct'],
                    'hold_days': (trade_data['exit_date'] - trade_data['entry_date']).days
                }
                
                # Generate Chart
                try:
                    with st.spinner(f"Generando gráfico para {trade_data['symbol']}..."):
                        fig = db.create_trade_chart(
                            trade_data['symbol'], 
                            trade_data['entry_date'].strftime('%Y-%m-%d'), 
                            signal_data
                        )
                        st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Error generando gráfico: {e}")
                
                # Trade Story/Log
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.subheader("📊 Métricas Clave")
                    st.markdown(f"""
                    - **Entrada:** ${trade_data['entry_price']:.2f}
                    - **Salida:** ${trade_data['exit_price']:.2f}
                    - **Retorno:** {trade_data['returns_pct']:+.2f}%
                    - **Días en Posición:** {(trade_data['exit_date'] - trade_data['entry_date']).days} días
                    """)
                
                with c2:
                    st.subheader("📝 Lógica de Ejecución")
                    reason = trade_data.get('signal_reason', 'N/A')
                    # Parse reason for better display if it has pipes
                    if "|" in str(reason):
                        parts = str(reason).split("|")
                        main_reason = parts[0].strip()
                        events = parts[1].strip() if len(parts) > 1 else ""
                        
                        st.info(f"**Señal:** {main_reason}")
                        if events:
                            st.write("**Eventos:**")
                            for evt in events.split('+'):
                                st.code(evt.strip())
                    else:
                        st.info(str(reason))

else:
    st.info("👋 Bienvenido. Configura los parámetros de riesgo a la izquierda y pulsa 'EJECUTAR BACKTEST'.")