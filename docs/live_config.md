# VPS Live Configuration & Operational Guide

This document defines the exact live production configuration, active scripts, systemd services, crontab schedules, and synchronization pipelines running on the VPS, resolving **Issue #29**.

---

## 1. System Overview & Architecture

The VPS instance acts as the "Torre de Control" (Control Tower). It runs 24/7 in the GCP zone `us-central1-f` (synchronized with the New York Stock Exchange timezone `America/New_York`).

### Data Flow Diagram

```
[Finviz Monitor Scrape] ---> (outputs/paper_finviz/)
        |
        v
[live_auto_trader.py]   ---> (Telegram alerts & position logs)
        |
        v
[Pre/Post-Market Cron]  ---> (logs/live/ & logs/cron_*)
        |
(Weekly Friday Archive)
        |
        v   (sync_from_vps.sh via SSH/rsync)
[Local Lab Machine]     ---> (outputs/ & logs/vps/)
```

---

## 2. Active Services (Systemd)

The auto-trading and listener bots run as systemd background services managed via `systemctl`:

### A. Live Auto-Trader Service (`momentum-auto.service`)
*   **Path**: `deploy/services/momentum-auto.service`
*   **Description**: Monitors active setups, queries current prices, and executes mock paper trades.
*   **Guardrail**: Requires `LIVE_AUTO_TRADER_ENABLED=1` in the VPS `.env` file to take new positions.
*   **Execution Command**:
    ```bash
    /home/xxmalcomandaxx/swing-momentum-v1/.venv/bin/python scripts/live_auto_trader.py --monitor --interval 1 --telegram
    ```
*   **Logs**: `logs/live/auto_trader.log`

### B. Telegram Bot Listener Service (`momentum-bot.service`)
*   **Path**: `deploy/services/momentum-bot.service`
*   **Description**: Listens for manual queries, status checks, and commands from approved Telegram chat IDs.
*   **Execution Command**:
    ```bash
    /home/xxmalcomandaxx/swing-momentum-v1/.venv/bin/python scripts/telegram_bot_listener.py
    ```
*   **Logs**: `logs/live/telegram_bot.log`

---

## 3. Crontab Schedules (America/New_York)

The cron jobs are configured via `deploy/crontab_vps.txt` to run at scheduled market intervals:

| Time (NY) | Frequency | Target Command / Script | Log Destination | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **08:30** | Mon - Fri | `scripts/finviz_monitor.py` | `logs/cron_pre_market.log` | Scraping setups and prepping premarket briefs. |
| **09:30** | Mon - Fri | `scripts/send_watchlist.py` | `logs/cron_watchlist.log` | Transmitting watchlists to Telegram channel at open. |
| **09:29** | Mon - Fri | `systemctl start finviz-live-promoter` | - | Activating live signals stream for the day. |
| **16:01** | Mon - Fri | `systemctl stop finviz-live-promoter` | - | Halting live signals stream at market close. |
| **16:15** | Mon - Fri | `scripts/send_signal_alerts.py --telegram` | `logs/cron_post_market.log` | Compiling daily summaries and PnL alerts. |
| **17:00** | Friday | `deploy/weekly_archive_vps.sh` | `logs/cron_weekly_archive.log` | Archiving and compressing weekly outputs. |
| **06:00** | Saturday | `find logs -name "*.log" -mtime +30 -delete` | `logs/cron_cleanup.log` | Rotating/clearing logs older than 30 days. |

---

## 4. Local Lab Synchronization

The research machine pulls VPS data down using the [sync_from_vps.sh](file:///home/marcos/trade/momentum-v2/sync_from_vps.sh) script, which runs every Friday at market close.

### Data Synchronized:
1.  **Daily Snapshots**: `outputs/paper_finviz/YYYY-MM-DD/snapshot.json` (daily scrape universe and metrics).
2.  **Telemetry/Alerts**: `outputs/telegram_monitor/` (premarket briefs, prealerts, radar rotation).
3.  **Live Signal Tracking**: `outputs/live_signals/YYYY-MM-DD/rejection_audit.csv` (vital for auditing the sector exclusion and ticker cap).
4.  **Journal logs**: `outputs/paper_finviz/journal.json` (running record of system performance) and `rejected_short_history.json`.
5.  **VPS Config Snapshots**: Saved to `config/vps_snapshot/` to audit config drift between research (Local) and production (VPS).

---

## 5. Cross-Reference & Core Settings

The active strategy settings deployed on the VPS are validated against the parameters audited in [docs/exit_config_audit.md](file:///home/marcos/trade/momentum-v2/docs/exit_config_audit.md):
*   **Active Config Source**: `config/production_config.json`
*   **Primary Sizing**: Dynamic extension sizing (E25) enabled under `tier3_fixed.use_dynamic_extension_sizing`.
*   **Sector Exclusions**: XLV is blacklisted (`exclude_sectors: ["XLV"]`).
*   **Exits & Weights**: TP1 at 1.25R (33% size), TP2 at 3.0R (33% size), and Runner (34% size) managed live (see exit audit for runner trailing stop differences).
