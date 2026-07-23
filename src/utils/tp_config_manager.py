#!/usr/bin/env python3
"""
TP Configuration Manager
========================
Maneja la comunicación dinámica entre scripts para distribuciones TP óptimas.

Evita hardcodeo al centralizar la configuración TP en un archivo compartido.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


class TPConfigManager:
    """Gestor centralizado de configuraciones TP óptimas."""

    CONFIG_PATH = Path("config/tp_optimal.json")
    PRESETS_PATH = Path("config/tp_presets.json")

    # Distribuciones hardcoded disponibles (fallback)
    FALLBACK_PRESETS = {
        "classic": {"tp1_pct": 0.50, "tp2_pct": 0.30, "runner_pct": 0.20},
        "balanced": {"tp1_pct": 0.33, "tp2_pct": 0.33, "runner_pct": 0.34},
        "aggressive_runner": {"tp1_pct": 0.25, "tp2_pct": 0.30, "runner_pct": 0.45},
        "conservative": {"tp1_pct": 0.40, "tp2_pct": 0.35, "runner_pct": 0.25},
        "extreme": {"tp1_pct": 0.20, "tp2_pct": 0.30, "runner_pct": 0.50},
    }

    PRESETS = FALLBACK_PRESETS

    @classmethod
    def load_presets(cls) -> Dict:
        """Carga presets de tp_presets.json y los valida."""
        if cls.PRESETS_PATH.exists():
            try:
                with open(cls.PRESETS_PATH, "r") as f:
                    presets = json.load(f)
                # Validar la suma de cada preset
                for name, dist in presets.items():
                    tp1 = float(dist.get("tp1_pct", 0.0))
                    tp2 = float(dist.get("tp2_pct", 0.0))
                    runner = float(dist.get("runner_pct", 0.0))
                    if abs(tp1 + tp2 + runner - 1.0) >= 1e-4:
                        raise ValueError(
                            f"Preset '{name}' distribution does not sum to 1.0: "
                            f"{tp1} + {tp2} + {runner} = {tp1 + tp2 + runner}"
                        )
                cls.PRESETS = presets
                return presets
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Error loading {cls.PRESETS_PATH}: {e}. Using fallback presets."
                )
        cls.PRESETS = cls.FALLBACK_PRESETS
        return cls.FALLBACK_PRESETS

    @classmethod
    def get_optimal_tp(cls, preset_name: str = "optimize") -> Optional[Dict]:
        """
        Obtiene distribución TP óptima.

        Args:
            preset_name: Nombre del preset o "optimize" para cargar óptimo guardado

        Returns:
            Dict con tp1_pct, tp2_pct, runner_pct o None si no existe
        """
        cls.load_presets()

        # Si no es optimize, devolver preset
        if preset_name != "optimize":
            val = cls.PRESETS.get(preset_name)
            if val:
                tp1 = float(val.get("tp1_pct", 0.0))
                tp2 = float(val.get("tp2_pct", 0.0))
                runner = float(val.get("runner_pct", 0.0))
                if abs(tp1 + tp2 + runner - 1.0) >= 1e-4:
                    raise ValueError(
                        f"Loaded TP distribution for preset '{preset_name}' does not sum to 1.0: "
                        f"{tp1} + {tp2} + {runner} = {tp1 + tp2 + runner}"
                    )
            return val

        # Si es optimize, intentar cargar óptimo guardado
        if cls.CONFIG_PATH.exists():
            try:
                with open(cls.CONFIG_PATH, "r") as f:
                    config = json.load(f)

                # Verificar que sea reciente (menos de 7 días)
                saved_date = datetime.fromisoformat(
                    config.get("timestamp", "2000-01-01")
                )
                days_old = (datetime.now() - saved_date).days

                if days_old <= 7:
                    tp1 = float(config["tp1_pct"])
                    tp2 = float(config["tp2_pct"])
                    runner = float(config["runner_pct"])
                    if abs(tp1 + tp2 + runner - 1.0) >= 1e-4:
                        raise ValueError(
                            f"Saved optimal TP distribution does not sum to 1.0: "
                            f"{tp1} + {tp2} + {runner} = {tp1 + tp2 + runner}"
                        )
                    return {
                        "tp1_pct": tp1,
                        "tp2_pct": tp2,
                        "runner_pct": runner,
                        "sharpe": config.get("sharpe", 0),
                        "source": f"saved ({days_old}d ago)",
                    }
                else:
                    print(
                        f"[WARN]  Saved TP config is {days_old} days old, consider re-optimizing"
                    )

            except Exception as e:
                print(f"[WARN]  Could not load saved TP config: {e}")

        return None

    @classmethod
    def save_optimal_tp(
        cls,
        tp1_pct: float,
        tp2_pct: float,
        runner_pct: float,
        sharpe: float = 0,
        trades: int = 0,
        source: str = "optimization",
    ):
        """
        Guarda distribución TP óptima para uso futuro.

        Args:
            tp1_pct: Porcentaje TP1
            tp2_pct: Porcentaje TP2
            runner_pct: Porcentaje Runner
            sharpe: Sharpe ratio obtenido
            trades: Número de trades
            source: Fuente de los datos (e.g., "optimize_tp_distributions", "walk_forward")
        """
        if abs(tp1_pct + tp2_pct + runner_pct - 1.0) >= 1e-4:
            raise ValueError(
                f"TP distribution to save does not sum to 1.0: "
                f"{tp1_pct} + {tp2_pct} + {runner_pct} = {tp1_pct + tp2_pct + runner_pct}"
            )

        cls.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

        config = {
            "timestamp": datetime.now().isoformat(),
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "runner_pct": runner_pct,
            "sharpe": sharpe,
            "trades": trades,
            "source": source,
        }

        with open(cls.CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)

        print(
            f"[U+1F4BE] Optimal TP saved: {tp1_pct:.0%}/{tp2_pct:.0%}/{runner_pct:.0%} (Sharpe: {sharpe:.3f})"
        )
        print(f"   Location: {cls.CONFIG_PATH}")

    @classmethod
    def get_all_presets(cls) -> Dict:
        """Devuelve todos los presets disponibles."""
        cls.load_presets()
        return cls.PRESETS.copy()

    @classmethod
    def clear_saved_optimal(cls):
        """Elimina configuración óptima guardada (forzar re-optimización)."""
        if cls.CONFIG_PATH.exists():
            cls.CONFIG_PATH.unlink()
            print(f"[U+1F5D1]  Cleared saved TP config: {cls.CONFIG_PATH}")


# Inicializar
TPConfigManager.load_presets()


# Funciones de conveniencia para uso directo
def get_optimal_tp(preset_name: str = "optimize") -> Optional[Dict]:
    """Wrapper para TPConfigManager.get_optimal_tp"""
    return TPConfigManager.get_optimal_tp(preset_name)


def save_optimal_tp(
    tp1_pct: float,
    tp2_pct: float,
    runner_pct: float,
    sharpe: float = 0,
    trades: int = 0,
    source: str = "optimization",
):
    """Wrapper para TPConfigManager.save_optimal_tp"""
    TPConfigManager.save_optimal_tp(
        tp1_pct, tp2_pct, runner_pct, sharpe, trades, source
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        TPConfigManager.clear_saved_optimal()
    else:
        # Test: Mostrar estado actual
        print("Current TP Configuration Status:")
        print("=" * 50)

        # Presets disponibles
        print("\nAvailable Presets:")
        for name, values in TPConfigManager.PRESETS.items():
            print(
                f"  {name:20s}: {values['tp1_pct']:.0%} / {values['tp2_pct']:.0%} / {values['runner_pct']:.0%}"
            )

        # Configuración óptima guardada
        print("\nSaved Optimal Configuration:")
        optimal = TPConfigManager.get_optimal_tp("optimize")
        if optimal:
            print(
                f"  TP: {optimal['tp1_pct']:.0%} / {optimal['tp2_pct']:.0%} / {optimal['runner_pct']:.0%}"
            )
            print(f"  Sharpe: {optimal.get('sharpe', 'N/A')}")
            print(f"  Source: {optimal.get('source', 'N/A')}")
        else:
            print("  No saved optimal configuration found")
            print("  Run: python3 optimize_tp_distributions.py --mode optimize")
