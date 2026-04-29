# 🏎️ Ticker Management Guide

## 📋 MÉTODOS PARA AGREGAR TICKERS

### **1. Argumentos CLI** (Más rápido)
```bash
# Agregar 3 tickers directamente
python3 add_tickers_quick.py TSLA META NVDA

# Con opciones
python3 add_tickers_quick.py AAPL MSFT --skip-existing
```

### **2. Lista con --tickers** (Copiar/pegar)
```bash
# Desde string (cualquier formato)
python3 add_tickers_quick.py --tickers "AAPL, MSFT, GOOGL, META"

# Funciona con espacios o comas
python3 add_tickers_quick.py --tickers "AAPL MSFT GOOGL"
```

### **3. Desde Archivo** (Lista grande)
```bash
# Crear archivo con tickers
cat > my_tickers.txt << 'EOL'
# Mi lista de tickers
AAPL
MSFT
GOOGL
META, TSLA, NVDA
EOL

# Cargar desde archivo
python3 add_tickers_quick.py --file my_tickers.txt
```

### **4. Modo Interactivo** ⭐ (Más flexible)
```bash
python3 add_tickers_quick.py --interactive
```
Luego pega tu lista (cualquier formato):
```
AAPL, MSFT, GOOGL
TSLA META
NVDA
```
Presiona **Ctrl+D** (Linux/Mac) o **Ctrl+Z** (Windows) para terminar.

---

## 🎯 EJEMPLOS DE USO COMÚN

### **Agregar Top 10 Tech:**
```bash
python3 add_tickers_quick.py \
  AAPL MSFT GOOGL AMZN META \
  NVDA TSLA AMD INTC QCOM \
  --skip-existing
```

### **Desde lista de Reddit/Twitter:**
```bash
# Copiar la lista → pegar en modo interactivo
python3 add_tickers_quick.py --interactive

# Pegar:
# "I'm bullish on PLTR, HOOD, COIN, SQ"
# → Extrae: PLTR, HOOD, COIN, SQ
```

### **Actualizar tickers existentes:**
```bash
# Sin --skip-existing, actualiza data
python3 add_tickers_quick.py AAPL MSFT --start-date 2024-01-01
```

### **Solo 2024 (testing):**
```bash
python3 add_tickers_quick.py \
  --file new_tickers.txt \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --skip-existing
```

---

## 📁 FORMATOS DE ARCHIVO SOPORTADOS

### **Formato 1: Uno por línea**
```
AAPL
MSFT
GOOGL
```

### **Formato 2: CSV**
```
AAPL, MSFT, GOOGL, META
TSLA, NVDA, AMD
```

### **Formato 3: Mixto con comentarios**
```
# Tech Giants
AAPL MSFT GOOGL

# EV
TSLA, RIVN

# AI
NVDA, AMD, PLTR
```

Todos funcionan con `--file`!

---

## 🔄 WORKFLOW RECOMENDADO

### **Primera vez (Setup inicial):**
```bash
# 1. Poblar lista base (tu lista de 397)
python3 populate_custom_list.py --skip-existing

# 2. Verificar cuántos tienes
python3 -c "
from src.data.ticker_cache import TickerCache
cache = TickerCache()
query = 'SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache'
print(f'Tickers en DB: {cache.conn.execute(query).fetchone()[0]}')
"
```

### **Agregar más después (Dinámico):**
```bash
# Opción A: Directo
python3 add_tickers_quick.py SQ HOOD COIN --skip-existing

# Opción B: Desde archivo
echo "SQ, HOOD, COIN" > new_tickers.txt
python3 add_tickers_quick.py --file new_tickers.txt --skip-existing

# Opción C: Interactivo (copiar/pegar)
python3 add_tickers_quick.py --interactive
# (pega tu lista, Ctrl+D)
```

### **Después de agregar:**
```bash
# Ver tickers disponibles
python3 show_universe.py

# Ejecutar Bugatti con nuevo fold-size
./quick_run_bugatti.sh
```

---

## 🛠️ SCRIPTS AUXILIARES

### **Ver qué tickers tienes:**
```bash
python3 -c "
from src.data.ticker_cache import TickerCache
cache = TickerCache()
query = 'SELECT DISTINCT ticker FROM ohlcv_cache ORDER BY ticker'
tickers = [r[0] for r in cache.conn.execute(query).fetchall()]
print(f'Total: {len(tickers)}\n')
for i, t in enumerate(tickers, 1):
    print(f'{t:6s}', end='  ')
    if i % 10 == 0: print()
"
```

### **Verificar data de un ticker:**
```bash
python3 -c "
from src.data.ticker_cache import TickerCache
ticker = 'AAPL'
cache = TickerCache()
df = cache.get_ohlcv(ticker, '2020-01-01', '2024-12-31', offline=True)
print(f'{ticker}: {len(df)} days')
print(f'Range: {df.index[0]} to {df.index[-1]}')
"
```

### **Eliminar tickers rotos:**
```bash
python3 -c "
from src.data.ticker_cache import TickerCache
cache = TickerCache()
# Eliminar tickers con muy poca data
cache.conn.execute('DELETE FROM ohlcv_cache WHERE ticker IN (SELECT ticker FROM ohlcv_cache GROUP BY ticker HAVING COUNT(*) < 100)')
cache.conn.commit()
print('✅ Cleaned!')
"
```

---

## 📊 COMPARACIÓN DE MÉTODOS

| Método | Velocidad | Flexibilidad | Uso |
|--------|-----------|--------------|-----|
| CLI args | ⚡⚡⚡ | ⭐ | 1-5 tickers |
| --tickers | ⚡⚡ | ⭐⭐ | Lista corta (<20) |
| --file | ⚡⚡ | ⭐⭐⭐ | Lista grande (>50) |
| --interactive | ⚡ | ⭐⭐⭐ | Copy/paste de web |
| populate_custom_list.py | ⚡ | ⭐ | Setup inicial (hardcoded) |

---

## 🎯 TU WORKFLOW IDEAL

```bash
# 1. Setup inicial (una vez)
python3 populate_custom_list.py --skip-existing

# 2. Agregar nuevos (cada semana/mes)
python3 add_tickers_quick.py --interactive

# 3. Ejecutar Bugatti
./quick_run_bugatti.sh

# 4. Repetir paso 2-3 según necesites
```

**"Dinámico = No editar código, solo ejecutar con nuevos inputs"** 🏎️💨
