# Design: Ingestion Resilience & Self-Healing Pipeline

## Architecture Decisions

### 1. Retry with Jitter (Tenacity)
- Wrap batch download functions in `src/data/ticker_cache.py` with `@retry(wait=wait_random_exponential(min=1, max=10), stop=stop_after_attempt(3))`.
- Prevents API rate-limiting spikes on Finviz and yfinance.

### 2. Dead Letter Queue (DLQ)
- Failed tickers during batch processing write to `data/dlq_failures.json`.
- `live_trading_scanner.py` reads `data/dlq_failures.json` on initialization and retries failed symbols before main scan.

### 3. Concurrency Protection (WAL Mode)
- Verify `PRAGMA journal_mode=WAL` remains active on `sqlite3.connect()` initialization in `ticker_cache.py`.
