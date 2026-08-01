"""Tests for earnings enrichment hardening in MarketDataProvider.

Cubre el fix del crash silencioso en Stage-4 (S4 Optuna):
  1. Fallos de yfinance/curl_cffi no propagan excepciones (retorno vacío).
  2. Reintentos acotados con backoff.
  3. Cache negativo en memoria para evitar re-descargas del mismo símbolo.
  4. Cache en memoria acotado (FIFO) para limitar el uso de memoria.
  5. La descarga usa el backend `requests` (sin curl_cffi nativo).
Todos los tests son offline: todo el tráfico de red está mockeado.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from src.data.market_data import MarketDataProvider


@pytest.fixture
def provider(tmp_path):
    """MarketDataProvider aislado: TickerCache y red mockeados."""
    with patch("src.data.market_data.TickerCache") as mock_cache_cls:
        provider = MarketDataProvider(cache_dir=tmp_path)
        mock_cache_cls.assert_called_once()
        provider.sqlite_cache.get_earnings_history.return_value = None
        yield provider


def _earnings_frame() -> pd.DataFrame:
    """DataFrame de earnings realista como lo devuelve yfinance."""
    idx = pd.DatetimeIndex(
        ["2025-01-15", "2025-04-15", "2025-07-15"], tz="UTC", name="Earnings Date"
    )
    return pd.DataFrame(
        {
            "EPS Estimate": [1.0, 2.0, 3.0],
            "Reported EPS": [0.9, 2.1, None],
            "Surprise(%)": [1.0, -1.0, None],
        },
        index=idx,
    )


def _ticker_ok(df: pd.DataFrame) -> MagicMock:
    """Mock de yf.Ticker cuyo atributo earnings_dates devuelve df."""
    ticker = MagicMock()
    ticker.earnings_dates = df
    return ticker


class TestEarningsHardening:
    """Contrato: get_earnings_dates nunca propaga excepciones."""

    @patch("src.data.market_data.time.sleep")
    @patch("src.data.market_data.yf.Ticker")
    def test_download_failure_returns_empty_without_exception(
        self, mock_ticker, mock_sleep, provider
    ):
        """Un fallo de yfinance (red/parseo) retorna DatetimeIndex vacío."""
        mock_ticker.side_effect = RuntimeError("simulated yfinance failure")

        result = provider.get_earnings_dates("ABC")

        assert isinstance(result, pd.DatetimeIndex)
        assert result.empty
        assert mock_ticker.call_count == 3, "debería reintentar 3 veces"

    @patch("src.data.market_data.time.sleep")
    @patch("src.data.market_data.yf.Ticker")
    def test_uses_requests_session_not_curl_cffi(self, mock_ticker, mock_sleep, provider):
        """El Ticker recibe la sesión requests compartida (sin curl_cffi)."""
        mock_ticker.side_effect = RuntimeError("boom")
        provider.get_earnings_dates("ABC")
        session = mock_ticker.call_args[1]["session"]
        assert isinstance(session, requests.Session)

    @patch("src.data.market_data.time.sleep")
    @patch("src.data.market_data.yf.Ticker")
    def test_retry_then_success(self, mock_ticker, mock_sleep, provider):
        """Reintenta tras fallos transitorios y retorna fechas ordenadas."""
        df = _earnings_frame()
        mock_ticker.side_effect = [
            RuntimeError("transient"),
            RuntimeError("transient"),
            _ticker_ok(df),
        ]

        result = provider.get_earnings_dates("ABC")

        assert mock_ticker.call_count == 3
        assert isinstance(result, pd.DatetimeIndex)
        assert len(result) == 3
        assert result[0] < result[-1]
        assert result.tz is None, "fechas devueltas deben ser tz-naive"
        provider.sqlite_cache.save_earnings.assert_called_once()

    @patch("src.data.market_data.time.sleep")
    @patch("src.data.market_data.yf.Ticker")
    def test_negative_cache_prevents_redownload(self, mock_ticker, mock_sleep, provider):
        """Un símbolo fallido no se vuelve a descargar en el mismo proceso."""
        mock_ticker.side_effect = RuntimeError("boom")

        first = provider.get_earnings_dates("ABC")
        second = provider.get_earnings_dates("ABC")

        assert first.empty and second.empty
        assert mock_ticker.call_count == 3, "solo la primera llamada descarga (3 intentos)"

    @patch("src.data.market_data.yf.Ticker")
    def test_sqlite_cache_hit_skips_download(self, mock_ticker, provider):
        """Si SQLite tiene earnings, no se toca la red."""
        cached = pd.DataFrame(
            {"report_date": ["2025-03-01", "2025-06-01", "2025-09-01"]}
        )
        provider.sqlite_cache.get_earnings_history.return_value = cached

        result = provider.get_earnings_dates("ABC")

        assert isinstance(result, (pd.DatetimeIndex, pd.Series))
        assert list(result) == [
            pd.Timestamp("2025-03-01"),
            pd.Timestamp("2025-06-01"),
            pd.Timestamp("2025-09-01"),
        ]
        mock_ticker.assert_not_called()

    @patch("src.data.market_data.yf.Ticker")
    def test_success_is_memory_cached(self, mock_ticker, provider):
        """Tras el primer éxito, las siguientes llamadas no descargan."""
        mock_ticker.return_value = _ticker_ok(_earnings_frame())

        provider.get_earnings_dates("ABC")
        provider.get_earnings_dates("ABC")

        assert mock_ticker.call_count == 1

    @patch("src.data.market_data.yf.Ticker")
    def test_memory_cache_is_bounded(self, mock_ticker, provider):
        """El cache en memoria se desaloja FIFO y no crece sin límite."""
        mock_ticker.side_effect = RuntimeError("boom")
        with patch("src.data.market_data._EARNINGS_CACHE_MAX", 3):
            for i in range(6):
                provider.get_earnings_dates(f"SYM{i}")

        assert len(provider._earnings_cache) <= 3
        assert "SYM0" not in provider._earnings_cache, "entrada más antigua desalojada"
        assert "SYM5" in provider._earnings_cache

    @patch("src.data.market_data.yf.Ticker")
    def test_session_is_reused_across_symbols(self, mock_ticker, provider):
        """Todas las descargas comparten la misma sesión requests."""
        mock_ticker.side_effect = RuntimeError("boom")

        provider.get_earnings_dates("ABC")
        provider.get_earnings_dates("XYZ")

        sessions = {call.kwargs.get("session") for call in mock_ticker.call_args_list}
        assert len(sessions) == 1
        assert provider._earnings_session is not None
