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

    # Distribuciones hardcoded disponibles (fallback)
    PRESETS = {
        "classic": {"tp1_pct": 0.50, "tp2_pct": 0.30, "runner_pct": 0.20},
        "balanced": {"tp1_pct": 0.33, "tp2_pct": 0.33, "runner_pct": 0.34},
        "aggressive_runner": {"tp1_pct": 0.25, "tp2_pct": 0.30, "runner_pct": 0.45},
        "conservative": {"tp1_pct": 0.40, "tp2_pct": 0.35, "runner_pct": 0.25},
        "extreme": {"tp1_pct": 0.20, "tp2_pct": 0.30, "runner_pct": 0.50},
    }

    @classmethod
    def get_optimal_tp(cls, preset_name: str = "optimize") -> Optional[Dict]:
        """
        Obtiene distribución TP óptima.

        Args:
            preset_name: Nombre del preset o "optimize" para cargar óptimo guardado

        Returns:
            Dict con tp1_pct, tp2_pct, runner_pct o None si no existe
        """
        # Si no es optimize, devolver preset hardcoded
        if preset_name != "optimize":
            return cls.PRESETS.get(preset_name)

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
                    return {
                        "tp1_pct": config["tp1_pct"],
                        "tp2_pct": config["tp2_pct"],
                        "runner_pct": config["runner_pct"],
                        "sharpe": config.get("sharpe", 0),
                        "source": f"saved ({days_old}d ago)",
                    }
                else:
                    print(
                        f"⚠️  Saved TP config is {days_old} days old, consider re-optimizing"
                    )

            except Exception as e:
                print(f"⚠️  Could not load saved TP config: {e}")

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
            f"💾 Optimal TP saved: {tp1_pct:.0%}/{tp2_pct:.0%}/{runner_pct:.0%} (Sharpe: {sharpe:.3f})"
        )
        print(f"   Location: {cls.CONFIG_PATH}")

    @classmethod
    def get_all_presets(cls) -> Dict:
        """Devuelve todos los presets disponibles."""
        return cls.PRESETS.copy()

    @classmethod
    def clear_saved_optimal(cls):
        """Elimina configuración óptima guardada (forzar re-optimización)."""
        if cls.CONFIG_PATH.exists():
            cls.CONFIG_PATH.unlink()
            print(f"🗑️  Cleared saved TP config: {cls.CONFIG_PATH}")


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
