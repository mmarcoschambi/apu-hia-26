# VPS Telegram Demo Runbook

## Objetivo
Levantar la etapa intermedia en VPS con:
- `paper_finviz` como radar de research remoto
- `telegram_bot_listener` como proceso persistente
- `paper_demo_telegram` como portfolio demo separado

## Variables `.env`
Mínimas:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID_MONITOR=...
TELEGRAM_CHAT_ID_DEMO=...
```

Opcionales ya existentes:

```env
PAPER_CAPITAL=100000
MAX_DD_ALERT_PCT=33
MIN_PARITY_PCT=80
```

## Comandos manuales
Monitor Finviz:

```bash
python3 scripts/finviz_monitor.py --date 2024-06-17
```

Refresh de candidatos demo:

```bash
python3 scripts/paper_demo_telegram.py --date 2024-06-17
```

Listener persistente:

```bash
python3 scripts/telegram_bot_listener.py
```

Wrappers:

```bash
bash scripts/run_finviz_monitor.sh --date 2024-06-17
bash scripts/run_demo_refresh.sh --date 2024-06-17
bash scripts/run_telegram_listener.sh
```

## Systemd
Archivos de ejemplo:

- `deploy/systemd/telegram-bot-listener.service`
- `deploy/systemd/finviz-monitor.service`

Asumen:

- repo en `/opt/momentum-v2`
- `.env` en `/opt/momentum-v2/.env`
- logs en `/opt/momentum-v2/logs/`

Pasos típicos:

```bash
sudo cp deploy/systemd/telegram-bot-listener.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot-listener
sudo systemctl start telegram-bot-listener
sudo systemctl status telegram-bot-listener
```

## Cron recomendado
Premarket brief:

```cron
0 9 * * 1-5 cd /opt/momentum-v2 && /usr/bin/env bash scripts/run_finviz_monitor.sh >> logs/cron_finviz_monitor.log 2>&1
```

Refresh de candidatos demo:

```cron
5 9 * * 1-5 cd /opt/momentum-v2 && /usr/bin/env bash scripts/run_demo_refresh.sh >> logs/cron_demo_refresh.log 2>&1
```

Pulse intraday:

```cron
0 11,13,15 * * 1-5 cd /opt/momentum-v2 && /usr/bin/env bash scripts/run_finviz_monitor.sh >> logs/cron_intraday_pulse.log 2>&1
```

## Estructura de outputs
Monitor:

- `outputs/telegram_monitor/<date>/market_status.json`
- `outputs/telegram_monitor/<date>/premarket_brief.json`
- `outputs/telegram_monitor/<date>/prealerts.json`
- `outputs/telegram_monitor/<date>/close_summary.json`

Demo:

- `outputs/paper_demo_telegram/runs/<date>/execution_intents.csv`
- `outputs/paper_demo_telegram/runs/<date>/execution_intents.jsonl`
- `outputs/paper_demo_telegram/runs/<date>/orders.csv`
- `outputs/paper_demo_telegram/runs/<date>/fills.csv`
- `outputs/paper_demo_telegram/runs/<date>/positions.csv`
- `outputs/paper_demo_telegram/runs/<date>/telegram_events.jsonl`
- `outputs/paper_demo_telegram/runs/<date>/decision_audit.jsonl`
- `outputs/paper_demo_telegram/runs/<date>/portfolio_state.json`
- `outputs/paper_demo_telegram/runs/<date>/run_report.json`

## Tres mundos
- `local_db`: estudio canónico local, comparación con WF, fuera del VPS
- `paper_finviz`: radar/research remoto
- `paper_demo_telegram`: demo operativo del flujo futuro broker

## Troubleshooting rápido
- Si el bot no responde:
  - revisar `TELEGRAM_BOT_TOKEN`
  - revisar `TELEGRAM_CHAT_ID_MONITOR` y `TELEGRAM_CHAT_ID_DEMO`
  - revisar `outputs/telegram_state/updates_offset.json`
- Si Finviz no genera señales:
  - revisar `outputs/paper_finviz/<date>/snapshot.json`
  - revisar warnings de parseo en `market_status.json`
- Si `/signals` no muestra candidatos demo:
  - correr `scripts/paper_demo_telegram.py --date <fecha>`
  - verificar `execution_intents.csv`
- Si approve/reject no persiste:
  - revisar `telegram_events.jsonl`
  - revisar `decision_audit.jsonl`
  - revisar `portfolio_state.json`
