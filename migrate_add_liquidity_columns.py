#!/usr/bin/env python3
"""
MIGRACIÓN: Agregar Columnas de Liquidez
========================================
Agrega dollar_volume y rolling_dollar_vol_20 a la tabla existente
y recalcula los valores para todos los tickers en cache.
"""

import sqlite3
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

DB_PATH = "data/ticker_cache.db"

def migrate_database():
    """
    Paso 1: Agregar columnas a la tabla
    """
    print("="*80)
    print("  🔧 MIGRACIÓN: Agregando Columnas de Liquidez")
    print("="*80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verificar columnas actuales
    cursor.execute("PRAGMA table_info(ohlcv_cache)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"\n📋 Columnas actuales: {columns}")
    
    # Agregar columnas si no existen
    if 'dollar_volume' not in columns:
        print("\n➕ Agregando columna: dollar_volume")
        cursor.execute("ALTER TABLE ohlcv_cache ADD COLUMN dollar_volume REAL")
        conn.commit()
        print("   ✅ Agregada")
    else:
        print("\n✅ Columna dollar_volume ya existe")
    
    if 'rolling_dollar_vol_20' not in columns:
        print("\n➕ Agregando columna: rolling_dollar_vol_20")
        cursor.execute("ALTER TABLE ohlcv_cache ADD COLUMN rolling_dollar_vol_20 REAL")
        conn.commit()
        print("   ✅ Agregada")
    else:
        print("\n✅ Columna rolling_dollar_vol_20 ya existe")
    
    conn.close()
    print("\n" + "="*80)
    print("  ✅ COLUMNAS AGREGADAS EXITOSAMENTE")
    print("="*80)


def recalculate_liquidity():
    """
    Paso 2: Re-calcular liquidez para todos los tickers
    """
    print("\n" + "="*80)
    print("  📊 RECALCULANDO LIQUIDEZ PARA TODOS LOS TICKERS")
    print("="*80)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Obtener lista de tickers únicos
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ticker FROM ohlcv_cache ORDER BY ticker")
    tickers = [row[0] for row in cursor.fetchall()]
    
    print(f"\n📈 Total tickers en cache: {len(tickers)}")
    print("\n⏳ Procesando...")
    
    updated = 0
    errors = 0
    
    for i, ticker in enumerate(tickers, 1):
        try:
            # Cargar datos del ticker
            query = f"""
                SELECT date, close, volume 
                FROM ohlcv_cache 
                WHERE ticker = '{ticker}'
                ORDER BY date ASC
            """
            df = pd.read_sql_query(query, conn, parse_dates=['date'])
            
            if len(df) == 0:
                continue
            
            # Calcular métricas de liquidez
            df['dollar_volume'] = df['close'] * df['volume']
            df['rolling_dollar_vol_20'] = df['dollar_volume'].rolling(
                window=20, 
                min_periods=1
            ).mean()
            
            # Actualizar cada fila
            for _, row in df.iterrows():
                conn.execute("""
                    UPDATE ohlcv_cache 
                    SET dollar_volume = ?, rolling_dollar_vol_20 = ?
                    WHERE ticker = ? AND date = ?
                """, (
                    float(row['dollar_volume']),
                    float(row['rolling_dollar_vol_20']),
                    ticker,
                    row['date'].strftime('%Y-%m-%d')
                ))
            
            updated += 1
            
            # Progress
            if i % 100 == 0 or i == len(tickers):
                print(f"   {i}/{len(tickers)} - {ticker} ✅")
                conn.commit()  # Commit cada 100
        
        except Exception as e:
            errors += 1
            print(f"   ❌ Error en {ticker}: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*80)
    print("  ✅ RECÁLCULO COMPLETADO")
    print("="*80)
    print(f"\n✅ Actualizados: {updated} tickers")
    if errors > 0:
        print(f"❌ Errores: {errors} tickers")


def verify_migration():
    """
    Paso 3: Verificar que todo funcionó
    """
    print("\n" + "="*80)
    print("  🧪 VERIFICACIÓN DE MIGRACIÓN")
    print("="*80)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Verificar columnas
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(ohlcv_cache)")
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"\n📋 Columnas finales: {columns}")
    
    if 'dollar_volume' in columns and 'rolling_dollar_vol_20' in columns:
        print("   ✅ Ambas columnas presentes")
    else:
        print("   ❌ Faltan columnas!")
        return False
    
    # Verificar datos de muestra
    print("\n📊 Muestra de datos (NVDA últimos 5 días):")
    query = """
        SELECT date, close, volume, dollar_volume, rolling_dollar_vol_20
        FROM ohlcv_cache
        WHERE ticker = 'NVDA'
        ORDER BY date DESC
        LIMIT 5
    """
    df = pd.read_sql_query(query, conn)
    
    if not df.empty:
        print(df.to_string(index=False))
        
        # Verificar que no hay NULLs
        nulls_dv = df['dollar_volume'].isna().sum()
        nulls_rdv = df['rolling_dollar_vol_20'].isna().sum()
        
        print(f"\n📊 Valores NULL:")
        print(f"   dollar_volume: {nulls_dv}")
        print(f"   rolling_dollar_vol_20: {nulls_rdv}")
        
        if nulls_dv == 0 and nulls_rdv == 0:
            print("   ✅ No hay valores NULL")
        else:
            print("   ⚠️  Algunos valores NULL encontrados")
    else:
        print("   ⚠️  No hay datos para NVDA")
    
    # Contar tickers líquidos en fecha específica
    print("\n📈 Tickers líquidos el 2024-01-09 (día NVDA):")
    query = """
        SELECT COUNT(*) as count
        FROM ohlcv_cache
        WHERE date = '2024-01-09'
        AND rolling_dollar_vol_20 >= 15000000
        AND close >= 5
    """
    cursor.execute(query)
    count = cursor.fetchone()[0]
    print(f"   Total: {count} tickers")
    
    if count > 0:
        print("   ✅ Filtro de liquidez funcional")
    else:
        print("   ⚠️  Ningún ticker cumple criterio")
    
    conn.close()
    
    print("\n" + "="*80)
    print("  ✅ VERIFICACIÓN COMPLETADA")
    print("="*80)
    
    return True


def main():
    print("\n" + "="*80)
    print("  🚀 INICIO DE MIGRACIÓN")
    print("="*80)
    print(f"\nBase de datos: {DB_PATH}")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Confirmación
    print("\n⚠️  IMPORTANTE:")
    print("   • Esta operación modificará la base de datos")
    print("   • Se recomienda hacer backup antes")
    print("   • Puede tomar varios minutos")
    
    confirm = input("\n¿Continuar? (s/n): ")
    
    if confirm.lower() != 's':
        print("\n❌ Migración cancelada")
        return
    
    # Ejecutar migración
    try:
        # Paso 1: Agregar columnas
        migrate_database()
        
        # Paso 2: Recalcular datos
        recalculate_liquidity()
        
        # Paso 3: Verificar
        success = verify_migration()
        
        if success:
            print("\n" + "="*80)
            print("  🎉 MIGRACIÓN EXITOSA")
            print("="*80)
            print("\n✅ Ahora puedes usar el filtro de liquidez histórica")
            print("✅ Prueba ejecutando un backtest con SQLite")
            print("\n💡 Próximos pasos:")
            print("   1. Reinicia Streamlit")
            print("   2. Selecciona 'Todo el Mercado (SQLite)'")
            print("   3. Ejecuta backtest")
        else:
            print("\n⚠️  Migración completada con advertencias")
            print("   Revisa los mensajes arriba para detalles")
    
    except Exception as e:
        print(f"\n❌ ERROR EN MIGRACIÓN: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
