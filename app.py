import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

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

    # --- KPIs Principales ---
    st.markdown("### Métricas Clave")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_trades = len(df_filtered)
    win_rate = (df_filtered['is_profitable'].sum() / total_trades * 100) if total_trades > 0 else 0
    avg_return = df_filtered['returns_pct'].mean()
    total_return = df_filtered['returns_pct'].sum()
    
    col1.metric("Total Operaciones", total_trades)
    col2.metric("Win Rate", f"{win_rate:.2f}%")
    col3.metric("Retorno Promedio", f"{avg_return:.2f}%")
    col4.metric("Retorno Total Acumulado", f"{total_return:.2f}%")

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
