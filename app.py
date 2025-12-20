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

# Función para ejecutar el backtest con UI de progreso
def run_backtest_with_progress(start_date, end_date, stop_loss_pct=None):
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_area = st.empty()
    logs = []

    cmd = [
        "python3", "backtest_headless.py",
        "--start", str(start_date),
        "--end", str(end_date)
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
                    # Mostrar solo las últimas 5 líneas para no saturar
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
st.title("📈 Momentum V2 - Análisis de Backtest")

# --- Gestión de Watchlist y Ejecución (Barra Lateral Superior) ---
st.sidebar.header("⚙️ Configuración y Ejecución")

# Inputs de fecha para el runner
run_start_date = st.sidebar.date_input("Fecha Inicio Backtest", value=datetime(2024, 1, 1))
run_end_date = st.sidebar.date_input("Fecha Fin Backtest", value=datetime.now())

# Stop Loss Config
use_custom_stop = st.sidebar.checkbox("Definir Stop Loss Fijo (%)")
stop_loss_input = 2.0
if use_custom_stop:
    stop_loss_input = st.sidebar.number_input("Stop Loss %", value=3.0, step=0.5, help="Define la distancia inicial del Stop Loss.")

if st.sidebar.button("🚀 EJECUTAR BACKTEST", use_container_width=True, help="Ejecuta backtest_headless.py"):
    sl_val = stop_loss_input if use_custom_stop else None
    if run_backtest_with_progress(run_start_date, run_end_date, stop_loss_pct=sl_val):
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

# --- Gestión de Watchlist (Sidebar) ---
with st.sidebar.expander("📝 Gestionar Watchlist", expanded=False):
    watchlist_data = load_watchlist_json()
    
    tab1, tab2 = st.tabs(["Editar/Ver", "Crear Nueva"])
    
    # --- TAB 1: EDITAR EXISTENTE ---
    with tab1:
        if watchlist_data:
            categories = list(watchlist_data.keys())
            selected_category = st.selectbox("Seleccionar Lista", categories)

            if selected_category:
                current_symbols = watchlist_data[selected_category]
                st.write(f"**{len(current_symbols)} símbolos**")
                st.code(", ".join(current_symbols))

                # Bulk Add a lista existente
                new_symbols_str = st.text_area("Añadir (separados por coma)", placeholder="AAPL, TSLA, NVDA")
                if st.button("Añadir a Lista"):
                    if new_symbols_str:
                        new_list = [s.strip().upper() for s in new_symbols_str.split(',') if s.strip()]
                        # Evitar duplicados
                        added_count = 0
                        for s in new_list:
                            if s not in watchlist_data[selected_category]:
                                watchlist_data[selected_category].append(s)
                                added_count += 1
                        
                        if added_count > 0:
                            save_watchlist_json(watchlist_data)
                            st.success(f"✅ {added_count} símbolos añadidos.")
                            st.rerun()
                        else:
                            st.warning("Todos los símbolos ya estaban en la lista.")

                st.markdown("---")
                # Eliminar Símbolo Individual
                symbol_to_remove = st.selectbox("Borrar Símbolo", ["Seleccionar..."] + sorted(current_symbols))
                if st.button("Borrar Símbolo"):
                    if symbol_to_remove != "Seleccionar...":
                        watchlist_data[selected_category].remove(symbol_to_remove)
                        save_watchlist_json(watchlist_data)
                        st.rerun()
                
                # Borrar Lista Completa
                if st.button("🗑️ Borrar Lista Completa", type="primary"):
                    del watchlist_data[selected_category]
                    save_watchlist_json(watchlist_data)
                    st.success(f"Lista '{selected_category}' eliminada.")
                    st.rerun()
        else:
            st.info("No hay listas creadas.")

    # --- TAB 2: CREAR NUEVA ---
    with tab2:
        st.write("Crear una nueva lista personalizada")
        new_list_name = st.text_input("Nombre de la Lista", placeholder="Ej. MIS_FAVORITOS").upper().strip()
        bulk_symbols = st.text_area("Pegar Símbolos (separados por coma)", placeholder="BE, CRDO, AVGO, RDDT, ...", height=150)
        
        if st.button("💾 Guardar Nueva Lista"):
            if new_list_name and bulk_symbols:
                if new_list_name in watchlist_data:
                    st.error("Ya existe una lista con ese nombre.")
                else:
                    # Parsear símbolos
                    cleaned_symbols = [s.strip().upper() for s in bulk_symbols.split(',') if s.strip()]
                    # Eliminar duplicados en la entrada
                    cleaned_symbols = list(set(cleaned_symbols))
                    
                    if cleaned_symbols:
                        watchlist_data[new_list_name] = cleaned_symbols
                        save_watchlist_json(watchlist_data)
                        st.success(f"✅ Lista '{new_list_name}' creada con {len(cleaned_symbols)} símbolos.")
                        st.rerun()
                    else:
                        st.error("La lista de símbolos parece vacía.")
            else:
                st.warning("Por favor ingresa un nombre y al menos un símbolo.")

st.sidebar.markdown("---")

# --- Formulario de Filtros y Simulación ---
with st.sidebar.form("filtros_form"):
    st.header("🔍 Filtros de Visualización")
    
    # Valores por defecto para los filtros
    if not df_raw.empty:
        symbols_list = ['Todos'] + sorted(df_raw['symbol'].unique().tolist())
        min_date_val = df_raw['entry_date'].min().date()
        max_date_val = df_raw['exit_date'].max().date()
        signal_types = ['Todos'] + sorted(df_raw['signal_type'].unique().tolist())
    else:
        symbols_list = ['Todos']
        min_date_val = datetime.now().date()
        max_date_val = datetime.now().date()
        signal_types = ['Todos']

    f_symbol = st.selectbox("Símbolo", symbols_list)
    f_signal = st.selectbox("Tipo de Señal", signal_types)
    f_dates = st.date_input("Rango de Fechas (Visualización)", value=(min_date_val, max_date_val))
    
    st.markdown("---")
    st.header("💰 Simulación (Post-Trade)")
    f_capital = st.number_input("Capital Inicial ($)", value=10000.0, step=1000.0)
    f_pos_size = st.number_input("Tamaño Posición ($)", value=1000.0, step=100.0)
    
    # Explicación clara de que este valor es solo para calcular R
    st.markdown("**Métricas R-Multiples**")
    f_risk = st.number_input("Riesgo Estimado (%)", value=2.0, step=0.1, help="Usado solo para calcular cuántas 'R' ganaste. No afecta el backtest real.")
    
    submitted = st.form_submit_button("APLICAR CAMBIOS", use_container_width=True)

# Lógica de Filtrado (solo se activa al cargar o al pulsar el botón del form)
if not df_raw.empty:
    df_filtered = df_raw.copy()
    
    if f_symbol != 'Todos':
        df_filtered = df_filtered[df_filtered['symbol'] == f_symbol]
    if f_signal != 'Todos':
        df_filtered = df_filtered[df_filtered['signal_type'] == f_signal]
    if len(f_dates) == 2:
        df_filtered = df_filtered[
            (df_filtered['entry_date'].dt.date >= f_dates[0]) &
            (df_filtered['exit_date'].dt.date <= f_dates[1])
        ]

    # --- Cálculos ---
    df_filtered = df_filtered.sort_values('exit_date')
    df_filtered['Qty'] = f_pos_size / df_filtered['entry_price']
    df_filtered['Result'] = (df_filtered['returns_pct'] / 100) * f_pos_size
    df_filtered['r_multiple'] = df_filtered['returns_pct'] / (f_risk if f_risk > 0 else 1.0)
    df_filtered['Running_Capital'] = f_capital + df_filtered['Result'].cumsum()

    # Métricas
    total_trades = len(df_filtered)
    winners = df_filtered[df_filtered['Result'] > 0]
    losers = df_filtered[df_filtered['Result'] <= 0]
    num_winners, num_losers = len(winners), len(losers)
    win_rate = (num_winners / total_trades * 100) if total_trades > 0 else 0.0
    closed_pnl = df_filtered['Result'].sum()
    final_cap = f_capital + closed_pnl
    
    # --- UI Principal ---
    st.markdown("### Resumen de Rendimiento")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Perf. General (%)", f"{(closed_pnl/f_capital)*100:,.2f}%")
    c2.metric("Capital Final", f"${final_cap:,.2f}")
    c3.metric("Win Rate", f"{win_rate:.1f}%")
    c4.metric("PnL Cerrado", f"${closed_pnl:,.2f}")

    # Cards Adicionales
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Total Trades", total_trades)
    c6.metric("Total R", f"{df_filtered['r_multiple'].sum():.2f}R")
    c7.metric("Profit Factor", f"{(winners['Result'].sum()/abs(losers['Result'].sum())) if num_losers > 0 else 0:.2f}")
    c8.metric("Expectancy (R)", f"{df_filtered['r_multiple'].mean() if total_trades > 0 else 0:.2f}R")

    st.markdown("---")

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        fig_equity = px.line(df_filtered, x='exit_date', y='Running_Capital', title='Curva de Capital ($)')
        st.plotly_chart(fig_equity, use_container_width=True)
    with col_chart2:
        fig_hist = px.histogram(df_filtered, x='Result', title='Distribución PnL ($)')
        st.plotly_chart(fig_hist, use_container_width=True)

    st.markdown("### Detalle de Operaciones")
    df_display = df_filtered.copy()
    df_display['Type'] = 'Long'
    df_display['Qty'] = df_display['Qty'].map('{:.2f}'.format)
    df_display['Entry Price'] = df_display['entry_price'].map('${:.2f}'.format)
    df_display['Exit Price'] = df_display['exit_price'].map('${:.2f}'.format)
    df_display['Result'] = df_display['Result'].map('${:.2f}'.format)
    df_display['Entry Date'] = df_display['entry_date'].dt.strftime('%Y-%m-%d')
    df_display['Exit Date'] = df_display['exit_date'].dt.strftime('%Y-%m-%d')
    
    st.dataframe(
        df_display[['symbol', 'Type', 'Qty', 'Entry Date', 'Entry Price', 'Exit Date', 'Exit Price', 'signal_type', 'Result']].sort_values('Exit Date', ascending=False),
        use_container_width=True, hide_index=True
    )
else:
    st.info("No hay datos. Haz clic en 'EJECUTAR BACKTEST' para generar resultados.")