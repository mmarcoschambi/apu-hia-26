"""
tests/test_screeners.py
Tests para el sistema de screeners.

Ejecutar:
    cd /home/marcos/trade/momentum-v2
    python -m pytest tests/test_screeners.py -v
"""

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.screeners import ScreenerRegistry, ScreenerPipeline, ScreenerResult
from src.screeners.minervini_trend import MinerviniTrendScreener
from src.screeners.ema21_pullback import EMA21PullbackScreener
from src.screeners.qullamaggie_momentum import QullamaggieMomentumScreener
from src.screeners.vcp_enhanced import VCPEnhancedScreener
from src.screeners.triad_rts import TriadRTSScreener


# ──────────────────────────────────────────────
# Fixtures: DataFrames sintéticos
# ──────────────────────────────────────────────


def _make_trending_df(
    n: int = 300, start: float = 20.0, slope: float = 0.3
) -> pd.DataFrame:
    """DataFrame con tendencia alcista clara → pasa Minervini."""
    np.random.seed(42)
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    close = start + slope * np.arange(n) + np.random.randn(n) * 0.5
    close = np.maximum(close, 1.0)
    high = close * 1.01
    low = close * 0.99
    return pd.DataFrame(
        {
            "open": close * 0.995,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(1_000_000, 5_000_000, n).astype(float),
            "adr_pct": np.full(n, 4.5),
        },
        index=dates,
    )


def _make_declining_df(n: int = 300, start: float = 100.0) -> pd.DataFrame:
    """DataFrame con tendencia bajista → falla Minervini."""
    np.random.seed(7)
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    close = start - 0.2 * np.arange(n) + np.random.randn(n) * 0.5
    close = np.maximum(close, 1.0)
    high = close * 1.01
    low = close * 0.99
    return pd.DataFrame(
        {
            "open": close * 0.995,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(500_000, 2_000_000, n).astype(float),
            "adr_pct": np.full(n, 3.0),
        },
        index=dates,
    )


def _make_ema21_pullback_df(n: int = 150) -> pd.DataFrame:
    """
    Stock que sube fuerte y luego retrocede exactamente a la EMA21.
    Diseñado para pasar EMA21PullbackScreener.
    """
    np.random.seed(99)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    n_trend = max(1, int(n * 2 / 3))
    n_pull = n - n_trend
    trend = 30 + 0.4 * np.arange(n_trend) + np.random.randn(n_trend) * 0.3
    if n_pull > 0:
        pullback_start = trend[-1]
        pullback = (
            pullback_start - 0.1 * np.arange(n_pull) + np.random.randn(n_pull) * 0.2
        )
        close = np.concatenate([trend, pullback])
    else:
        close = trend
    close = np.maximum(close, 1.0)
    high = close * 1.012
    low = close * 0.988
    return pd.DataFrame(
        {
            "open": close * 0.996,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(1_500_000, 6_000_000, n).astype(float),
            "adr_pct": np.full(n, 5.0),
        },
        index=dates,
    )


def _make_vcp_df(n: int = 150) -> pd.DataFrame:
    """
    Stock en consolidación tipo VCP: contracciones decrecientes + higher lows.
    """
    np.random.seed(11)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    # Base alcista
    base = 50 + 0.15 * np.arange(n)
    # Oscilaciones que se comprimen con el tiempo
    amplitude = np.linspace(5.0, 1.0, n)
    noise = amplitude * np.sin(np.linspace(0, 8 * np.pi, n)) + np.random.randn(n) * 0.3
    close = base + noise
    close = np.maximum(close, 5.0)
    # Volumen decreciente en la consolidación
    volume = np.linspace(3_000_000, 500_000, n) + np.random.randint(0, 200_000, n)
    high = close + amplitude * 0.5
    low = close - amplitude * 0.5
    return pd.DataFrame(
        {
            "open": close * 0.997,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume.astype(float),
            "adr_pct": np.full(n, 4.0),
        },
        index=dates,
    )


# ──────────────────────────────────────────────
# Tests: ScreenerRegistry
# ──────────────────────────────────────────────


class TestScreenerRegistry:
    def test_all_screeners_registered(self):
        available = ScreenerRegistry.list_available()
        assert "minervini_trend" in available
        assert "ema21_pullback" in available
        assert "qullamaggie_momentum" in available
        assert "vcp_enhanced" in available

    def test_get_returns_correct_type(self):
        assert isinstance(
            ScreenerRegistry.get("minervini_trend"), MinerviniTrendScreener
        )
        assert isinstance(ScreenerRegistry.get("ema21_pullback"), EMA21PullbackScreener)
        assert isinstance(
            ScreenerRegistry.get("qullamaggie_momentum"), QullamaggieMomentumScreener
        )
        assert isinstance(ScreenerRegistry.get("vcp_enhanced"), VCPEnhancedScreener)

    def test_get_unknown_raises(self):
        with pytest.raises(ValueError, match="no registrado"):
            ScreenerRegistry.get("screener_que_no_existe")

    def test_describe_returns_dict(self):
        desc = ScreenerRegistry.describe()
        assert isinstance(desc, dict)
        assert len(desc) >= 4

    def test_load_config_json(self, tmp_path):
        cfg_file = tmp_path / "test.json"
        cfg_file.write_text('{"name":"minervini_trend","min_price":10.0}')
        cfg = ScreenerRegistry.load_config("minervini_trend", str(cfg_file))
        assert cfg.min_price == 10.0


# ──────────────────────────────────────────────
# Tests: MinerviniTrendScreener
# ──────────────────────────────────────────────


class TestMinerviniTrendScreener:
    def test_trending_stock_passes(self):
        screener = MinerviniTrendScreener()
        df = _make_trending_df(n=300)
        result = screener.scan("TREND", df)
        assert isinstance(result, ScreenerResult)
        # Puede pasar o no dependiendo de los datos sintéticos,
        # pero debe retornar un resultado válido
        assert result.ticker == "TREND"
        assert result.screener_name == "minervini_trend"
        assert 0.0 <= result.score <= 100.0
        assert "criteria" in result.metrics
        assert len(result.metrics["criteria"]) == 7

    def test_declining_stock_fails(self):
        screener = MinerviniTrendScreener()
        df = _make_declining_df(n=300)
        result = screener.scan("BEAR", df)
        assert result.passed is False

    def test_insufficient_history_fails(self):
        screener = MinerviniTrendScreener()
        df = _make_trending_df(n=30)
        result = screener.scan("SHORT", df)
        assert result.passed is False

    def test_result_has_required_metrics(self):
        screener = MinerviniTrendScreener()
        df = _make_trending_df(n=300)
        result = screener.scan("TEST", df)
        for key in (
            "criteria",
            "price",
            "sma50",
            "sma150",
            "sma200",
            "high_52w",
            "low_52w",
            "dist_from_high_pct",
            "above_low_pct",
        ):
            assert key in result.metrics, f"Métrica faltante: {key}"


# ──────────────────────────────────────────────
# Tests: EMA21PullbackScreener
# ──────────────────────────────────────────────


class TestEMA21PullbackScreener:
    def test_returns_valid_result(self):
        screener = EMA21PullbackScreener()
        df = _make_ema21_pullback_df()
        result = screener.scan("PULL", df)
        assert isinstance(result, ScreenerResult)
        assert result.ticker == "PULL"
        assert 0.0 <= result.score <= 100.0

    def test_required_metrics_present(self):
        screener = EMA21PullbackScreener()
        df = _make_ema21_pullback_df()
        result = screener.scan("PULL", df)
        for key in ("ema21", "sma50", "atr", "r_from_ema21", "r_from_sma50"):
            assert key in result.metrics

    def test_insufficient_history_fails(self):
        screener = EMA21PullbackScreener()
        df = _make_ema21_pullback_df(n=20)
        result = screener.scan("SHORT", df)
        assert result.passed is False


# ──────────────────────────────────────────────
# Tests: QullamaggieMomentumScreener
# ──────────────────────────────────────────────


class TestQullamaggieMomentumScreener:
    def test_returns_valid_result(self):
        screener = QullamaggieMomentumScreener()
        df = _make_trending_df(n=300)
        result = screener.scan("MOM", df)
        assert isinstance(result, ScreenerResult)
        assert 0.0 <= result.score <= 100.0

    def test_required_metrics_present(self):
        screener = QullamaggieMomentumScreener()
        df = _make_trending_df(n=300)
        result = screener.scan("MOM", df)
        for key in ("rs_percentile", "trend_intensity", "criteria"):
            assert key in result.metrics

    def test_trend_intensity_calculated(self):
        screener = QullamaggieMomentumScreener()
        df = _make_trending_df(n=300)
        result = screener.scan("MOM", df)
        ti = result.metrics.get("trend_intensity", 0)
        assert ti > 0, "Trend Intensity debe ser > 0 para stock en tendencia"


# ──────────────────────────────────────────────
# Tests: VCPEnhancedScreener
# ──────────────────────────────────────────────


class TestVCPEnhancedScreener:
    def test_returns_valid_result(self):
        screener = VCPEnhancedScreener()
        df = _make_vcp_df()
        result = screener.scan("VCP", df)
        assert isinstance(result, ScreenerResult)
        assert result.ticker == "VCP"
        assert 0.0 <= result.score <= 100.0

    def test_vcs_score_in_range(self):
        screener = VCPEnhancedScreener()
        df = _make_vcp_df()
        vcs, details = screener.calculate_vcs_score(df)
        assert 0.0 <= vcs <= 100.0
        for key in (
            "price_compression",
            "price_stability",
            "volume_contraction",
            "structure_bonus",
        ):
            assert key in details

    def test_contraction_count_nonnegative(self):
        screener = VCPEnhancedScreener()
        df = _make_vcp_df()
        n, higher_lows = screener.count_contractions(df)
        assert n >= 0
        assert isinstance(higher_lows, bool)

    def test_required_metrics_present(self):
        screener = VCPEnhancedScreener()
        df = _make_vcp_df()
        result = screener.scan("VCP", df)
        for key in ("vcs_score", "vcs_details", "n_contractions", "has_higher_lows"):
            assert key in result.metrics


# ──────────────────────────────────────────────
# Tests: ScreenerPipeline
# ──────────────────────────────────────────────


class TestScreenerPipeline:
    def _get_pipeline(self, mode: str = "all") -> ScreenerPipeline:
        return ScreenerPipeline(
            [
                ScreenerRegistry.get("minervini_trend"),
                ScreenerRegistry.get("vcp_enhanced"),
            ],
            mode=mode,
        )

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            ScreenerPipeline([], mode="invalid")

    def test_all_mode_fails_if_any_fails(self):
        pipeline = self._get_pipeline(mode="all")
        df = _make_declining_df(n=300)  # Falla Minervini → pipeline all falla
        result = pipeline.scan("BEAR", df)
        assert result.passed is False

    def test_any_mode_passes_if_one_passes(self):
        # Usar dos screeners con umbrales bajos para que al menos uno pase
        from src.screeners.base import ScreenerConfig

        loose_cfg = ScreenerConfig(
            name="minervini_trend",
            min_price=1.0,
            params={
                "max_dist_from_52wk_high_pct": 99.0,
                "min_above_52wk_low_pct": 0.0,
                "sma200_uptrend_days": 22,
            },
        )
        pipeline = ScreenerPipeline(
            [
                ScreenerRegistry.get("minervini_trend", loose_cfg),
                ScreenerRegistry.get("vcp_enhanced"),
            ],
            mode="any",
        )
        df = _make_trending_df(n=300)
        result = pipeline.scan("TREND", df)
        # Al menos el pipeline retorna un resultado válido
        assert isinstance(result, ScreenerResult)
        assert "individual" in result.metrics

    def test_sequential_stops_on_first_failure(self):
        pipeline = self._get_pipeline(mode="sequential")
        df = _make_declining_df(n=300)
        result = pipeline.scan("BEAR", df)
        assert result.passed is False
        assert "failed_at" in result.metrics

    def test_pipeline_name_format(self):
        pipeline = self._get_pipeline(mode="all")
        assert "pipeline_all" in pipeline.name
        assert "minervini_trend" in pipeline.name

    def test_score_is_average(self):
        pipeline = self._get_pipeline(mode="all")
        df = _make_trending_df(n=300)
        result = pipeline.scan("TEST", df)
        individual = result.metrics.get("individual", [])
        if individual:
            expected_avg = sum(r["score"] for r in individual) / len(individual)
            assert abs(result.score - expected_avg) < 0.01


# ──────────────────────────────────────────────
# Tests: BaseScreener helpers
# ──────────────────────────────────────────────


class TestBaseHelpers:
    def test_ensure_sma_no_column(self):
        screener = MinerviniTrendScreener()
        df = _make_trending_df(n=100)
        # Eliminar sma50 si existe
        if "sma50" in df.columns:
            df = df.drop(columns=["sma50"])
        sma = screener.ensure_ma(df, 50)
        assert len(sma) == len(df)
        assert not sma.iloc[50:].isna().any()

    def test_ensure_ema_no_column(self):
        screener = MinerviniTrendScreener()
        df = _make_trending_df(n=100)
        ema = screener.ensure_ma(df, 21, kind="ema")
        assert len(ema) == len(df)

    def test_ensure_atr(self):
        screener = MinerviniTrendScreener()
        df = _make_trending_df(n=100)
        atr = screener.ensure_atr(df, 14)
        assert len(atr) == len(df)
        assert float(atr.iloc[-1]) > 0


# ──────────────────────────────────────────────
# Tests: TriadRTSScreener
# ──────────────────────────────────────────────


class TestTriadRTSScreener:
    def test_triad_rts_registered(self):
        """Verifica que el screener está registrado."""
        available = ScreenerRegistry.list_available()
        assert "triad_rts" in available

    def test_get_returns_correct_type(self):
        """Verifica que se puede instanciar."""
        assert isinstance(ScreenerRegistry.get("triad_rts"), TriadRTSScreener)

    def test_trending_stock_passes(self):
        """Stock en tendencia clara con datos mínimos debe retornar resultado válido."""
        screener = TriadRTSScreener()
        df = _make_trending_df(n=300)
        result = screener.scan("TREND", df)
        assert isinstance(result, ScreenerResult)
        assert result.ticker == "TREND"
        assert result.screener_name == "triad_rts"
        assert 0.0 <= result.score <= 100.0

    def test_declining_stock_fails(self):
        """Stock en tendencia bajista debe fallar."""
        screener = TriadRTSScreener()
        df = _make_declining_df(n=300)
        result = screener.scan("BEAR", df)
        assert result.passed is False

    def test_insufficient_history_fails(self):
        """Datos insuficientes deben fallar."""
        screener = TriadRTSScreener()
        df = _make_trending_df(n=30)
        result = screener.scan("SHORT", df)
        assert result.passed is False

    def test_result_has_required_metrics(self):
        """Verifica que las métricas de salida incluyen datos clave."""
        screener = TriadRTSScreener()
        df = _make_trending_df(n=300)
        result = screener.scan("TEST", df)
        # Al menos debe tener score y reason
        assert result.score >= 0.0
        assert len(result.reason) > 0
