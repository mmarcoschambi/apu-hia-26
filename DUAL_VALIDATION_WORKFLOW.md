# DUAL VALIDATION WORKFLOW
========================

## Problema Identificado

- **V6_PRO/THOR** (motor rápido): Optimizado para velocidad
- **AdvancedEngine** (motor producción): Todos los filtros y features
- **Convergencia imperfecta**: Resultados pueden divergir hasta 25-30%

## Solución: Validación Dual

En lugar de forzar convergencia 100% (que tomaría días de debugging), usamos workflow pragmático:

```
Walk Forward (V6_PRO) → Top 3 params → Validate (Advanced) → Best params
  [2-4 horas]                           [1 hora]              [Producción]
```

## Ventajas

✅ **No requiere convergencia perfecta** - Los motores pueden divergir
✅ **Params validados en motor final** - Garantiza funcionamiento en producción
✅ **Rápido** - V6_PRO para búsqueda intensiva, Advanced solo para top params
✅ **Robusto** - Params funcionan en AMBOS motores

## Usage

### Quick Test (2-3 horas total)
```bash
bash run_dual_validation.sh --quick
```

- Walk Forward: 2023-2024, 2 ventanas, 20 trials
- Validation: Top 3 configs, 2 años
- Total: ~2-3 horas

### Full Production (6-8 horas total)
```bash
bash run_dual_validation.sh
```

- Walk Forward: 2020-2024, 15 ventanas, 50 trials
- Validation: Top 5 configs, 5 años
- Total: ~6-8 horas

## Workflow Detallado

### STEP 1: Walk Forward Optimization

```bash
python3 walk_forward_validation.py --start 2020-01-01 --end 2024-12-31
```

**Motor usado:** OptimizationEngineV6_PRO
**Velocidad:** 2-3x más rápido que Advanced
**Output:** `outputs/walk_forward_results.json`

### STEP 2: Validate Top Params

```bash
python3 validate_top_params_with_advanced.py --top 3 --period 2020-01-01:2024-12-31
```

**Motor usado:** AdvancedVectorBTEngine (producción)
**Valida:** Top 3 configuraciones en período largo
**Output:** `config/validated_production_params.json`

### STEP 3: Use in Production

Los params en `validated_production_params.json` están garantizados para funcionar con Advanced engine:

```bash
# Live scanning
python3 live_scanner.py --use-validated-params

# Streamlit dashboard
streamlit run app.py
```

## Architetura

```
┌─────────────────────────────────────────────────────────┐
│                DUAL VALIDATION WORKFLOW                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. OPTIMIZATION (Fast)                                 │
│     ┌────────────────────────────────────┐              │
│     │ Walk Forward + V6_PRO/THOR        │              │
│     │ • 15 windows × 50 trials           │              │
│     │ • 2-4 horas                        │              │
│     │ • Encuentra rangos robustos        │              │
│     └────────────────────────────────────┘              │
│                    ↓                                    │
│              Top 3-5 configs                            │
│                    ↓                                    │
│  2. VALIDATION (Precise)                                │
│     ┌────────────────────────────────────┐              │
│     │ Long backtest + Advanced          │              │
│     │ • 5 años × top configs             │              │
│     │ • 1 hora                           │              │
│     │ • Verifica en motor producción     │              │
│     └────────────────────────────────────┘              │
│                    ↓                                    │
│              Best validated params                      │
│                    ↓                                    │
│  3. PRODUCTION                                          │
│     ┌────────────────────────────────────┐              │
│     │ Advanced Engine                    │              │
│     │ • Live trading                     │              │
│     │ • Params probados y validados      │              │
│     └────────────────────────────────────┘              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Convergencia Realista

**NO buscamos convergencia 100%** - Es innecesario y costoso.

**Criterio aceptable:**
- ✅ Trades: diff < 20%
- ✅ Return: diff < 3 puntos porcentuales
- ✅ Mismo signo (no uno gana y otro pierde)
- ✅ Sharpe: diff < 0.5

**La validación dual elimina la necesidad de convergencia perfecta:**
- V6_PRO encuentra rangos de params
- Advanced valida cuáles funcionan en producción
- Usas solo los que pasan ambas validaciones

## Estado Actual

- ✅ Walk Forward configurado con V6_PRO
- ✅ Script de validación creado
- ✅ Workflow completo automatizado
- ⚠️ Convergencia THOR-Advanced ~25% diff (aceptable para validación dual)

## Próximos Pasos

1. Ejecutar workflow completo:
   ```bash
   bash run_dual_validation.sh --quick  # Test rápido (2-3h)
   ```

2. Revisar params recomendados:
   ```bash
   cat config/validated_production_params.json
   ```

3. Si satisfactorio, ejecutar full:
   ```bash
   bash run_dual_validation.sh  # Production (6-8h)
   ```

## Notas

- **V6_PRO** es ~2-3x más rápido (no 100x - marketing)
- **THOR y V6_PRO** son hermanos (~1000 líneas cada uno)
- **Walk Forward YA usa V6_PRO** correctamente
- **No necesitas convergencia perfecta** con este workflow
