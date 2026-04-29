"""
Finviz Universe Provider - Scraping de universe desde Finviz para paper trading.
"""

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


@dataclass
class UniverseFetchResult:
    tickers: list[str]
    provider: str
    fetched_at: str
    pages_ok: int
    raw_rows: int
    parse_warnings: list[str]
    ok: bool
    error: Optional[str] = None


def _build_screener_url(base_url: str, filters: str, sort: str, page: int) -> str:
    """Construye URL del screener con paginación."""
    row_offset = (page - 1) * 20 + 1
    return f"{base_url}?f={filters}&s={sort}&r={row_offset}"


def _fetch_page(
    session: requests.Session, url: str, timeout: int, retries: int
) -> Optional[str]:
    """Descarga una página con retry/backoff."""
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.text
            logger.warning(f"HTTP {response.status_code} para {url}")
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{retries} falló: {e}")
        time.sleep(2**attempt)
    return None


def _parse_tickers_pandas(html: str) -> list[str]:
    """Parsea tickers usando pandas.read_html."""
    try:
        dfs = pd.read_html(StringIO(html))
        best_candidate: list[str] = []
        for df in dfs:
            if "Ticker" in df.columns:
                tickers = (
                    df["Ticker"].dropna().astype(str).str.strip().str.upper().tolist()
                )
                tickers = [
                    t
                    for t in tickers
                    if t and 1 <= len(t) <= 5 and re.match(r"^[A-Z][A-Z0-9-]{0,4}$", t)
                ]
                if len(tickers) > len(best_candidate):
                    best_candidate = tickers
        if best_candidate:
            return [t.replace(".", "-") for t in best_candidate]
        if dfs:
            for df in dfs:
                for col in df.columns:
                    if df[col].dtype == object:
                        vals = df[col].dropna().astype(str)
                        potential = vals[
                            vals.str.match(r"^[A-Z]{1,5}$", na=False)
                        ].tolist()
                        if potential:
                            return [t.replace(".", "-") for t in potential]
    except Exception as e:
        logger.debug(f"pandas parse falló: {e}")
    return []


def _parse_tickers_regex(html: str) -> list[str]:
    """Fallback: parsea tickers con regex desde quote.ashx?t=."""
    pattern = r"quote\.ashx\?t=([A-Z0-9\.\-]{1,10})"
    matches = re.findall(pattern, html)
    unique = []
    seen = set()
    for raw_ticker in matches:
        ticker = _normalize_ticker(raw_ticker)
        if 1 <= len(ticker) <= 5 and ticker not in seen:
            seen.add(ticker)
            unique.append(ticker)
    return unique


def _normalize_ticker(ticker: str) -> str:
    """Normaliza ticker: limpia y estandariza."""
    t = ticker.strip().upper()
    t = t.replace(".", "-")
    t = re.sub(r"[^A-Z\-]", "", t)
    return t


def fetch_finviz_universe(cfg: dict) -> UniverseFetchResult:
    """
    Descarga universe desde Finviz con robust scraping.

    Args:
        cfg: Configuración del provider (finviz section)

    Returns:
        UniverseFetchResult con tickers y metadatos
    """
    finviz_cfg = cfg.get("finviz", {})
    base_url = finviz_cfg.get("base_url", "https://finviz.com/screener.ashx")
    filters = finviz_cfg.get("filters", "cap_midover,sh_avgvol_o1000,sh_price_o10")
    sort = finviz_cfg.get("sort", "relativevolume")
    max_pages = finviz_cfg.get("max_pages", 20)
    timeout = finviz_cfg.get("timeout_sec", 15)
    retries = finviz_cfg.get("retries", 3)
    min_tickers = finviz_cfg.get("min_tickers", 80)

    warnings = []
    all_tickers = set()
    pages_ok = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    session = requests.Session()
    session.headers.update(headers)

    for page in range(1, max_pages + 1):
        url = _build_screener_url(base_url, filters, sort, page)
        html = _fetch_page(session, url, timeout, retries)

        if html is None:
            warnings.append(f"page_{page}_fetch_failed")
            continue

        pages_ok += 1

        tickers_pd = _parse_tickers_pandas(html)
        if not tickers_pd:
            tickers_regex = _parse_tickers_regex(html)
            if tickers_regex:
                all_tickers.update(tickers_regex)
                warnings.append(f"page_{page}_fallback_regex")
            else:
                warnings.append(f"page_{page}_no_tickers_parsed")
        else:
            all_tickers.update(tickers_pd)

    normalized = [_normalize_ticker(t) for t in all_tickers]
    normalized = list(set([t for t in normalized if t and len(t) <= 5]))
    normalized.sort()

    raw_rows = len(all_tickers)

    if len(normalized) < min_tickers:
        return UniverseFetchResult(
            tickers=normalized,
            provider="finviz_scrape",
            fetched_at=datetime.now().isoformat(),
            pages_ok=pages_ok,
            raw_rows=raw_rows,
            parse_warnings=warnings,
            ok=False,
            error=f"insufficient_tickers: {len(normalized)} < {min_tickers}",
        )

    return UniverseFetchResult(
        tickers=normalized,
        provider="finviz_scrape",
        fetched_at=datetime.now().isoformat(),
        pages_ok=pages_ok,
        raw_rows=raw_rows,
        parse_warnings=warnings,
        ok=True,
    )


def load_config() -> dict:
    """Carga configuración del sistema."""
    import json
    from pathlib import Path

    config_path = (
        Path(__file__).parent.parent.parent / "config" / "production_config.json"
    )
    if config_path.exists():
        return json.load(open(config_path))
    return {}


def get_universe() -> UniverseFetchResult:
    """Obtiene universe usando configuración del sistema."""
    cfg = load_config()
    universe_cfg = cfg.get("universe_source", {})

    if not universe_cfg.get("enabled", True):
        return UniverseFetchResult(
            tickers=[],
            provider="disabled",
            fetched_at=datetime.now().isoformat(),
            pages_ok=0,
            raw_rows=0,
            parse_warnings=[],
            ok=False,
            error="provider_disabled",
        )

    return fetch_finviz_universe(universe_cfg)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = get_universe()
    print(f"Ok: {result.ok}")
    print(f"Tickers: {len(result.tickers)}")
    print(f"Error: {result.error}")
    print(f"Warnings: {result.parse_warnings}")
