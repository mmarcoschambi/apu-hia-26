"""
src/screeners/registry.py
ScreenerRegistry singleton para registro y lookup de screeners.
"""
import json
from pathlib import Path
from typing import Dict, Type, List, Optional

from .base import BaseScreener, ScreenerConfig


class ScreenerRegistry:
    """
    Registro global de screeners.
    Uso como decorator:

        @ScreenerRegistry.register
        class MyScreener(BaseScreener):
            ...
    """
    _screeners: Dict[str, Type[BaseScreener]] = {}
    _default_configs: Dict[str, ScreenerConfig] = {}
    _cached_configs: Dict[str, ScreenerConfig] = {}

    @classmethod
    def register(cls, screener_class: Type[BaseScreener]) -> Type[BaseScreener]:
        """Decorator que registra un screener y almacena su config por defecto."""
        # Instanciar temporalmente para obtener name y config
        tmp = screener_class.__new__(screener_class)
        tmp.config = None
        name = tmp.name if isinstance(tmp.name, str) else screener_class.name
        instance = screener_class()
        cls._screeners[name] = screener_class
        cls._default_configs[name] = instance.get_default_config()
        return screener_class

    @classmethod
    def get(cls, name: str, config: Optional[ScreenerConfig] = None) -> BaseScreener:
        """Obtiene una instancia del screener con config opcional."""
        if name not in cls._screeners:
            available = cls.list_available()
            raise ValueError(
                f"Screener '{name}' no registrado. Disponibles: {available}"
            )
        return cls._screeners[name](config)

    @classmethod
    def list_available(cls) -> List[str]:
        """Lista los nombres de screeners registrados."""
        return list(cls._screeners.keys())

    @classmethod
    def load_config(
        cls,
        name: str,
        config_path: Optional[str] = None,
    ) -> ScreenerConfig:
        """
        Carga una ScreenerConfig desde JSON o retorna la default.

        El JSON puede contener cualquier subconjunto de campos de ScreenerConfig.
        Campos desconocidos van a 'params'.
        """
        cache_key = f"{name}:{config_path}" if config_path else name
        if cache_key in cls._cached_configs:
            import copy
            return copy.deepcopy(cls._cached_configs[cache_key])

        if config_path:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Separar campos conocidos de params extra
            known = {
                k: v for k, v in data.items()
                if k in ScreenerConfig.__dataclass_fields__
            }
            extra = {k: v for k, v in data.items() if k not in known}
            if extra:
                known.setdefault("params", {}).update(extra)
            cfg = ScreenerConfig(**known)
            cls._cached_configs[cache_key] = cfg
            import copy
            return copy.deepcopy(cfg)

        # Buscar JSON en config/screeners/<name>.json
        default_path = Path(__file__).parent.parent.parent / "config" / "screeners" / f"{name}.json"
        if default_path.exists():
            cfg = cls.load_config(name, str(default_path))
            cls._cached_configs[cache_key] = cfg
            import copy
            return copy.deepcopy(cfg)

        cfg = cls._default_configs.get(name, ScreenerConfig(name=name))
        cls._cached_configs[cache_key] = cfg
        import copy
        return copy.deepcopy(cfg)

    @classmethod
    def describe(cls) -> Dict[str, str]:
        """Retorna un dict {name: description} de todos los screeners registrados."""
        result = {}
        for name, klass in cls._screeners.items():
            instance = klass()
            result[name] = instance.description
        return result
