# Progreso — facturas-ai-lab

Registro de cada paso o fase cerrada. Lo actualiza Claude al cerrar un paso y `/cerrar-fase` al cerrar una fase.
"Qué aprendí" va en mis palabras.

## Resumen

| Fase | Estado | Inicio | Cierre |
|------|--------|--------|--------|
| 0 — Setup del laboratorio | en curso | 2026-10-12 | |
| 1A — Generador de facturas sintéticas | pendiente | | |
| 1B — Scraper de normativa ARCA | pendiente | | |
| 1C — Datos reales (opcional) | pendiente | | |
| 2 — Extracción con visión | pendiente | | |
| 3 — Búsqueda y RAG | pendiente | | |
| 4 — Agente y MCP | pendiente | | |
| 5 — App y deploy | pendiente | | |
| 6 — Evals y observabilidad | pendiente | | |
| 7 — Fine-tuning | pendiente | | |
| 8 — Inferencia y costos | pendiente | | |
| 9 — Seguridad | pendiente | | |
| 10 — Cierre y portfolio | pendiente | | |

## Registro

<!--
Plantilla para cada entrada (copiar y completar):

### AAAA-MM-DD — Fase X, paso N: <título>
- **Qué construí:**
- **Qué aprendí:**
- **Dudas abiertas:**
-->

### 2026-10-12 — Fase 0, paso 1: uv y Python 3.12 fijado
- **Qué construí:** `.python-version` con `3.12.8` (versión exacta, incluido el patch). Verificado: `uv run python --version` → `Python 3.12.8`, aunque el Python del sistema es 3.14.4. uv 0.11.15.
- **Qué aprendí:**
  - **Qué es uv:** una sola herramienta que reemplaza a pyenv, venv, pip y pip-tools. Instala versiones de Python, crea entornos virtuales, resuelve dependencias y las fija en un lockfile (`uv.lock`).
  - **Cómo se usa:** `uv python pin 3.12` fija la versión. `uv add <dep>` agrega una dependencia. `uv sync` deja el entorno igual al lockfile. `uv run <comando>` ejecuta dentro del entorno del proyecto, sin activar nada a mano.
  - **Cómo funcionan los entornos virtuales con uv:** cada proyecto tiene su `.venv/` con su propio intérprete y sus paquetes, separado del Python del sistema (3.14 en mi máquina). uv crea y actualiza ese `.venv/` solo cuando corro `uv sync` o `uv run` dentro de un proyecto (con `pyproject.toml`; sin él, `uv run` usa el intérprete directamente y no crea `.venv/`), y lo arma con la versión que dice `.python-version`. Los Pythons que instala uv viven en `~/.local/share/uv/python/` y nunca tocan el del sistema.
  - **Por qué `.python-version` va al repo:** porque el proyecto se ejecuta en el contexto de un entorno con Python 3.12, y uv lee ese archivo para elegir esa versión para el proyecto.
- **Dudas abiertas:**

### 2026-10-12 — Fase 0, paso 2: git init y primer commit
- **Qué construí:** repo git en `main` con el primer commit (docs, skills de Claude Code, `.gitignore`, `.env.example`, `.python-version`). Verificado con `git check-ignore -v` que `.env`, `.venv/` y `data/` quedan afuera y que los PDFs de `tests/fixtures/` se permiten por la negación.
- **Qué aprendí:** _(completar en mis palabras)_
- **Dudas abiertas:**
