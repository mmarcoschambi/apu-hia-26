# Fix: Streamlit Table Sorting Issue

## 🐛 Problema Identificado

Las columnas numéricas con valores positivos y negativos no se ordenaban correctamente al hacer click en los headers de la tabla:

**Columnas afectadas:**
- `position_value` (ej: $5,000, $3,200)
- `monetary_risk` (ej: $100, $250)
- `returns_pct` (ej: +5.2%, -2.4%)
- `r_multiple` (ej: +2.5R, -1.2R)
- `Result` (P/L) (ej: $260.00, -$72.00)

**Comportamiento erróneo:**
- Click en "R Multiple" no ordenaba correctamente
- Valores negativos aparecían en lugares incorrectos
- Solo fechas y símbolos (text) funcionaban bien

## 🔍 Causa Raíz

El código original convertía valores numéricos a strings ANTES de pasarlos a `st.dataframe()`:

```python
# ❌ CÓDIGO ANTERIOR (INCORRECTO)
df_disp['position_value'] = df_disp['position_value'].map('${:,.0f}'.format)
df_disp['monetary_risk'] = df_disp['monetary_risk'].map('${:,.0f}'.format)
df_disp['Result'] = df_disp['Result'].map('${:,.2f}'.format)
df_disp['returns_pct'] = df_disp['returns_pct'].map('{:+.2f}%'.format)
df_disp['r_multiple'] = df_disp['r_multiple'].map('{:+.2f}R'.format)

st.dataframe(df_disp[cols].sort_values('entry_date', ascending=False))
```

**Problema:** `.map(format)` convierte números a strings:
- `2.5` → `"+2.50R"` (string)
- `-1.2` → `"-1.20R"` (string)

El ordenamiento de strings es alfabético, no numérico:
- Alfabético: `"-1.20R"` < `"+2.50R"` < `"+3.10R"` ❌
- Numérico: `-1.2` < `2.5` < `3.1` ✅

## ✅ Solución Implementada

Usar `st.column_config` para formatear la VISUALIZACIÓN sin convertir los datos subyacentes:

```python
# ✅ CÓDIGO NUEVO (CORRECTO)
st.dataframe(
    df_disp[cols].sort_values('entry_date', ascending=False),
    use_container_width=True,
    hide_index=True,
    column_config={
        "symbol": st.column_config.TextColumn("Symbol", width="small"),
        "entry_date": st.column_config.DateColumn("Entry Date", format="YYYY-MM-DD"),
        "days_held": st.column_config.NumberColumn("Days", format="%d"),
        "signal_type": st.column_config.TextColumn("Signal"),
        "shares": st.column_config.NumberColumn("Shares", format="%.2f"),
        "position_value": st.column_config.NumberColumn("Position", format="$%,.0f"),
        "monetary_risk": st.column_config.NumberColumn("Risk", format="$%,.0f"),
        "returns_pct": st.column_config.NumberColumn("Return %", format="%+.2f%%"),
        "r_multiple": st.column_config.NumberColumn("R Multiple", format="%+.2f R"),
        "Result": st.column_config.NumberColumn("P/L", format="$%,.2f")
    }
)
```

## 🎯 Beneficios

1. **Ordenamiento correcto:** Los valores numéricos se ordenan matemáticamente
2. **Formato visual:** La tabla se ve igual (con $, %, R, etc.)
3. **Datos intactos:** Los valores subyacentes siguen siendo numéricos
4. **Interactividad:** Click en cualquier columna ordena correctamente

## 📊 Ejemplo de Ordenamiento

### Por R Multiple (descendente - mejores primero):
```
Symbol  R Multiple  Return %   P/L
NVDA    +3.10 R    +6.20%    $372.00
AAPL    +2.50 R    +5.20%    $260.00
GOOGL   +0.80 R    +1.60%     $72.00
TSLA    -0.50 R    -1.00%    -$25.00
MSFT    -1.20 R    -2.40%    -$72.00
```

### Por R Multiple (ascendente - peores primero):
```
Symbol  R Multiple  Return %   P/L
MSFT    -1.20 R    -2.40%    -$72.00
TSLA    -0.50 R    -1.00%    -$25.00
GOOGL   +0.80 R    +1.60%     $72.00
AAPL    +2.50 R    +5.20%    $260.00
NVDA    +3.10 R    +6.20%    $372.00
```

## 🔧 Formato de Columnas

| Columna | Tipo | Formato | Ejemplo |
|---------|------|---------|---------|
| symbol | Text | - | "AAPL" |
| entry_date | Date | YYYY-MM-DD | "2024-12-15" |
| days_held | Number | %d | 5 |
| shares | Number | %.2f | 10.25 |
| position_value | Number | $%,.0f | $5,000 |
| monetary_risk | Number | $%,.0f | $250 |
| returns_pct | Number | %+.2f%% | +5.20% |
| r_multiple | Number | %+.2f R | +2.50 R |
| Result | Number | $%,.2f | $260.00 |

## 🧪 Testing

El ordenamiento ahora funciona correctamente en todas las columnas numéricas:

✅ Position Value: Ordena por valor monetario
✅ Monetary Risk: Ordena por riesgo
✅ Return %: Ordena correctamente negativos y positivos
✅ R Multiple: Ordena de peor (-) a mejor (+) trade
✅ Result (P/L): Ordena por ganancia/pérdida real

## 📝 Notas Técnicas

- `st.column_config` es la forma recomendada por Streamlit (>= 1.23.0)
- Mantiene tipos de datos originales en el DataFrame
- El formato se aplica solo en la capa de visualización
- Compatible con sorting, filtering, y otras operaciones interactivas

## 🚀 Archivo Modificado

- `app.py` (líneas 275-302)

