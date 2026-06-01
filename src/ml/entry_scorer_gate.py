import logging
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np

# Lazy load dependencies to avoid heavy imports unless needed
_scorer_class = None

def _get_scorer_class():
    global _scorer_class
    if _scorer_class is None:
        from src.ml.entry_scorer import EntryScorer
        _scorer_class = EntryScorer
    return _scorer_class

logger = logging.getLogger(__name__)

class EntryScorerGate:
    _instance: Optional["EntryScorerGate"] = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(EntryScorerGate, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self, model_path: Optional[str] = None):
        if self._initialized:
            return
        
        self._initialized = True
        self.model_path = Path(model_path or "models/entry_scorer.pkl")
        self.scorer = None
        
        try:
            if self.model_path.exists():
                EntryScorer = _get_scorer_class()
                self.scorer = EntryScorer.load(str(self.model_path))
                logger.info(f"EntryScorerGate loaded model from {self.model_path}")
            else:
                logger.warning(f"EntryScorerGate: Model file not found at {self.model_path}. EntryScorer will bypass filtering.")
        except Exception as e:
            logger.warning(f"EntryScorerGate: Failed to load model at {self.model_path}: {e}. EntryScorer will bypass filtering.")
            
    def score(self, features: Dict[str, Any]) -> float:
        """
        Calcula la probabilidad de que el trade sea exitoso.
        Si el modelo no está disponible, retorna 1.0 (no filtra).
        """
        if self.scorer is None:
            return 1.0
        try:
            return float(self.scorer.predict_proba(features))
        except Exception as e:
            logger.warning(f"EntryScorerGate: Error predicting probability: {e}")
            return 1.0
            
    def should_enter(self, features: Dict[str, Any], threshold: float = 0.40) -> bool:
        """
        Determina si se debe entrar al trade basándose en el score del modelo.
        """
        if self.scorer is None:
            return True
        prob = self.score(features)
        return prob >= threshold
