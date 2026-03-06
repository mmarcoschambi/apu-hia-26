import numpy as np
from numba import njit, float64, int64, boolean, types


@njit(cache=True, fastmath=True)
def simulate_fast_core(
    close_arr,
    high_arr,
    low_arr,
    open_arr,
    volume_arr,
    entries_arr,
    atr_arr,
    sma20_arr,
    ema10_arr,
    ema8_arr,
    ema21_arr,
    adr_arr,
    rvol_arr,
    entry_score_arr,
    spy_close_arr,
    spy_sma50_arr,
    initial_capital,
    tp1_r,
    tp2_r,
    tp1_pct,
    tp2_pct,
    runner_pct,
    risk_pct_per_trade,
    max_exposure_pct,
    be_threshold_r,
    use_trailing_stop,
    max_stop_pct,
    risk_dollars,
    use_fixed_dollar_risk,
    use_atr_stop,
    atr_stop_multiplier,
    atr_trailing_multiplier,
):
    """
    Núcleo de simulación de alta velocidad compilado con Numba.
    MEMORY OPTIMIZED: Uses float32 arrays (50% memory reduction vs float64).

    ATR-BASED STOP SYSTEM:
    - Entry Stop: ATR × multiplier (1.5-2.0 depending on ADR)
    - Post-TP1 Trailing: entry + ATR × 0.5 (profit lock, not breakeven)
    - Runner Trailing: highest_close - ATR × trailing_multiplier

    Args:
        Arrays de Numpy (n_dias, n_tickers) con precios e indicadores.
        use_atr_stop: If True, use ATR-based stops; if False, use fixed %
        atr_stop_multiplier: ATR multiplier for initial stop (1.5-2.0)
        atr_trailing_multiplier: ATR multiplier for trailing (2.0-3.0)

    Returns:
        equity_curve: Array (n_dias,) con el valor total del portafolio.
        trades_log: Array estructurado simplificado para reconstruir historial.
    """
    n_days, n_tickers = close_arr.shape

    # --- ESTADO DEL PORTAFOLIO ---
    cash = float(initial_capital)
    equity_curve = np.zeros(n_days, dtype=np.float64)

    # --- ESTADO DE POSICIONES (Por Ticker) - MEMORY OPTIMIZED: float32 ---
    pos_active = np.zeros(n_tickers, dtype=np.bool_)

    pos_shares = np.zeros(n_tickers, dtype=np.float32)
    pos_original_shares = np.zeros(n_tickers, dtype=np.float32)
    pos_entry_price = np.zeros(n_tickers, dtype=np.float32)
    pos_stop_price = np.zeros(n_tickers, dtype=np.float32)
    pos_tp1_price = np.zeros(n_tickers, dtype=np.float32)
    pos_tp2_price = np.zeros(n_tickers, dtype=np.float32)
    pos_stop_dist = np.zeros(n_tickers, dtype=np.float32)
    pos_entry_day = np.zeros(n_tickers, dtype=np.float64)
    pos_initial_risk = np.zeros(n_tickers, dtype=np.float32)

    # ATR-based stop tracking
    pos_entry_atr = np.zeros(n_tickers, dtype=np.float32)  # ATR at entry
    pos_highest_close = np.zeros(n_tickers, dtype=np.float32)  # For trailing

    # Contexto de Entrada (Snapshots)
    pos_rvol = np.zeros(n_tickers, dtype=np.float32)
    pos_adr = np.zeros(n_tickers, dtype=np.float32)
    pos_vol = np.zeros(n_tickers, dtype=np.float32)
    pos_entry_score = np.zeros(n_tickers, dtype=np.float32)  # Entry Quality Score

    # Flags de estado
    pos_tp1_done = np.zeros(n_tickers, dtype=np.bool_)
    pos_tp2_done = np.zeros(n_tickers, dtype=np.bool_)
    pos_be_done = np.zeros(n_tickers, dtype=np.bool_)

    # Registro de trades - DYNAMIC RESIZING to save memory
    initial_max_trades = min(50000, n_days * 100)
    trade_log_idx = 0
    trades_log = np.zeros(
        (initial_max_trades, 12), dtype=np.float64
    )  # 12 cols: day, ticker, exit_type, exit_price, exit_shares, pnl, entry_day, risk, rvol, adr, vol, entry_score

    # --- BUCLE PRINCIPAL (Día a Día) ---
    for t in range(n_days):
        # 1. Valorar Portafolio al Cierre de hoy
        current_equity = cash
        for i in range(n_tickers):
            if pos_active[i]:
                current_price = close_arr[t, i]
                if np.isnan(current_price):
                    if t > 0:
                        current_price = close_arr[t - 1, i]
                    else:
                        current_price = pos_entry_price[i]
                current_equity += pos_shares[i] * current_price

        equity_curve[t] = current_equity

        # Saltamos el último día
        if t == n_days - 1:
            break

        # 2. Procesar SALIDAS (Exit Logic) - Prioridad: STOP > TP2 > TP1 > RUNNER
        for i in range(n_tickers):
            if not pos_active[i]:
                continue

            curr_low = low_arr[t, i]
            curr_high = high_arr[t, i]
            curr_close = close_arr[t, i]

            if np.isnan(curr_close):
                continue

            exit_signal = False
            exit_type = -1
            exit_shares = 0.0
            exit_price = 0.0

            # --- TRAILING STOP (ATR-based o Breakeven) ---
            if use_trailing_stop and not pos_be_done[i]:
                if use_atr_stop and pos_entry_atr[i] > 0:
                    # ATR-based trailing: move to entry + 0.5*ATR (profit lock)
                    current_r = (
                        (curr_high - pos_entry_price[i]) / pos_stop_dist[i]
                        if pos_stop_dist[i] > 0
                        else 0
                    )
                    if current_r >= be_threshold_r:
                        # Move stop to small profit lock, not breakeven
                        new_stop = pos_entry_price[i] + (pos_entry_atr[i] * 0.5)
                        pos_stop_price[i] = max(pos_stop_price[i], new_stop)
                        pos_be_done[i] = True
                else:
                    # Original breakeven logic
                    current_r = (
                        (curr_high - pos_entry_price[i]) / pos_stop_dist[i]
                        if pos_stop_dist[i] > 0
                        else 0
                    )
                    if current_r >= be_threshold_r:
                        pos_stop_price[i] = max(pos_stop_price[i], pos_entry_price[i])
                        pos_be_done[i] = True

            # --- RUNNER ATR TRAILING (after TP2) ---
            # Update highest close for trailing
            if pos_tp1_done[i] and pos_tp2_done[i] and use_atr_stop:
                pos_highest_close[i] = max(pos_highest_close[i], curr_high)
                # Update trailing stop: highest - ATR × multiplier
                if pos_entry_atr[i] > 0:
                    atr_trail_stop = pos_highest_close[i] - (
                        pos_entry_atr[i] * atr_trailing_multiplier
                    )
                    pos_stop_price[i] = max(pos_stop_price[i], atr_trail_stop)

            # --- PRIORIDAD CORREGIDA: TARGETS ANTES QUE STOPS ---
            # Esto permite que TP1/TP2 se ejecuten en el mismo día que un pullback

            # --- A) TAKE PROFIT 1 (Prioridad máxima) ---
            if not pos_tp1_done[i] and curr_high >= pos_tp1_price[i]:
                exit_signal = True
                exit_type = 1
                # Vender tp1_pct del ORIGINAL
                exit_shares = np.floor(pos_original_shares[i] * tp1_pct)
                exit_price = pos_tp1_price[i]

                # Check Gap Up
                day_open = open_arr[t, i]
                if not np.isnan(day_open) and day_open > pos_tp1_price[i]:
                    exit_price = day_open

            # --- B) TAKE PROFIT 2 (Segunda prioridad) ---
            elif not pos_tp2_done[i] and curr_high >= pos_tp2_price[i]:
                exit_signal = True
                exit_type = 2
                # Calcular shares: tp2_pct del ORIGINAL
                # Si TP1 ya se ejecutó, quedan (100% - tp1_pct) del original
                # TP2 es tp2_pct del original
                if pos_tp1_done[i]:
                    # Quedan: original * (1 - tp1_pct)
                    # TP2 es: original * tp2_pct
                    # Porcentaje de lo que queda: tp2_pct / (1 - tp1_pct)
                    remaining_pct = 1.0 - tp1_pct
                    if remaining_pct > 0:
                        shares_pct_of_remaining = tp2_pct / remaining_pct
                        exit_shares = np.floor(pos_shares[i] * shares_pct_of_remaining)
                    else:
                        exit_shares = pos_shares[i]  # Vender todo si queda poco
                else:
                    # TP1 no ejecutado, vender tp2_pct del original
                    exit_shares = np.floor(pos_original_shares[i] * tp2_pct)

                exit_price = pos_tp2_price[i]

                # Check Gap Up
                day_open = open_arr[t, i]
                if not np.isnan(day_open) and day_open > pos_tp2_price[i]:
                    exit_price = day_open

            # --- C) STOP LOSS (Tercera prioridad - solo si no hit targets) ---
            elif curr_low <= pos_stop_price[i]:
                exit_signal = True
                exit_type = 0
                exit_shares = pos_shares[i]
                exit_price = pos_stop_price[i]

                # Check Gap Down
                day_open = open_arr[t, i]
                if not np.isnan(day_open) and day_open < pos_stop_price[i]:
                    exit_price = day_open

            # --- D) RUNNER EXIT (runner_pct restante) - EMA8/EMA21 Crossover ---
            # Lógica simplificada y más reactiva:
            #   - Mientras EMA8 > EMA21: mantener runner (tendencia fuerte)
            #   - Cuando EMA8 cruza bajo EMA21: cerrar inmediatamente
            #   - Si trailing stop ATR se activa, también cierra
            # Esto captura el momentum genuino sin cortar demasiado pronto como SMA20
            elif pos_tp1_done[i] and pos_tp2_done[i] and pos_shares[i] > 0:
                runner_exit = False

                ema8_val = ema8_arr[t, i]
                ema21_val = ema21_arr[t, i]

                # Primero verificar trailing stop ATR (protección dinámica)
                if curr_close < pos_stop_price[i]:
                    runner_exit = True
                # Luego verificar EMA8/EMA21 crossover (fin de tendencia)
                elif (
                    not np.isnan(ema8_val)
                    and not np.isnan(ema21_val)
                    and ema8_val > 0
                    and ema21_val > 0
                ):
                    if ema8_val < ema21_val:  # EMA8 cruza bajo EMA21 = fin de tendencia
                        runner_exit = True

                if runner_exit:
                    exit_signal = True
                    exit_type = 3  # RUNNER
                    exit_shares = pos_shares[i]  # Vender todo lo que queda
                    exit_price = curr_close

            # --- EJECUTAR SALIDA ---
            if exit_signal and exit_shares > 0:
                # Asegurar que no vendamos más de lo que tenemos
                exit_shares = min(exit_shares, pos_shares[i])

                pnl = (exit_price - pos_entry_price[i]) * exit_shares
                cash += exit_price * exit_shares
                pos_shares[i] -= exit_shares

                # Registrar Trade - DYNAMIC RESIZING to save memory
                if trade_log_idx >= trades_log.shape[0]:
                    new_size = trades_log.shape[0] * 2  # Double the capacity
                    new_trades = np.zeros((new_size, 12), dtype=np.float64)
                    new_trades[:trade_log_idx] = trades_log
                    trades_log = new_trades
                trades_log[trade_log_idx, 0] = t
                trades_log[trade_log_idx, 1] = i
                trades_log[trade_log_idx, 2] = exit_type
                trades_log[trade_log_idx, 3] = exit_price
                trades_log[trade_log_idx, 4] = exit_shares
                trades_log[trade_log_idx, 5] = pnl
                trades_log[trade_log_idx, 6] = pos_entry_day[i]
                trades_log[trade_log_idx, 7] = pos_initial_risk[i]
                trades_log[trade_log_idx, 8] = pos_rvol[i]  # CONTEXT RVOL
                trades_log[trade_log_idx, 9] = pos_adr[i]  # CONTEXT ADR
                trades_log[trade_log_idx, 10] = pos_vol[i]  # CONTEXT VOL
                trades_log[trade_log_idx, 11] = pos_entry_score[
                    i
                ]  # ENTRY QUALITY SCORE
                trade_log_idx += 1

                # Actualizar Flags
                if exit_type == 0:  # STOP total - cerrar todo
                    pos_active[i] = False
                    pos_shares[i] = 0
                    pos_tp1_done[i] = False
                    pos_tp2_done[i] = False
                    pos_be_done[i] = False
                elif exit_type == 1:
                    pos_tp1_done[i] = True
                elif exit_type == 2:
                    pos_tp2_done[i] = True
                elif exit_type == 3:  # RUNNER - cerrar todo
                    pos_active[i] = False
                    pos_shares[i] = 0
                    pos_tp1_done[i] = False
                    pos_tp2_done[i] = False
                    pos_be_done[i] = False

                # Limpieza residual
                if pos_shares[i] < 1:
                    pos_active[i] = False
                    pos_shares[i] = 0
                    pos_tp1_done[i] = False
                    pos_tp2_done[i] = False
                    pos_be_done[i] = False

        # 3. Procesar ENTRADAS (Entry Logic) - Prioritized by Quality Score
        invested_equity = current_equity - cash
        max_invested = current_equity * max_exposure_pct

        if invested_equity < max_invested:
            # Find all tickers with entry signals today
            entry_indices = np.zeros(n_tickers, dtype=np.int64)
            entry_scores = np.zeros(n_tickers, dtype=np.float32)
            num_entries = 0

            for i in range(n_tickers):
                if not pos_active[i] and entries_arr[t, i]:
                    entry_indices[num_entries] = i
                    entry_scores[num_entries] = entry_score_arr[t, i]
                    num_entries += 1

            # Sort entries by score (descending) using simple selection sort
            # This is efficient for small number of entries per day
            for i in range(num_entries):
                max_idx = i
                max_score = entry_scores[i]
                for j in range(i + 1, num_entries):
                    if entry_scores[j] > max_score:
                        max_idx = j
                        max_score = entry_scores[j]
                # Swap
                if max_idx != i:
                    entry_indices[i], entry_indices[max_idx] = (
                        entry_indices[max_idx],
                        entry_indices[i],
                    )
                    entry_scores[i], entry_scores[max_idx] = (
                        entry_scores[max_idx],
                        entry_scores[i],
                    )

            # Process entries in score order (highest quality first)
            for idx in range(num_entries):
                i = entry_indices[idx]

                if pos_active[i]:
                    continue

                if entries_arr[t, i]:
                    curr_close = close_arr[t, i]
                    curr_atr = atr_arr[t, i]
                    curr_adr = adr_arr[t, i]

                    if np.isnan(curr_close) or np.isnan(curr_atr) or curr_atr <= 0:
                        continue

                    # --- STOP DISTANCE CALCULATION ---
                    # ATR-based or fixed percentage depending on use_atr_stop
                    if use_atr_stop:
                        # ATR-based stop with ADR-adjusted multiplier
                        # High ADR stocks (> 6%): use higher multiplier
                        if not np.isnan(curr_adr) and curr_adr > 6.0:
                            effective_multiplier = (
                                atr_stop_multiplier * 1.2
                            )  # More room for volatile
                        else:
                            effective_multiplier = atr_stop_multiplier

                        stop_dist = curr_atr * effective_multiplier
                    else:
                        # Fixed percentage stop (original)
                        stop_dist = curr_close * max_stop_pct

                    if stop_dist <= 0:
                        continue

                    # --- RISK CALCULATION ---
                    if use_fixed_dollar_risk:
                        risk_amt = risk_dollars
                    else:
                        risk_amt = current_equity * risk_pct_per_trade

                    if risk_amt <= 0:
                        continue

                    shares = np.floor(risk_amt / stop_dist)

                    if shares <= 0:
                        continue

                    cost = shares * curr_close

                    # Verificar cash disponible
                    if cash >= cost:
                        # Ejecutar Entrada
                        cash -= cost
                        pos_active[i] = True
                        pos_shares[i] = shares
                        pos_original_shares[i] = shares
                        pos_entry_price[i] = curr_close
                        pos_stop_dist[i] = stop_dist
                        pos_entry_day[i] = float(t)
                        pos_initial_risk[i] = risk_amt
                        pos_entry_atr[i] = curr_atr  # Store ATR for trailing
                        pos_highest_close[i] = curr_close  # Initialize for trailing

                        # Guardar Contexto (Snapshots)
                        pos_rvol[i] = rvol_arr[t, i]
                        pos_adr[i] = adr_arr[t, i]
                        pos_vol[i] = volume_arr[t, i]
                        pos_entry_score[i] = entry_score_arr[t, i]

                        # Definir Niveles basados en R
                        pos_stop_price[i] = curr_close - stop_dist
                        pos_tp1_price[i] = curr_close + (stop_dist * tp1_r)
                        pos_tp2_price[i] = curr_close + (stop_dist * tp2_r)

                        # Reset Flags
                        pos_tp1_done[i] = False
                        pos_tp2_done[i] = False
                        pos_be_done[i] = False

    return equity_curve, trades_log[:trade_log_idx]
