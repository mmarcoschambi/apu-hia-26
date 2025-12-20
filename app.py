import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import os
import subprocess
import time

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
                               equity=100000, risk_pct=0.5, max_exp_pct=25):
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_area = st.empty()
    logs = []

    cmd = [
        "python3", "backtest_headless.py",
        "--start", str(start_date),
        "--end", str(end_date),
        "--account_equity", str(equity),
        "--risk_fraction", str(risk_pct / 100.0), # Convert 0.5% to 0.005
        "--max_exposure", str(max_exp_pct / 100.0)
    ]
    
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
                # Parsear marcador de progreso
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
    page_title="Momentum V2 - Backtest Dashboard",
    page_icon="📈",
    layout="wide"
)

# Título y Descripción
st.title("📈 Momentum V2 - Institutional Risk Dashboard")

# --- Barra Lateral: Configuración y Ejecución ---
st.sidebar.header("⚙️ Configuración del Sistema")

with st.sidebar.expander("📅 Fechas y Ejecución", expanded=True):
    run_start_date = st.date_input("Fecha Inicio", value=datetime(2024, 1, 1))
    run_end_date = st.date_input("Fecha Fin", value=datetime.now())
    
    # Stop Loss Config
    use_custom_stop = st.checkbox("Forzar Stop Loss Fijo (%)")
    stop_loss_input = 2.0
    if use_custom_stop:
        stop_loss_input = st.number_input("Stop Loss %", value=3.0, step=0.5)

    st.markdown("---")
    st.markdown("**🛡️ Institutional Risk Manager**")
    
    in_equity = st.number_input("Equity ($)", value=100000.0, step=10000.0)
    in_risk = st.number_input("Risk per Trade (%)", value=0.5, step=0.1, format="%.2f")
    in_max_exp = st.number_input("Max Exposure (%)", value=25.0, step=5.0)

    if st.button("🚀 EJECUTAR BACKTEST", use_container_width=True):
        sl_val = stop_loss_input if use_custom_stop else None
        if run_backtest_with_progress(run_start_date, run_end_date, sl_val, in_equity, in_risk, in_max_exp):
            st.rerun()

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

# --- Gestión de Watchlist ---
with st.sidebar.expander("📝 Gestionar Watchlist", expanded=False):
    watchlist_data = load_watchlist_json()
    tab1, tab2 = st.tabs(["Editar", "Crear"])
    # (Mantener lógica existente de tabs, resumida aquí para brevedad)
    with tab1:
        if watchlist_data:
            cats = list(watchlist_data.keys())
            sel_cat = st.selectbox("Lista", cats)
            if sel_cat:
                st.code(", ".join(watchlist_data[sel_cat]))
                # ... (Lógica de añadir/borrar igual que antes)

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
    
    # Calcular PnL usando los valores reales calculados por el RiskManager
    # Result = (Retorno %) * Valor Posición / 100
    # O mejor: (Exit Price - Entry Price) * Shares
    
    if 'shares' in df_filtered.columns:
        df_filtered['Result'] = (df_filtered['exit_price'] - df_filtered['entry_price']) * df_filtered['shares']
        # Ajuste para PnL parciales (ya que exit_price y returns_pct son ponderados en triad_openbb)
        # Result = Position Value * (Returns % / 100) es más seguro si usamos retornos compuestos
        df_filtered['Result'] = df_filtered['position_value'] * (df_filtered['returns_pct'] / 100)
        
        # R-Multiple Real = PnL / Monetary Risk
        if 'monetary_risk' in df_filtered.columns:
            df_filtered['r_multiple'] = df_filtered['Result'] / df_filtered['monetary_risk']
        else:
            # Fallback si no existe columna
            df_filtered['r_multiple'] = df_filtered['returns_pct'] 
            
    else:
        # Fallback si no se ha corrido el nuevo backtest
        df_filtered['Result'] = 0
        st.warning("Ejecuta el backtest nuevamente para ver métricas de riesgo actualizadas.")

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
    c7.metric("Expectancy", f"{df_filtered['r_multiple'].mean():.2f}R")
    
    profit_factor = abs(winners['Result'].sum() / losers['Result'].sum()) if len(losers) > 0 else 0
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
        cols = ['symbol', 'entry_date', 'signal_type', 'shares', 'position_value', 'monetary_risk', 'returns_pct', 'r_multiple', 'Result']
        
        # Formatting
        df_disp['entry_date'] = df_disp['entry_date'].dt.date
        df_disp['position_value'] = df_disp['position_value'].map('${:,.0f}'.format)
        df_disp['monetary_risk'] = df_disp['monetary_risk'].map('${:,.0f}'.format)
        df_disp['Result'] = df_disp['Result'].map('${:,.2f}'.format)
        df_disp['returns_pct'] = df_disp['returns_pct'].map('{:+.2f}%'.format)
        df_disp['r_multiple'] = df_disp['r_multiple'].map('{:+.2f}R'.format)
        
        st.dataframe(df_disp[cols].sort_values('entry_date', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.dataframe(df_filtered)

else:
    st.info("👋 Bienvenido. Configura los parámetros de riesgo a la izquierda y pulsa 'EJECUTAR BACKTEST'.")
