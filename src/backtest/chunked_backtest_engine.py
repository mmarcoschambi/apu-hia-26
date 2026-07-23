#!/usr/bin/env python3
"""
Chunked Backtest Engine - Para backtests de largo plazo (>1 año)

Divide el período en chunks de tiempo (trimestres/años) y procesa
independientemente para evitar problemas de memoria y rendimiento.

USO:
    engine = ChunkedBacktestEngine(tickers, start_date, end_date, chunk_period='quarter')
    results = engine.run()
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
from src.data.ticker_cache import TickerCache
from src.indicators.indicator_cache import IndicatorCache, PrecomputedIndicators

logger = logging.getLogger(__name__)


class ChunkedBacktestEngine:
    """
    Motor de backtest con chunking temporal para períodos largos.
    """

    def __init__(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000,
        chunk_period: str = "quarter",  # 'month', 'quarter', 'half_year', 'year'
        lookback_days: int = 365,
        offline_mode: bool = True,
        engine_params: Optional[Dict] = None,
    ):
        self.tickers = tickers
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_capital = initial_capital
        self.chunk_period = chunk_period
        self.lookback_days = lookback_days
        self.offline_mode = offline_mode
        self.engine_params = engine_params or {}

        self.cache = TickerCache()
        self.indicator_cache = IndicatorCache()

        # Validar chunk_period
        valid_periods = ["month", "quarter", "half_year", "year"]
        if chunk_period not in valid_periods:
            raise ValueError(f"chunk_period debe ser uno de: {valid_periods}")

        # Generar chunks
        self.chunks = self._generate_chunks()

        logger.info(f"[U+1F4CA] ChunkedBacktestEngine inicializado")
        logger.info(f"   Periodo total: {start_date} a {end_date}")
        logger.info(f"   Chunks {chunk_period}: {len(self.chunks)}")

    def _generate_chunks(self) -> List[Tuple[datetime, datetime]]:
        """Genera chunks de tiempo basados en chunk_period."""
        chunks = []
        current_start = self.start_date

        chunk_days = {
            "month": 30,
            "quarter": 90,
            "half_year": 180,
            "year": 365,
        }[self.chunk_period]

        while current_start < self.end_date:
            current_end = min(current_start + timedelta(days=chunk_days), self.end_date)
            chunks.append((current_start, current_end))
            current_start = current_end + timedelta(days=1)

        return chunks

    def run(self, **backtest_params) -> pd.DataFrame:
        """
        Ejecuta backtest chunked.

        Returns:
            DataFrame con todos los trades del período completo.
        """
        logger.info(f"[U+1F680] Iniciando backtest chunked ({len(self.chunks)} chunks)")
        logger.info(f"   Capital inicial: ${self.initial_capital:,.2f}")

        all_trades = []
        current_capital = self.initial_capital
        chunk_results = []

        for i, (chunk_start, chunk_end) in enumerate(self.chunks):
            logger.info(f"\n{'=' * 60}")
            logger.info(
                f"CHUNK {i + 1}/{len(self.chunks)}: {chunk_start.date()} a {chunk_end.date()}"
            )
            logger.info(f"   Capital actual: ${current_capital:,.2f}")
            logger.info(f"{'=' * 60}")

            # Extender start_date para lookback
            extended_start = chunk_start - timedelta(days=self.lookback_days)

            # Crear engine para este chunk
            chunk_engine = OptimizationEngineTHOR(
                tickers=self.tickers,
                start_date=extended_start.strftime("%Y-%m-%d"),
                end_date=chunk_end.strftime("%Y-%m-%d"),
                initial_capital=current_capital,
                lookback_days=self.lookback_days,
                offline_mode=self.offline_mode,
                **self.engine_params,
            )

            # Ejecutar backtest en este chunk
            try:
                chunk_result = chunk_engine.backtest(backtest_params)

                # Extraer trades del resultado
                if "trades_df" in chunk_result:
                    chunk_trades = chunk_result["trades_df"]
                elif "trades" in chunk_result:
                    chunk_trades = chunk_result["trades"]
                else:
                    logger.warning(f"   No trades found in chunk result")
                    chunk_trades = pd.DataFrame()

                # Filtrar trades que están dentro del chunk (excluir lookback)
                chunk_trades = chunk_trades[
                    chunk_trades["entry_date"] >= chunk_start
                ].copy()

                if not chunk_trades.empty:
                    # Agregar info del chunk
                    chunk_trades["chunk_id"] = i + 1
                    chunk_trades["chunk_start"] = chunk_start.date()
                    chunk_trades["chunk_end"] = chunk_end.date()

                    all_trades.append(chunk_trades)

                    # Calcular capital final del chunk
                    chunk_pnl = chunk_trades["pnl"].sum()
                    current_capital += chunk_pnl

                    logger.info(f"   Trades: {len(chunk_trades)}")
                    logger.info(f"   PnL chunk: ${chunk_pnl:,.2f}")
                    logger.info(f"   Capital final: ${current_capital:,.2f}")

                    chunk_results.append(
                        {
                            "chunk_id": i + 1,
                            "start": chunk_start.date(),
                            "end": chunk_end.date(),
                            "trades": len(chunk_trades),
                            "pnl": chunk_pnl,
                            "capital_start": current_capital - chunk_pnl,
                            "capital_end": current_capital,
                        }
                    )

                    # Liberar memoria del engine
                    del chunk_engine
                    import gc

                    gc.collect()

            except Exception as e:
                logger.error(f"[FAIL] Error en chunk {i + 1}: {e}")
                import traceback

                traceback.print_exc()
                continue

        # Combinar todos los trades
        if all_trades:
            final_df = pd.concat(all_trades, ignore_index=True)
            logger.info(f"\n{'=' * 60}")
            logger.info(f"[OK] BACKTEST COMPLETADO")
            logger.info(f"   Total trades: {len(final_df)}")
            logger.info(f"   Capital final: ${current_capital:,.2f}")
            logger.info(
                f"   Retorno total: {(current_capital / self.initial_capital - 1) * 100:.2f}%"
            )
            logger.info(f"{'=' * 60}")

            # Guardar summary de chunks
            if chunk_results:
                chunk_summary_df = pd.DataFrame(chunk_results)
                chunk_summary_path = "outputs/backtests/chunk_summary.csv"
                chunk_summary_df.to_csv(chunk_summary_path, index=False)
                logger.info(f"[U+1F4C1] Chunk summary guardado: {chunk_summary_path}")

            return final_df
        else:
            logger.warning("[WARN] No se generaron trades en ningún chunk")
            return pd.DataFrame()


class IncrementalBacktestEngine:
    """
    Motor de backtest incremental para actualizar backtests existentes.
    Solo procesa días nuevos desde el último backtest.
    """

    def __init__(
        self,
        tickers: List[str],
        existing_results_path: str,
        offline_mode: bool = True,
    ):
        self.tickers = tickers
        self.existing_results_path = existing_results_path
        self.offline_mode = offline_mode
        self.cache = TickerCache()

        # Cargar resultados existentes
        self.existing_results = pd.read_csv(existing_results_path)
        self.existing_results["entry_date"] = pd.to_datetime(
            self.existing_results["entry_date"]
        )

        # Determinar fecha de inicio incremental
        self.last_date = self.existing_results["entry_date"].max()
        self.start_date = self.last_date + timedelta(days=1)
        self.end_date = datetime.now().date()

        logger.info(f"[U+1F4CA] IncrementalBacktestEngine inicializado")
        logger.info(f"   Última fecha: {self.last_date.date()}")
        logger.info(f"   Nuevos días: {self.start_date.date()} a {self.end_date}")

    def run(self, **backtest_params) -> pd.DataFrame:
        """
        Ejecuta backtest incremental y combina con resultados existentes.
        """
        logger.info(f"[U+1F680] Iniciando backtest incremental")

        # Calcular capital actual desde resultados existentes
        initial_capital = (
            self.existing_results["pnl"].sum() + 100000
        )  # Asumiendo 100k inicial

        # Ejecutar backtest solo para días nuevos
        chunked_engine = ChunkedBacktestEngine(
            tickers=self.tickers,
            start_date=self.start_date.strftime("%Y-%m-%d"),
            end_date=self.end_date.strftime("%Y-%m-%d"),
            initial_capital=initial_capital,
            chunk_period="month",
            offline_mode=self.offline_mode,
        )

        new_trades = chunked_engine.run(**backtest_params)

        # Combinar con resultados existentes
        if not new_trades.empty:
            final_df = pd.concat([self.existing_results, new_trades], ignore_index=True)
            logger.info(f"[OK] Backtest incremental completado")
            logger.info(f"   Trades existentes: {len(self.existing_results)}")
            logger.info(f"   Nuevos trades: {len(new_trades)}")
            logger.info(f"   Total: {len(final_df)}")

            return final_df
        else:
            logger.info("[INFO] No hay nuevos trades que agregar")
            return self.existing_results


if __name__ == "__main__":
    # Ejemplo de uso
    logging.basicConfig(level=logging.INFO)

    tickers = ["NVDA", "TSLA", "AAPL", "MSFT", "GOOGL"]
    start_date = "2022-01-01"
    end_date = "2025-12-31"  # 4 años

    # Ejecutar backtest chunked
    engine = ChunkedBacktestEngine(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        chunk_period="quarter",  # Procesar por trimestres
    )

    results = engine.run()
    print(f"\n[U+1F4CA] Results shape: {results.shape}")
    print(f"[U+1F4CA] Total PnL: ${results['pnl'].sum():,.2f}")
