import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import os
import subprocess
import time
from config.universe_presets import LIQUID_MID_CAPS

# Función para cargar/guardar watchlist
WATCHLIST_FILE = 'config/watchlist.json'
# ... (rest of the file until the Watchlist Manager section)
    # --- TAB 2: CREAR NUEVA ---
    with tab2:
        st.write("Crear una nueva lista personalizada")
        
        # Opciones de carga rápida
        if st.button("📥 Cargar Universo Mid-Cap (Automático)", help="Carga ~100 acciones líquidas Mid-Cap ($2B-$20B) filtradas."):
             st.session_state['new_list_name_input'] = "INSTITUTIONAL_MIDCAPS"
             st.session_state['bulk_symbols_input'] = ", ".join(LIQUID_MID_CAPS)
             st.success("Universo cargado en el formulario. Revisa y guarda.")

        # Inputs con session state para permitir llenado automático
        default_name = st.session_state.get('new_list_name_input', "")
        default_symbols = st.session_state.get('bulk_symbols_input', "")

        new_list_name = st.text_input("Nombre de la Lista", value=default_name, placeholder="Ej. MIS_FAVORITOS").upper().strip()
        bulk_symbols = st.text_area("Pegar Símbolos", value=default_symbols, placeholder="BE, CRDO, AVGO, ...", height=150)
        
        if st.button("💾 Guardar Nueva Lista"):
            if new_list_name and bulk_symbols:
                cleaned = [s.strip().upper() for s in bulk_symbols.split(',') if s.strip()]
                # Eliminar duplicados
                cleaned = list(set(cleaned))
                if cleaned:
                    watchlist_data[new_list_name] = cleaned
                    save_watchlist_json(watchlist_data)
                    st.success(f"✅ Lista '{new_list_name}' creada con {len(cleaned)} símbolos.")
                    # Limpiar session state
                    if 'new_list_name_input' in st.session_state: del st.session_state['new_list_name_input']
                    if 'bulk_symbols_input' in st.session_state: del st.session_state['bulk_symbols_input']
                    st.rerun()
            else:
                st.warning("El nombre o la lista no pueden estar vacíos.")

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
        # Ajuste para PnL parciales (usando return_pct que ya pondera salidas)
        # Result = Position Value * (Returns % / 100)
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
        cols = ['symbol', 'entry_date', 'signal_type', 'shares', 'position_value', 'monetary_risk', 'returns_pct', 'r_multiple', 'Result']
        
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