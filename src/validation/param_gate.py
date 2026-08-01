"""
Guard de gobernanza de parámetros (ParamGate).

Autoriza un config para producción/live SOLO cuando se cumplen AMBAS
validaciones independientes:

1. Métricas OOS numéricas (endurecimiento de 3dc817d): las métricas deben
   existir y superar los umbrales de producción (trades, DSR, MDD).
2. Recibo físico de Purged CV (restaurado desde c219151): debe existir en
   artifacts/purged_cv/ un reporte `purged_cv_report_*.json` con
   `gate_passed == True` y `params_json_source` coincidente con el config
   solicitado.

El requisito (2) se perdió durante la limpieza de 3dc817d y se restaura aquí
para que un config rechazado (p.ej. validated_production_params.json,
2026-07-30) no pueda volver a entrar silenciosamente a producción/live.
"""
import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Ruta canónica de los recibos físicos de Purged CV (artefactos auditable).
# Los tests la reemplazan vía monkeypatch para inyectar recibos falsos.
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts" / "purged_cv"


class RejectedConfigError(RuntimeError):
    """Se intentó autorizar un config sin evidencia completa (métricas OOS + recibo Purged CV)."""


def assert_params_cleared(params_json_path: str) -> Dict[str, Any]:
    """
    Verifica que exista al menos un reporte de Purged CV con gate_passed=True
    y params_json_source == params_json_path.

    Restaurado desde c219151, adaptado a la ruta actual de recibos
    (artifacts/purged_cv/).

    Args:
        params_json_path: path del archivo de parámetros a autorizar.

    Returns:
        El reporte aprobado que respalda el config.

    Raises:
        RejectedConfigError: si no hay recibo (sin recibo) o si el recibo
            existente fue rechazado explícitamente (recibo rechazado).
    """
    params_json_path = str(Path(params_json_path).as_posix())

    if not ARTIFACTS_DIR.exists():
        raise RejectedConfigError(
            f"Sin recibo: no existe {ARTIFACTS_DIR}/ — no hay ningún Purged CV corrido. "
            f"No se puede autorizar '{params_json_path}' para producción/live."
        )

    approved: Optional[Dict[str, Any]] = None
    rejected_found = False

    for report_path in sorted(ARTIFACTS_DIR.glob("purged_cv_report_*.json")):
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        if report.get("params_json_source") != params_json_path:
            continue

        if report.get("gate_passed") is True:
            approved = report
        else:
            rejected_found = True
            logger.warning(
                f"Recibo RECHAZADO para '{params_json_path}' ({report_path.name}): "
                f"degradación {report.get('degradation_pct')}%"
            )

    if approved is None:
        reason = (
            "tiene un recibo de Purged CV explícitamente RECHAZADO"
            if rejected_found
            else "nunca fue evaluado por Purged CV (sin recibo)"
        )
        raise RejectedConfigError(
            f"'{params_json_path}' {reason}. No autorizado para producción/live."
        )

    return approved


class ParamGate:
    """
    Módulo de gobernanza: exige métricas OOS + recibo físico de Purged CV
    antes de promover un config a producción/live (Phase 6 Infrastructure Freeze).
    """

    # Umbral de trades para PROMOCIÓN a producción.
    # N=150 vs N=30 (screening exploratorio):
    # - N=30: piso de significancia estadística POR FOLD del Purged CV
    #   (src/validation/purged_walk_forward.py → MIN_OOS_TRADES; ver
    #   openspec/specs/purged-cross-validation/spec.md, PCV-REQ-03): un fold
    #   con menos de 30 trades OOS se marca como estadísticamente
    #   insignificante y el gate emite warning en el reporte.
    # - N=150: mínimo de trades OOS agregados para PROMOVER un config a
    #   producción/live. Es una constante de gobernanza de producción; no hay
    #   spec formal que la fije (ver DECISIONS.md, entrada 2026-07-31).
    # Ambos conviven: el screening descarta configs débiles por fold; la
    # promoción exige evidencia consolidada suficiente en producción.
    MIN_TRADES = 150
    MIN_DSR = 0.35
    MAX_MDD = -30.0  # e.g., -25.0 is better than -30.0

    @classmethod
    def calculate_hash(cls, config: Dict[str, Any]) -> str:
        """Calculates a canonical SHA-256 hash for the config."""
        # Remove volatile governance keys before hashing
        clean_config = {
            k: v
            for k, v in config.items()
            if k not in ["governance_hash", "promoted_at", "validation_passed"]
        }
        canonical_str = json.dumps(clean_config, sort_keys=True)
        return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()

    @classmethod
    def validate_metrics(cls, config: Dict[str, Any]) -> None:
        """
        Valida las métricas OOS numéricas del config contra los umbrales de
        producción. Fail-closed por defecto.

        Raises:
            RejectedConfigError: si el config no está marcado como validado,
                si no trae métricas OOS (sin métricas), o si alguna métrica
                queda bajo umbral (métricas bajo umbral).
        """
        if not config.get("validation_passed", False):
            raise RejectedConfigError(
                "Sin métricas: validation_passed es False o falta en el config."
            )

        metrics = config.get("oos_metrics", {})
        if not metrics:
            raise RejectedConfigError(
                "Sin métricas: el config no contiene oos_metrics."
            )

        trades = metrics.get("trades", 0)
        dsr = metrics.get("dsr", 0.0)
        mdd = metrics.get("mdd_pct", -100.0)

        if trades < cls.MIN_TRADES:
            raise RejectedConfigError(
                f"Métricas bajo umbral: trades {trades} < {cls.MIN_TRADES}."
            )
        if dsr < cls.MIN_DSR:
            raise RejectedConfigError(
                f"Métricas bajo umbral: dsr {dsr} < {cls.MIN_DSR}."
            )
        if mdd < cls.MAX_MDD:
            raise RejectedConfigError(
                f"Métricas bajo umbral: mdd {mdd} < {cls.MAX_MDD}."
            )

    @classmethod
    def validate_candidate(cls, config: Dict[str, Any]) -> bool:
        """
        Valida únicamente las métricas OOS numéricas (sin recibo físico).

        Retrocompatibilidad: el flujo completo de promoción a producción
        exige ADEMÁS el recibo físico de Purged CV (ver assert_promotable).

        Args:
            config: candidato con oos_metrics y validation_passed.

        Returns:
            True si las métricas pasan; False en caso contrario.
        """
        try:
            cls.validate_metrics(config)
            return True
        except RejectedConfigError as exc:
            logger.error(f"Governance REJECT: {exc}")
            return False

    @classmethod
    def assert_promotable(
        cls,
        config: Dict[str, Any],
        params_json_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exige AMBAS validaciones antes de autorizar producción/live:
        (a) métricas OOS numéricas, (b) recibo físico de Purged CV.

        Args:
            config: candidato con oos_metrics y validation_passed.
            params_json_path: path del archivo de parámetros que debe tener
                recibo aprobado. Si es None, se intenta leer del propio
                config (clave `params_json_source`).

        Returns:
            El recibo de Purged CV aprobado que respalda el config.

        Raises:
            RejectedConfigError: con mensajes que distinguen sin métricas,
                métricas bajo umbral, sin recibo y recibo rechazado.
        """
        cls.validate_metrics(config)

        source = (
            params_json_path
            if params_json_path is not None
            else config.get("params_json_source")
        )
        if source is None:
            raise RejectedConfigError(
                "Sin recibo: el config no declara params_json_source y no se "
                "suministró params_json_path. No se puede verificar la evidencia."
            )
        return assert_params_cleared(source)

    @classmethod
    def promote(
        cls,
        config: Dict[str, Any],
        target_path: Path,
        params_json_path: Optional[str] = None,
    ) -> bool:
        """
        Valida (métricas + recibo) y promueve un config a target_path,
        sellándolo con un hash criptográfico.

        Args:
            config: candidato a promover. Debe incluir `params_json_source`
                o pasarse params_json_path para verificar el recibo.
            target_path: destino de producción.
            params_json_path: source de parámetros para verificar el recibo.

        Returns:
            True si la promoción se completó; False si alguna gate rechazó.
        """
        try:
            cls.assert_promotable(config, params_json_path)
        except RejectedConfigError as exc:
            logger.error(f"Promotion aborted: {exc}")
            return False

        config["governance_hash"] = cls.calculate_hash(config)
        config["promoted_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)

        logger.info(
            f"Governance SUCCESS: Config promoted to {target_path} "
            f"with hash {config['governance_hash']}"
        )
        return True

    @classmethod
    def verify_tampering(cls, config_path: Path) -> bool:
        """
        Verifies if a promoted config on disk has been tampered with.
        """
        if not config_path.exists():
            return False

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        stored_hash = config.get("governance_hash")
        if not stored_hash:
            logger.error("Tampering REJECT: No governance_hash found in file")
            return False

        calculated = cls.calculate_hash(config)
        if stored_hash != calculated:
            logger.error(f"Tampering REJECT: Hash mismatch! Stored: {stored_hash}, Calc: {calculated}")
            return False

        return True
