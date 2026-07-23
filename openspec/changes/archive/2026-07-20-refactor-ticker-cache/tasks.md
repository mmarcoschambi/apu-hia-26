# Tasks: Refactor ticker_cache.py for Resilience

- [x] 1. Refactor `update_ohlcv_batch()` in `src/data/ticker_cache.py` to use `tenacity` retry with exponential jitter.
- [x] 2. Implement DLQ writer to `data/dlq_failures.json` for failed ticker batches.
- [x] 3. Update `live_trading_scanner.py` to drain and retry `data/dlq_failures.json`.
- [x] 4. Confirm `journal_mode=WAL` is preserved on database connection setup.
- [x] 5. Run verification suite via `scripts/sdd_verify_wrapper.py`.
