import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ParamGate:
    """
    Governance module to enforce strict quantitative gates before promoting
    new parameters to production (Phase 6 Infrastructure Freeze).
    """
    
    MIN_TRADES = 150
    MIN_DSR = 0.35
    MAX_MDD = -30.0  # e.g., -25.0 is better than -30.0
    
    @classmethod
    def calculate_hash(cls, config: Dict[str, Any]) -> str:
        """Calculates a canonical SHA-256 hash for the config."""
        # Remove volatile governance keys before hashing
        clean_config = {k: v for k, v in config.items() if k not in ["governance_hash", "promoted_at", "validation_passed"]}
        canonical_str = json.dumps(clean_config, sort_keys=True)
        return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()

    @classmethod
    def validate_candidate(cls, config: Dict[str, Any]) -> bool:
        """
        Validates if a candidate meets all strict governance requirements.
        Fail-closed by default.
        """
        if not config.get("validation_passed", False):
            logger.error("Governance REJECT: validation_passed is False or missing")
            return False
            
        metrics = config.get("oos_metrics", {})
        if not metrics:
            logger.error("Governance REJECT: No OOS metrics found in config")
            return False
            
        trades = metrics.get("trades", 0)
        dsr = metrics.get("dsr", 0.0)
        mdd = metrics.get("mdd_pct", -100.0)
        
        if trades < cls.MIN_TRADES:
            logger.error(f"Governance REJECT: trades {trades} < {cls.MIN_TRADES}")
            return False
            
        if dsr < cls.MIN_DSR:
            logger.error(f"Governance REJECT: dsr {dsr} < {cls.MIN_DSR}")
            return False
            
        if mdd < cls.MAX_MDD:
            logger.error(f"Governance REJECT: mdd {mdd} < {cls.MAX_MDD}")
            return False
            
        return True

    @classmethod
    def promote(cls, config: Dict[str, Any], target_path: Path) -> bool:
        """
        Validates and promotes a config to the target path, sealing it with a hash.
        """
        if not cls.validate_candidate(config):
            logger.error("Promotion aborted due to failed validation gates.")
            return False
            
        config["governance_hash"] = cls.calculate_hash(config)
        import datetime
        config["promoted_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
            
        logger.info(f"Governance SUCCESS: Config promoted to {target_path} with hash {config['governance_hash']}")
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
