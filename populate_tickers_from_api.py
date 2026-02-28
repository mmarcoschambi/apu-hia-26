#!/usr/bin/env python3
"""
POPULATE TICKERS FROM API - Script para poblar la base de datos de tickers desde la API
=======================================================================================
Este script toma la respuesta de la API de Polygon.io y la inserta en la base de datos
de tickers, realizando validaciones típicas como duplicados y manejo de errores.
"""

import sys
import json
import sqlite3
import requests
import logging
from datetime import datetime
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('populate_tickers.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Añadir el directorio raíz al path para importar módulos locales
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.ticker_cache import TickerCache


def fetch_all_tickers_from_api(api_key, limit=1000):
    """
    Obtiene todos los tickers disponibles desde la API de Polygon.io

    Args:
        api_key: Clave de API de Polygon.io
        limit: Límite de resultados por solicitud (máximo 1000)

    Returns:
        Lista de diccionarios con la información de los tickers
    """
    logger.info("📡 Obteniendo tickers desde la API...")

    all_tickers = []
    url = f"https://api.polygon.io/v3/reference/tickers?market=stocks&active=true&order=asc&limit={limit}&sort=ticker&apiKey=hkLqAmt9c0fDTHFr_QU8oo0dEBpPneJl"

    while url:
        try:
            response = requests.get(url)
            response.raise_for_status()

            data = response.json()
            tickers_batch = data.get('results', [])
            all_tickers.extend(tickers_batch)

            logger.info(f"   📥 Recibidos {len(tickers_batch)} tickers (total acumulado: {len(all_tickers)})")

            # Obtener la URL para la siguiente página si existe
            url = data.get('next_url', None)

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error obteniendo datos de la API: {e}")
            break
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error decodificando JSON: {e}")
            break

    logger.info(f"✅ Total de tickers obtenidos: {len(all_tickers)}")
    return all_tickers


def validate_and_clean_tickers(tickers_data):
    """
    Valida y limpia los datos de los tickers

    Args:
        tickers_data: Lista de diccionarios con la información de los tickers

    Returns:
        Lista de tickers válidos y limpios
    """
    logger.info("✅ Validando y limpiando datos de tickers...")

    valid_tickers = []
    invalid_count = 0

    for ticker_info in tickers_data:
        # Validar que tenga los campos necesarios
        if 'ticker' not in ticker_info or not ticker_info['ticker']:
            invalid_count += 1
            continue

        # Limpiar el ticker (remover caracteres especiales, etc.)
        clean_ticker = ticker_info['ticker'].strip().upper().replace('.', '-')

        # Validar formato del ticker (solo letras y guiones)
        if not clean_ticker.isalnum() and not '-' in clean_ticker:
            invalid_count += 1
            continue

        # Crear objeto limpio con solo los campos necesarios
        clean_info = {
            'ticker': clean_ticker,
            'name': ticker_info.get('name', '').strip(),
            'market': ticker_info.get('market', ''),
            'locale': ticker_info.get('locale', ''),
            'primary_exchange': ticker_info.get('primary_exchange', ''),
            'type': ticker_info.get('type', ''),
            'active': ticker_info.get('active', False),
            'currency_name': ticker_info.get('currency_name', ''),
            'cik': ticker_info.get('cik', ''),
            'composite_figi': ticker_info.get('composite_figi', ''),
            'share_class_figi': ticker_info.get('share_class_figi', ''),
            'last_updated_utc': ticker_info.get('last_updated_utc', '')
        }

        valid_tickers.append(clean_info)

    logger.info(f"   ✅ {len(valid_tickers)} tickers válidos")
    logger.info(f"   ❌ {invalid_count} tickers inválidos eliminados")

    return valid_tickers


def get_existing_tickers_from_db(db_path):
    """
    Obtiene los tickers ya existentes en la base de datos

    Args:
        db_path: Ruta a la base de datos SQLite

    Returns:
        Conjunto de tickers existentes
    """
    logger.info("🔍 Obteniendo tickers existentes en la base de datos...")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT ticker FROM universe")
        existing_tickers = {row[0] for row in cursor.fetchall()}
        conn.close()

        logger.info(f"   🗃️  {len(existing_tickers)} tickers encontrados en la base de datos")
        return existing_tickers
    except Exception as e:
        logger.error(f"❌ Error obteniendo tickers existentes: {e}")
        return set()


def filter_new_tickers(valid_tickers, existing_tickers):
    """
    Filtra los tickers para obtener solo los nuevos (no duplicados)

    Args:
        valid_tickers: Lista de tickers válidos
        existing_tickers: Conjunto de tickers ya existentes

    Returns:
        Lista de nuevos tickers que no están en la base de datos
    """
    logger.info("🔍 Filtrando tickers nuevos (eliminando duplicados)...")

    new_tickers = []
    duplicate_count = 0

    for ticker_info in valid_tickers:
        if ticker_info['ticker'] in existing_tickers:
            duplicate_count += 1
        else:
            new_tickers.append(ticker_info)

    logger.info(f"   ➕ {len(new_tickers)} nuevos tickers para insertar")
    logger.info(f"   🚫 {duplicate_count} duplicados encontrados y omitidos")

    return new_tickers


def insert_tickers_to_db(tickers_to_insert, db_path):
    """
    Inserta los nuevos tickers en la base de datos

    Args:
        tickers_to_insert: Lista de tickers a insertar
        db_path: Ruta a la base de datos SQLite

    Returns:
        Número de tickers insertados exitosamente
    """
    print("💾 Insertando nuevos tickers en la base de datos...")

    success_count = 0
    error_count = 0

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Preparar la consulta SQL para evitar inyecciones
        insert_query = '''
            INSERT OR IGNORE INTO universe
            (ticker, name, exchange, sector, industry, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        '''

        # Preparar los datos para inserción masiva
        ticker_records = []
        for ticker_info in tickers_to_insert:
            record = (
                ticker_info['ticker'],
                ticker_info['name'],
                ticker_info.get('primary_exchange', ''),
                ticker_info.get('type', ''),  # Usar 'type' como sector temporalmente
                ticker_info.get('market', ''),  # Usar 'market' como industry temporalmente
                datetime.now().strftime('%Y-%m-%d')
            )
            ticker_records.append(record)

        # Ejecutar inserción masiva
        try:
            cursor.executemany(insert_query, ticker_records)
            conn.commit()
            success_count = cursor.rowcount if cursor.rowcount > 0 else len(ticker_records)

            print(f"   ✅ {success_count} tickers insertados exitosamente")

        except sqlite3.Error as e:
            print(f"   ❌ Error durante la inserción masiva: {e}")
            # Si falla la inserción masiva, intentar una por una
            conn.rollback()
            success_count = 0
            for i, ticker_info in enumerate(tickers_to_insert, 1):
                try:
                    cursor.execute(insert_query, (
                        ticker_info['ticker'],
                        ticker_info['name'],
                        ticker_info.get('primary_exchange', ''),
                        ticker_info.get('type', ''),
                        ticker_info.get('market', ''),
                        datetime.now().strftime('%Y-%m-%d')
                    ))
                    success_count += 1

                    # Mostrar progreso cada 100 inserciones
                    if i % 100 == 0:
                        print(f"   🔄 Procesados: {i}/{len(tickers_to_insert)} ({i/len(tickers_to_insert)*100:.1f}%)")

                except sqlite3.Error as single_error:
                    print(f"   ❌ Error insertando ticker {ticker_info['ticker']}: {single_error}")
                    error_count += 1

            conn.commit()

        conn.close()

        if error_count > 0:
            print(f"   ❌ {error_count} errores durante la inserción")

        return success_count

    except Exception as e:
        print(f"❌ Error general durante la inserción: {e}")
        return 0


def main():
    print("="*80)
    print("  🚀 POPULAR BASE DE DATOS DE TICKERS DESDE API")
    print("="*80)

    # Configuración
    API_KEY = "hkLqAmt9c0fDTHFr_QU8oo0dEBpPneJl"  # Tu clave de API
    DB_PATH = project_root / "data" / "ticker_cache.db"

    print(f"\n🔧 Configuración:")
    print(f"   🗄️  Base de datos: {DB_PATH}")
    print(f"   🌐 API Key: {'*' * len(API_KEY[:-4])}{API_KEY[-4:]}")  # Ocultar parte de la clave

    # Asegurar que el directorio de datos existe
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 1. Obtener tickers de la API
    tickers_data = fetch_all_tickers_from_api(API_KEY, limit=1000)  # Máximo permitido por solicitud

    if not tickers_data:
        logger.error("❌ No se pudieron obtener tickers de la API")
        return

    # 2. Validar y limpiar los datos
    valid_tickers = validate_and_clean_tickers(tickers_data)

    if not valid_tickers:
        logger.error("❌ No hay tickers válidos para procesar")
        return

    # 3. Obtener tickers existentes en la base de datos
    existing_tickers = get_existing_tickers_from_db(DB_PATH)

    # 4. Filtrar nuevos tickers (eliminar duplicados)
    new_tickers = filter_new_tickers(valid_tickers, existing_tickers)

    if not new_tickers:
        logger.info("✅ No hay nuevos tickers para insertar (todos ya existen en la base de datos)")
        return

    # 5. Insertar nuevos tickers en la base de datos
    inserted_count = insert_tickers_to_db(new_tickers, DB_PATH)

    # Resultado final
    print("\n" + "="*80)
    print("  📊 RESULTADO FINAL")
    print("="*80)
    print(f"   📥 Tickers recibidos de la API: {len(tickers_data)}")
    print(f"   ✅ Tickers válidos: {len(valid_tickers)}")
    print(f"   🗃️  Tickers existentes: {len(existing_tickers)}")
    print(f"   ➕ Tickers nuevos a insertar: {len(new_tickers)}")
    print(f"   💾 Tickers insertados exitosamente: {inserted_count}")

    if inserted_count > 0:
        print(f"\n🎉 ¡Base de datos actualizada exitosamente!")
    else:
        print(f"\n⚠️  No se insertaron tickers nuevos.")

    logger.info(f"Proceso completado. Tickers recibidos: {len(tickers_data)}, "
                f"válidos: {len(valid_tickers)}, nuevos insertados: {inserted_count}")


if __name__ == "__main__":
    main()
