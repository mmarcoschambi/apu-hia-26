# Plan de despliegue del VPS para Finviz + Telegram

## Resumen
Configurar el VPS solo para el flujo liviano de `Finviz + Telegram`, dejando fuera `paper_local_db.py` y cualquier dependencia de la base pesada local. El VPS quedará con tres jobs de cron en horario `America/New_York`, un entorno Python dedicado en `.venv`, carga explícita de `.env` mediante un wrapper común, y `telegram_bot_listener.py` corriendo 24/7 en `tmux`.

## Cambios de implementación
- Mantener en cron solo estos flujos:
  - `08:30` `scripts/finviz_monitor.py`
  - `08:45` `scripts/paper_demo_telegram.py --telegram`
  - `16:15` `scripts/portfolio_status.py --telegram`
- Excluir `scripts/paper_local_db.py` del VPS por dependencia en BD local pesada.
- Crear `logs/` antes de habilitar cron para evitar fallos silenciosos por redirección.
- Usar `CRON_TZ=America/New_York` en `crontab` para que DST quede resuelto por el sistema.
- No usar `/usr/bin/python3` directo como decisión principal. Crear `.venv` del proyecto y ejecutar todo desde ahí.
- No depender de que cron “vea” `.env` por arte de magia. Crear un wrapper shell común que:
  - haga `cd /home/marcos/trade/momentum-v2`
  - exporte variables desde `.env`
  - ejecute `/home/marcos/trade/momentum-v2/.venv/bin/python ...`
- Usar `tmux` para el listener persistente:
  - sesión `tg_listener`
  - comando `python scripts/telegram_bot_listener.py`
  - operación manual post-reboot, salvo que más adelante se migre a `systemd`

## Interfaces y configuración operativa
- Variables mínimas en `.env`:
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
  - `TELEGRAM_CHAT_ID_MONITOR`
  - `TELEGRAM_CHAT_ID_DEMO`
  - `PAPER_CAPITAL`
  - `MAX_DD_ALERT_PCT`
  - `MIN_PARITY_PCT`
- Caveat importante ya verificado:
  - `scripts/telegram_bot_listener.py` y `scripts/portfolio_status.py` cargan `.env`
  - `scripts/finviz_monitor.py` y `scripts/paper_demo_telegram.py` no hacen `load_dotenv()`
  - por eso el wrapper o `source .env` en cron no es opcional
- Mantener `finviz_monitor.py` como job de premarket por Telegram.
- No usar `live_trading_scanner.py` en este plan del VPS; no forma parte del flujo definitivo que estás aprobando.

## Pruebas y aceptación
- Preparación:
  - verificar que `.venv` exista y tenga dependencias instaladas
  - verificar que `.env` tenga token y chat IDs reales
  - verificar `mkdir -p logs`
- Smoke tests manuales:
  - correr `./run_vps_job.sh scripts/finviz_monitor.py` y confirmar mensaje en chat monitor
  - correr `./run_vps_job.sh scripts/paper_demo_telegram.py --telegram` y confirmar tarjetas en chat demo
  - correr `./run_vps_job.sh scripts/portfolio_status.py --telegram` y confirmar resumen o salida sin error
  - levantar `./run_vps_job.sh scripts/telegram_bot_listener.py` en `tmux` y confirmar que responde a botones/callbacks
- Validación de cron:
  - usar horarios temporales de prueba a 2-3 minutos vista
  - revisar `logs/cron_monitor.log`, `logs/cron_demo_tg.log`, `logs/cron_portfolio.log`
  - confirmar que no hay errores por variables ausentes ni imports faltantes

## Supuestos y defaults
- El VPS no alojará la BD local pesada ni pipelines dependientes de ella.
- El listener quedará en `tmux` por ahora, aceptando reinicio manual tras reboot.
- El proyecto vivirá en `/home/marcos/trade/momentum-v2`.
- La receta final debe usar `.venv` + wrapper con `.env` como estándar operativo del VPS.