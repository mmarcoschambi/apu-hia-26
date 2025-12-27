#!/usr/bin/env python3
"""
Script para obtener los tickers más líquidos según el rolling_dollar_vol_20
"""
import sys
from pathlib import Path

# Añadir el directorio raíz al path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.ticker_cache import TickerCache
from datetime import datetime, timedelta

def get_top_liquidity_tickers(limit=20, min_price=5.0, min_rolling_dollar_vol=15000000):
    """
    Obtiene los tickers más líquidos según el rolling_dollar_vol_20

    Args:
        limit: Número de tickers a retornar
        min_price: Precio mínimo
        min_rolling_dollar_vol: Volumen en dólares mínimo
    """
    cache = TickerCache()

    # Buscar la fecha más reciente con datos disponibles
    print("🔍 Buscando fecha más reciente con datos...")

    # Primero, encontrar la fecha más reciente en la base de datos
    date_query = """
        SELECT DISTINCT date
        FROM ohlcv_cache
        WHERE rolling_dollar_vol_20 IS NOT NULL
        ORDER BY date DESC
        LIMIT 1
    """
    result = cache.conn.execute(date_query).fetchone()

    if result:
        recent_date = result[0]
        print(f"📅 Fecha más reciente encontrada: {recent_date}")

        try:
            # Intentamos obtener tickers con el nuevo filtro de liquidez por fecha
            top_tickers = cache.get_active_tickers(
                sort_by='liquidity',
                limit=limit,
                date_filter=recent_date,
                min_price=min_price,
                min_rolling_dollar_vol=min_rolling_dollar_vol
            )

            print(f"\n🏆 TOP {len(top_tickers)} TICKERS MÁS LÍQUIDOS (Fecha: {recent_date})")
            print("="*60)
            print(f"{'Rank':<4} {'Ticker':<8} {'$Vol 20D (M)':<15}")
            print("-"*60)

            # Para mostrar el volumen, necesitamos consultar directamente la base de datos
            for i, ticker in enumerate(top_tickers, 1):
                # Consultar el rolling_dollar_vol_20 para este ticker en la fecha específica
                query = """
                    SELECT ticker, rolling_dollar_vol_20
                    FROM ohlcv_cache
                    WHERE ticker = ? AND date = ?
                    ORDER BY rolling_dollar_vol_20 DESC
                """
                result = cache.conn.execute(query, (ticker, recent_date)).fetchone()

                if result and result[1] is not None:
                    vol_millions = result[1] / 1_000_000
                    print(f"{i:<4} {result[0]:<8} ${vol_millions:>12.2f}M")
                else:
                    print(f"{i:<4} {ticker:<8} {'N/A':<15}")

            cache.close()
            return top_tickers

        except Exception as e:
            print(f"Error obteniendo tickers por liquidez: {e}")
    else:
        print("⚠️ No se encontraron datos con rolling_dollar_vol_20 en la base de datos")

    # Si falla con date_filter o no hay datos, intentamos con el método anterior
    print("\n📊 Obteniendo top tickers por volumen promedio histórico...")
    try:
        top_tickers = cache.get_active_tickers(sort_by='liquidity', limit=limit)

        print(f"\n🏆 TOP {len(top_tickers)} TICKERS MÁS LÍQUIDOS (Promedio Histórico)")
        print("="*60)
        print(f"{'Rank':<4} {'Ticker':<8} {'$Vol Promedio (M)':<15}")
        print("-"*60)

        # Consultar el volumen promedio para estos tickers
        for i, ticker in enumerate(top_tickers, 1):
            query = """
                SELECT ticker, AVG(close * volume) as avg_dollar_vol
                FROM ohlcv_cache
                WHERE ticker = ? AND close >= ?
                GROUP BY ticker
            """
            result = cache.conn.execute(query, (ticker, min_price)).fetchone()

            if result and result[1] is not None:
                vol_millions = result[1] / 1_000_000
                print(f"{i:<4} {result[0]:<8} ${vol_millions:>12.2f}M")
            else:
                print(f"{i:<4} {ticker:<8} {'N/A':<15}")

        cache.close()
        return top_tickers
    except Exception as e:
        print(f"Error obteniendo tickers por volumen promedio: {e}")
        cache.close()
        return []

def get_top_liquidity_by_date(date_str=None, limit=20, min_price=5.0, min_rolling_dollar_vol=15000000):
    """
    Obtiene los tickers más líquidos para una fecha específica

    Args:
        date_str: Fecha específica en formato 'YYYY-MM-DD' o None para la más reciente
        limit: Número de tickers a retornar
        min_price: Precio mínimo
        min_rolling_dollar_vol: Volumen en dólares mínimo
    """
    cache = TickerCache()

    # Si no se proporciona fecha, encontrar la más reciente
    if date_str is None:
        date_query = """
            SELECT DISTINCT date
            FROM ohlcv_cache
            WHERE rolling_dollar_vol_20 IS NOT NULL
            ORDER BY date DESC
            LIMIT 1
        """
        result = cache.conn.execute(date_query).fetchone()
        if result:
            date_str = result[0]
            print(f"📅 Fecha más reciente encontrada: {date_str}")
        else:
            print("❌ No se encontraron fechas con datos de rolling_dollar_vol_20")
            cache.close()
            return []

    # Consultar tickers líquidos para la fecha específica
    query = """
        SELECT ticker, rolling_dollar_vol_20
        FROM ohlcv_cache
        WHERE date = ? AND close >= ? AND rolling_dollar_vol_20 >= ?
        ORDER BY rolling_dollar_vol_20 DESC
        LIMIT ?
    """

    results = cache.conn.execute(query, (date_str, min_price, min_rolling_dollar_vol, limit)).fetchall()

    print(f"\n🏆 TOP {len(results)} TICKERS MÁS LÍQUIDOS ({date_str})")
    print("="*60)
    print(f"{'Rank':<4} {'Ticker':<8} {'$Vol 20D (M)':<15} {'Precio':<10}")
    print("-"*60)

    for i, (ticker, dollar_vol, *_) in enumerate(results, 1):
        vol_millions = dollar_vol / 1_000_000
        # Obtener el precio actual para esta fecha
        price_query = "SELECT close FROM ohlcv_cache WHERE ticker = ? AND date = ?"
        price_result = cache.conn.execute(price_query, (ticker, date_str)).fetchone()
        price = price_result[0] if price_result else "N/A"
        print(f"{i:<4} {ticker:<8} ${vol_millions:>12.2f}M {price:>9.2f}")

    cache.close()
    return [row[0] for row in results]

if __name__ == "__main__":
    print("🔍 OBTENIENDO TOP DE TICKERS POR LIQUIDEZ...")

    # Primero intentamos con la consulta directa por fecha
    top_tickers = get_top_liquidity_by_date(limit=20)

    if not top_tickers:
        print("\n⚠️ No se encontraron tickers con los criterios de liquidez actuales.")
        print("Intentando con volumen promedio...")
        top_tickers = get_top_liquidity_tickers(limit=20)

    print(f"\n✅ Se encontraron {len(top_tickers)} tickers líquidos")