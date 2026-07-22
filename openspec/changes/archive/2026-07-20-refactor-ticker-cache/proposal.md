# Proposal: Refactor ticker_cache.py for Ingestion Resilience

## Intent
Implement resilience patterns in `src/data/ticker_cache.py` without breaking financial backtest baselines or corrupting SQLite transaction state.

## Scope
- Inject `@retry` with randomized jitter (`tenacity`) in `update_ohlcv_batch()`.
- Add Dead Letter Queue (DLQ) routing to `data/dlq_failures.json`.
- Confirm and preserve `PRAGMA journal_mode=WAL` for concurrent thread access.

## Rollback Plan
Revert changes to `src/data/ticker_cache.py` via git checkout if `sdd-verify` returns `verdict: fail`.
