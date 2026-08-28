#!/usr/bin/env python3
"""Validación estructural del docker-compose.yml (no requiere Docker)."""
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"


def main():
    with open(COMPOSE, "r", encoding="utf-8") as f:
        c = yaml.safe_load(f)

    print("=" * 60)
    print(" PMA-Docker 2026 - Validacion estructural compose")
    print("=" * 60)
    print(f"Networks: {list(c.get('networks', {}).keys())}")
    for n, cfg in c.get("networks", {}).items():
        print(f"  - {n}: driver={cfg.get('driver', 'bridge')} internal={cfg.get('internal', False)} name={cfg.get('name', '-')}")

    print(f"Volumes: {list(c.get('volumes', {}).keys())}")
    print(f"Services: {list(c.get('services', {}).keys())}")

    errors = []

    # --- REQ-1: MySQL NO debe tener ports publicado ---
    mysql = c["services"].get("mysql", {})
    if "ports" in mysql:
        errors.append(f"FAIL: mysql publica puertos en host: {mysql['ports']}")
    else:
        print("  [OK] MySQL NO publica puertos en host (US-13)")

    # --- REQ-2: MySQL debe exponer 3306 ---
    expose = mysql.get("expose", [])
    if "3306" not in [str(e).strip() for e in expose]:
        errors.append("FAIL: mysql no expone 3306")
    else:
        print("  [OK] MySQL expone 3306 internamente (US-04)")

    # --- REQ-3: app-network internal:true ---
    app_net = c.get("networks", {}).get("app-network", {})
    if not app_net.get("internal"):
        errors.append("FAIL: app-network no es internal=true")
    else:
        print("  [OK] app-network es internal=true (US-13)")

    # --- REQ-4: backup-network internal:true ---
    backup_net = c.get("networks", {}).get("backup-network", {})
    if not backup_net.get("internal"):
        errors.append("FAIL: backup-network no es internal=true")
    else:
        print("  [OK] backup-network es internal=true (US-06)")

    # --- REQ-5: mysql-backup service exists ---
    if "mysql-backup" not in c.get("services", {}):
        errors.append("FAIL: servicio mysql-backup no declarado (US-06)")
    else:
        print("  [OK] servicio mysql-backup declarado (US-06)")

    # --- REQ-6: cada servicio en redes declaradas ---
    for s, cfg in c.get("services", {}).items():
        nets = cfg.get("networks", [])
        if isinstance(nets, dict):
            net_list = list(nets.keys())
        else:
            net_list = nets
        for n in net_list:
            if n not in c.get("networks", {}):
                errors.append(f"FAIL: servicio {s} referencia red no declarada: {n}")

    # --- REQ-7: restart policy en todos los servicios ---
    for s, cfg in c.get("services", {}).items():
        if not cfg.get("restart"):
            errors.append(f"WARN: servicio {s} sin restart policy")

    # --- REQ-8: healthcheck en servicios criticos ---
    for s in ("mysql", "nginx-gateway"):
        if "healthcheck" not in c["services"].get(s, {}):
            errors.append(f"FAIL: {s} sin healthcheck")

    # --- REQ-9: alias 'mysql' y 'mysql-db' en app-network ---
    mysql_nets = mysql.get("networks", {})
    if isinstance(mysql_nets, dict):
        app_cfg = mysql_nets.get("app-network", {})
        aliases = app_cfg.get("aliases", []) if isinstance(app_cfg, dict) else []
        if "mysql" not in aliases or "mysql-db" not in aliases:
            errors.append("FAIL: mysql sin aliases 'mysql' y 'mysql-db' en app-network")
        else:
            print("  [OK] aliases 'mysql' y 'mysql-db' presentes (US-08)")

    # --- REQ-10: n8n debe usar DB_TYPE=mysqldb ---
    n8n = c["services"].get("n8n-automation", {})
    env_list = [str(e) for e in n8n.get("environment", [])]
    if not any("DB_TYPE=mysqldb" in e for e in env_list):
        errors.append("FAIL: n8n sin DB_TYPE=mysqldb")
    else:
        print("  [OK] n8n con DB_TYPE=mysqldb (US-08)")
    if not any("DB_MYSQLDB_HOST=mysql" in e for e in env_list):
        errors.append("FAIL: n8n sin DB_MYSQLDB_HOST=mysql")
    else:
        print("  [OK] n8n apunta a host 'mysql' interno (US-08)")

    # --- REQ-11: n8n volumen workflows ---
    n8n_vols = n8n.get("volumes", [])
    if not any("workflows" in str(v) for v in n8n_vols):
        errors.append("FAIL: n8n sin volumen de workflows (US-09)")
    else:
        print("  [OK] n8n monta workflows (US-09)")

    # --- REQ-12: log rotation ---
    for s, cfg in c.get("services", {}).items():
        if "logging" not in cfg:
            errors.append(f"WARN: {s} sin log rotation (US-14)")

    print("=" * 60)
    if errors:
        print(f" ERRORES ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    print(f" OK - {len(c['services'])} servicios validados correctamente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
