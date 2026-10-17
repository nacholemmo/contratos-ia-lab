# Progreso — contratos-ia-lab

Registro de cada paso o fase cerrada. Lo actualiza Claude al cerrar un paso y `/cerrar-fase` al cerrar una fase.
"Qué aprendí" va en mis palabras.

## Resumen

| Fase | Estado | Inicio | Cierre |
|------|--------|--------|--------|
| 0 — Setup del laboratorio | cerrada | 2026-10-12 | 2026-10-17 |
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

### 2026-10-13 — Fase 0, paso 4: ruff y pytest
- **Qué construí:** ruff 0.17.0 y pytest 9.1.1 en `[dependency-groups] dev` del `pyproject.toml` raíz (`uv add --dev`). ruff: `target-version = "py312"`, `line-length = 100`, `archive/` excluido con `extend-exclude`, reglas `E, F, I, UP, B, SIM, C4, T20`. pytest: `testpaths = ["packages"]`, `--strict-markers` y los marcadores `slow` y `network` excluidos por defecto. Verificado: `ruff check .` sin errores, `ruff format --check .` con 14 archivos ya formateados y `pytest` cargando la configuración (todavía 0 tests, código 5).
- **Qué aprendí:** toda la configuración inicial con uv: instalar en el proyecto los paquetes necesarios y las herramientas de desarrollo para validar (pytest) y para lint y formato (ruff).
  - Con `uv add --dev`, ruff y pytest quedan en `[dependency-groups] dev` del pyproject raíz y no en las dependencias de `core`: son herramientas para desarrollar y no viajan con el paquete.
- **Dudas abiertas:** ¿activar `DTZ` (fechas con zona horaria) cuando empiecen los cálculos de fechas?

### 2026-10-17 — Fase 0, paso 5: modelos de alquileres en core
- **Qué construí:** `models.py` de `core` con los modelos del dominio. Enums `Rol`, `Moneda`, `Indice`, `RegimenLegal`, `TipoPropiedad` y `TipoDocumento`. `Persona` con DNI o CUIT y validación del dígito verificador (`cuit_valido`, módulo 11). `Propiedad` con la dirección separada en partes. `Evidencia` (fragmento literal + página ≥ 1). `Contrato` con un campo gemelo `<dato>_evidencia` opcional por cada dato clave; `clausulas` es directamente `list[Evidencia]` y `regimen_legal` no lleva evidencia porque se deduce de la fecha. `Documento` con tipo, `referencia_archivo` (path o URL), `nombre_original` y vínculos opcionales `persona_id` y `contrato_ids`. `Persona` y `Contrato` tienen `id: UUID` con `default_factory=uuid4`. Verificado: ninguna línea pasa los 100 caracteres después de `ruff format`.
- **Qué aprendí:**
- **Dudas abiertas:**
  - Fase 2: excluir los `id` del JSON schema de extracción para que el LLM no los invente.
  - Fase 2: con evidencias opcionales, el extractor tiene que exigir que todo dato no nulo tenga su evidencia.
  - Fase 7: ¿coordenadas en `Evidencia` para resaltar el fragmento en la pantalla de revisión?

### 2026-10-17 — Fase 0, paso 6: primeros tests
- **Qué construí:** `packages/core/tests/test_models.py` con 5 tests sobre datos sintéticos: contrato válido (con su evidencia), CUIT con dígito verificador inválido rechazado (con `match` para asegurar que lo rechaza el validador y no el `pattern`), monto como `Decimal` exacto, monto con 3 decimales rechazado y `id` distintos por `Persona`. En el pyproject raíz, `src = ["packages/*/src"]` para que ruff agrupe los imports de los paquetes propios como first-party. Verificado: `uv run pytest -v` → 5 passed; `ruff check` y `ruff format --check` sin errores; `uv sync --locked` en limpio.
- **Qué aprendí:**
- **Dudas abiertas:**

### 2026-10-17 — Cierre de la Fase 0: setup del laboratorio
- **Qué construí:** monorepo con workspace de uv (Python 3.12.8, un solo `uv.lock` y un `.venv/`), ruff y pytest como dependencias de desarrollo, paquete `core` con los modelos del dominio (`Persona`, `Propiedad`, `Evidencia`, `Contrato`, `Documento` y sus enums) y 5 tests. Verificado: `uv sync --locked` en limpio, `uv run pytest` → 5 passed, `ruff check` y `ruff format --check` sin errores.
- **Qué aprendí:**
  - `.python-version` y `requires-python` son los dos del proyecto: el primero es la versión exacta con la que desarrollo (uv arma el `.venv` con ella); el segundo es el rango que el paquete acepta, por eso `>=3.12` y no un patch fijo.
  - El régimen legal no lo decide un LLM: es un dato derivado de la fecha de firma con una tabla fija, así que lo calcula código determinístico con tests. Por eso no lleva evidencia; solo lo extraído del papel la lleva. El LLM sirve donde hay que interpretar (clasificar documentos, extraer datos).
  - `match` en `pytest.raises` asegura que el test falla por la razón correcta: sin él, un CUIT rechazado por el `pattern` daría verde aunque el validador del dígito estuviera roto (falso verde).
- **Dudas abiertas:**
  - ~~`Contrato` tiene `fecha_inicio` pero no `fecha_firma`~~ → resuelto el 2026-10-17 (ver abajo).
  - ¿Activar `DTZ` en ruff cuando empiecen los cálculos de fechas? (del paso 4)

### 2026-10-17 — Ajuste previo a la 1A: fecha_firma en Contrato
- **Qué construí:** `fecha_firma: date | None` en `Contrato`, con su gemelo `fecha_firma_evidencia`. Opcional porque el papel puede tenerla en blanco y el LLM no debe inventarla. Sin validador entre fechas: una firma posterior al inicio pasa en la vida real (alquiler de palabra que se formaliza después). Test nuevo: un contrato sin `fecha_firma` es válido. Verificado: `uv run pytest` → 6 passed.
- **Qué aprendí:**
- **Dudas abiertas:**
  - Fase 4: la función que deduce el régimen, ¿qué hace si `fecha_firma` es null? (¿usar `fecha_inicio` y marcarlo para revisión?)
  - Fase 7: la pantalla de revisión muestra tres estados por dato, deducidos de valor y evidencia: verde (valor + evidencia), verificar (valor sin evidencia) y completar a mano (null).
