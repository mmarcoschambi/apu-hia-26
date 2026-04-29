El Pipeline Cuantitativo Profesional (Tu Nuevo Flujo de Trabajo)

  Etapa 1: La Sandbox (Investigación y Ablation)
  Aquí nacen las ideas. Se vale ensuciarse, pero en un entorno aislado.
   * Herramienta: Scripts como run_walkforward_hybrid.py o notebooks de Jupyter en una carpeta /experiments.
   * Objetivo: Tienes una idea (ej. "¿Qué pasa si exijo que el ADR sea mayor a 1.2% y el RS mayor a 80?"). Usas el script híbrido para probar si el
     concepto crudo tiene Edge (ventaja estadística). No buscas los parámetros perfectos de Take Profit, solo miras si el Win Rate base y el Profit
     Factor mejoran en OOS al aplicar esa regla.
   * Regla de oro: Si la idea no sobrevive aquí con parámetros fijos y simples (ej. salir a los 10 días fijos), se descarta. No intentes arreglar
     una mala idea optimizándola.

  Etapa 2: Integración al Core (El Enchufe)
  La idea demostró valor. Ahora hay que enseñársela a la "Olla Mágica".
   * Herramienta: Editas src/backtest/vectorbt_engine_advanced.py y los archivos de configuración (config/defaults.py).
   * Objetivo: Traducir tu idea ganadora a código oficial.
       * Ejemplo de Filtro: Si el RS > 80 funcionó, te aseguras de que el engine tenga los parámetros use_rs_percentile=True y
         min_rs_percentile=80.0 (¡cosa que ya hicimos hoy!).
       * Ejemplo de Nuevo Patrón (ej. "Pocket Pivot"): Añades la lógica matemática en src/indicators/ y le dices al engine que acepte --signal-type
         pocket_pivot.
   * Regla de oro: NUNCA dupliques el motor completo para probar una idea nueva. Añade Feature Flags (interruptores booleanos como
     use_mi_nueva_idea = True/False). Así mantienes un solo motor mantenible.

  Etapa 3: Optimización y La Guillotina (ResearchGate)
  Aquí es donde separamos la suerte de la verdadera ventaja estadística.
   * Herramienta: optimize_3tier.py.
   * Objetivo: Le dices a Optuna: "Aquí está mi nueva idea integrada. Búscame la mejor forma de gestionarle el riesgo y las salidas (TP1, TP2,
     Runner)".
   * La Guillotina (Fase 4 interna): Una vez que Optuna encuentra los mejores números, entra el ResearchGate (CSCV / Walk-Forward / Stress Test).
     Este paso agarrará tus parámetros "perfectos" y los someterá a comisiones dobles, slippage, y permutaciones matemáticas.
   * Regla de oro: Si el ResearchGate dice REJECTED (PBO > 50%), significa que Optuna hizo curve-fitting (memorizó el pasado). No lo operes en
     Live. Vuelve a la Etapa 1 con una idea diferente. Solo confía en lo que sale como APPROVED.

  Etapa 4: Producción (Live Trading)
  Operativa aburrida, sistemática y matemática.
   * Herramienta: live_trading_scanner.py leyendo FINAL_CONFIG.json.
   * Objetivo: El script de optimización (Etapa 3) escupió un JSON con la "Golden Config" aprobada. Tu escáner en vivo solo lee ese archivo.
   * Regla de oro: En Live Trading no se toca la lógica. El Live Scanner es un robot "tonto" que ejecuta exactamente las reglas matemáticas que la
     Etapa 3 garantizó que son robustas.

  ---

  ¿Cómo aplicar esto HOY a tu "A+B"?

  Para cerrar tu trabajo actual (A+B) con este estándar de oro:

   1. Ya usaste run_walkforward_hybrid.py (Etapa 1) y confirmaste que mezclar el Breakout (A) con el RS (B) es buena idea.
   2. Ya integramos la tabla de RS al Engine (Etapa 2) hoy mismo.
   3. Tu paso inmediato es correr la Etapa 3:

   1     python3 optimize_3tier.py --trials 200 --tickers 300 --start 2019-01-01 --end 2025-06-30 --jobs 4
   4. Siéntate a esperar (puede tardar un par de horas). Si el resultado final del log dice ✅ STRATEGY APPROVED y genera el FINAL_CONFIG.json,
      tienes un sistema institucional listo para imprimir dinero. Si dice ❌ REJECTED, significa que la combinación A+B necesita reglas más
      estrictas (quizás exigir RS > 85 en lugar de 80).

  Manteniendo este flujo estricto (Investigar en aislado -> Integrar al Core -> Someter al Juez -> Pasar a Live), nunca más tendrás código
  duplicado ni dudarás de si estás operando una anomalía estadística o un Edge real.
