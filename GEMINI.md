# Project Instructions: Momentum V2

> Este archivo es leído automáticamente por Gemini. Para el estado completo del sistema, módulos activos,
> baselines de performance y roadmap, consultar `SYSTEM_CONTEXT.md` en la raíz del repositorio.
> Para reglas de comportamiento del agente, convenciones de código y protocolo ScrumBan, consultar `AGENTS.md`.

## Architectural Patterns
- **Signal Engine**: Canonical truth for all signal logic (`src/signals/signal_engine.py`). Shared between live and backtest.
- **Tier 2 Filters**: Multi-layered validation including RS, ADR, Sector ETF, and Thematic Groups.
- **Thematic Divergence**: Variant E (Theme OK, Sector NO) is the current high-conviction filter for swing setups (horizon >= 10 days).

## Environment Separation (Laboratory vs VPS)
The system is **Auto-Aware** of its environment:
- **Laboratory (Local)**: If `data/ticker_cache.db` exists → **Hybrid Mode** (PIT primary, Finviz observation).
- **Torre de Control (VPS)**: No DB → **Finviz Live** promoted to primary decision source for 24/7 monitoring.
- **Deploy to VPS**: `./deploy_vps.sh`
- **Data Sync from VPS**: `./sync_from_vps.sh`

## Session Close Protocol (CRITICAL)
Always output session summaries using the full 11-section unified template defined in Section 9 of AGENTS.md (Goal, Instructions, Discoveries, Accomplished, Next Steps, Relevant Files, 1. Git Range, 2. System State JSON, 3. Decisions Mapped, 4. Statistical Significance, 5. Duplication Check). NEVER truncate after Relevant Files.


