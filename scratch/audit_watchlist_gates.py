"""
scratch/audit_watchlist_gates.py

Cuantifica cuantos tickers del universo son rechazados por cada una
de las 4 gates de watchlist_detail, de forma aislada y combinada.

Uso:
    .venv/Scripts/python scratch/audit_watchlist_gates.py
"""

import json
import sys
from pathlib import Path

CACHE_FILE = Path(".cache/universes_RUSSELL1000_200.json")
SNAPSHOT_DIR = Path("outputs/live_signals")


def load_universe(cache_file: Path) -> tuple[set[str], str | None]:
    """Load universe from cache file, return (tickers_set, last_date_or_None)."""
    if not cache_file.exists():
        print(f"[SKIP]  No se encontró caché: {cache_file}")
        # Fallback: buscar cualquier universes_*.json
        alt = sorted(Path(".cache").glob("universes_*.json"))
        if alt:
            print(f"  Usando alternativa: {alt[-1].name}")
            cache_file = alt[-1]
        else:
            print("  No hay ningún archivo de caché de universos disponible.")
            return set(), None

    raw = json.loads(cache_file.read_text())
    # Nuevo formato con __meta__
    if isinstance(raw, dict) and "__meta__" in raw:
        meta = raw.get("__meta__", {})
        dates = sorted(k for k in raw if k != "__meta__" and isinstance(raw[k], list))
        if not dates:
            print(f"[ERROR] Caché {cache_file.name} no contiene datos de fechas.")
            return set(), None
        last_date = dates[-1]
        universe = set(raw[last_date])
        print(f"  Formato: nuevo (con __meta__, params={meta.get('params', {})})")
    else:
        # Legacy format: dict of date -> tickers
        dates = sorted(k for k in raw if isinstance(raw[k], list))
        if not dates:
            print(f"[ERROR] Caché {cache_file.name} sin datos de tickers por fecha.")
            return set(), None
        last_date = dates[-1]
        universe = set(raw[last_date])

    print(f"  Universo ({cache_file.name}, fecha={last_date}): {len(universe)} tickers")
    return universe, last_date


def find_best_snapshot(snapshot_dir: Path):
    """Find the most recent snapshot with watchlist_detail."""
    if not snapshot_dir.exists():
        print(f"[SKIP]  No existe el directorio: {snapshot_dir}")
        return None

    # Buscar scan_metadata*.json primero (recursivo)
    snapshots = sorted(snapshot_dir.rglob("scan_metadata*.json"))
    if not snapshots:
        snapshots = sorted(snapshot_dir.rglob("*.json"))

    if not snapshots:
        print("  No se encontraron archivos JSON en outputs/live_signals/")
        return None

    for snap in reversed(snapshots):
        try:
            data = json.loads(snap.read_text())
            if "watchlist_detail" in data:
                return snap, data
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [WARN]  Error leyendo {snap.name}: {e}")
            continue

    print("  Ningún snapshot contiene 'watchlist_detail'.")
    return None


def analyze_gates(universe: set[str], detail: dict, snapshot_name: str, meta: dict):
    """Core analysis: gate-by-gate isolation, combo analysis, universe coverage."""
    gates = ["last_base_entry", "last_liquidity", "last_quality", "last_consolidation"]
    gate_labels = {
        "last_base_entry": "Base Entry",
        "last_liquidity": "Liquidity",
        "last_quality": "Quality",
        "last_consolidation": "Consolidation",
    }

    n_detail = len(detail)
    detail_tickers = set(detail.keys())

    print(f"\n{'='*70}")
    print(f"  AUDITORÍA DE GATES — {snapshot_name}")
    print(f"  Universe: {len(universe)} tickers")
    print(f"  Watchlist detail: {n_detail} tickers")
    print(f"{'='*70}\n")

    # --- Gate isolation: count passed/failed within detail ---
    print("--- 1. Gates individuales (dentro del detail) ---")
    gate_stats = {}
    for gate in gates:
        passed = sum(1 for v in detail.values() if v.get(gate, False))
        failed = n_detail - passed
        pct_of_detail = (failed / n_detail * 100) if n_detail > 0 else 0
        gate_stats[gate] = {"passed": passed, "failed": failed, "pct_detail": pct_of_detail}

        bar = "#" * int(pct_of_detail / 5) + " " * (20 - int(pct_of_detail / 5))
        label = gate_labels.get(gate, gate)
        print(f"  {label:20s} | {passed:4d} passed / {failed:4d} failed ({pct_of_detail:5.1f}% del detail) {bar}")

    # --- Gate that catches most ---
    worst_gate = max(gates, key=lambda g: gate_stats[g]["failed"])
    worst_pct = gate_stats[worst_gate]["pct_detail"]
    if worst_pct > 60:
        print(f"\n  [ALERTA] {gate_labels.get(worst_gate, worst_gate)} concentra "
              f"{worst_pct:.1f}% del rechazo (>60%). Estrategia a discutir.")
    else:
        print(f"\n  [OK] Gate mas restrictivo: {gate_labels.get(worst_gate, worst_gate)} "
              f"({worst_pct:.1f}% del detail). Dentro de rango esperado.")

    # --- Combined gates: how many pass ALL ---
    print(f"\n--- 2. Combo: cuántos pasan TODAS las gates ---")
    all_pass = sum(
        1 for v in detail.values()
        if all(v.get(g, False) for g in gates)
    )
    some_fail = n_detail - all_pass
    print(f"  Pasan TODAS: {all_pass:4d} ({all_pass/n_detail*100:5.1f}% del detail)" if n_detail else "  Pasan TODAS: N/A")
    print(f"  FALLAN alguna: {some_fail:4d} ({some_fail/n_detail*100:5.1f}% del detail)" if n_detail else "  FALLAN alguna: N/A")

    # --- Universe coverage ---
    print(f"\n--- 3. Cobertura del universo ---")
    missing = universe - detail_tickers
    in_detail = universe & detail_tickers
    only_detail = detail_tickers - universe

    print(f"  En universo y detail: {len(in_detail):4d} ({len(in_detail)/len(universe)*100:5.1f}%)" if universe else "  En universo y detail: N/A")
    print(f"  En universo NO en detail: {len(missing):4d} ({len(missing)/len(universe)*100:5.1f}%)" if universe else "  En universo NO en detail: N/A")
    print(f"  En detail NO en universo: {len(only_detail):4d}")

    if only_detail:
        print(f"    Ejemplos: {sorted(only_detail)[:5]}")

    # --- Per-gate isolation (what if we remove just one gate?) ---
    print(f"\n--- 4. ¿Qué pasa si removemos UNA gate? ---")
    for gate_to_remove in gates:
        remaining = sum(
            1 for v in detail.values()
            if all(v.get(g, False) for g in gates if g != gate_to_remove)
        )
        gain = remaining - all_pass
        print(f"  Sin {gate_labels.get(gate_to_remove, gate_to_remove):20s}: {remaining:4d} pasarían (gain: +{gain:3d})")


def main():
    print("=" * 70)
    print("  AUDIT: Watchlist Gates Distribution")
    print("=" * 70)

    # 1. Universe
    universe, last_date = load_universe(CACHE_FILE)
    if not universe:
        print("\n[RESULTADO] No hay datos de universo para analizar.")
        print("  Ejecutá primero un backtest o scanner para generar el caché.")
        sys.exit(0)

    # 2. Snapshot
    result = find_best_snapshot(SNAPSHOT_DIR)
    if result is None:
        print("\n[RESULTADO] No hay snapshot con watchlist_detail para analizar.")
        print("  Ejecutá el scanner en vivo para generar outputs/live_signals/.")
        sys.exit(0)

    snap_path, snap_data = result

    # Extraer metadata del snapshot
    meta = {
        "universe_size": snap_data.get("universe_size", "N/A"),
        "scan_date": snap_data.get("scan_date", snap_data.get("date", "N/A")),
        "source": snap_data.get("source", "N/A"),
    }

    print(f"\n  Metadata del snapshot:")
    for k, v in meta.items():
        print(f"    {k}: {v}")

    detail = snap_data["watchlist_detail"]
    analyze_gates(universe, detail, snap_path.name, meta)

    print(f"\n{'='*70}")
    print("  AUDITORÍA COMPLETADA")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
