# Momentum Trading System v2 📈

Sistema cuantitativo autónomo de swing trading de alta convicción (holding >= 10 días) diseñado para capturar setups de momentum mediante fuerza relativa, rotación sectorial, filtros de régimen de mercado y divergencia temática.

---

## 🗺️ Punto de Partida Obligatorio

Para entender la arquitectura, el estado de desarrollo actual y cómo operar en el repositorio, utilizá los siguientes documentos unificados:

1.  **Estado Actual y Reglas de Negocio:** Consultá [SYSTEM_CONTEXT.md](file:///home/marcos/trade/momentum-v2/SYSTEM_CONTEXT.md) en la raíz para conocer los módulos operativos, configuraciones de riesgo activas y el roadmap del proyecto.
2.  **Guía de Inicio Rápido (Quick Start):** Consultá [docs/GETTING_STARTED.md](file:///home/marcos/trade/momentum-v2/docs/GETTING_STARTED.md) para ver comandos oficiales de ejecución de backtest, live scanner, streamlit dashboard y sincronización de entorno.
3.  **Playbook de Desarrollo (SDD + ScrumBan):** Consultá [docs/playbook_sdd_scrumban.md](file:///home/marcos/trade/momentum-v2/docs/playbook_sdd_scrumban.md) para conocer las convenciones Git, Strict TDD y flujos de trabajo de los agentes de IA.

---

## 🛠️ Stack Tecnológico

*   **Lenguaje:** Python 3.10+
*   **Motor de Simulación:** vectorbt (vectorizado de alta velocidad)
*   **Machine Learning:** LightGBM & Optuna (hiperparámetros)
*   **Visualización & Control:** Streamlit (App de producción local/VPS)
*   **Gestión del Backlog:** GitHub CLI & ScrumBan

---

## 📂 Estructura Principal del Repositorio

*   `src/` — Código fuente de producción (signals, backtest, data, ml, utils).
*   `scripts/` — Runners y herramientas oficiales de automatización.
*   `tests/` — Suite completa de integración y QA (`pytest`).
*   `configs/` y `config/` — Parámetros de configuración del sistema (JSON/YAML).
*   `docs/` — Documentación unificada del sistema.
*   `docs/archive/` — Archivo histórico de análisis, decisiones de arquitectura antiguas y artefactos de sesión.
