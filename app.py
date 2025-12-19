import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import os

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

# Configuración de la página
st.set_page_config(
    page_title="Momentum V2 - Backtest Dashboard",
    page_icon="📈",
    layout="wide"
)

# Título y Descripción
st.title("📈 Momentum V2 - Análisis de Backtest")
st.markdown("Dashboard interactivo para analizar los resultados de las estrategias de Momentum V2.")

# Carga de datos
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('backtest_results.csv')
        # Convertir columnas de fecha
        df['entry_date'] = pd.to_datetime(df['entry_date'])
        df['exit_date'] = pd.to_datetime(df['exit_date'])
        return df
    except FileNotFoundError:
        st.error("No se encontró el archivo 'backtest_results.csv'. Por favor, ejecuta el backtest primero.")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- Sidebar Filtros ---
    st.sidebar.header("Filtros")
    
    # Filtro de Símbolo
    symbols = ['Todos'] + sorted(df['symbol'].unique().tolist())
    selected_symbol = st.sidebar.selectbox("Símbolo", symbols)
    
    # Filtro de Tipo de Señal
    if 'signal_type' in df.columns:
        signal_types = ['Todos'] + sorted(df['signal_type'].unique().tolist())
        selected_signal = st.sidebar.selectbox("Tipo de Señal", signal_types)
    else:
        selected_signal = 'Todos'

    # Filtro de Fechas
    min_date = df['entry_date'].min()
    max_date = df['exit_date'].max()
    date_range = st.sidebar.date_input(
        "Rango de Fechas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # Aplicar Filtros
    df_filtered = df.copy()
    
    if selected_symbol != 'Todos':
        df_filtered = df_filtered[df_filtered['symbol'] == selected_symbol]
        
    if selected_signal != 'Todos':
        df_filtered = df_filtered[df_filtered['signal_type'] == selected_signal]
        
    if len(date_range) == 2:
        df_filtered = df_filtered[
            (df_filtered['entry_date'].dt.date >= date_range[0]) &
            (df_filtered['exit_date'].dt.date <= date_range[1])
        ]

    # --- Gestión de Watchlist (Sidebar) ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("Gestión de Watchlist")

    watchlist_data = load_watchlist_json()
    categories = list(watchlist_data.keys())

    # Selector de Categoría para editar
    selected_category = st.sidebar.selectbox("Categoría Watchlist", categories)

    if selected_category:
        current_symbols = watchlist_data[selected_category]
        with st.sidebar.expander(f"Ver símbolos de {selected_category}"):
            st.code(", ".join(current_symbols))

        # Añadir Símbolo
        new_symbol = st.sidebar.text_input("Añadir Símbolo (e.g. AMD)").upper()
        if st.sidebar.button("Añadir"):
            if new_symbol and new_symbol not in current_symbols:
                watchlist_data[selected_category].append(new_symbol)
                save_watchlist_json(watchlist_data)
                st.sidebar.success(f"{new_symbol} añadido!")
                st.rerun()
            elif new_symbol in current_symbols:
                st.sidebar.warning("El símbolo ya existe.")

        # Eliminar Símbolo
        symbol_to_remove = st.sidebar.selectbox("Eliminar Símbolo", ["Seleccionar..."] + sorted(current_symbols))
        if st.sidebar.button("Eliminar"):
            if symbol_to_remove != "Seleccionar...":
                watchlist_data[selected_category].remove(symbol_to_remove)
                save_watchlist_json(watchlist_data)
                st.sidebar.success(f"{symbol_to_remove} eliminado!")
                st.rerun()

    # --- Parámetros de Simulación (Sidebar) ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("Simulación de Portafolio")
    initial_capital = st.sidebar.number_input("Capital Inicial ($)", value=10000.0, step=1000.0)
    position_size = st.sidebar.number_input("Tamaño Posición ($)", value=1000.0, step=100.0)
    assumed_risk_pct = st.sidebar.number_input("Riesgo Estimado por Trade (%)", value=2.0, step=0.1, help="Usado para calcular métricas R. Ejemplo: Si tu stop loss promedio es 2%, pon 2.")

    # --- Cálculos Avanzados ---
    # Calcular PnL en $
    df_filtered['pnl_dollar'] = (df_filtered['returns_pct'] / 100) * position_size
    
    # Calcular R-Multiples (aproximación basada en riesgo estimado)
    # R = Retorno % / Riesgo %
    # Si riesgo_estimado es 0, evitar división por cero
    risk_denom = assumed_risk_pct if assumed_risk_pct > 0 else 1.0
    df_filtered['r_multiple'] = df_filtered['returns_pct'] / risk_denom

    # Métricas Agregadas
    total_trades = len(df_filtered)
    winners = df_filtered[df_filtered['pnl_dollar'] > 0]
    losers = df_filtered[df_filtered['pnl_dollar'] <= 0]
    
    num_winners = len(winners)
    num_losers = len(losers)
    
    win_rate = (num_winners / total_trades * 100) if total_trades > 0 else 0.0
    
    closed_trades_pnl = df_filtered['pnl_dollar'].sum()
    
    # Capital Disponible (Teórico)
    # Asumimos que todas las operaciones son secuenciales o acumulativas al capital
    # Para simplificar: Capital Actual = Capital Inicial + PnL Total
    available_capital = initial_capital + closed_trades_pnl
    
    # Open Trades PnL - (Placeholder o lógica futura)
    # Sin datos en tiempo real, lo dejamos en 0 o requeriría conectar con API
    open_trades_pnl = 0.0 
    
    # Métricas Avanzadas
    avg_win_dollar = winners['pnl_dollar'].mean() if num_winners > 0 else 0
    avg_loss_dollar = abs(losers['pnl_dollar'].mean()) if num_losers > 0 else 0
    
    risk_reward_ratio = (avg_win_dollar / avg_loss_dollar) if avg_loss_dollar > 0 else 0
    
    total_r = df_filtered['r_multiple'].sum()
    
    gross_profit = winners['pnl_dollar'].sum()
    gross_loss = abs(losers['pnl_dollar'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    
    # Expectancy (R) = (Win Rate * Avg Win R) - (Loss Rate * Avg Loss R)
    # O simplemente Average R per trade
    expectancy_r = df_filtered['r_multiple'].mean() if total_trades > 0 else 0
    
    # General Performance %
    general_performance_pct = (closed_trades_pnl / initial_capital) * 100

    # --- Visualización de Cards ---
    st.markdown("### Resumen de Rendimiento")
    
    # Fila 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("General Performance (%)", f"{general_performance_pct:,.2f}%")
    c2.metric("Available Capital", f"${available_capital:,.2f}")
    c3.metric("Open Trades PnL", f"${open_trades_pnl:,.2f}", help="Requiere datos en tiempo real")
    c4.metric("Closed Trades PnL", f"${closed_trades_pnl:,.2f}")
    
    # Fila 2
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Win Rate (%)", f"{win_rate:.1f}%")
    c6.metric("Total Trades", f"{total_trades}")
    c7.metric("Winners", f"{num_winners}")
    c8.metric("Losers", f"{num_losers}")
    
    # Fila 3
    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Risk/Reward Ratio", f"{risk_reward_ratio:.2f}")
    c10.metric("Total R", f"{total_r:.2f}R")
    c11.metric("Profit Factor", f"{profit_factor:.2f}")
    c12.metric("Expectancy (R)", f"{expectancy_r:.2f}R")

    st.markdown("---")

    # --- Gráficos ---
    
    col_chart1, col_chart2 = st.columns(2)

    # 1. Curva de Equidad (Equity Curve)
    with col_chart1:
        st.subheader("Curva de Rendimiento Acumulado")
        df_filtered = df_filtered.sort_values('exit_date')
        df_filtered['cumulative_return'] = df_filtered['returns_pct'].cumsum()
        
        fig_equity = px.line(
            df_filtered, 
            x='exit_date', 
            y='cumulative_return',
            title='Crecimiento del Portafolio (%)',
            labels={'cumulative_return': 'Retorno Acumulado (%)', 'exit_date': 'Fecha de Salida'}
        )
        st.plotly_chart(fig_equity, use_container_width=True)

    # 2. Distribución de Retornos
    with col_chart2:
        st.subheader("Distribución de Retornos")
        fig_hist = px.histogram(
            df_filtered, 
            x='returns_pct',
            nbins=30,
            title='Distribución de Ganancias/Pérdidas',
            labels={'returns_pct': 'Retorno (%)'},
            color_discrete_sequence=['#636EFA']
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    # 3. Retornos por Símbolo (si hay múltiples)
    if selected_symbol == 'Todos':
        st.subheader("Rendimiento por Símbolo")
        symbol_performance = df_filtered.groupby('symbol')['returns_pct'].sum().sort_values(ascending=False).reset_index()
        fig_bar = px.bar(
            symbol_performance,
            x='symbol',
            y='returns_pct',
            title='Retorno Total por Símbolo',
            labels={'returns_pct': 'Retorno Total (%)', 'symbol': 'Símbolo'},
            color='returns_pct',
            color_continuous_scale='RdYlGn'
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- Tabla de Datos ---
    st.markdown("### Detalle de Operaciones")
    st.dataframe(
        df_filtered[['entry_date', 'symbol', 'entry_price', 'exit_date', 'exit_price', 'returns_pct', 'signal_type', 'is_profitable']].sort_values('entry_date', ascending=False),
        use_container_width=True
    )

else:
    st.info("No hay datos para mostrar. Asegúrate de que el archivo backtest_results.csv existe y contiene datos.")