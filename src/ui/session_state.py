"""
session_state.py — Fase 2
==========================
Árbol de estado explícito para el dashboard con selectores dependientes.

Diseño:
  - Todo el estado vive bajo el namespace "dash." para evitar colisiones
  - selected_asset: str — activo seleccionado (o "ALL")
  - selected_pattern: str — patrón seleccionado (o "ALL")
  - selected_feature: str — feature/variable seleccionada para análisis
  - view_scope: "global" | "asset" | "asset+pattern"

  - Callbacks de dependencia:
      asset cambió → resetear pattern y feature si ya no son válidos
      pattern cambió → resetear feature si ya no es válida

Uso desde app.py:
    from src.ui.session_state import DashboardState

    state = DashboardState(st.session_state)
    state.init()

    # Renderizar selector de activo
    asset = state.render_asset_selector(asset_list)
    pattern = state.render_pattern_selector(pattern_index)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import streamlit as st

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Keys del namespace
# ─────────────────────────────────────────────────────────────────────────────

NS = "dash."

KEY_ASSET = NS + "selected_asset"
KEY_PATTERN = NS + "selected_pattern"
KEY_FEATURE = NS + "selected_feature"
KEY_SCOPE = NS + "view_scope"
KEY_PREV_ASSET = NS + "_prev_asset"
KEY_PREV_PATTERN = NS + "_prev_pattern"
KEY_INITIALIZED = NS + "_initialized"

ALL_LABEL = "ALL"
SCOPE_GLOBAL = "global"
SCOPE_ASSET = "asset"
SCOPE_ASSET_PATTERN = "asset+pattern"


class DashboardState:
    """
    Wrapper sobre st.session_state que maneja el árbol de estado del dashboard.

    Garantiza:
      - No hay estado "huérfano" (patrón inexistente para activo seleccionado)
      - Reruns de Streamlit no rompen la selección
      - No se cruzan estados entre tabs/widgets
    """

    def __init__(self, session: Any = None) -> None:
        self._session = session or st.session_state

    # ──────────────────────────────────────────────────────────────────────────
    # Init
    # ──────────────────────────────────────────────────────────────────────────

    def init(self) -> None:
        """Inicializar estado con defaults si no existe."""
        if self._session.get(KEY_INITIALIZED):
            return

        defaults = {
            KEY_ASSET: ALL_LABEL,
            KEY_PATTERN: ALL_LABEL,
            KEY_FEATURE: ALL_LABEL,
            KEY_SCOPE: SCOPE_GLOBAL,
            KEY_PREV_ASSET: ALL_LABEL,
            KEY_PREV_PATTERN: ALL_LABEL,
            KEY_INITIALIZED: True,
        }
        for key, value in defaults.items():
            if key not in self._session:
                self._session[key] = value

    # ──────────────────────────────────────────────────────────────────────────
    # Getters / Setters
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def selected_asset(self) -> str:
        return self._session.get(KEY_ASSET, ALL_LABEL)

    @selected_asset.setter
    def selected_asset(self, value: str) -> None:
        self._session[KEY_ASSET] = value
        self._update_scope()

    @property
    def selected_pattern(self) -> str:
        return self._session.get(KEY_PATTERN, ALL_LABEL)

    @selected_pattern.setter
    def selected_pattern(self, value: str) -> None:
        self._session[KEY_PATTERN] = value
        self._update_scope()

    @property
    def selected_feature(self) -> str:
        return self._session.get(KEY_FEATURE, ALL_LABEL)

    @selected_feature.setter
    def selected_feature(self, value: str) -> None:
        self._session[KEY_FEATURE] = value

    @property
    def view_scope(self) -> str:
        return self._session.get(KEY_SCOPE, SCOPE_GLOBAL)

    # ──────────────────────────────────────────────────────────────────────────
    # Callbacks de dependencia
    # ──────────────────────────────────────────────────────────────────────────

    def on_asset_changed(
        self,
        new_asset: str,
        pattern_index: Dict[str, List[str]],
    ) -> None:
        """
        Callback al cambiar activo.
        Resetea patrón y feature si ya no son válidos para el nuevo activo.
        """
        old_asset = self._session.get(KEY_PREV_ASSET, ALL_LABEL)
        if new_asset == old_asset:
            return

        self._session[KEY_PREV_ASSET] = new_asset
        self._session[KEY_ASSET] = new_asset

        # Obtener patrones válidos para el nuevo activo
        valid_patterns = self._get_valid_patterns(new_asset, pattern_index)

        # Resetear patrón si ya no es válido
        current_pattern = self._session.get(KEY_PATTERN, ALL_LABEL)
        if current_pattern not in valid_patterns:
            logger.debug(
                f"[State] Reseteando pattern '{current_pattern}' "
                f"(no válido para asset '{new_asset}')"
            )
            self._session[KEY_PATTERN] = ALL_LABEL
            self._session[KEY_PREV_PATTERN] = ALL_LABEL

        # Siempre resetear feature al cambiar de activo
        self._session[KEY_FEATURE] = ALL_LABEL
        self._update_scope()

    def on_pattern_changed(self, new_pattern: str) -> None:
        """
        Callback al cambiar patrón.
        Resetea feature si cambia el contexto de análisis.
        """
        old_pattern = self._session.get(KEY_PREV_PATTERN, ALL_LABEL)
        if new_pattern == old_pattern:
            return

        self._session[KEY_PREV_PATTERN] = new_pattern
        self._session[KEY_PATTERN] = new_pattern
        # Resetear feature al cambiar patrón
        self._session[KEY_FEATURE] = ALL_LABEL
        self._update_scope()

    # ──────────────────────────────────────────────────────────────────────────
    # Scope automático
    # ──────────────────────────────────────────────────────────────────────────

    def _update_scope(self) -> None:
        asset = self._session.get(KEY_ASSET, ALL_LABEL)
        pattern = self._session.get(KEY_PATTERN, ALL_LABEL)

        if asset == ALL_LABEL:
            self._session[KEY_SCOPE] = SCOPE_GLOBAL
        elif pattern == ALL_LABEL:
            self._session[KEY_SCOPE] = SCOPE_ASSET
        else:
            self._session[KEY_SCOPE] = SCOPE_ASSET_PATTERN

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers de validación
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_valid_patterns(
        asset: str, pattern_index: Dict[str, List[str]]
    ) -> List[str]:
        """Retorna lista de patrones válidos para un activo."""
        if asset == ALL_LABEL:
            patterns = pattern_index.get("ALL", ["any"])
        else:
            patterns = pattern_index.get(asset, pattern_index.get("ALL", ["any"]))

        # Siempre incluir ALL como opción
        result = [ALL_LABEL]
        result.extend([p for p in patterns if p != ALL_LABEL])
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Renderizado de selectores en sidebar
    # ──────────────────────────────────────────────────────────────────────────

    def render_asset_selector(
        self,
        asset_list: List[str],
        pattern_index: Dict[str, List[str]],
        key_suffix: str = "",
    ) -> str:
        """
        Renderiza selectbox de activo en el contexto actual (sidebar u otro).
        Dispara callback on_asset_changed automáticamente.

        Returns:
            Asset seleccionado actualmente.
        """
        options = [ALL_LABEL] + [a for a in asset_list if a != ALL_LABEL]
        current = self._session.get(KEY_ASSET, ALL_LABEL)

        # Asegurar que el valor actual siga siendo válido
        if current not in options:
            current = ALL_LABEL
            self._session[KEY_ASSET] = ALL_LABEL

        idx = options.index(current) if current in options else 0

        selected = st.selectbox(
            "🏦 Activo",
            options=options,
            index=idx,
            key=f"_dash_asset_sel{key_suffix}",
            help="Filtrar todas las métricas por activo. 'ALL' = vista global.",
        )

        if selected != current:
            self.on_asset_changed(selected, pattern_index)

        return selected

    def render_pattern_selector(
        self,
        pattern_index: Dict[str, List[str]],
        key_suffix: str = "",
    ) -> str:
        """
        Renderiza selectbox de patrón dependiente del activo actual.
        Sólo muestra patrones válidos para el activo seleccionado.

        Returns:
            Patrón seleccionado actualmente.
        """
        asset = self._session.get(KEY_ASSET, ALL_LABEL)
        valid_patterns = self._get_valid_patterns(asset, pattern_index)

        current_pattern = self._session.get(KEY_PATTERN, ALL_LABEL)
        # Asegurar validez
        if current_pattern not in valid_patterns:
            current_pattern = ALL_LABEL
            self._session[KEY_PATTERN] = ALL_LABEL

        idx = valid_patterns.index(current_pattern) if current_pattern in valid_patterns else 0

        selected = st.selectbox(
            "📐 Patrón / Señal",
            options=valid_patterns,
            index=idx,
            key=f"_dash_pattern_sel{key_suffix}",
            help=f"Patrones disponibles para {asset}. 'ALL' = todos los patrones.",
        )

        if selected != current_pattern:
            self.on_pattern_changed(selected)

        return selected

    def render_scope_badge(self) -> None:
        """Renderiza badge visual del scope activo."""
        asset = self.selected_asset
        pattern = self.selected_pattern
        scope = self.view_scope

        if scope == SCOPE_GLOBAL:
            st.info("🌐 Vista: **Global** — todas las señales y activos")
        elif scope == SCOPE_ASSET:
            st.info(f"🏦 Vista: **{asset}** — todos los patrones")
        else:
            st.info(f"🔍 Vista: **{asset} · {pattern}**")

    # ──────────────────────────────────────────────────────────────────────────
    # Reset
    # ──────────────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Resetea todo el árbol de estado al valor inicial."""
        keys_to_reset = [
            KEY_ASSET, KEY_PATTERN, KEY_FEATURE, KEY_SCOPE,
            KEY_PREV_ASSET, KEY_PREV_PATTERN,
        ]
        for key in keys_to_reset:
            if key in self._session:
                del self._session[key]
        self._session[KEY_INITIALIZED] = False
        self.init()

    def as_dict(self) -> Dict[str, str]:
        """Exporta el estado actual como dict plano (útil para debug)."""
        return {
            "asset": self.selected_asset,
            "pattern": self.selected_pattern,
            "feature": self.selected_feature,
            "scope": self.view_scope,
        }
