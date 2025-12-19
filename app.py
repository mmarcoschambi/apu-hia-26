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
st.markdown("""
Esta herramienta simula el rendimiento de la estrategia. 
**Cómo funciona el cálculo:**
1. Defines un **Capital Inicial**.
2. Defines un **Tamaño de Posición** fijo (cuánto dinero inviertes por operación).
3. El sistema calcula cuántas acciones (`Qty`) compras con ese dinero.
4. El **Resultado** es la ganancia o pérdida en dólares basada en el movimiento del precio.
""")

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
    # Ordenar por fecha de salida para simular evolución del capital
    df_filtered = df_filtered.sort_values('exit_date')

    # 1. Calcular Cantidad (Qty) y Resultado ($)
    # Qty = Tamaño Posición / Precio Entrada
    df_filtered['Qty'] = df_filtered.apply(lambda row: position_size / row['entry_price'], axis=1)
    
    # Resultado ($) = (Precio Salida - Precio Entrada) * Qty
    # Nota: Usamos returns_pct para mayor precisión si existe discrepancia en precios brutos, 
    # pero para consistencia con la tabla, calculamos directo:
    df_filtered['Result'] = (df_filtered['returns_pct'] / 100) * position_size
    
    # 2. Calcular R-Multiples
    risk_denom = assumed_risk_pct if assumed_risk_pct > 0 else 1.0
    df_filtered['r_multiple'] = df_filtered['returns_pct'] / risk_denom

    # 3. Evolución de Capital
    # Capital Acumulado = Capital Inicial + Suma Acumulativa de Resultados
    df_filtered['Running_Capital'] = initial_capital + df_filtered['Result'].cumsum()

    # Métricas Agregadas
    total_trades = len(df_filtered)
    winners = df_filtered[df_filtered['Result'] > 0]
    losers = df_filtered[df_filtered['Result'] <= 0]
    
    num_winners = len(winners)
    num_losers = len(losers)
    
    win_rate = (num_winners / total_trades * 100) if total_trades > 0 else 0.0
    
    closed_trades_pnl = df_filtered['Result'].sum()
    final_capital = initial_capital + closed_trades_pnl
    
    open_trades_pnl = 0.0 
    
    avg_win_dollar = winners['Result'].mean() if num_winners > 0 else 0
    avg_loss_dollar = abs(losers['Result'].mean()) if num_losers > 0 else 0
    
    risk_reward_ratio = (avg_win_dollar / avg_loss_dollar) if avg_loss_dollar > 0 else 0
    total_r = df_filtered['r_multiple'].sum()
    gross_profit = winners['Result'].sum()
    gross_loss = abs(losers['Result'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    expectancy_r = df_filtered['r_multiple'].mean() if total_trades > 0 else 0
    general_performance_pct = (closed_trades_pnl / initial_capital) * 100

    # --- Visualización de Cards ---
    st.markdown("### Resumen de Rendimiento")
    
    # Fila 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("General Performance (%)", f"{general_performance_pct:,.2f}%")
    c2.metric("Available Capital", f"${final_capital:,.2f}")
    c3.metric("Open Trades PnL", f"${open_trades_pnl:,.2f}")
    c4.metric("Closed Trades PnL", f"${closed_trades_pnl:,.2f}", delta_color="normal")
    
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

    with col_chart1:
        st.subheader("Curva de Capital (Equity Curve)")
        fig_equity = px.line(
            df_filtered, 
            x='exit_date', 
            y='Running_Capital',
            title=f'Crecimiento del Capital (Inicio: ${initial_capital:,.0f})',
            labels={'Running_Capital': 'Capital ($)', 'exit_date': 'Fecha de Cierre'}
        )
        st.plotly_chart(fig_equity, use_container_width=True)

    with col_chart2:
        st.subheader("Distribución de PnL ($)")
        fig_hist = px.histogram(
            df_filtered, 
            x='Result',
            nbins=30,
            title='Distribución de Ganancias/Pérdidas en Dólares',
            labels={'Result': 'PnL ($)'},
            color_discrete_sequence=['#636EFA']
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    # --- Tabla de Datos (Formato Solicitado) ---
    st.markdown("### Detalle de Operaciones")
    
    # Preparar tabla para visualización exacta
    # Ticker | Type | Qty | Entry Date | Entry Price | Exit Date | Exit Price | signal-type | Result
    df_display = df_filtered.copy()
    df_display['Ticker'] = df_display['symbol']
    df_display['Type'] = 'Long' # Asumimos Long-only por ahora
    # Formatear columnas
    df_display['Qty'] = df_display['Qty'].apply(lambda x: f"{x:.4f}")
    df_display['Entry Price'] = df_display['entry_price'].apply(lambda x: f"${x:.2f}")
    df_display['Exit Price'] = df_display['exit_price'].apply(lambda x: f"${x:.2f}")
    df_display['Result'] = df_display['Result'].apply(lambda x: f"${x:.2f}")
    
    # Formatear Fechas para que se vean limpias
    df_display['Entry Date'] = df_display['entry_date'].dt.strftime('%Y-%m-%d')
    df_display['Exit Date'] = df_display['exit_date'].dt.strftime('%Y-%m-%d')

    # Seleccionar y reordenar columnas
    cols_to_show = [
        'Ticker', 'Type', 'Qty', 'Entry Date', 'Entry Price', 
        'Exit Date', 'Exit Price', 'signal_type', 'Result'
    ]
    
    # Usar st.dataframe con estilo para el color del resultado si es posible, 
    # o simplemente mostrar la tabla limpia.
    st.dataframe(
        df_display[cols_to_show].sort_values('Exit Date', ascending=False),
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("No hay datos para mostrar. Asegúrate de que el archivo backtest_results.csv existe y contiene datos.")
