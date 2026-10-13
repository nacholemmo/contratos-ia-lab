# Progreso — contratos-ia-lab

Registro de cada paso o fase cerrada. Lo actualiza Claude al cerrar un paso y `/cerrar-fase` al cerrar una fase.
"Qué aprendí" va en mis palabras.

## Resumen

| Fase | Estado | Inicio | Cierre |
|------|--------|--------|--------|
| 0 — Setup del laboratorio | en curso (pasos 1–3 hechos) | 2026-10-12 | |
| 1A — Generador de contratos sintéticos | pendiente | | |
| 1B — Series de índices y normativa | pendiente | | |
| 1C — Documentos complementarios sintéticos | pendiente | | |
| 2 — Extracción de contratos | pendiente | | |
| 3 — Clasificación de documentos y régimen | pendiente | | |
| 4 — Motor de ajustes y eventos | pendiente | | |
| 5 — RAG sobre contrato y normativa | pendiente | | |
| 6 — Agente y MCP | pendiente | | |
| 7 — App web, revisión humana y cartera | pendiente | | |
| 8 — Bot de WhatsApp y avisos | pendiente | | |
| 9 — Evals y observabilidad | pendiente | | |
| 10 — Fine-tuning (opcional) | pendiente | | |
| 11 — Inferencia y costos | pendiente | | |
| 12 — Seguridad y datos personales | pendiente | | |
| 13 — Piloto y portfolio | pendiente | | |

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
- **Qué aprendí:** a configurar git en el proyecto: identidad, rama `main`, y revisar con `git status` y `git check-ignore -v` que lo sensible (`.env`, `.venv/`, `data/`) quede afuera antes del primer commit.
- **Dudas abiertas:**

### 2026-10-12 — Fase 0, paso 3: workspace de uv
- **Qué construí:** `pyproject.toml` raíz como workspace **virtual** (solo `[tool.uv.workspace]` con `members = ["packages/*"]`, sin `[project]`). `uv sync` crea `.venv/` con Python 3.12.8 y genera `uv.lock`. La advertencia "No `requires-python` value found" es esperada hasta que exista el primer miembro (`core`, paso 4).
- **Qué aprendí:** a configurar el entorno como workspace de uv: un solo `uv.lock` y un solo `.venv/` para todos los paquetes de `packages/`. La raíz virtual solo coordina; `requires-python` del lock es el rango que acepta el proyecto, no la versión que uso (esa está en `.python-version`).
- **Dudas abiertas:**

### 2026-10-12 — Fase 0, paso 4: paquete core y modelo Comprobante
- **Qué construí:** paquete `packages/core` (`uv init --lib`, `requires-python` corregido de `>=3.12.8` a `>=3.12`, pydantic 2.14). `models.py` con `TipoComprobante` (StrEnum), `Item` y `Comprobante`. Montos en `Decimal` con un tipo reutilizable `Monto` (`ge=0`, 2 decimales); CUIT con `pattern=^\d{11}$`; punto de venta 1–99999; número 1–99999999; CAE opcional de 14 dígitos. Verificado: el caso inválido (CUIT con letras, montos negativos) da 4 errores de validación y una factura C con IVA 0 y sin CAE valida.
- **Qué aprendí:**
  - Crear modelos de datos con clases que heredan de `BaseModel` (pydantic): a partir de las anotaciones de tipo, valida y convierte los datos al crear el objeto, y rechaza lo inválido diciendo qué campo falló y por qué.
  - Comprobación de tipos en Python con restricciones: `ge`/`le`/`gt`/`lt` para números, `min_length`/`max_length`/`pattern` para textos, `Decimal` para dinero (no `float`), `Annotated` para reusar un tipo con sus restricciones (`Monto`).
  - Mejorar las `description` para el LLM: van al JSON schema y el modelo las lee como instrucciones, así que tienen que decir el formato esperado (11 dígitos sin guiones, AAAA-MM-DD, 0 en facturas C).
- **Dudas abiertas:**

### 2026-10-13 — Migración de facturas-ai-lab a contratos-ia-lab
- **Qué cambió:** el laboratorio pasa del dominio de facturas de ARCA a contratos de alquiler para inmobiliarias. Las entradas anteriores son del proyecto de facturas: los pasos 1 a 3 (uv, git, workspace) se reutilizan tal cual; el paso 4 (modelo `Comprobante`) quedó en `archive/facturas/models.py` como referencia, junto con el roadmap y las fuentes viejas.
- **Fase 0 reordenada:** 4 = ruff y pytest, 5 = adaptar `core` a los modelos de alquileres, 6 = primeros tests.
- **Nuevo:** `docs/validacion.md` (entrevistas con inmobiliarias) y la skill `/entrevista`.
