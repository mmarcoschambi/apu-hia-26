import sqlite3
conn = sqlite3.connect('data/ticker_cache.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT COUNT(*) as total,
           COUNT(DISTINCT ticker || DATE(date)) as unique_pairs
    FROM ohlcv_cache
    WHERE date LIKE '2025%'
""")

result = cursor.fetchone()
print(f"📊 Registros 2025:")
print(f"   Total: {result[0]:,}")
print(f"   Pares únicos ticker/fecha: {result[1]:,}")
print(f"   Duplicados: {result[0] - result[1]:,}")
print(f"   % duplicado: {(result[0] - result[1])/result[0]*100:.1f}%")

conn.close()
