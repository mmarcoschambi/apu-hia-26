"""Snapshot schema contract for pre-market Finviz snapshots (issue #74).

Guarda contra drift de schema productor/consumidor: todo candidato de
``watchlist_detail`` debe exponer los campos que los consumidores downstream
asumen (gatillo live #73 calcula RVOL desde ``avg_volume_20d``; el promoter
usa ``price``/``score``). La deteccion debe ser automatica y ruidosa, no
manual como se descubrio el drift original.
"""

from __future__ import annotations

import math
from typing import Any

AVG_VOLUME_KEY = "avg_volume_20d"

# Claves obligatorias en cada candidato del watchlist_detail.
REQUIRED_CANDIDATE_KEYS: tuple[str, ...] = (
    "score",
    "price",
    "rvol",
    AVG_VOLUME_KEY,
)


def validate_snapshot(snapshot: dict[str, Any]) -> list[str]:
    """Valida el contrato de schema de un snapshot pre-market.

    Args:
        snapshot: Snapshot completo tal como lo escribe ``run_pre``.

    Returns:
        Lista de violaciones legibles (vacia si el snapshot cumple). No lanza:
        el llamador decide como reportarlas (log critico + campo embebido).
    """
    violations: list[str] = []
    watchlist = snapshot.get("watchlist_detail")
    if watchlist is None:
        return ["snapshot sin 'watchlist_detail'"]
    if not isinstance(watchlist, dict):
        return [
            f"'watchlist_detail' debe ser dict, got {type(watchlist).__name__}"
        ]

    for ticker in sorted(watchlist):
        detail = watchlist[ticker]
        if not isinstance(detail, dict):
            violations.append(f"{ticker}: detalle debe ser dict")
            continue

        for key in REQUIRED_CANDIDATE_KEYS:
            if detail.get(key) is None:
                violations.append(f"{ticker}: falta key requerida '{key}'")

        avg_vol = detail.get(AVG_VOLUME_KEY)
        if avg_vol is None:
            continue  # ausencia ya reportada arriba
        if isinstance(avg_vol, bool) or not isinstance(avg_vol, (int, float)):
            violations.append(
                f"{ticker}: '{AVG_VOLUME_KEY}' debe ser numerica, "
                f"got {type(avg_vol).__name__}"
            )
        elif not math.isfinite(float(avg_vol)) or avg_vol <= 0:
            violations.append(
                f"{ticker}: '{AVG_VOLUME_KEY}' debe ser > 0 finita, got {avg_vol!r}"
            )

    return violations
