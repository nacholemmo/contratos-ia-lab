# Progreso — contratos-ia-lab

Registro de cada paso o fase cerrada. Lo actualiza Claude al cerrar un paso y `/cerrar-fase` al cerrar una fase.
"Qué aprendí" va en mis palabras.

## Resumen

| Fase | Estado | Inicio | Cierre |
|------|--------|--------|--------|
| 0 — Setup del laboratorio | cerrada | 2026-10-12 | 2026-10-17 |
| 1 — Generador sintético | en curso | 2026-10-18 | |
| 2 — Clasificación de documentos | pendiente | | |
| 3 — Extracción por tipo de documento, con evidencia | pendiente | | |
| 4 — Evaluaciones contra el generador | pendiente | | |
| 5 — RAG sobre normativa | pendiente | | |
| 6 — Servidor MCP | pendiente | | |
| 7 — Agente con LangGraph | pendiente | | |
| 8 — Deploy y LLMOps | pendiente | | |

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

### 2026-10-18 — Cambio de alcance: servicio de IA sin estado para Avisa
- **Qué cambió:** el repo pasa a ser el servicio de IA del módulo Alquileres de Avisa, sin estado, con dos funciones: generador de contratos sintéticos (`POST /synthetic/contracts`) y extracción de datos de documentos (`POST /extract`). Avisa es la única fuente de verdad: guarda los datos, hace la revisión humana, calcula aumentos y vencimientos y manda los avisos. Roadmap nuevo de 6 fases (generador, clasificación, extracción, evaluaciones, API, deploy); la Fase 0 se mantiene y los modelos de `core` quedan como esquemas de salida de la extracción y ground truth del generador. `CLAUDE.md` actualizado.
- **Qué quedó afuera:** base de datos, multi-tenant, login, cálculo de aumentos, series de índices, avisos, agente y fine-tuning. RAG: no hace falta para extraer (un contrato entra entero en el contexto); el de normativa es candidato a servicio aparte y el de contratos iría dentro de Avisa o del agente, donde están los datos.
- **Dudas abiertas:**
  - Fase 3: ¿`regimen_legal` lo devuelve este servicio como dato derivado o lo calcula Avisa? (inclinación: Avisa).
  - Fase 3: `Documento` tiene `referencia_archivo` y vínculos (`persona_id`, `contrato_ids`), que son conceptos con estado; revisar si sobran.
  - Las dudas anotadas para la ex Fase 7 (coordenadas en `Evidencia`, tres estados por dato en la revisión) pasan a ser temas de Avisa; las coordenadas podrían volver si Avisa resalta el fragmento.

### 2026-10-18 — Fase 1, paso 1: datos falsos coherentes con semilla
- **Qué construí:** paquete `packages/synthetic` (Faker 40.43, depende de `core` como miembro del workspace). `Source(seed)` agrupa `random.Random` y `Faker("es_AR")` con la misma semilla y genera UUID reproducibles. `identity.py`: `generate_dni` y `cuit_from_dni` (prefijo 20/27, y 23 cuando el dígito verificador daría 10, recalculado con el mismo helper `_digito_verificador`). `contracts.py`: `generate_persona`, `generate_propiedad` (tabla de localidades coherente), `regimen_por_fecha` (bordes 17/10/2023 y 29/12/2023), `choose_terms` (leyes viejas fijas; DNU con decisiones en cadena moneda → índice → frecuencia, y pesos representativos en constantes `PESOS_*_DNU`) y `generate_contrato(seed)`. Verificado: `uv run pytest` → 37 passed; `ruff check` y `ruff format --check` sin errores.
- **Qué aprendí:**
  - **Semilla:** el número inicial del generador pseudoaleatorio. Con la misma semilla sale la misma secuencia y, por lo tanto, el mismo contrato. Es como un lockfile para el azar: la variación sigue existiendo, pero es reproducible.
  - `Source` tiene su propio `random.Random` (no el `random` global, que cualquier librería puede mover) y `derive("redaccion")` arma una semilla nueva con sha256, no con `hash()`, que cambia entre ejecuciones de Python.
  - Para qué sirve: si el extractor falla en el contrato 17, lo regenero con la semilla 17 y depuro ese caso exacto, sin guardar ningún PDF. El determinismo depende también de las versiones fijadas en `uv.lock` (Faker, fpdf2).
- **Dudas abiertas:**
  - Faker `es_AR` (40.43): `name_male()` falla y `city()`/`province()` no son coherentes entre sí; por eso nombres por partes y tabla propia de localidades.
  - El determinismo depende también de la versión de Faker fijada en `uv.lock`: actualizar Faker puede cambiar los contratos de cada semilla.
  - Fase 4: los pesos `PESOS_*_DNU` son aproximados; ajustarlos con datos reales (docs/validacion.md). Reportar por separado el set representativo y el de casos difíciles.
  - `identity.py`: sobra el `# noqa: F401` del import de `PESOS_CUIT`; `PREFIJO_POR_SEXO` podría tiparse `dict[Sexo, str]`.

### 2026-10-22 — Roadmap alineado con el path AI Engineer / FDE
- **Qué cambió:** el roadmap sigue el calendario del path (oct.–nov. Fases 1 a 3, dic. evals, ene. RAG, feb. MCP y agente, mar. deploy). La interfaz con Avisa pasa de API REST a un **servidor MCP propio** (Fase 6): sirve al backend de Avisa y a Claude, y el agente lo usa como cliente. Se suman tracing con Langfuse y la comparación de dos modelos o prompts a la Fase 4, el RAG sobre normativa (Fase 5, `packages/normativa`) y el agente con LangGraph (Fase 7, `packages/agent`). El servicio sigue sin estado: esos paquetes lo consumen y él no depende de ellos. El repo pasa a ser público: README actualizado y licencia MIT.
- **Dudas abiertas:**
  - Fase 6: si el backend de Avisa llama siempre la misma tool de forma fija, ¿alcanza MCP o conviene sumar un REST mínimo? Revisarlo con el uso real.

### 2026-10-22 — Fase 1, paso 2: plantillas y variantes de redacción
- **Qué construí:** Jinja2 3.1 y num2words 0.5 en `synthetic`. `Source.derive(label)`: sub-fuente estable por etapa (sha256 de `semilla:etiqueta`, no `hash()`), para que la redacción no quede correlacionada con los datos. `wording.py`: frases con variantes para fecha (meses fijos, sin locale), plazo, índice + frecuencia en una sola frase, propiedad (con concordancia de género) y DNI/CUIT con o sin separadores. `amounts.py`: `numero_ar` (formato argentino), `monto_en_letras` (num2words + apócope "veintiún mil" / "un mil" + centavos "CON 05/100") y `format_monto` en números, letras o ambos. `clauses.py`: cláusulas con Jinja2 (`StrictUndefined`), numeración con ordinales o "CLÁUSULA N", cláusulas opcionales (depósito, garantía) y `fragmentos` por cláusula: el texto literal que respalda cada dato del `Contrato`, base de la evidencia del paso 3. Verificado: `uv run pytest` → 660 passed; `ruff check` sin errores.
- **Qué aprendí:**
  - `monto_en_letras`: num2words sabe escribir números, pero no cómo se escriben en un contrato. Hay que corregir su salida: la **apócope** ("veintiuno mil" → "veintiún mil"; es perder letras al final, no omitir los centavos) y los centavos con dos dígitos (`{centavos:02d}` → "CON 05/100").
  - El orden de los `replace` importa: "veintiuno mil" contiene "uno mil", así que va primero el caso especial y después el general.
  - Invertí las ramas del `if` en un intento y rompí casos que antes pasaban: la tabla parametrizada de tests lo mostró caso por caso. Conviene escribir primero el caso que agrega algo (`if centavos:`) y correr los tests después de cada cambio.
  - `Decimal` y no `float` para separar los centavos: con `float`, `0.05 * 100` puede dar 4.999… y truncar a 4.
- **Dudas abiertas:**
  - `monto_en_letras` corrige la apócope solo delante de "mil": alcanza para el rango actual (hasta 1,4 M). Si el generador produce millones ("veintiuno millones"), sumar la regla; el test que barre el rango lo va a detectar.
  - ¿Activar `RUF100` en ruff para detectar `noqa` que ya no hacen falta?

### 2026-10-22 — Fase 1, paso 3: PDF con la marca SINTÉTICO y evidencia por página
- **Qué construí:** fpdf2 2.8 en `synthetic` y pypdf 6.21 en dev (solo para tests). `pdf.py`: `ContratoPDF` con marca de agua "SINTÉTICO" rotada, aviso arriba y "SINTÉTICO · Página N de M" abajo en cada página; metadatos que lo marcan como sintético y fecha de creación fija (sin ella, la misma semilla daría otros bytes). `_write_clause` mide la cláusula con `multi_cell(dry_run=True)` y salta de página antes si no entra, así cada fragmento queda en una sola página y la página se anota después de escribir. `with_evidence` arma los `<campo>_evidencia` y `clausulas` (expensas y rescisión). `generate_contract(seed) -> (bytes, Contrato)`. En `clauses.py`, cuatro cláusulas sin datos (conservación, prohibiciones, jurisdicción) para que los contratos tengan varias páginas. Tests: mismos bytes por semilla, marca en cada página y cada evidencia encontrada en su página al releer el PDF con pypdf. Verificado: `uv run pytest` → 789 passed; `ruff check` sin errores.
- **Qué aprendí:**
  - Estamos generando contratos de forma determinista para probar que un LLM, que es probabilístico, obtenga la respuesta que necesitamos. Determinista para que el examen sea siempre el mismo: si la precisión cambia, cambió el extractor y no los contratos.
  - Al LLM no se le pide pasa/no pasa como en un test clásico: se le mide una **tasa** por campo ("acierta el monto en el 96 %") y dónde falla. Y todo lo que se puede verificar alrededor del LLM es código determinista: pydantic valida el formato y la evidencia se busca en la página. El LLM propone y el código verifica.
  - El JSON es el **ground truth**: la planilla de respuestas de cada PDF (dato, fragmento literal y página). En la Fase 4 se compara campo por campo con lo que extrae el LLM; acá sale gratis y exacto porque el generador escribe el PDF a partir de los datos.
  - Todo esto es un **eval harness**: dataset con respuestas (Fase 1), sistema bajo prueba (Fases 2-3), scorers y reporte (Fase 4). No confundirlo con un agent harness (Claude Code, LangGraph), que ejecuta un agente.
  - La página de cada fragmento se anota mientras se escribe. Para que un fragmento no quede partido, mido la cláusula con `multi_cell(dry_run=True)` (el mismo cálculo que la escritura real) y salto de página antes si no entra. `pdf.unbreakable()` no sirvió porque el `header()` usa `rotation()`.
  - Fecha de creación fija en el PDF: si no, la misma semilla da otros bytes.
- **Dudas abiertas:**
  - `pdf.unbreakable()` no sirve con un `header()` que usa `rotation()`; por eso la medición manual.
  - Una cláusula más larga que una página se partiría igual y su evidencia quedaría con la última página. Revisarlo en el paso 4 (cláusulas raras).
  - La cláusula de objeto dice "destino de vivienda" aunque la propiedad sea local u oficina. Revisarlo en el paso 4 o al sumar contratos comerciales.
  - Los bytes del PDF dependen también de la versión de fpdf2 fijada en `uv.lock` (igual que Faker).

### 2026-10-22 — Ajuste de la Fase 1: mayoría de contratos en Mendoza
- **Qué construí:** seis localidades del Gran Mendoza en `LOCALIDADES` (Godoy Cruz, Guaymallén, Las Heras, Luján de Cuyo, Maipú y San Rafael; CP aproximados) y `PESOS_PROVINCIA` (Mendoza 70 %, CABA 12 %, Buenos Aires 10 %, Córdoba y Santa Fe 4 % cada una). `generate_propiedad` elige en dos etapas: la provincia por peso y una localidad dentro de ella, así el porcentaje no depende de cuántas localidades tenga cada provincia. Tests: los pesos cubren la tabla y suman 1, Mendoza sale entre el 65 % y el 75 % en 2000 propiedades y aparecen todas las localidades. Modelos de contrato de referencia anotados en `docs/fuentes.md`. Verificado: `uv run pytest packages/synthetic` → 785 passed; `ruff check` y `ruff format --check` sin errores.
- **Qué aprendí:**
  - **Distribución objetivo:** el set sintético tiene que parecerse a lo que el servicio va a ver en producción (Avisa: mayoría Mendoza), pero con un resto variado para que el extractor no se acostumbre a un solo formato de dirección.
  - Elegir en dos etapas (provincia por peso, después localidad dentro de ella) separa dos perillas: el porcentaje por provincia no cambia aunque sume localidades.
  - Python: `_elegir` devuelve un `str`, no una fila; un `str` también es una secuencia, así que `rng.choice("Mendoza")` devuelve una letra y desempaquetar un `str` en 3 variables falla. List comprehension `[fila for fila in LOCALIDADES if fila[1] == provincia]` es como `filter` en JS. `a, b, c = tupla` desempaqueta si la cantidad coincide. Ante la duda, probar en el intérprete qué devuelve cada línea.
  - Comparar con modelos reales (GCBA, Roomix, Mendoza) encontró un error que ningún test detectaba: la rescisión de la ley vieja en contratos DNU. Los tests verifican coherencia con el ground truth; que el texto sea correcto para el régimen lo valida alguien que conoce el dominio.
  - Tabla completa (`PLANTILLAS_RESCISION` con los tres regímenes) en vez de `if … else`: documenta la decisión legal y un régimen nuevo sin regla falla en el test en vez de heredar en silencio la del DNU.
  - Tribunales: Mendoza y Córdoba se organizan en circunscripciones; Buenos Aires, en departamentos judiciales. Los datos de dominio se verifican en una fuente, no se infieren por analogía. En el generador conviene fallar (`ValueError` con mensaje) ante una provincia desconocida; `NotImplementedError` es para código sin escribir. Ternario `x if cond else y` (como `cond ? x : y`) y f-strings (como template literals).
- **Dudas abiertas:**
  - ~~**Error de dominio:** la cláusula de rescisión usa la regla de la ley anterior (a los 6 meses, con un mes de preaviso) también en contratos DNU, donde se puede rescindir en cualquier momento pagando el 10 % del saldo (art. 1221 del CCyC reformado). Corregirlo según `regimen_legal` en el ajuste de plantillas.~~ → resuelto el 2026-10-22: `PLANTILLAS_RESCISION` mapea cada régimen a su regla (las leyes 27.551 y 27.737 comparten la misma, el DNU tiene la suya). Tests: la cláusula dice "10%" si y solo si el contrato es DNU, y el set incluye los tres regímenes. `uv run pytest packages/synthetic` → 987 passed.
  - ~~Ajuste de plantillas, antes del paso 4: numeración "ARTÍCULO N", fecha "a los … días del mes de …" y jurisdicción por provincia.~~ → resuelto el 2026-10-22: tercera numeración "ARTÍCULO N:"; `frase_fecha_cierre` ("a los veintiún días del mes de…", con apócope en `dia_en_letras`) y la fecha de firma va en el encabezado o en una cláusula final `cierre`, nunca en los dos; `frase_tribunales` por localidad (CABA: Juzgados Nacionales en lo Civil; Mendoza: Primera Circunscripción, salvo San Rafael en la Segunda; Buenos Aires: departamento judicial de cada ciudad; Córdoba y Rosario por circunscripción), y `ValueError` si la provincia no está. `uv run pytest packages/synthetic` → 1204 passed.
  - Para el paso 4 (casos difíciles): guiones de relleno `.-----`, canon escalonado por año, seguro de caución como garantía (sin persona garante) y aspecto de fotocopia escaneada como el modelo de Mendoza.
  - Verificar los CP de Mendoza contra el Correo Argentino.
  - Fase 3 (esquema de extracción): campos candidatos que salieron del modelo del GCBA y que Avisa podría usar: día de pago ("del 1 al 10 de cada mes", útil para vencimientos y avisos), tasa o regla de mora y tipo de garantía (persona garante o seguro de caución). Decidirlo con el uso real.

### 2026-10-24 — Fase 1, paso 4a: casos difíciles etiquetados, datos faltantes y montos en letras
- **Qué construí:** el paso 4 queda dividido en 4a, 4b y 4c en el roadmap. `cases.py`: `CasoDificil` (fecha de firma en blanco, persona sin DNI ni CUIT, sin código postal, montos solo en letras) con su probabilidad en `P_CASO`; `elegir_casos` (mía: un sorteo independiente por caso con `source.rng`, así se pueden combinar); `normalizar_casos` (sin repetidos y en el orden del enum) y `aplicar_faltantes` (los datos faltantes en null con `model_copy`). `Muestra`: seed, `sintetico=True`, casos y contrato; es el ground truth etiquetado que va a escribir la CLI. `generate_sample(seed, casos=None)`: la semilla elige sus casos o un test los fuerza (`[]` da un contrato limpio); `generate_contract` mantiene su firma. La redacción ya no deja "(CP None)" ni comas colgando, y `render_clauses(..., solo_letras=True)` fuerza los montos en letras. Verificado: `uv run pytest packages/synthetic` → 1366 passed; `ruff check` y `ruff format --check` sin errores.
- **Qué aprendí:**
  - **Variación controlada y etiquetado:** un set de evaluación sirve para diagnosticar, no solo para poner una nota. Con la etiqueta de cada caso, la Fase 4 puede decir "acierta el 98 % en contratos limpios y el 60 % con montos en letras" en vez de un promedio que esconde dónde falla.
  - Las etiquetas no van en `Contrato` (lo que el LLM extrae y no puede saber), sino en un envoltorio del set (`Muestra`).
  - "No hay" y "no figura" son cosas distintas: `deposito = None` hoy significa que no hay depósito. Por eso los faltantes de 4a son campos donde null solo puede significar "no figura".
  - Los casos usan su propia sub-fuente (`derive("casos")`): sumar un caso no cambia el contrato de ninguna semilla existente. Sortear siempre todos los casos consume siempre la misma cantidad de números del rng.
  - Con sorteos independientes, la proporción de contratos limpios sale de multiplicar las probabilidades (0,9⁴ ≈ 66 %), no de una constante: al sumar casos se achica sola.
  - Python: la indentación es la sintaxis (lo que en JS son las llaves); un bloque con 3 espacios y otro con 4 da `IndentationError`. Una línea vacía con espacios la corrige `ruff format`.
- **Dudas abiertas:**
  - Si 4b y 4c suman casos al 10 %, el set limpio baja del 50 % y falla `test_la_mayoria_de_los_contratos_queda_limpia`: bajar las probabilidades o generar un set limpio aparte.
  - Fecha de firma en blanco: el ground truth conserva `regimen_legal` de la fecha real. Relacionado con la duda de la Fase 4 sobre qué hace el extractor si `fecha_firma` es null.
  - Faltante del depósito (la cláusula está pero sin monto): el modelo no lo puede distinguir de "no hay depósito". Decidirlo si aparece en contratos reales.
