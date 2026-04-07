//@version=6
indicator(title='Cockpit v2', shorttitle='Cockpit', overlay=true, max_bars_back=253)

// ==========================================
// [1] Inputs
// ==========================================

// --- Core Stats Inputs ---
grp_tbl           = 'Core Stats: Table Settings'
show_empty_row    = input.bool(true,  title='Add empty rows (Top & Bottom)', group=grp_tbl)
gap_growth        = input.int(1,      title='Gap before Growth Table', minval=0, maxval=5, group=grp_tbl)
gap_rs            = input.int(1,      title='Gap before RS Table', minval=0, maxval=5, group=grp_tbl)
posTable          = input.string(defval='Center Center', title='Table Position', options=['Top Left','Top Right','Center Left','Center Center','Center Right','Bottom Left','Bottom Right'], group=grp_tbl)
tbl_size          = input.string('Normal', title='Table Size', options=['Tiny','Small','Normal','Large'], group=grp_tbl)
bg_col            = input.color(color.new(color.black, 100), title='Background Color', group=grp_tbl)
inp_width         = input.int(12, 'Column Width (%)', minval = 1, maxval = 30, group=grp_tbl)

grp_logic         = "Core Stats: Sniper Logic"
zone_min          = input.float(-0.5, "Zone Min (ATR)", step=0.1, group=grp_logic)
zone_max          = input.float(1.0,  "Zone Max (ATR)", step=0.1, group=grp_logic)
filter_sma50_max  = input.float(3.0,  "50SMA Max Dist (ATR)", step=0.1, group=grp_logic)

grp_col           = "Core Stats: Colors"
txt_col           = input.color(color.rgb(255, 204, 128), title='Text Color', group=grp_col)
col_21_ok         = input.color(color.rgb(0, 255, 0), "ATR 21EMA OK", group=grp_col)
col_21_ng         = input.color(color.red,            "ATR 21EMA NG", group=grp_col)
col_10w_ok        = input.color(color.rgb(0, 255, 0), "ATR 10WMA OK", group=grp_col)

col_10w_ng        = input.color(color.red,            "ATR 10WMA NG", group=grp_col)
col_50_ok         = input.color(color.rgb(0, 255, 0), "ATR 50SMA OK", group=grp_col)
col_50_ng         = input.color(color.red,            "ATR 50SMA NG",  group=grp_col)

grp_low           = "Core Stats: 21EMA Low"
col_low_safe      = input.color(color.rgb(0, 255, 0), "Price > Low",     group=grp_low)
col_low_stop      = input.color(color.red,            "Price < Low", group=grp_low)


grp_pct           = "Core Stats: 21EMA Low %"
pct_thresh_good   = input.float(5.0, "Good % (<=)", step=0.5, group=grp_pct)
pct_thresh_warn   = input.float(8.0, "Warn % (<=)", step=0.5, group=grp_pct)
col_pct_good      = input.color(color.rgb(0, 255, 0),   "Good (<5%)",      group=grp_pct)
col_pct_warn      = input.color(color.rgb(255, 245, 157), "Warn (5-8%)",     group=grp_pct)
col_pct_bad       = input.color(color.red,              "Bad (>8%)",       group=grp_pct)
col_pct_minus     = input.color(color.red,              "Minus (<0%)",     group=grp_pct)

grp_3wt           = "Core Stats: 3-Weeks Tight"
col_3wt_yes       = input.color(color.rgb(0, 255, 0), "3WT Active (Yes)",  group=grp_3wt)
col_3wt_no        = input.color(color.rgb(255, 204, 128), "3WT Inactive (No)", group=grp_3wt)

grp_adr           = "Core Stats: ADR%"
adrp_threshold    = input.float(3.5, title='ADR% Min', step=0.1, group=grp_adr)
adrp_max          = input.float(8.0, title='ADR% Max', step=0.1, group=grp_adr)
color_adrp_ok     = input.color(color.rgb(0, 255, 0), title='ADR% OK', group=grp_adr)
color_adrp_ng     = input.color(color.red,            title='ADR% NG', group=grp_adr)


grp_disp          = 'Core Stats: Toggles'
show_adrp         = input.bool(true,  title='Show ADR%',            group=grp_disp)
show_zone_21      = input.bool(true,  title='Show ATR 21EMA',       group=grp_disp)
show_zone_10w     = input.bool(true,  title='Show ATR 10WMA',       group=grp_disp)
show_zone_50      = input.bool(true,  title='Show ATR 50SMA',       group=grp_disp) 
show_ema21_low    = input.bool(true,  title='Show 21EMA Low',       group=grp_disp)
show_low_pct      = input.bool(true,  title='Show 21EMA Low %',     group=grp_disp)
show_3wt          = input.bool(true,  title='Show 3-Weeks Tight',   group=grp_disp)
show_atrx         = input.bool(true,  title='Show ATR% 50SMA',      group=grp_disp)
show_ipo_date     = input.bool(true,  title='Show IPO Timer',       group=grp_disp)

grp_param         = 'Core Stats: Parameters'
adrp_len          = input.int(20, title='ADR% Length',                      group=grp_param)
atr_len           = input.int(14, title='ATR Length',                       group=grp_param)

wt_thresh         = input.float(1.5, title='3WT Threshold (%)', step=0.1,   group=grp_param)
atrx_lvl_7        = 7.0
atrx_lvl_8        = 8.0
atrx_lvl_9        = 9.0
atrx_lvl_10       = 10.0
atrx_lvl_11       = 11.0


// --- Growth Table Inputs ---
grp_g_set    = 'Growth Table: Settings'
show_growth  = input.bool(true, 'Show Growth Table', group=grp_g_set)

grp_g_col    = 'Growth Table: Colors'
color_text_g = input.color(color.rgb(255, 204, 128), 'Text Color', group = grp_g_col)
color_est_g  = input.color(color.new(color.blue, 100), 'Estimate Column BG', group = grp_g_col)
color_pos_g  = input.color(color.new(color.green, 30), 'Positive Growth', group = grp_g_col)
color_neg_g  = input.color(color.new(color.red, 30), 'Negative Growth', group = grp_g_col)
color_high_g = input.color(color.new(#00ff00, 0), 'High Growth (>25%)', group = grp_g_col)

// --- RS Table Inputs ---
grp_rs_main = 'RS Table: Main'
show_rs_table = input.bool(true, 'Show RS Table', group=grp_rs_main)
rs_benchmark = input.symbol('SPY', title = 'RS Benchmark', group=grp_rs_main)
calc_mode = input.string('Daily (Fixed)', 'Calculation Timeframe Mode', options = ['Daily (Fixed)', 'Current Chart'], group = grp_rs_main)

calc_tf = calc_mode == 'Daily (Fixed)' ? 'D' : timeframe.period

grp_rs_periods = 'RS Table: Periods'

rs_length_w1 = input.int(5, 'Period 1 (Short)', minval = 5, group = grp_rs_periods, inline = 'RS1')
show_rs_w1 = input.bool(false, '', group = grp_rs_periods, inline = 'RS1')

rs_length_m1 = input.int(21, 'Period 2 (Medium)', minval = 5, group = grp_rs_periods, inline = 'RS2')
show_rs_m1 = input.bool(true, '', group = grp_rs_periods, inline = 'RS2')


rs_length_m3 = input.int(63, 'Period 3 (Longer)', minval = 5, group = grp_rs_periods, inline = 'RS3')
show_rs_m3 = input.bool(true, '', group = grp_rs_periods, inline = 'RS3')

rs_length_m6 = input.int(126, 'Period 4 (Long)', minval = 5, group = grp_rs_periods, inline = 'RS4')
show_rs_m6 = input.bool(true, '', group = grp_rs_periods, inline = 'RS4')

show_rs_avg = input.bool(true, title = 'Show Average RS Column', group = grp_rs_periods)

// Highlight
grp_highlight = 'RS Table: Highlight'
highlight_mode = input.string('Text', 'Highlight Mode', options=['Background', 'Text'], group = grp_highlight)
highlight_strong_color = input.color(color.new(#00ff00, 0), 'Strong RS Color', group = grp_highlight, inline = 'H1')
highlight_strong_pct = input.float(80.0, 'Strong Threshold (%)', minval = 50, maxval = 99, group = grp_highlight, inline = 'H1')
enable_strong_highlight = input.bool(true, 'Strong', group = grp_highlight, inline = 'H1')

highlight_neutral_color = input.color(color.new(#ffcc80, 0), 'Neutral RS Color', group = grp_highlight, inline = 'H2')
highlight_weak_pct = input.float(39.0, 'Weak Threshold (%)', minval = 1, maxval = 50, group = grp_highlight, inline = 'H3')
enable_neutral_highlight = input.bool(false, 'Neutral', group = grp_highlight, inline = 'H2')

highlight_weak_color = input.color(color.new(color.red, 0), 'Weak RS Color', group = grp_highlight, inline = 'H3')
enable_weak_highlight = input.bool(true, 'Weak', group = grp_highlight, inline = 'H3')

// RS Settings
sort_key_options = input.string('P2', title = 'Sort By RS Period', options = ['P1', 'P2', 'P3', 'P4', 'P Avg'], group = grp_rs_main)
show_current_chart_ticker = input.bool(true, title = 'Show Current Chart Ticker', group = grp_rs_main)

rs_show_decimals = input.bool(true, title = 'Show RS Decimals', group = grp_rs_main)

// Tickers
group_name = 'RS Table: Tickers (Max 35)' 
ticker_1 = input.symbol('QQQ', 'Ticker 1', group = group_name, inline = 'T1')
is_set_1 = input.bool(true, '', group = group_name, inline = 'T1')
ticker_2 = input.symbol('QQQE', 'Ticker 2', group = group_name, inline = 'T2')
is_set_2 = input.bool(true, '', group = group_name, inline = 'T2')
ticker_3 = input.symbol('RSP', 'Ticker 3', group = group_name, inline = 'T3')

is_set_3 = input.bool(true, '', group = group_name, inline = 'T3')
ticker_4 = input.symbol('DIA', 'Ticker 4', group = group_name, inline = 'T4')
is_set_4 = input.bool(true, '', group = group_name, inline = 'T4')

ticker_5 = input.symbol('IWM', 'Ticker 5', group = group_name, inline = 'T5')
is_set_5 = input.bool(true, '', group = group_name, inline = 'T5')
ticker_6 = input.symbol('XLV', 'Ticker 6', group = group_name, inline = 'T6')
is_set_6 = input.bool(true, '', group = group_name, inline = 'T6')
ticker_7 = input.symbol('XLE', 'Ticker 7', group = group_name, inline = 'T7')
is_set_7 = input.bool(true, '', group = group_name, inline = 'T7')
ticker_8 = input.symbol('XLF', 'Ticker 8', group = group_name, inline = 'T8')
is_set_8 = input.bool(true, '', group = group_name, inline = 'T8')

ticker_9 = input.symbol('XLRE', 'Ticker 9', group = group_name, inline = 'T9')
is_set_9 = input.bool(true, '', group = group_name, inline = 'T9')
ticker_10 = input.symbol('XLB', 'Ticker 10', group = group_name, inline = 'T10')
is_set_10 = input.bool(true, '', group = group_name, inline = 'T10')
ticker_11 = input.symbol('XLP', 'Ticker 11', group = group_name, inline = 'T11')
is_set_11 = input.bool(true, '', group = group_name, inline = 'T11')
ticker_12 = input.symbol('XLU', 'Ticker 12', group = group_name, inline = 'T12')
is_set_12 = input.bool(true, '', group = group_name, inline = 'T12')
ticker_13 = input.symbol('XLY', 'Ticker 13', group = group_name, inline = 'T13')

is_set_13 = input.bool(true, '', group = group_name, inline = 'T13')

ticker_14 = input.symbol('XLK', 'Ticker 14', group = group_name, inline = 'T14')
is_set_14 = input.bool(true, '', group = group_name, inline = 'T14')
ticker_15 = input.symbol('XLC', 'Ticker 15', group = group_name, inline = 'T15')
is_set_15 = input.bool(true, '', group = group_name, inline = 'T15')
ticker_16 = input.symbol('XLI', 'Ticker 16', group = group_name, inline = 'T16')
is_set_16 = input.bool(true, '', group = group_name, inline = 'T16')
ticker_17 = input.symbol('SMH', 'Ticker 17', group = group_name, inline = 'T17')
is_set_17 = input.bool(false, '', group = group_name, inline = 'T17')
ticker_18 = input.symbol('', 'Ticker 18', group = group_name, inline = 'T18')
is_set_18 = input.bool(false, '', group = group_name, inline = 'T18')
ticker_19 = input.symbol('', 'Ticker 19', group = group_name, inline = 'T19')

is_set_19 = input.bool(false, '', group = group_name, inline = 'T19')
ticker_20 = input.symbol('', 'Ticker 20', group = group_name, inline = 'T20')
is_set_20 = input.bool(false, '', group = group_name, inline = 'T20')
ticker_21 = input.symbol('', 'Ticker 21', group = group_name, inline = 'T21')
is_set_21 = input.bool(false, '', group = group_name, inline = 'T21')
ticker_22 = input.symbol('', 'Ticker 22', group = group_name, inline = 'T22')
is_set_22 = input.bool(false, '', group = group_name, inline = 'T22')
ticker_23 = input.symbol('', 'Ticker 23', group = group_name, inline = 'T23')
is_set_23 = input.bool(false, '', group = group_name, inline = 'T23')
ticker_24 = input.symbol('', 'Ticker 24', group = group_name, inline = 'T24')
is_set_24 = input.bool(false, '', group = group_name, inline = 'T24')
ticker_25 = input.symbol('', 'Ticker 25', group = group_name, inline = 'T25')
is_set_25 = input.bool(false, '', group = group_name, inline = 'T25')
ticker_26 = input.symbol('', 'Ticker 26', group = group_name, inline = 'T26')
is_set_26 = input.bool(false, '', group = group_name, inline = 'T26')
ticker_27 = input.symbol('', 'Ticker 27', group = group_name, inline = 'T27')
is_set_27 = input.bool(false, '', group = group_name, inline = 'T27')
ticker_28 = input.symbol('', 'Ticker 28', group = group_name, inline = 'T28')
is_set_28 = input.bool(false, '', group = group_name, inline = 'T28')
ticker_29 = input.symbol('', 'Ticker 29', group = group_name, inline = 'T29')
is_set_29 = input.bool(false, '', group = group_name, inline = 'T29')
ticker_30 = input.symbol('', 'Ticker 30', group = group_name, inline = 'T30')
is_set_30 = input.bool(false, '', group = group_name, inline = 'T30')
ticker_31 = input.symbol('', 'Ticker 31', group = group_name, inline = 'T31')

is_set_31 = input.bool(false, '', group = group_name, inline = 'T31')
ticker_32 = input.symbol('', 'Ticker 32', group = group_name, inline = 'T32')
is_set_32 = input.bool(false, '', group = group_name, inline = 'T32')
ticker_33 = input.symbol('', 'Ticker 33', group = group_name, inline = 'T33')
is_set_33 = input.bool(false, '', group = group_name, inline = 'T33')
ticker_34 = input.symbol('', 'Ticker 34', group = group_name, inline = 'T34')
is_set_34 = input.bool(false, '', group = group_name, inline = 'T34')
ticker_35 = input.symbol('', 'Ticker 35', group = group_name, inline = 'T35')

is_set_35 = input.bool(false, '', group = group_name, inline = 'T35')


// ==========================================
// [2] Global Declarations
// ==========================================
var array<string> ticker_names_data = array.new_string()
var array<float> rs_w1_data = array.new_float()
var array<float> rs_m1_data = array.new_float()
var array<float> rs_m3_data = array.new_float()
var array<float> rs_m6_data = array.new_float()

var array<float> rs_avg_data = array.new_float()



// ==========================================
// [3] Functions (Global Scope)
// ==========================================
format_price(price) =>
    if na(price)
        '-'
    else
        str.tostring(math.round(price * 100) / 100.0, format.mintick)


calc_g(cur, prev) =>
    if not na(cur) and not na(prev) and prev != 0
        (cur - prev) / math.abs(prev) * 100
    else
        na

f_c(val) =>

    na(val) ? color_text_g : val >= 25 ? color_high_g : val > 0 ? color_pos_g : color_neg_g

f_s(val) =>
    na(val) ? 'N/A' : str.tostring(val, '#,###.0') + '%'


f_get_rs_color_cond(rs_value) =>
    color_to_use = color(na)
    if not na(rs_value)

        if rs_value >= highlight_strong_pct and enable_strong_highlight
            color_to_use := highlight_strong_color
        else if rs_value < highlight_weak_pct and enable_weak_highlight
            color_to_use := highlight_weak_color
        else if rs_value >= highlight_weak_pct and rs_value < highlight_strong_pct and enable_neutral_highlight

            color_to_use := highlight_neutral_color
    color_to_use

f_get_rs_data(_ticker, _tf, _l1, _l2, _l3, _l4, _bench) =>
    if str.length(_ticker) > 0
        _pair = _ticker + ' / ' + _bench
        request.security(_pair, _tf, [ta.percentrank(close, _l1), ta.percentrank(close, _l2), ta.percentrank(close, _l3), ta.percentrank(close, _l4)], ignore_invalid_symbol=true)
    else
        [na, na, na, na]

f_safe_ticker(t) => str.length(t) > 0 ? t : 'SPY' 

f_clean_ticker_name(ticker_name) =>
    array_split = str.split(ticker_name, ':')
    no_prefix = array.size(array_split) > 1 ? array.get(array_split, array.size(array_split) - 1) : ticker_name
    s1 = str.replace_all(no_prefix, '"', '')
    s2 = str.replace_all(s1, '}', '')
    s3 = str.replace_all(s2, '{', '')
    s3

f_calculate_avg_rs(rs_w1, rs_m1, rs_m3, rs_m6, show_w1, show_m1, show_m3, show_m6) =>
    total_rs = 0.0
    count = 0.0
    if show_w1 and not na(rs_w1)
        total_rs := total_rs + rs_w1
        count := count + 1

    if show_m1 and not na(rs_m1)
        total_rs := total_rs + rs_m1
        count := count + 1
    if show_m3 and not na(rs_m3)
        total_rs := total_rs + rs_m3
        count := count + 1
    if show_m6 and not na(rs_m6)
        total_rs := total_rs + rs_m6
        count := count + 1
    avg = count > 0 ? total_rs / count : na
    avg

f_draw_stat_row(_t, _lbl, _val_str, _val_col, _row, _max_cols, _txt_col, _tsize) =>

    table.cell(_t, 0, _row, _lbl, text_color=_txt_col, text_size=_tsize, text_halign=text.align_left)
    table.merge_cells(_t, 0, _row, 1, _row)
    table.cell(_t, 2, _row, _val_str, text_color=_val_col, text_size=_tsize, text_halign=text.align_right)
    table.merge_cells(_t, 2, _row, _max_cols - 1, _row)



// ==========================================
// [4] Calculations
// ==========================================
s  = syminfo.tickerid

// ADR%
arp = 100 * (ta.sma(high / low, adrp_len) - 1)


// Daily Data
sma50D   = request.security(s, 'D', ta.sma(close, 50), barmerge.gaps_off, barmerge.lookahead_off)
atrD     = request.security(s, 'D', ta.atr(atr_len),   barmerge.gaps_off, barmerge.lookahead_off)
ema21    = request.security(s, 'D', ta.ema(close, 21), barmerge.gaps_off, barmerge.lookahead_off)
ema21Low = request.security(s, 'D', ta.ema(low,   21), barmerge.gaps_off, barmerge.lookahead_off)
wma10W   = request.security(s, 'W', ta.wma(close, 10), barmerge.gaps_off, barmerge.lookahead_off)


// Sniper Logic
dist_21_atr  = (close - ema21) / atrD
dist_10w_atr = (close - wma10W) / atrD
dist_50_atr  = (close - sma50D) / atrD
in_zone_21  = dist_21_atr >= zone_min and dist_21_atr <= zone_max
in_zone_10w = dist_10w_atr >= zone_min and dist_10w_atr <= zone_max
status_color_21  = in_zone_21 ? col_21_ok : col_21_ng
status_color_10w = in_zone_10w ? col_10w_ok : col_10w_ng
status_color_50 = (dist_50_atr > 0 and dist_50_atr <= filter_sma50_max) ? col_50_ok : col_50_ng

// Stats
gain_from_ma_pct = (close / sma50D) - 1.0
atr_pct_daily    = atrD / close
atrx_from_sma50  = (na(sma50D) or sma50D == 0 or na(atrD) or atrD <= 0) ? na : (gain_from_ma_pct / atr_pct_daily)

// 3-Weeks Tight
[w_c0, w_c1, w_c2] = request.security(s, 'W', [close, close[1], close[2]], barmerge.gaps_off, barmerge.lookahead_off)
is_3wt = false
if not na(w_c0) and not na(w_c1) and not n    diff1_pct = math.abs(w_c0 - w_c1) / w_c1 * 100
    diff2_pct = math.abs(w_c1 - w_c2) / w_c2 * 100
    if diff1_pct <= wt_thresh and diff2_pct <= wt_thresh
        is_3wt := true

// IPO age
ipoSince = request.security(s, 'D', (bar_index + 1) / 252.0)


// 21EMA Low %

low_pct = 0.0
if not na(ema21Low) and close > 0 and ema21Low > 0
    if close >= ema21Low
        low_pct := (close - ema21Low) / ema21Low * 100
    else

        low_pct := (close - ema21Low) / close * 100

// EPS Data
eps_actual = request.earnings(syminfo.tickerid, earnings.actual, ignore_invalid_symbol = true)
eps_stand = request.earnings(syminfo.tickerid, earnings.standardized, ignore_invalid_symbol = true)
calc_eps = na(eps_actual) ? eps_stand : eps_actual
bool new_earn = calc_eps != calc_eps[1]

e_0 = calc_eps
e_1 = ta.valuewhen(new_earn, calc_eps, 1)
e_2 = ta.valuewhen(new_earn, calc_eps, 2)
e_3 = ta.valuewhen(new_earn, calc_eps, 3)
e_4 = ta.valuewhen(new_earn, calc_eps, 4)
e_5 = ta.valuewhen(new_earn, calc_eps, 5)
e_6 = ta.valuewhen(new_earn, calc_eps, 6)

raw_rev = request.financial(syminfo.tickerid, 'TOTAL_REVENUE', 'FQ', ignore_invalid_symbol = true)
bool new_rev = raw_rev != raw_rev[1] and not na(raw_rev)

r_0 = raw_rev
r_1 = ta.valuewhen(new_rev, raw_rev, 1)
r_2 = ta.valuewhen(new_rev, raw_rev, 2)
r_3 = ta.valuewhen(new_rev, raw_rev, 3)
r_4 = ta.valuewhen(new_rev, raw_rev, 4)
r_5 = ta.valuewhen(new_rev, raw_rev, 5)
r_6 = ta.valuewhen(new_rev, raw_rev, 6)

future_eps = earnings.future_eps
future_rev = earnings.future_revenue

eg_0 = calc_g(e_0, e_4)
eg_1 = calc_g(e_1, e_5)
eg_2 = calc_g(e_2, e_6)

rg_0 = calc_g(r_0, r_4)
rg_1 = calc_g(r_1, r_5)
rg_2 = calc_g(r_2, r_6)
est_eg = calc_g(future_eps, e_3)
est_rg = calc_g(future_rev, r_3)

// RS Data Fetch
current_clean_ticker = syminfo.prefix + ":" + syminfo.ticker

[rs_w1_current, rs_m1_current, rs_m3_current, rs_m6_current] = f_get_rs_data(current_clean_ticker, calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)

[rs_w1_1, rs_m1_1, rs_m3_1, rs_m6_1] = f_get_rs_data(f_safe_ticker(ticker_1), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_2, rs_m1_2, rs_m3_2, rs_m6_2] = f_get_rs_data(f_safe_ticker(ticker_2), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_3, rs_m1_3, rs_m3_3, rs_m6_3] = f_get_rs_data(f_safe_ticker(ticker_3), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_4, rs_m1_4, rs_m3_4, rs_m6_4] = f_get_rs_data(f_safe_ticker(ticker_4), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_5, rs_m1_5, rs_m3_5, rs_m6_5] = f_get_rs_data(f_safe_ticker(ticker_5), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_6, rs_m1_6, rs_m3_6, rs_m6_6] = f_get_rs_data(f_safe_ticker(ticker_6), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_7, rs_m1_7, rs_m3_7, rs_m6_7] = f_get_rs_data(f_safe_ticker(ticker_7), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_8, rs_m1_8, rs_m3_8, rs_m6_8] = f_get_rs_data(f_safe_ticker(ticker_8), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_9, rs_m1_9, rs_m3_9, rs_m6_9] = f_get_rs_data(f_safe_ticker(ticker_9), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_10, rs_m1_10, rs_m3_10, rs_m6_10] = f_get_rs_data(f_safe_ticker(ticker_10), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_11, rs_m1_11, rs_m3_11, rs_m6_11] = f_get_rs_data(f_safe_ticker(ticker_11), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_12, rs_m1_12, rs_m3_12, rs_m6_12] = f_get_rs_data(f_safe_ticker(ticker_12), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_13, rs_m1_13, rs_m3_13, rs_m6_13] = f_get_rs_data(f_safe_ticker(ticker_13), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_14, rs_m1_14, rs_m3_14, rs_m6_14] = f_get_rs_data(f_safe_ticker(ticker_14), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)

[rs_w1_15, rs_m1_15, rs_m3_15, rs_m6_15] = f_get_rs_data(f_safe_ticker(ticker_15), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_16, rs_m1_16, rs_m3_16, rs_m6_16] = f_get_rs_data(f_safe_ticker(ticker_16), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_17, rs_m1_17, rs_m3_17, rs_m6_17] = f_get_rs_data(f_safe_ticker(ticker_17), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_18, rs_m1_18, rs_m3_18, rs_m6_18] = f_get_rs_data(f_safe_ticker(ticker_18), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_19, rs_m1_19, rs_m3_19, rs_m6_19] = f_get_rs_data(f_safe_ticker(ticker_19), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_20, rs_m1_20, rs_m3_20, rs_m6_20] = f_get_rs_data(f_safe_ticker(ticker_20), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_21, rs_m1_21, rs_m3_21, rs_m6_21] = f_get_rs_data(f_safe_ticker(ticker_21), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_22, rs_m1_22, rs_m3_22, rs_m6_22] = f_get_rs_data(f_safe_ticker(ticker_22), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_23, rs_m1_23, rs_m3_23, rs_m6_23] = f_get_rs_data(f_safe_ticker(ticker_23), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_24, rs_m1_24, rs_m3_24, rs_m6_24] = f_get_rs_data(f_safe_ticker(ticker_24), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_25, rs_m1_25, rs_m3_25, rs_m6_25] = f_get_rs_data(f_safe_ticker(ticker_25), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_26, rs_m1_26, rs_m3_26, rs_m6_26] = f_get_rs_data(f_safe_ticker(ticker_26), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_27, rs_m1_27, rs_m3_27, rs_m6_27] = f_get_rs_data(f_safe_ticker(ticker_27), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_28, rs_m1_28, rs_m3_28, rs_m6_28] = f_get_rs_data(f_safe_ticker(ticker_28), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_29, rs_m1_29, rs_m3_29, rs_m6_29] = f_get_rs_data(f_safe_ticker(ticker_29), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_30, rs_m1_30, rs_m3_30, rs_m6_30] = f_get_rs_data(f_safe_ticker(ticker_30), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_31, rs_m1_31, rs_m3_31, rs_m6_31] = f_get_rs_data(f_safe_ticker(ticker_31), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_32, rs_m1_32, rs_m3_32, rs_m6_32] = f_get_rs_data(f_safe_ticker(ticker_32), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_33, rs_m1_33, rs_m3_33, rs_m6_33] = f_get_rs_data(f_safe_ticker(ticker_33), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_34, rs_m1_34, rs_m3_34, rs_m6_34] = f_get_rs_data(f_safe_ticker(ticker_34), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)
[rs_w1_35, rs_m1_35, rs_m3_35, rs_m6_35] = f_get_rs_data(f_safe_ticker(ticker_35), calc_tf, rs_length_w1, rs_length_m1, rs_length_m3, rs_length_m6, rs_benchmark)


// ==========================================
// [5] Drawing Logic
// ==========================================
tablePos = switch posTable
    'Top Left'     => position.top_left
    'Top Right'    => position.top_right
    'Center Left'  => position.middle_left
    'Center Center'=> position.middle_center
    'Center Right' => position.middle_right
    'Bottom Left'  => position.bottom_left
    'Bottom Right' => position.bottom_right

tsize = switch tbl_size
    "Tiny"   => size.tiny
    "Small"  => size.small
    "Normal" => size.normal
    "Large"  => size.large

var table t = na


if barstate.islast
    array.clear(ticker_names_data)
    array.clear(rs_w1_data)
    array.clear(rs_m1_data)
    array.clear(rs_m3_data)
    array.clear(rs_m6_data)
    array.clear(rs_avg_data)

    ticker_symbols = array.from(ticker_1, ticker_2, ticker_3, ticker_4, ticker_5, ticker_6, ticker_7, ticker_8, ticker_9, ticker_10, ticker_11, ticker_12, ticker_13, ticker_14, ticker_15, ticker_16, ticker_17, ticker_18, ticker_19, ticker_20, ticker_21, ticker_22, ticker_23, ticker_24, ticker_25, ticker_26, ticker_27, ticker_28, ticker_29, ticker_30, ticker_31, ticker_32, ticker_33, ticker_34, ticker_35)
    is_set_flags = array.from(is_set_1, is_set_2, is_set_3, is_set_4, is_set_5, is_set_6, is_set_7, is_set_8, is_set_9, is_set_10, is_set_11, is_set_12, is_set_13, is_set_14, is_set_15, is_set_16, is_set_17, is_set_18, is_set_19, is_set_20, is_set_21, is_set_22, is_set_23, is_set_24, is_set_25, is_set_26, is_set_27, is_set_28, is_set_29, is_set_30, is_set_31, is_set_32, is_set_33, is_set_34, is_set_35)

    rs_w1_values = array.from(rs_w1_1, rs_w1_2, rs_w1_3, rs_w1_4, rs_w1_5, rs_w1_6, rs_w1_7, rs_w1_8, rs_w1_9, rs_w1_10, rs_w1_11, rs_w1_12, rs_w1_13, rs_w1_14, rs_w1_15, rs_w1_16, rs_w1_17, rs_w1_18, rs_w1_19, rs_w1_20, rs_w1_21, rs_w1_22, rs_w1_23, rs_w1_24, rs_w1_25, rs_w1_26, rs_w1_27, rs_w1_28, rs_w1_29, rs_w1_30, rs_w1_31, rs_w1_32, rs_w1_33, rs_w1_34, rs_w1_35)

    rs_m1_values = array.from(rs_m1_1, rs_m1_2, rs_m1_3, rs_m1_4, rs_m1_5, rs_m1_6, rs_m1_7, rs_m1_8, rs_m1_9, rs_m1_10, rs_m1_11, rs_m1_12, rs_m1_13, rs_m1_14, rs_m1_15, rs_m1_16, rs_m1_17, rs_m1_18, rs_m1_19, rs_m1_20, rs_m1_21, rs_m1_22, rs_m1_23, rs_m1_24, rs_m1_25, rs_m1_26, rs_m1_27, rs_m1_28, rs_m1_29, rs_m1_30, rs_m1_31, rs_m1_32, rs_m1_33, rs_m1_34, rs_m1_35)
    rs_m3_values = array.from(rs_m3_1, rs_m3_2, rs_m3_3, rs_m3_4, rs_m3_5, rs_m3_6, rs_m3_7, rs_m3_8, rs_m3_9, rs_m3_10, rs_m3_11, rs_m3_12, rs_m3_13, rs_m3_14, rs_m3_15, rs_m3_16, rs_m3_17, rs_m3_18, rs_m3_19, rs_m3_20, rs_m3_21, rs_m3_22, rs_m3_23, rs_m3_24, rs_m3_25, rs_m3_26, rs_m3_27, rs_m3_28, rs_m3_29, rs_m3_30, rs_m3_31, rs_m3_32, rs_m3_33, rs_m3_34, rs_m3_35)
    rs_m6_values = array.from(rs_m6_1, rs_m6_2, rs_m6_3, rs_m6_4, rs_m6_5, rs_m6_6, rs_m6_7, rs_m6_8, rs_m6_9, rs_m6_10, rs_m6_11, rs_m6_12, rs_m6_13, rs_m6_14, rs_m6_15, rs_m6_16, rs_m6_17, rs_m6_18, rs_m6_19, rs_m6_20, rs_m6_21, rs_m6_22, rs_m6_23, rs_m6_24, rs_m6_25, rs_m6_26, rs_m6_27, rs_m6_28, rs_m6_29, rs_m6_30, rs_m6_31, rs_m6_32, rs_m6_33, rs_m6_34, rs_m6_35)


    for i = 0 to 34 by 1
        rs_w1_f = array.get(rs_w1_values, i)
        rs_m1_f = array.get(rs_m1_values, i)
        rs_m3_f = array.get(rs_m3_values, i)
        rs_m6_f = array.get(rs_m6_values, i)
        avg_rs = f_calculate_avg_rs(rs_w1_f, rs_m1_f, rs_m3_f, rs_m6_f, show_rs_w1, show_rs_m1, show_rs_m3, show_rs_m6)


        if array.get(is_set_flags, i) and array.get(ticker_symbols, i) != ''
            array.push(ticker_names_data, f_clean_ticker_name(array.get(ticker_symbols, i)))
            array.push(rs_w1_data, rs_w1_f)
            array.push(rs_m1_data, rs_m1_f)
            array.push(rs_m3_data, rs_m3_f)
            array.push(rs_m6_data, rs_m6_f)
            array.push(rs_avg_data, avg_rs)

    array<float> rs_to_sort = switch sort_key_options
        'P1' => rs_w1_data
        'P2' => rs_m1_data
        'P3' => rs_m3_data
        'P4' => rs_m6_data
        'P Avg' => rs_avg_data
        => rs_m1_data
    
    var array<int> sorted_indices = array.new_int()
    if array.size(rs_to_sort) > 0
        sorted_indices := array.sort_indices(array.copy(rs_to_sort), order.descending)

    // Calculate columns
    num_rs_metrics = 0
    if show_rs_w1
        num_rs_metrics += 1

    if show_rs_m1
        num_rs_metrics += 1
    if show_rs_m3
        num_rs_metrics += 1
    if show_rs_m6
        num_rs_metrics += 1
    if show_rs_avg
        num_rs_metrics += 1

    max_cols = math.max(5, 1 + num_rs_metrics)
    
    ticker_col_span = max_cols - num_rs_metrics
    if ticker_col_span < 1
        ticker_col_span := 1


    if na(t)
        t := table.new(tablePos, max_cols, 100, bgcolor=bg_col, border_width=1)
    
    table.clear(t, 0, 0, max_cols-1, 99)


    // PART 1: Core Stats (Balanced)
    adrp_c = show_adrp and not na(arp) ? (arp >= adrp_threshold and arp <= adrp_max ? color_adrp_ok : color_adrp_ng) : txt_col
    wt_c   = is_3wt ? col_3wt_yes : col_3wt_no
    int row = 0

    for c = 0 to max_cols - 1
        table.cell(t, c, 0, '', width=inp_width) 

    if show_empty_row
        table.cell(t, 0, row, '', bgcolor=bg_col)

        table.merge_cells(t, 0, row, max_cols - 1, row)
        row += 1

    // --- Added: Description & Industry ---
    table.cell(t, 0, row, syminfo.description, text_color=txt_col, text_size=tsize, text_halign=text.align_center)
    table.merge_cells(t, 0, row, max_cols - 1, row)
    row += 1
    
    table.cell(t, 0, row, syminfo.industry, text_color=color.new(txt_col, 20), text_size=size.small, text_halign=text.align_center)
    table.merge_cells(t, 0, row, max_cols - 1, row)
    row += 1

    table.cell(t, 0, row, '', bgcolor=bg_col)
    table.merge_cells(t, 0, row, max_cols - 1, row)

    row += 1

    // -------------------------------------

    if show_adrp

        f_draw_stat_row(t, 'ADR %', str.tostring(arp, '0.00') + '%', adrp_c, row, max_cols, txt_col, tsize)
        row += 1 
    if show_zone_21
        f_draw_stat_row(t, 'ATR 21EMA', str.tostring(dist_21_atr, '0.00'), status_color_21, row, max_cols, txt_col, tsize)
        row += 1 
    if show_zone_10w

        f_draw_stat_row(t, 'ATR 10WMA', str.tostring(dist_10w_atr, '0.00'), status_color_10w, row, max_cols, txt_col, tsize)
        row += 1 
    if show_zone_50
        f_draw_stat_row(t, 'ATR 50SMA', str.tostring(dist_50_atr, '0.00'), status_color_50, row, max_cols, txt_col, tsize)
        row += 1
    if show_ema21_low
        color c_low = close < ema21Low ? col_low_stop : col_low_safe
        f_draw_stat_row(t, '21EMA Low', format_price(ema21Low), c_low, row, max_cols, txt_col, tsize)
        row += 1 
    if show_low_pct
        color c_pct = txt_col
        if low_pct < 0
            c_pct := col_pct_minus 
        else if low_pct <= pct_thresh_good
            c_pct := col_pct_good  
        else if low_pct <= pct_thresh_warn
            c_pct := col_pct_warn  
        else
            c_pct := col_pct_bad   
        f_draw_stat_row(t, '21EMA Low %', str.tostring(low_pct, '0.00') + "%", c_pct, row, max_cols, txt_col, tsize)
        row += 1
    if show_3wt
        f_draw_stat_row(t, '3-Weeks Tight', is_3wt ? "YES" : "-", wt_c, row, max_cols, txt_col, tsize)
        row += 1
    if show_atrx
        color atrx_c = txt_col
        if atrx_from_sma50 >= atrx_lvl_11

            atrx_c := color.rgb(215, 35, 35)
        else if atrx_from_sma50 >= atrx_lvl_10
            atrx_c := color.rgb(227, 80, 68)
        else if atrx_from_sma50 >= atrx_lvl_9
            atrx_c := color.rgb(232, 125, 96)
        else if atrx_from_sma50 >= atrx_lvl_8
            atrx_c := color.rgb(241, 160, 107)
        else if atrx_from_sma50 >= atrx_lvl_7
            atrx_c := color.rgb(243, 196, 122)
        f_draw_stat_row(t, 'ATR% 50SMA', str.tostring(atrx_from_sma50, '0.00'), atrx_c, row, max_cols, txt_col, tsize)
        row += 1 
    if show_ipo_date
        f_draw_stat_row(t, 'IPO Timer', str.tostring(ipoSince, '0.0') + 'Y', txt_col, row, max_cols, txt_col, tsize)
        row += 1

    // PART 2: Growth Table
    if show_growth
        if gap_growth > 0
            for r = 0 to gap_growth - 1
                table.cell(t, 0, row + r, '', bgcolor=bg_col)
                table.merge_cells(t, 0, row + r, max_cols - 1, row + r)
            row += gap_growth
        
        table.cell(t, 0, row, '', text_color = color_text_g, text_size = tsize, bgcolor = bg_col, text_halign = text.align_center)
        table.cell(t, 1, row, 'Next', text_color = color_text_g, text_size = tsize, bgcolor = color_est_g, text_halign = text.align_center)
        table.cell(t, 2, row, 'Current', text_color = color_text_g, text_size = tsize, bgcolor = bg_col, text_halign = text.align_center)
        table.cell(t, 3, row, '1Q Ago', text_color = color_text_g, text_size = tsize, bgcolor = bg_col, text_halign = text.align_center)
        table.cell(t, 4, row, '2Q Ago', text_color = color_text_g, text_size = tsize, bgcolor = bg_col, text_halign = text.align_center)
        if max_cols > 5
            table.merge_cells(t, 4, row, max_cols - 1, row)
        row += 1

        table.cell(t, 0, row, 'EPS', text_color = color_text_g, text_size = tsize, text_halign = text.align_center)
        table.cell(t, 1, row, f_s(est_eg), text_color = f_c(est_eg), text_size = tsize, bgcolor = color_est_g, text_halign = text.align_center)
        table.cell(t, 2, row, f_s(eg_0), text_color = f_c(eg_0), text_size = tsize, text_halign = text.align_center)
        table.cell(t, 3, row, f_s(eg_1), text_color = f_c(eg_1), text_size = tsize, text_halign = text.align_center)
        table.cell(t, 4, row, f_s(eg_2), text_color = f_c(eg_2), text_size = tsize, text_halign = text.align_center)
        if max_cols > 5

            table.merge_cells(t, 4, row, max_cols - 1, row)
        row += 1

        table.cell(t, 0, row, 'Sales', text_color = color_text_g, text_size = tsize, text_halign = text.align_center)
        table.cell(t, 1, row, f_s(est_rg), text_color = f_c(est_rg), text_size = tsize, bgcolor = color_est_g, text_halign = text.align_center)
        table.cell(t, 2, row, f_s(rg_0), text_color = f_c(rg_0), text_size = tsize, text_halign = text.align_center)
        table.cell(t, 3, row, f_s(rg_1), text_color = f_c(rg_1), text_size = tsize, text_halign = text.align_center)
        table.cell(t, 4, row, f_s(rg_2), text_color = f_c(rg_2), text_size = tsize, text_halign = text.align_center)
        if max_cols > 5
            table.merge_cells(t, 4, row, max_cols - 1, row)
        row += 1


    // PART 3: RS Table
    if show_rs_table
        if gap_rs > 0
            for r = 0 to gap_rs - 1
                table.cell(t, 0, row + r, '', bgcolor=bg_col)
                table.merge_cells(t, 0, row + r, max_cols - 1, row + r)
            row += gap_rs
        
        rs_fmt = rs_show_decimals ? '0.00' : '0'

        // Header Row
        table.cell(t, 0, row, 'Ticker', text_color = txt_col, bgcolor = bg_col, text_halign = text.align_left, text_size = tsize)
        if ticker_col_span > 1
            table.merge_cells(t, 0, row, ticker_col_span - 1, row)
        
        int rs_col = ticker_col_span

        if show_rs_w1
            is_sort_key = sort_key_options == 'P1' ? '*' : ''
            table.cell(t, rs_col, row, 'RS' + str.tostring(rs_length_w1) + is_sort_key, text_color = txt_col, bgcolor = bg_col, text_halign = text.align_center, text_size = tsize)
            rs_col += 1
        if show_rs_m1

            is_sort_key = sort_key_options == 'P2' ? '*' : ''
            table.cell(t, rs_col, row, 'RS' + str.tostring(rs_length_m1) + is_sort_key, text_color = txt_col, bgcolor = bg_col, text_halign = text.align_center, text_size = tsize)
            rs_col += 1
        if show_rs_m3
            is_sort_key = sort_key_options == 'P3' ? '*' : ''
            table.cell(t, rs_col, row, 'RS' + str.tostring(rs_length_m3) + is_sort_key, text_color = txt_col, bgcolor = bg_col, text_halign = text.align_center, text_size = tsize)
            rs_col += 1
        if show_rs_m6

            is_sort_key = sort_key_options == 'P4' ? '*' : ''
            table.cell(t, rs_col, row, 'RS' + str.tostring(rs_length_m6) + is_sort_key, text_color = txt_col, bgcolor = bg_col, text_halign = text.align_center, text_size = tsize)
            rs_col += 1
        if show_rs_avg
            is_sort_key = sort_key_options == 'P Avg' ? '*' : ''
            table.cell(t, rs_col, row, 'Avg' + is_sort_key, text_color = txt_col, bgcolor = bg_col, text_halign = text.align_center, text_size = tsize)
            rs_col += 1
        
        row += 1

        // Current Ticker
        if show_current_chart_ticker
            current_ticker_name = f_clean_ticker_name(syminfo.tickerid)

            avg_rs_current = f_calculate_avg_rs(rs_w1_current, rs_m1_current, rs_m3_current, rs_m6_current, show_rs_w1, show_rs_m1, show_rs_m3, show_rs_m6)
            
            table.cell(t, 0, row, current_ticker_name, text_color = txt_col, bgcolor = bg_col, text_halign = text.align_left, text_size = tsize)
            if ticker_col_span > 1
                table.merge_cells(t, 0, row, ticker_col_span - 1, row)
            
            rs_col := ticker_col_span


            if show_rs_w1
                cond_c = f_get_rs_color_cond(rs_w1_current)
                c_bg = highlight_mode == 'Background' and not na(cond_c) ? cond_c : bg_col
                c_txt = highlight_mode == 'Text' and not na(cond_c) ? cond_c : txt_col
                table.cell(t, rs_col, row, str.tostring(rs_w1_current, rs_fmt), text_color = c_txt, bgcolor = c_bg, text_halign = text.align_right, text_size = tsize)
                rs_col += 1
            if show_rs_m1
                cond_c = f_get_rs_color_cond(rs_m1_current)
                c_bg = highlight_mode == 'Background' and not na(cond_c) ? cond_c : bg_col
                c_txt = highlight_mode == 'Text' and not na(cond_c) ? cond_c : txt_col
                table.cell(t, rs_col, row, str.tostring(rs_m1_current, rs_fmt), text_color = c_txt, bgcolor = c_bg, text_halign = text.align_right, text_size = tsize)
                rs_col += 1
            if show_rs_m3
                cond_c = f_get_rs_color_cond(rs_m3_current)
                c_bg = highlight_mode == 'Background' and not na(cond_c) ? cond_c : bg_col
                c_txt = highlight_mode == 'Text' and not na(cond_c) ? cond_c : txt_col
                table.cell(t, rs_col, row, str.tostring(rs_m3_current, rs_fmt), text_color = c_txt, bgcolor = c_bg, text_halign = text.align_right, text_size = tsize)
                rs_col += 1
            if show_rs_m6
                cond_c = f_get_rs_color_cond(rs_m6_current)
                c_bg = highlight_mode == 'Background' and not na(cond_c) ? cond_c : bg_col
                c_txt = highlight_mode == 'Text' and not na(cond_c) ? cond_c : txt_col
                table.cell(t, rs_col, row, str.tostring(rs_m6_current, rs_fmt), text_color = c_txt, bgcolor = c_bg, text_halign = text.align_right, text_size = tsize)
                rs_col += 1
            if show_rs_avg
                cond_c = f_get_rs_color_cond(avg_rs_current)
                c_bg = highlight_mode == 'Background' and not na(cond_c) ? cond_c : bg_col
                c_txt = highlight_mode == 'Text' and not na(cond_c) ? cond_c : txt_col
                table.cell(t, rs_col, row, str.tostring(avg_rs_current, rs_fmt), text_color = c_txt, bgcolor = c_bg, text_halign = text.align_right, text_size = tsize)
                rs_col += 1
            row += 1

        // Sorted List
        if array.size(sorted_indices) > 0
            for i = 0 to array.size(sorted_indices) - 1
                idx = array.get(sorted_indices, i)
                
                table.cell(t, 0, row, array.get(ticker_names_data, idx), text_color = txt_col, bgcolor = bg_col, text_halign = text.align_left, text_size = tsize)
                if ticker_col_span > 1
                    table.merge_cells(t, 0, row, ticker_col_span - 1, row)
                
                rs_col := ticker_col_span

                if show_rs_w1
                    val = array.get(rs_w1_data, idx)
                    cond_c = f_get_rs_color_cond(val)
                    c_bg = highlight_mode == 'Background' and not na(cond_c) ? cond_c : bg_col
                    c_txt = highlight_mode == 'Text' and not na(cond_c) ? cond_c : txt_col
                    table.cell(t, rs_col, row, str.tostring(val, rs_fmt), text_color = c_txt, bgcolor = c_bg, text_halign = text.align_right, text_size = tsize)
                    rs_col += 1
                if show_rs_m1
                    val = array.get(rs_m1_data, idx)
                    cond_c = f_get_rs_color_cond(val)
                    c_bg = highlight_mode == 'Background' and not na(cond_c) ? cond_c : bg_col
                    c_txt = highlight_mode == 'Text' and not na(cond_c) ? cond_c : txt_col
                    table.cell(t, rs_col, row, str.tostring(val, rs_fmt), text_color = c_txt, bgcolor = c_bg, text_halign = text.align_right, text_size = tsize)
                    rs_col += 1
                if show_rs_m3
                    val = array.get(rs_m3_data, idx)
                    cond_c = f_get_rs_color_cond(val)
                    c_bg = highlight_mode == 'Background' and not na(cond_c) ? cond_c : bg_col
                    c_txt = highlight_mode == 'Text' and not na(cond_c) ? cond_c : txt_col
                    table.cell(t, rs_col, row, str.tostring(val, rs_fmt), text_color = c_txt, bgcolor = c_bg, text_halign = text.align_right, text_size = tsize)
                    rs_col += 1
                if show_rs_m6

                    val = array.get(rs_m6_data, idx)
                    cond_c = f_get_rs_color_cond(val)
                    c_bg = highlight_mode == 'Background' and not na(cond_c) ? cond_c : bg_col
                    c_txt = highlight_mode == 'Text' and not na(cond_c) ? cond_c : txt_col
                    table.cell(t, rs_col, row, str.tostring(val, rs_fmt), text_color = c_txt, bgcolor = c_bg, text_halign = text.align_right, text_size = tsize)
                    rs_col += 1
                if show_rs_avg
                    val = array.get(rs_avg_data, idx)
                    cond_c = f_get_rs_color_cond(val)
                    c_bg = highlight_mode == 'Background' and not na(cond_c) ? cond_c : bg_col
                    c_txt = highlight_mode == 'Text' and not na(cond_c) ? cond_c : txt_col
                    table.cell(t, rs_col, row, str.tostring(val, rs_fmt), text_color = c_txt, bgcolor = c_bg, text_halign = text.align_right, text_size = tsize)
                    rs_col += 1
                
                row += 1

    if show_empty_row
        table.cell(t, 0, row, '', bgcolor=bg_col)
        table.merge_cells(t, 0, row, max_cols - 1, row)
