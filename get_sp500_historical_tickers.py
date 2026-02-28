#!/usr/bin/env python3
"""
Script para obtener todos los tickers del S&P 500 desde 2014 hasta la fecha actual.
Lee el archivo histórico y acumula todos los tickers únicos que han formado parte del índice.
"""

import pandas as pd
from pathlib import Path
import sys

def get_all_sp500_tickers_since_year(csv_file_path, start_year=2014):
    """
    Lee el archivo CSV de componentes históricos del S&P 500 y devuelve un conjunto
    de todos los tickers únicos que han estado en el índice desde el start_year.

    Args:
        csv_file_path (str or Path): Ruta al archivo CSV con la historia de componentes.
        start_year (int): Año desde el cual se empieza a acumular tickers.

    Returns:
        set: Conjunto de tickers únicos (sin la fecha de salida).
    """
    try:
        # Leer el archivo CSV
        df = pd.read_csv(csv_file_path)

        # Asegurarse de que la columna 'date' sea tipo datetime
        df['date'] = pd.to_datetime(df['date'])

        # Filtrar filas desde el año de inicio
        df_filtered = df[df['date'].dt.year >= start_year]

        # Extraer todos los tickers únicos de la columna 'tickers' para las filas filtradas
        all_tickers = set()
        for tickers_str in df_filtered['tickers']:
            # Dividir la cadena de tickers por coma
            tickers_list = tickers_str.split(',')
            for ticker_with_date in tickers_list:
                # Limpiar espacios en blanco
                ticker_with_date = ticker_with_date.strip()
                if ticker_with_date:
                    # Separar el ticker de la fecha de salida (si existe)
                    ticker = ticker_with_date.split('-')[0]
                    all_tickers.add(ticker)

        # Remover cadenas vacías o espacios en blanco si existen
        all_tickers = {ticker.strip() for ticker in all_tickers if isinstance(ticker, str) and ticker.strip()}

        return sorted(list(all_tickers)) # Devolver como lista ordenada

    except FileNotFoundError:
        print(f"❌ Error: Archivo no encontrado: {csv_file_path}")
        sys.exit(1)
    except KeyError as e:
        print(f"❌ Error: Columna no encontrada en el CSV: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado leyendo el archivo CSV: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Ruta al archivo histórico dentro del directorio clonado
    csv_path = Path("./sp500/sp500/S&P 500 Historical Components & Changes.csv") # Ajusta si el nombre es diferente
    
    print(f"🔍 Buscando archivo histórico en: {csv_path.absolute()}")
    
    if not csv_path.exists():
        print(f"❌ No se encontró el archivo esperado.")
        print("   Por favor, verifica que hayas clonado el repositorio sp500 correctamente")
        print("   y que el archivo 'S&P 500 Historical Components & Changes.csv' esté presente.")
        sys.exit(1)
    
    print(f"📅 Obteniendo tickers del S&P 500 desde {2014}...")
    tickers = get_all_sp500_tickers_since_year(csv_path, start_year=2014)
    
    print(f"✅ Total de tickers únicos encontrados desde {2014}: {len(tickers)}")
    
    # Mostrar algunos ejemplos
    print("\n📈 Primeros 20 tickers encontrados:")
    for i, ticker in enumerate(tickers[:20]):
        print(f"  - {ticker}")
    
    if len(tickers) > 20:
        print(f"  ... y {len(tickers) - 20} más.")
    
    # Guardar la lista completa en un archivo
    output_file = Path("sp500_tickers_since_2014.txt")
    with open(output_file, 'w') as f:
        for ticker in tickers:
            f.write(f"{ticker}\n")
    
    print(f"\n💾 Lista completa guardada en: {output_file.absolute()}")
    print(f"   El archivo contiene {len(tickers)} tickers, uno por línea.")