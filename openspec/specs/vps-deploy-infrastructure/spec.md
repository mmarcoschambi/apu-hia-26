# VPS Deploy Infrastructure Specification

## Purpose

Harden VPS deployment with systemd service units, PID-based lifecycle management, health monitoring, and deploy validation. Replace fragile `pkill -f` with supervised process control.

## Requirements

### Requirement: VPS-REQ-01 — systemd Service Units

The system SHALL provide two systemd service units: `momentum-trader.service` (Streamlit app + scanner loop) and `momentum-telegram.service` (Telegram bot). Both units SHALL use `Restart=always` and `RestartSec=10`. Service unit files SHALL be located at `/etc/systemd/system/` after deploy.

| Field | momentum-trader.service | momentum-telegram.service |
|-------|------------------------|---------------------------|
| ExecStart | `start_live_session.sh --headless` | `python3 -m src.paper.telegram_bot` |
| WorkingDirectory | `/opt/momentum-v2` | `/opt/momentum-v2` |
| Restart | always | always |
| RestartSec | 10 | 10 |
| User | momentum | momentum |

#### Scenario: Service start and restart
- GIVEN systemd units are installed
- WHEN `systemctl start momentum-trader` is issued
- THEN the process SHALL start under systemd supervision
- AND when the process crashes, systemd SHALL auto-restart it within 10 seconds

### Requirement: VPS-REQ-02 — PID-Based Lifecycle

The system SHALL write PID files to `/var/run/momentum/` for each process. Lifecycle operations (status, stop, restart) MUST use PID files, not `pkill -f`. The PID file directory SHALL be created during deploy.

#### Scenario: PID lifecycle
- GIVEN momentum-trader.service is running
- WHEN `/var/run/momentum/trader.pid` is read
- THEN the PID SHALL match the running process
- AND `kill $(cat /var/run/momentum/trader.pid)` SHALL terminate the process cleanly

### Requirement: VPS-REQ-03 — Health Check Endpoint

The system SHALL expose a health check script (`scripts/sv/health_check.sh`) that returns: process running (ok/fail), last trade timestamp, database connection status, and data freshness (minutes since last ohlcv cache update). Exit code 0 = healthy, 1 = degraded, 2 = critical.

#### Scenario: Health check — all healthy
- GIVEN both services are running, DB connected, last trade < 24h ago
- WHEN `health_check.sh` executes
- THEN exit code SHALL be 0
- AND output SHALL contain `PROCESS=running`, `LAST_TRADE=<timestamp>`, `DB=ok`

#### Scenario: Health check — one service down
- GIVEN momentum-trader is running but momentum-telegram is stopped
- WHEN `health_check.sh` executes
- THEN exit code SHALL be 1 (degraded)
- AND output SHALL list the failed service

### Requirement: VPS-REQ-04 — Deploy Validation

The `deploy_vps.sh` script SHALL: verify `git push origin/main` completed (SHA matches local), rsync files to VPS, install/update systemd units, run `health_check.sh --preflight`, and exit with failure if any step fails. The script SHALL NOT proceed if local git status is dirty.

#### Scenario: Clean deploy
- GIVEN local git is clean and `git push` succeeded
- WHEN `deploy_vps.sh` runs
- THEN it SHALL rsync, reload systemd, run preflight
- AND exit with code 0

#### Scenario: Dirty git blocks deploy
- GIVEN local git has uncommitted changes
- WHEN `deploy_vps.sh` runs
- THEN it SHALL exit with code 1 before any rsync
- AND output SHALL indicate "Uncommitted changes — deploy blocked"

### Requirement: VPS-REQ-05 — Environment Configuration

The system SHALL load Telegram tokens and sensitive configuration from `/opt/momentum-v2/.env`. The .env file MUST NOT be committed to git. The systemd unit SHALL use `EnvironmentFile=/opt/momentum-v2/.env`.

#### Scenario: Environment loading
- GIVEN a .env file with `TELEGRAM_BOT_TOKEN=xxx` and `TELEGRAM_CHAT_ID=yyy`
- WHEN momentum-telegram.service starts via systemd
- THEN the bot SHALL have access to these environment variables
- AND `.env` MUST NOT appear in `git status`

### Requirement: VPS-REQ-06 — Monitoring Log

The system SHALL write health check results to `/var/log/momentum/health.log` with ISO timestamps. A log rotation SHALL be configured (max 7 days retention).

#### Scenario: Health logging
- GIVEN a healthy system
- WHEN health check runs every 5 minutes (via systemd timer or cron)
- THEN `/var/log/momentum/health.log` SHALL contain one line per check with timestamp and status
