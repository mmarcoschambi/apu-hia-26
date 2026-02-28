import sqlite3
import pandas as pd
from datetime import date
import argparse

def get_nyse_holidays(year):
    """Devuelve los feriados de mercado USA para un año dado (NYSE)."""
    # Lista hardcoded de feriados de mercado USA para precisión absoluta
    fixed_holidays = {
        2018: ["2018-01-01", "2018-01-15", "2018-02-19", "2018-03-30", "2018-05-28", "2018-07-04", "2018-09-03", "2018-11-22", "2018-12-05", "2018-12-25"], # Dec 5: Bush Mourning
        2019: ["2019-01-01", "2019-01-21", "2019-02-18", "2019-04-19", "2019-05-27", "2019-07-04", "2019-09-02", "2019-11-28", "2019-12-25"],
        2020: ["2020-01-01", "2020-01-20", "2020-02-17", "2020-04-10", "2020-05-25", "2020-07-03", "2020-09-07", "2020-11-26", "2020-12-25"],
        2021: ["2021-01-01", "2021-01-18", "2021-02-15", "2021-04-02", "2021-05-31", "2021-07-05", "2021-09-06", "2021-11-25", "2021-12-24"],
        2022: ["2022-01-17", "2022-02-21", "2022-04-15", "2022-05-30", "2022-06-20", "2022-07-04", "2022-09-05", "2022-11-24", "2022-12-26"],
        2023: ["2023-01-02", "2023-01-16", "2023-02-20", "2023-04-07", "2023-05-29", "2023-06-19", "2023-07-04", "2023-09-04", "2023-11-23", "2023-12-25"],
        2024: ["2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25"],
        2025: ["2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25"],
        2026: ["2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"]
    }
    
    return set(fixed_holidays.get(year, []))

def scan_phantom_bars(fix=False):
    print("👻 ESCANEANDO VELAS FANTASMA (PHANTOM BARS)...")
    try:
        conn = sqlite3.connect('data/ticker_cache.db')
    except Exception as e:
        print(f"❌ Error conectando a DB: {e}")
        return

    total_phantoms = 0
    
    # Revisar últimos años
    for year in range(2018, 2027):
        holidays = get_nyse_holidays(year)
        if not holidays: continue
        
        # Formatear para SQL
        holidays_str = "', '".join(holidays)
        query = f"""
            SELECT ticker, date, close, volume 
            FROM ohlcv_cache 
            WHERE date IN ('{holidays_str}')
            ORDER BY date, ticker
        """
        
        try:
            cursor = conn.execute(query)
            phantoms = cursor.fetchall()
            
            if phantoms:
                print(f"\n📅 Año {year}: Encontrados {len(phantoms)} registros en feriados.")
                # Mostrar muestra diversa, priorizando SPY
                spy_phantom = [p for p in phantoms if p[0] == 'SPY']
                if spy_phantom:
                    print(f"   🚨 ALERTA: SPY encontrado en {spy_phantom[0][1]} (Cierre: ${spy_phantom[0][2]:.2f})")
                
                for row in phantoms[:5]: 
                    if row[0] != 'SPY':
                        print(f"   🚩 {row[0]} en {row[1]} (Cierre: ${row[2]:.2f})")
                
                if len(phantoms) > 5:
                    print(f"   ... y {len(phantoms)-5} más.")
                
                total_phantoms += len(phantoms)
                
                if fix:
                    print(f"   🧹 Borrando {len(phantoms)} registros corruptos de {year}...")
                    del_query = f"DELETE FROM ohlcv_cache WHERE date IN ('{holidays_str}')"
                    conn.execute(del_query)
                    conn.commit()
                    print("   ✅ Limpieza completada.")
        except Exception as e:
            print(f"❌ Error consultando {year}: {e}")
    
    conn.close()
    
    if total_phantoms == 0:
        print("\n✅ No se encontraron velas fantasma en feriados conocidos.")
    else:
        print(f"\n⚠️ Total de velas fantasma detectadas: {total_phantoms}")
        if not fix:
            print("💡 Ejecuta el script con '--fix' para eliminarlas automáticamente.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--fix', action='store_true', help='Eliminar registros corruptos encontrados')
    args = parser.parse_args()
    
    scan_phantom_bars(args.fix)
