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
    sector_multiplier_arr,
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
    fee_rate,
    slippage_rate,
    # --- EXP-010 Dynamic ADR Stop Params ---
    stop_mode=0,  # 0: fixed_pct, 1: adr_pct, 2: atr, 3: adr_floor, 4: adr_reject
    adr_stop_fraction=0.5,
    adr_stop_floor_pct=0.0,
    reject_stop_below_pct=0.0,
    sizing_mode=0,  # 0: fixed_risk, 1: adaptive_target_exposure
    max_position_pct=0.25,
    adr14_arr=None,
):
    """
    Núcleo de simulación de alta velocidad compilado con Numba.
    MEMORY OPTIMIZED: Uses float32 arrays (50% memory reduction vs float64).

    EXP-010 INTEGRATION:
    - stop_mode: controls initial stop calculation
    - sizing_mode: controls position sizing (fixed risk vs exposure target)
    - max_position_pct: cap for individual trade size

    Returns:
        equity_curve: Array (n_dias,) con el valor total del portafolio.
        trades_log: Array estructurado (n_trades, 20)
    """
    n_days, n_tickers = close_arr.shape

    # Use adr14 if provided, else fallback to adr_arr
    base_adr_arr = adr14_arr if adr14_arr is not None else adr_arr

    # --- ESTADO DEL PORTAFOLIO ---
    cash = float(initial_capital)
    equity_curve = np.zeros(n_days, dtype=np.float64)

    # --- ESTADO DE POSICIONES (Por Ticker) ---
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

    # Context tracking
    pos_entry_atr = np.zeros(n_tickers, dtype=np.float32)
    pos_highest_close = np.zeros(n_tickers, dtype=np.float32)
    pos_rvol = np.zeros(n_tickers, dtype=np.float32)
    pos_adr = np.zeros(n_tickers, dtype=np.float32)
    pos_vol = np.zeros(n_tickers, dtype=np.float32)
    pos_entry_score = np.zeros(n_tickers, dtype=np.float32)

    # New context for EXP-010
    pos_stop_mode = np.zeros(n_tickers, dtype=np.float32)
    pos_stop_dist_pct = np.zeros(n_tickers, dtype=np.float32)
    pos_sizing_mode = np.zeros(n_tickers, dtype=np.float32)

    # Flags de estado
    pos_tp1_done = np.zeros(n_tickers, dtype=np.bool_)
    pos_tp2_done = np.zeros(n_tickers, dtype=np.bool_)
    pos_be_done = np.zeros(n_tickers, dtype=np.bool_)

    # Registro de trades - Expanded to 20 columns for experimental data
    initial_max_trades = min(50000, n_days * 100)
    trade_log_idx = 0
    trades_log = np.zeros((initial_max_trades, 20), dtype=np.float64)
    # Cols: 0:day, 1:ticker, 2:exit_type, 3:exit_price, 4:exit_shares, 5:pnl, 
    # 6:entry_day, 7:risk, 8:rvol, 9:adr, 10:vol, 11:entry_score, 12:stop_loss, 
    # 13:tp1_target, 14:tp2_target, 15:stop_mode, 16:stop_dist_pct, 17:sizing_mode, 
    # 18:unused, 19:unused

    # --- BUCLE PRINCIPAL (Día a Día) ---
    for t in range(n_days):
        # 1. Valorar Portafolio
        current_equity = cash
        for i in range(n_tickers):
            if pos_active[i]:
                current_price = close_arr[t, i]
                if np.isnan(current_price):
                    current_price = close_arr[t - 1, i] if t > 0 else pos_entry_price[i]
                current_equity += pos_shares[i] * current_price
        equity_curve[t] = current_equity

        if t == n_days - 1: break

        # 2. Procesar SALIDAS
        for i in range(n_tickers):
            if not pos_active[i]: continue

            curr_low = low_arr[t, i]
            curr_high = high_arr[t, i]
            curr_close = close_arr[t, i]
            if np.isnan(curr_close): continue

            exit_signal = False
            exit_type = -1
            exit_shares = 0.0
            exit_price = 0.0

            # Trailing Stop / BE Logic
            if use_trailing_stop and not pos_be_done[i]:
                current_r = (curr_high - pos_entry_price[i]) / pos_stop_dist[i] if pos_stop_dist[i] > 0 else 0
                if current_r >= be_threshold_r:
                    if use_atr_stop and pos_entry_atr[i] > 0:
                        new_stop = pos_entry_price[i] + (pos_entry_atr[i] * 0.5)
                        pos_stop_price[i] = max(pos_stop_price[i], new_stop)
                    else:
                        pos_stop_price[i] = max(pos_stop_price[i], pos_entry_price[i])
                    pos_be_done[i] = True

            # Runner Trailing
            if pos_tp1_done[i] and pos_tp2_done[i] and use_atr_stop:
                pos_highest_close[i] = max(pos_highest_close[i], curr_high)
                if pos_entry_atr[i] > 0:
                    atr_trail_stop = pos_highest_close[i] - (pos_entry_atr[i] * atr_trailing_multiplier)
                    pos_stop_price[i] = max(pos_stop_price[i], atr_trail_stop)

            # Check Targets & Stop
            if not pos_tp1_done[i] and curr_high >= pos_tp1_price[i]:
                exit_signal, exit_type = True, 1
                exit_shares = np.floor(pos_original_shares[i] * tp1_pct)
                exit_price = max(pos_tp1_price[i], open_arr[t, i]) if not np.isnan(open_arr[t, i]) else pos_tp1_price[i]
            elif not pos_tp2_done[i] and curr_high >= pos_tp2_price[i]:
                exit_signal, exit_type = True, 2
                remaining_pct = 1.0 - tp1_pct
                exit_shares = np.floor(pos_shares[i] * (tp2_pct / remaining_pct)) if remaining_pct > 0 else pos_shares[i]
                exit_price = max(pos_tp2_price[i], open_arr[t, i]) if not np.isnan(open_arr[t, i]) else pos_tp2_price[i]
            elif curr_low <= pos_stop_price[i]:
                exit_signal, exit_type = True, 0
                exit_shares = pos_shares[i]
                exit_price = min(pos_stop_price[i], open_arr[t, i]) if not np.isnan(open_arr[t, i]) else pos_stop_price[i]
            elif pos_tp1_done[i] and pos_tp2_done[i] and pos_shares[i] > 0:
                # Runner Exit
                runner_exit = curr_close < pos_stop_price[i]
                if not runner_exit:
                    e8, e21 = ema8_arr[t, i], ema21_arr[t, i]
                    if not np.isnan(e8) and not np.isnan(e21) and e8 > 0 and e21 > 0:
                        if e8 < e21: runner_exit = True
                if runner_exit:
                    exit_signal, exit_type, exit_shares, exit_price = True, 3, pos_shares[i], curr_close

            if exit_signal and exit_shares > 0:
                exit_shares = min(exit_shares, pos_shares[i])
                pnl = (exit_price * (1 - slippage_rate) - pos_entry_price[i]) * exit_shares - (exit_price * exit_shares * fee_rate)
                cash += (exit_price * (1 - slippage_rate) * exit_shares) - (exit_price * exit_shares * fee_rate)
                pos_shares[i] -= exit_shares

                if trade_log_idx >= trades_log.shape[0]:
                    new_trades = np.zeros((trades_log.shape[0] * 2, 20), dtype=np.float64)
                    new_trades[:trade_log_idx] = trades_log
                    trades_log = new_trades
                
                trades_log[trade_log_idx, 0:6] = [t, i, exit_type, exit_price, exit_shares, pnl]
                trades_log[trade_log_idx, 6:12] = [pos_entry_day[i], pos_initial_risk[i], pos_rvol[i], pos_adr[i], pos_vol[i], pos_entry_score[i]]
                trades_log[trade_log_idx, 12:15] = [pos_stop_price[i], pos_tp1_price[i], pos_tp2_price[i]]
                trades_log[trade_log_idx, 15:18] = [pos_stop_mode[i], pos_stop_dist_pct[i], pos_sizing_mode[i]]
                trade_log_idx += 1

                if exit_type in (0, 3) or pos_shares[i] < 1:
                    pos_active[i] = False
                    pos_shares[i] = 0

        # 3. Procesar ENTRADAS
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

            # Process entries in score order
            for idx in range(num_entries):
                i = entry_indices[idx]
                if invested_equity >= max_invested: break
                
                curr_close = close_arr[t, i]
                curr_atr = atr_arr[t, i]
                curr_adr14 = base_adr_arr[t, i]
                
                if np.isnan(curr_close) or curr_close <= 0: continue

                # --- STOP CALCULATION (EXP-010) ---
                stop_dist_pct = max_stop_pct  # Default baseline
                
                if stop_mode == 1: # B1/B2/B3 cristian: min(max_stop, 0.5 * ADR)
                    stop_dist_pct = min(max_stop_pct, adr_stop_fraction * curr_adr14 / 100.0)
                elif stop_mode == 2: # C: min(max_stop, 1.5 * ATR)
                    if not np.isnan(curr_atr) and curr_atr > 0:
                        stop_dist_pct = min(max_stop_pct, 1.5 * curr_atr / curr_close)
                elif stop_mode == 3: # D/E: min(max_stop, max(0.5 * ADR, floor))
                    stop_dist_pct = min(max_stop_pct, max(adr_stop_fraction * curr_adr14 / 100.0, adr_stop_floor_pct))
                
                # B3 Reject Filter
                if stop_mode == 4: # adr_reject (B3 style logic)
                    stop_dist_pct = min(max_stop_pct, adr_stop_fraction * curr_adr14 / 100.0)
                    if stop_dist_pct < reject_stop_below_pct: continue
                
                stop_dist = curr_close * stop_dist_pct
                if stop_dist <= 0: continue

                # --- SIZING CALCULATION ---
                if sizing_mode == 0: # Fixed Risk
                    if use_fixed_dollar_risk: risk_amt = risk_dollars
                    else: risk_amt = current_equity * risk_pct_per_trade
                else: # Adaptive Target Exposure (B2)
                    # For B2, we want to size based on target exposure but limited by risk.
                    # Simple adaptive: same as fixed risk but we'll cap by max_position_pct below.
                    risk_amt = current_equity * risk_pct_per_trade
                
                risk_amt *= sector_multiplier_arr[t, i]
                if risk_amt <= 0: continue

                shares = np.floor(risk_amt / stop_dist)
                
                # --- MAX POSITION CAP ---
                entry_fill = open_arr[t+1, i] if t+1 < n_days and not np.isnan(open_arr[t+1, i]) else curr_close
                # Guard: open inválido (0 o NaN) al día siguiente -> evitar ZeroDivisionError
                if not (entry_fill > 0):
                    continue
                max_shares = np.floor((current_equity * max_position_pct) / (entry_fill * (1 + slippage_rate)))
                shares = min(shares, max_shares)

                if shares <= 0: continue

                entry_cost = shares * entry_fill * (1 + slippage_rate)
                entry_fee = entry_cost * fee_rate

                if cash >= (entry_cost + entry_fee):
                    cash -= (entry_cost + entry_fee)
                    invested_equity += entry_cost
                    pos_active[i] = True
                    pos_shares[i] = pos_original_shares[i] = shares
                    pos_entry_price[i] = entry_fill
                    pos_stop_dist[i] = stop_dist
                    pos_entry_day[i] = float(t + 1)
                    pos_initial_risk[i] = risk_amt
                    pos_entry_atr[i], pos_highest_close[i] = curr_atr, entry_fill
                    pos_rvol[i], pos_adr[i], pos_vol[i], pos_entry_score[i] = rvol_arr[t, i], curr_adr14, volume_arr[t, i], entry_score_arr[t, i]
                    pos_stop_price[i] = entry_fill - stop_dist
                    pos_tp1_price[i] = entry_fill + (stop_dist * tp1_r)
                    pos_tp2_price[i] = entry_fill + (stop_dist * tp2_r)
                    pos_stop_mode[i], pos_stop_dist_pct[i], pos_sizing_mode[i] = stop_mode, stop_dist_pct, sizing_mode

    return equity_curve, trades_log[:trade_log_idx]

