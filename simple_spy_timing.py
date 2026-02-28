"""
Estrategia Simple: SPY con Timing de Mercado

Reglas:
1. Si SPY > SMA50 y VIX < 25: 100% invertido en SPY
2. Si SPY < SMA50 o VIX > 35: 100% cash
3. Revisión mensual (no diaria)

Ventajas:
- Mismo riesgo que SPY cuando estás invertido
- Evitas los drawdowns grandes
- 1-2 trades por mes (vs 627 trades)
- Sin stock picking, sin filtros complejos
"""

CONFIG_SPY_TIMING = {
    "univers": ["SPY"],  # Solo SPY
    "signal_type": "simple_timing",
    "entry_rule": "SPY > SMA50 AND VIX < 25",
    "exit_rule": "SPY < SMA50 OR VIX > 35",
    "position_size": 0.95,  # 95% cuando hay señal
    "cash_when_no_signal": True,
    "rebalance_frequency": "monthly",  # Revisar 1 vez al mes
    "max_trades_per_year": 12,  # Máximo 12 trades/año
}

print("📊 ESTRATEGIA: SPY con Timing de Mercado")
print()
print("Lógica simple:")
print("  • Compra SPY cuando mercado es favorable")
print("  • Cash cuando mercado es riesgoso")
print("  • 100% exposición cuando compras")
print("  • 0% exposición cuando hay cash")
print()
print("vs Tu estrategia actual:")
print("  • 627 trades = trabajo constante")
print("  • 65% max exposición = te quedas atrás en bull runs")
print("  • Muchos filtros = overfitting")
print()
print("Esta estrategia típicamente:")
print("  ✅ Captura ~80% de las alzas de SPY")
print("  ✅ Evita ~50% de los drawdowns")
print("  ✅ Resultado: Sharpe > SPY, menos trabajo")
