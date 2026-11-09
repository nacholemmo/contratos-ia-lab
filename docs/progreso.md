# Progreso — contratos-ia-lab

Registro de cada paso o fase cerrada. Lo actualiza Claude al cerrar un paso y `/cerrar-fase` al cerrar una fase.
"Qué aprendí" va en mis palabras.

## Resumen

| Fase | Estado | Inicio | Cierre |
|------|--------|--------|--------|
| 0 — Setup del laboratorio | cerrada | 2026-10-12 | 2026-10-17 |
| 1 — Generador sintético | cerrada | 2026-10-18 | 2026-10-24 |
| 2 — Clasificación de documentos | en curso | 2026-10-25 | |
| 3 — Legajo fotografiado en el generador | pendiente | | |
| 4 — Extracción de la etapa 1, con evidencia | pendiente | | |
| 5 — Armado del legajo | pendiente | | |
| 6 — Evaluaciones contra el generador | pendiente | | |
| 7 — Servidor MCP | pendiente | | |
| 8 — Etapa 2: cierre con contrato y seguro | pendiente | | |
| 9 — Agente con LangGraph | pendiente | | |
| 10 — Deploy y LLMOps | pendiente | | |
| Opcional — RAG sobre normativa | pendiente | | |

Las fases se renumeraron el 2026-11-07 (ADR 0001); las entradas anteriores usan la numeración vieja.

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

### 2026-10-24 — Fase 1, paso 4b: cláusulas raras y casos según el contrato
- **Qué construí:** cuatro casos nuevos en `CasoDificil`: `GUIONES_DE_RELLENO` (guiones al final de cada párrafo), `CANON_ESCALONADO` (monto de cada año en la cláusula de precio, índice `FIJO` en el modelo y el monto del primer año como `monto_inicial`), `SEGURO_DE_CAUCION` (póliza de una aseguradora inventada en lugar de la persona garante) y `CLAUSULA_LARGA` (inventario de más de una página). Probabilidades: 8 % los de 4a y 5 % los nuevos, para que el set limpio quede en ~58 %. `es_aplicable` (mía): canon escalonado solo con DNU 70/2023 y plazo de 24 meses o más (también en dólares), caución solo si el contrato tenía garante (la reemplaza), y el resto siempre. `prepare_sample` descarta los casos sorteados que no aplican y tira `ValueError` con los forzados. `aplicar_faltantes` pasa a ser `aplicar_casos`. Arreglo: la cláusula de objeto dice "uso comercial" para locales, "oficina de uso profesional" para oficinas y "vivienda" para el resto. Verificado: `uv run pytest packages/synthetic` → 2023 passed; `ruff check` y `ruff format` sin errores.
- **Qué aprendí:**
  - Un caso difícil tiene que ser **realista**: un canon escalonado bajo la Ley 27.551 o un contrato de 12 meses con "segundo año" no existen, y un extractor evaluado con documentos imposibles mide algo que nunca va a ver en producción.
  - Sorteado y forzado reaccionan distinto: si lo sorteó la semilla y no aplica, se descarta (es azar); si lo forzó un test, es un error (pidió algo imposible y tiene que enterarse ya).
  - La frecuencia real de un caso es `P_CASO` × la proporción de contratos donde aplica (caución ≈ 0,05 × 2/3 ≈ 3 %). Para medir bien un caso raro, conviene un set forzado por caso además del sorteado.
  - Python resuelve los nombres al ejecutar la línea: un import que falta no avisa hasta que se usa (`NameError`). `ruff check` (F821) lo detecta antes, como un compilador.
- **Dudas abiertas:**
  - Canon escalonado: `Contrato` solo guarda el monto del primer año; los demás escalones quedan en el texto. Si Avisa los necesita para calcular los aumentos, hace falta un campo nuevo (Fase 3, junto con el tipo de garantía).
  - Tipo de garantía (persona o caución): ya era candidato a campo para la Fase 3 y ahora el generador lo produce. Hoy solo se nota por la ausencia de garantes.
  - La evidencia de un dato *dentro* de una cláusula de más de una página quedaría con la última página. El inventario no tiene datos, así que no pasa; revisarlo si una cláusula larga llega a tener uno.
  - Para la Fase 4: set forzado por caso (N contratos con cada caso) además del sorteado.

### 2026-10-24 — Fase 1, paso 4c: escaneo torcido (cierra el paso 4)
- **Qué construí:** pypdfium2 5.14 y Pillow 13 en `synthetic` (Pillow ya venía con fpdf2, pero se declara porque la importamos directamente). Caso `ESCANEO_TORCIDO` al 5 % (set limpio ≈ 55 %). `scan.py`: `rasterizar` (cada página a una imagen en grises a 150 DPI) y `degradar` (torcida ±2°, gris de fotocopia, 4.000 puntos de ruido y desenfoque leve, todo con `source.rng`). La escribí con la solución que pedí, después de dos intentos. En `pdf.py`: `pdf_de_imagenes` arma un PDF A4 de imágenes JPEG sin capa de texto, y `_marcar_sintetico` junta los metadatos. El ground truth del escaneado es idéntico al de su gemelo con texto. Los tests que leen el texto del PDF ya no usan el escaneo. Verificado: `uv run pytest packages/synthetic` en verde (incluye los 18 de `test_scan.py`); `ruff check` y `ruff format` sin errores. Revisado a ojo en `data/escaneo.pdf`.
- **Qué aprendí:**
  - **Documento sin capa de texto:** un escaneo es solo una foto; no hay texto que extraer y hace falta visión u OCR, con otro costo, latencia y errores. Es lo que compara la Fase 2, paso 2.
  - Escanear cambia la forma, no lo que dice: el ground truth es el mismo que el del gemelo con texto (misma semilla, sin el caso) y la evidencia se verifica en ese gemelo.
  - Pillow: `rotate`, `point` y `filter` devuelven una imagen nueva (como `.map()` en JS), mientras que `ImageDraw` dibuja sobre la imagen que recibe.
  - `point()` no corre una vez por píxel: llama a la función una vez por cada uno de los 256 tonos y arma una tabla (LUT) que aplica a toda la imagen. Sirve para el gris de fotocopia, no para ruido (cada punto necesita su propia posición y tono).
  - `rotate(expand=True)` agranda la imagen, y sin `fillcolor` las esquinas quedan negras. `randint` da enteros y `uniform` decimales (ángulo y radio de desenfoque).
  - `Image.effect_noise` usa el azar de C y no la semilla: rompería el determinismo. Todo el azar sigue pasando por `Source`, que ya llega sembrada (no hace falta volver a sembrarla).
- **Dudas abiertas:**
  - El escaneo es suave: un extractor con visión lo va a leer casi como el texto. Si en la Fase 4 la precisión del escaneo es casi igual a la del texto, sumar un nivel fuerte (más ángulo y ruido, contraste desparejo, como el modelo de Mendoza).
  - Los bytes del escaneo dependen también de las versiones de pypdfium2, Pillow y su libjpeg fijadas en `uv.lock`.
  - La suite tarda más porque rasteriza: si molesta, marcar los tests de escaneo como lentos (`pytest -m "not lento"`).

### 2026-10-24 — Fase 1, paso 5a: modelo DNI y ficha por cada parte del contrato
- **Qué construí:** el paso 5 queda dividido en 5a, 5b y 5c en el roadmap. Decisiones: evidencia por campo gemelo (como `Contrato`) y legajo generado desde el contrato de la misma semilla, para poder evaluar cruces. En `core`: `Sexo` (M, F, X) y `DNI` (mío, en varias vueltas y con la solución al final): solo número y apellido obligatorios, el resto `| None`, descripciones pensadas para el LLM, sin número de trámite ni lugar de nacimiento (minimización). En `synthetic`: `Identidad` (persona + nombre de pila, apellido y sexo, que el contrato no muestra) y `generate_contrato_con_identidades`, sin cambiar los contratos de ninguna semilla; `identity.py` usa el `Sexo` de core. `dni.py`: ficha de una página con presentación propia (nada del diseño oficial), apellido y nombre en mayúsculas, fechas y número con variantes, y `generate_dnis(seed)` con una sub-fuente por parte. `fechas_dni` (con la solución): todo relativo a la fecha de firma, DNI vigente, y el 29 de febrero resuelto con `_sumar_anios`. Verificado: `uv run pytest packages/core packages/synthetic` → 2308 passed; `ruff check` y `ruff format` sin errores.
- **Qué aprendí:**
  - **Legajo coherente:** el valor no está en extraer cada documento, sino en cruzarlos (¿el DNI coincide con el contrato?). Si el generador arma todo desde la misma semilla, el ground truth trae los cruces gratis. El caso PERSONA_SIN_DOCUMENTO se vuelve un cruce: el contrato no trae el DNI y la ficha sí.
  - No imitar documentos oficiales: mismos datos, presentación propia. Al extractor le alcanza con leer campos; un DNI con el diseño de RENAPER sería un modelo de falsificación.
  - **Esquemas de extracción:** con un LLM, "obligatorio" no significa "siempre está", significa "siempre va a responder algo". Obligatorio solo lo que define el documento; el resto `| None`, para que no invente.
  - Pydantic: un campo opcional necesita las dos cosas juntas, `X | None` en el tipo y `None` de default. El JSON Schema que lee el LLM sale del tipo, y pydantic no valida los defaults (en TS no compilaría; acá lo atrapa un type checker o un test del schema).
  - La `description` de un campo es código para el LLM: un error de copiar y pegar ("razón social" en el apellido) no lo detecta ningún test de tipos, solo los evals por campo.
  - `date_of_birth` de Faker calcula la edad contra `date.today()`: rompe la coherencia con firmas viejas y el determinismo (la misma semilla da otra fecha mañana), y ningún test de "misma semilla" lo detecta porque corre el mismo día.
  - Python no tiene "sumar años": `replace(year=...)` falla con el 29 de febrero. Hacia adelante el aniversario es el 1 de marzo; hacia atrás, el 28 de febrero. Los bordes de fechas se testean con la fecha fija, no esperando que el azar la encuentre.
- **Dudas abiertas:**
  - El número de DNI no está correlacionado con la edad (en la realidad, los de 7 dígitos son de gente mayor). Ajustarlo si un extractor o un eval lo usa.
  - DNI vencido: hoy todos están vigentes a la firma. Si sirve como advertencia para Avisa, sumarlo como caso difícil del legajo (`DNI_VENCIDO`).
  - Fase 4: el cruce de nombres necesita el comparador de texto normalizado (mayúsculas, tildes, orden nombre/apellido).
  - `EDAD_ULTIMA_ACTUALIZACION` y `VIGENCIA_DNI_ANIOS` salen de las reglas generales del DNI; verificarlas en una fuente oficial (casos de mayores de 75 o DNI anteriores a la tarjeta).

### 2026-10-24 — Fase 1, paso 5b: recibo de sueldo del inquilino
- **Qué construí (lo escribió Claude, a pedido mío):** `ReciboSueldo` en core: solo empleador y empleado obligatorios; CUIT del empleador y CUIL del empleado con dígito verificador; período `AAAA-MM`; fecha de ingreso; bruto, total de descuentos y neto como `Monto`. Sin CBU, banco, legajo, categoría ni detalle de conceptos (minimización). `cuit_empresa` (prefijo 30, o 33 si el verificador daría 10). `recibo.py`: un recibo por inquilino, empleadores inventados, aportes fijos (jubilación 11 %, Ley 19.032 3 %, obra social 3 %) redondeados al centavo, neto exactamente bruto - aportes, alquiler entre el 20 % y el 40 % del neto, período del mes anterior a la firma, ingreso desde los 16 años y al menos 3 meses antes del período, con la misma fecha de nacimiento que la ficha del DNI. En `dni.py`: `sumar_anios` público, `fuente_dni` y `referencia_legajo` para que otros documentos del legajo recalculen los datos del DNI. Verificado: `uv run pytest packages/core packages/synthetic` → 2843 passed.
- **Qué aprendí:**
  - El modelo guarda bruto, descuentos y neto aunque el neto se pueda calcular: se extrae lo que el papel dice, no lo que debería decir. Un neto que no cierra es una advertencia (paso 3.4); si el modelo lo calculara, el error quedaría escondido.
  - Dinero con código determinístico también en el generador: `Decimal`, `quantize` con `ROUND_HALF_UP` y el neto como resta exacta.
  - El legajo ya tiene tres cruces evaluables: DNI ↔ contrato (nombre y número), recibo ↔ contrato (CUIL) y DNI ↔ recibo (edad e ingreso). Ninguno se puede verificar con un documento solo.
- **Dudas abiertas:**
  - Un recibo por inquilino; las inmobiliarias suelen pedir los últimos tres. Sumarlos si un eval los necesita.
  - Contratos en dólares: el recibo usa un alquiler típico en pesos del año en vez de una cotización. Revisarlo si Avisa evalúa la relación alquiler/ingreso en USD.
  - Garantes: en la realidad también presentan recibos. Hoy solo los inquilinos; revisarlo en 5c.

### 2026-10-24 — Fase 1, paso 5c: garantía y seguro (cierra el paso 5)
- **Qué construí (lo escribió Claude, a pedido mío):** refactor de 4b: la aseguradora y la póliza de la caución salen de `datos_caucion(seed)` antes de redactar, así la cláusula y la póliza del legajo coinciden. En core: `TituloPropiedad` (titular e inmueble obligatorios), una base `Poliza` (aseguradora, número, vigencia) y sus hijas `PolizaCaucion` (tomador, asegurado, suma y moneda) y `SeguroInmueble` (asegurado, ubicación del riesgo, suma). `legajo.py`: `ContextoLegajo` con el contrato con casos (quién firma) y el limpio con sus identidades (los datos completos), la fecha de referencia, `sumar_meses` y `fin_de_contrato`. `fichas.py`: ficha genérica y `direccion()`. `garantia.py`: un título por garante que firma (otro inmueble, escritura desde sus 18 años) o, con el caso, la póliza de caución por todo el plazo. `seguro.py`: incendio, anual desde el inicio, a nombre del primer inquilino. DNI y recibo usan el contexto. Verificado: `uv run pytest packages/core packages/synthetic` → 3045 passed.
- **Qué aprendí:**
  - Dos modelos de garantía y no uno con un campo `tipo`: comparten casi nada, y un modelo único tendría la mitad de los campos siempre en null y un esquema confuso para el LLM. Lo común (aseguradora, número, vigencia) sí va en una base: es lo que Avisa usa para avisar vencimientos.
  - Cada documento del legajo usa dos contratos: el limpio para los datos y el aplicado para saber quién está. Pensarlo así encontró un bug de 5a que ningún test detectaba: con caución, el legajo traía DNI de garantes que el contrato ya no tenía.
  - Un dato que aparece en dos documentos (la póliza en la cláusula y en el legajo) tiene que generarse una vez, antes de los dos, y no adentro de uno de ellos.
- **Dudas abiertas:**
  - Título y póliza de caución son los dos `TipoDocumento.GARANTIA`: el extractor de la Fase 3 los tiene que distinguir (¿subtipo en la clasificación?).
  - El seguro es anual y el contrato dura más: las renovaciones (y el aviso de vencimiento) son de Avisa; acá solo la primera póliza.
  - Garantes con recibo de sueldo en vez de título (pasa en la realidad): no se generan.

### 2026-10-24 — Fase 1, paso 6: CLI que escribe el set con su legajo
- **Qué construí (lo escribió Claude, a pedido mío):** `export.py`: `write_legajo` escribe una carpeta por semilla (`0042/`) con el contrato y su legajo (PDF + JSON por documento, nombres por rol como `dni_inquilino_2`) y un `legajo.json` con el tipo, el modelo y el `persona_id` de cada documento; `MODELOS` (nombre → modelo pydantic); `write_manifest` con el resumen del set. `cli.py` con `argparse` y el script `generate` en `[project.scripts]` (ruff: T20 permitido en `cli.py`, como en `scripts/`). Al correrlo, el manifest mostró canon escalonado y caución con 0 contratos en 50 sorteados, así que se sumó un **set forzado**: `--por-caso N` (default 3) escribe `forzados/<caso>/<seed>/` con un solo caso por contrato, en semillas donde aplica y fuera del rango sorteado. Verificado: `uv run --package synthetic generate --n 50 --seed 42 --out data/synthetic/` → 50 contratos sorteados (27 limpios) y 3 forzados por cada uno de los 9 casos; tests de la CLI con los dos criterios de "Terminado cuando" (cada JSON valida contra su modelo, misma semilla → mismos bytes).
- **Qué aprendí:**
  - **Set representativo vs. set de cobertura:** el sorteado mide cómo le va al extractor en un día normal; el forzado garantiza un mínimo de cada caso raro. Con P_CASO × aplicabilidad ≈ 3 %, un caso puede salir 0 veces en 50, y la métrica global nunca se entera de que el extractor no lo sabe leer. Es el mismo problema de las clases raras en ML (estratificación).
  - El `manifest` con todos los casos, incluidos los que dan 0, es lo que hizo visible el problema antes de la Fase 4.
  - Un solo caso por contrato forzado: cada error se le puede atribuir a ese caso. Y como cada caso busca desde la misma semilla, el mismo contrato base aparece con distintos casos: una comparación controlada.
  - `persona_id` va en el índice del legajo, no en los modelos de core: los modelos son lo que extrae el LLM, que no conoce los ids.
  - `main(argv)` recibe los argumentos como parámetro: la CLI se testea llamando a una función, sin levantar un proceso.
- **Dudas abiertas:**
  - La CLI no borra lo que ya hay en la carpeta: la fuente de verdad es `legajo.json`, no los archivos presentes. Si cambia el código y una semilla deja de tener un documento, el viejo queda.
  - `documentos_por_modelo` del manifest cuenta solo el set sorteado; si hace falta, sumar el del forzado.

### 2026-10-24 — Ajuste de la Fase 1: contratos vigentes y legajos de Mendoza
- **Qué construí (Claude, a pedido mío):** `PESOS_ANIO_FIRMA` en `contracts.py` (2020 1 %, 2021-2022 2 %, 2023 10 %, 2024 25 %, 2025 35 %, 2026 25 %): la firma se elige en dos etapas, año por peso y un día de ese año dentro de la ventana. En `dni.py`, el domicilio sigue al inmueble: el 85 % vive en la misma provincia (`P_MISMA_PROVINCIA`) y el resto según `PESOS_PROVINCIA`. Tests de las dos proporciones. Set regenerado desde cero (`rm -rf data/synthetic`): de 50 contratos, 38 firmados entre 2024 y 2026 y 38 bajo el DNU; domicilios del DNI en Mendoza, del 35 % al 75 %; neto mediano de los recibos de 2025-2026 entre $ 2,8 y $ 3,1 millones.
- **Qué aprendí:**
  - Los montos "bajos" de los recibos eran coherentes con la fecha de firma (un recibo de 2020 trae un sueldo de 2020). El problema era la distribución: la firma uniforme desde 2020 daba un 68 % de contratos de 2020-2023, casi todos ya vencidos. El set tiene que parecerse a lo que Avisa recibe: contratos **vigentes**.
  - No afecta la extracción (el LLM lee el monto impreso), pero sí que la métrica sea representativa y cualquier validación con umbrales absolutos.
  - Muestrear uniforme es el default cómodo, y casi nunca la distribución del mundo. La pregunta es "¿uniforme sobre qué población?".
  - Un cambio "local" (el año de firma) mueve casi todas las proporciones del set (régimen, moneda, casos aplicables): hay que volver a leer el manifest.
- **Dudas abiertas:**
  - Los pesos por año son aproximados; ajustarlos con los contratos reales de las inmobiliarias (docs/validacion.md).
  - `ALQUILER_ARS_POR_ANIO` es nacional; en Mendoza los alquileres son más bajos que en CABA. Revisarlo con datos reales.

### 2026-10-24 — Cierre de la Fase 1: generador sintético
- **Qué construí:** `packages/synthetic`, un generador determinístico (Faker `es_AR`, plantillas Jinja2 y fpdf2, sin LLM) que produce contratos de locación en PDF con su ground truth (dato, fragmento literal y página), nueve casos difíciles etiquetados (datos faltantes, montos en letras, guiones, canon escalonado, caución, cláusula larga, escaneo torcido) y un legajo coherente por contrato (DNI, recibo de sueldo, título o caución, seguro), con los modelos de cada documento en `core`. La CLI `generate` escribe el set sorteado y el forzado con su `manifest`. Criterios de "Terminado cuando" verificados: 50 contratos con sus complementarios y su JSON en `data/synthetic/`; `test_cada_json_valida_contra_su_modelo`, `test_misma_semilla_mismo_pdf` y `test_misma_semilla_mismos_archivos` en verde; `uv run pytest packages/core packages/synthetic` → 3057 passed; `ruff check` y `ruff format --check` sin errores (al cerrar, `ruff format` acomodó cuatro archivos sin cambios de lógica).
- **Qué aprendí (según mis respuestas al cierre):**
  - Para evaluar un sistema probabilístico como un LLM hace falta un marco determinista (un eval harness): con los mismos datos y las mismas respuestas, se puede saber si el extractor extrae bien o inventa. *Corrección:* lo que da el examen fijo es poder atribuir un cambio de precisión al extractor y no a los datos; y como el LLM varía, se miden tasas sobre muchos documentos, no pasa/no pasa.
  - Los casos raros tienen probabilidad baja y pueden no salir; por eso el set forzado garantiza un mínimo. *Corrección:* el manifest cuenta los documentos; los sets miden cosas distintas: el sorteado, la precisión representativa (un día normal en Avisa), y el forzado, la precisión por caso, con un solo caso por contrato para atribuir cada error. Subir `P_CASO` arreglaría el forzado rompiendo el representativo.
  - Si los campos de un esquema fueran obligatorios y no están en el documento, el LLM los inventaría. *Complemento:* en un formulario, "obligatorio" bloquea a una persona hasta que aporta el dato; en un LLM significa "siempre va a responder algo", y el reintento con el error de validación lo empuja a completar.
- **Dudas abiertas para las próximas fases:**
  - Fase 2: título y póliza de caución son los dos `TipoDocumento.GARANTIA`; decidir si la clasificación lleva subtipo.
  - Fase 3: el número de DNI no está correlacionado con la edad; los escalones del canon y el tipo de garantía no tienen campo en `Contrato`.
  - Fase 4: comparador de nombres normalizado (mayúsculas, tildes, orden nombre/apellido); reportar sorteado y forzado por separado; si el escaneo da casi la misma precisión que el texto, sumar un nivel fuerte.
  - Pesos aproximados (años de firma, provincias, casos, alquileres nacionales): ajustarlos con los contratos reales de docs/validacion.md.

### 2026-10-25 — Fase 2, paso 1: llamada mínima a la API con tokens, costo y latencia
- **Qué construí:** paquete `packages/extractor` (`anthropic`, `pydantic-settings`, `core`). Modelo de trabajo: **Haiku 5.5** para toda la Fase 2 (saldo de USD 4,82, MVP). `settings.py`: la clave sale de `.env` como `SecretStr`; cliente con timeout de 30 s y 2 reintentos (los del SDK). `llm.py`, única puerta al LLM: `call_llm` manda `effort: "low"`, mide la latencia y devuelve el texto más un `LlmUsage` (modelo, tokens, costo, latencia, `stop_reason`, `request_id`); loguea solo esos metadatos; traduce los errores del SDK a `LlmError` y `LlmRefusal` y loguea solo el tipo de error; corta antes de llamar si el modelo no tiene precio en `PRICES`. `cost_usd` (lo escribí yo): `Decimal` exacto sin redondear, con la tarifa larga de Haiku (más de 100K tokens de entrada, toda la llamada ×5). CLI `llm-ping`. Verificado: `uv run pytest packages/extractor` → 13 passed; `uv run --package extractor llm-ping` → `in=25 out=4 cost_usd=0.0000045 latency=1.60s`; `uv run pytest packages/extractor -m network` → 1 passed.
- **Qué aprendí:**
  - Cada llamada a un LLM se mide con tres números: tokens, costo y latencia. Sin ellos no se pueden comparar los enfoques de la Fase 2 ni saber si el servicio es viable para Avisa.
  - El costo es dinero: `Decimal` y una sola división al final. Redondear a centavos daría 0 (una llamada cuesta fracciones de centavo).
  - Primero elegir la tarifa y después calcular una sola vez. El test de borde (100.001 tokens) es el que atrapó que faltaba la tarifa larga.
  - "Sin estado" también en los errores: el mensaje de un error de la API puede citar el documento, así que se loguea solo su tipo.
  - Una suscripción (Google AI Plus, Claude.ai) no da crédito de API: el servicio se paga por token.
- **Dudas abiertas:**
  - `Price` permite un umbral sin tarifas largas; validarlo en `__post_init__` si se suman modelos.
  - Haiku 5.5 acepta apagar el pensamiento con effort `high` o menos; medir en el paso 3 si cambia la calidad o el costo de clasificar.
  - Gemini (tier gratuito de AI Studio) como segundo modelo para la comparación de la Fase 4; nunca con documentos reales (el tier gratuito puede usar los datos).
  - Precios de caché de Haiku 5.5: no están en `PRICES`; sumarlos si se usa caché de prompts (few-shot).

### 2026-10-25 — Fase 2, paso 2: texto extraído vs. imagen de la página
- **Qué construí (Claude armó el esqueleto; la regla del híbrido la escribí yo, el umbral final con su ayuda):** `inputs.py`: texto e imagen de las primeras páginas con `pypdfium2` (imagen a 1568 px de lado largo, lo máximo que la API usa sin reducir); el texto va envuelto en `<documento>`; `has_usable_text` decide el híbrido: palabras de más de 3 letras ≥ `MIN_LONG_WORDS` (15). `classify.py`: prompt zero-shot con las etiquetas de `TipoDocumento` y la aclaración de que el documento es un dato, no instrucciones; `parse_tipo` (respuesta que no es etiqueta → `None`, cuenta como error). `experiment.py` y la CLI `experimento-entrada`: estima con `count_tokens` (gratis), no corre si supera `--max-usd`, corre cada documento en texto y en imagen y deriva el híbrido sin llamadas propias; guarda solo metadatos en `data/experimentos/`. Verificado: `uv run pytest packages/extractor` → 40 passed; `uv run --package extractor experimento-entrada --run` sobre 13 documentos (2 por tipo + 3 escaneos), estimado USD 0,0047, real 0,0041:

  | estrategia | aciertos | escaneos | USD | latencia |
  |---|---|---|---|---|
  | text | 9/13 | 0/3 | 0,0008 | 1,27 s |
  | image | 13/13 | 3/3 | 0,0033 | 1,91 s |
  | hybrid | 12/13 | 3/3 | 0,0015 | 1,35 s |

  **Elegido: híbrido.** Acierta los escaneos como la imagen, cuesta 2,2 veces menos y tarda casi como el texto.
- **Qué aprendí:**
  - Una imagen cuesta ~2.250 tokens fijos por página, tenga el texto que tenga; el texto, entre 500 (DNI) y 1.400 (contrato). Con Haiku es poco igual, pero el costo crece con el volumen de Avisa.
  - Un escaneo no tiene capa de texto: en modo texto el modelo recibe un documento vacío. Respondió `otro` y no adivinó, que es lo correcto.
  - La regla del híbrido es un clasificador chico con un umbral: una sola comparación, no un rango. El corte se corre hacia el error barato (mandar a imagen algo con texto cuesta centésimos de centavo; tomar un sello como texto cuesta una clasificación).
  - Que una función devuelva algo "truthy" no es lo mismo que devolver `bool`: los tests con `is True` lo atraparon.
  - Más muestras reducen la varianza, no el sesgo: con 13 documentos la conclusión sobre escaneos y costo es sólida (es determinística); la precisión fina va en el paso 4. "Más real" se consigue con otros datos, no con más de los mismos.
- **Dudas abiertas:**
  - `titulo_garante_1` dio `otro` en texto y `titulo_garante_2`, igual de formato, dio `garantia`: la constancia de titularidad no dice "garante". Es un problema de definición de la clase (la duda de la Fase 1 sobre `GARANTIA`); atacarlo en el paso 3 con una definición más precisa o con few-shot.
  - Los DNI y el resto del legajo sintético son PDFs con texto; los reales suelen ser fotos. Sumar al generador un legajo "fotografiado" para medir el híbrido donde importa.
  - No hay documentos `otro` en el set: el clasificador nunca tiene que rechazar.
  - `MIN_LONG_WORDS` está calibrado con datos sintéticos; recalibrarlo con escaneos reales.
  - La estimación tarda ~20 s para 13 documentos (secuencial); para el set completo, paralelizar o estimar con una muestra.

### 2026-11-07 — Reenfoque a legajos (ADR 0001)
- **Qué construí:** `docs/adr/0001-reenfoque-a-legajos.md`. El producto pasa de "gestión de contratos" a **armar legajos de alquiler a partir de fotos**, en dos etapas (evaluación y cierre) con el mismo motor. Roadmap nuevo: la Fase 2 sigue igual; se suman el legajo fotografiado en el generador (3), el armado del legajo (5) y la etapa 2 (8); la extracción se acota a la etapa 1 (4); el agente se acota a agrupación y asignación ambiguas (9); el RAG sobre normativa pasa a opcional. Actualizados README, CLAUDE.md, `docs/validacion.md` y la skill `/entrevista`.
- **Qué aprendí:**
- **Dudas abiertas:** las del ADR (sección "Decisiones abiertas").

### 2026-11-09 — Fase 2, paso 3: cuatro enfoques para clasificar
- **Qué construí:** sobre el set de 565 documentos (8 contratos escaneados), cuatro clasificadores con sus CLIs, que guardan solo metadatos en `data/experimentos/`.
  - **Reglas** (`rules.py`, `clasificar-reglas`): frases clave en orden, el contrato primero porque cita a los demás.
  - **LLM zero-shot híbrido** (`benchmark.py`, `clasificar-zero-shot`): estima el costo con una muestra estratificada de `count_tokens` y corta si el gasto real pasa el tope.
  - **LLM few-shot** (`fewshot.py`, `clasificar-few-shot`): el mismo prompt más 6 ejemplos de texto recortado. `select_examples` la escribí yo con la solución de Claude: uno por clase y, en garantía, un título y una caución. Los ejemplos salen de la evaluación. Zero-shot y few-shot comparten `run_llm_classifier` en la CLI.
  - **TF-IDF y embeddings + regresión logística** (`vectors.py`, `clasificar-vectores`): `multilingual-e5-small` corre local con `sentence-transformers`. Las dependencias van en el extra `ml`, y `torch` sale del índice de PyTorch solo CPU (configurado en la raíz). `split_by_legajo` la escribí yo: sortea legajos, no documentos, con `random.Random(seed)`.
  - **Resultados:**

  | enfoque | aciertos | escaneos | costo | latencia |
  |---|---|---|---|---|
  | reglas | 557/565 | 0/8 | 0 | ~0 |
  | TF-IDF + RL | 194/204 (prueba) | 0/8 | 0 | 0,3 ms |
  | embeddings + RL | 194/204 (prueba) | 0/8 | 0 | 48,5 ms |
  | LLM zero-shot | 562/565 | 8/8 | USD 0,039 | 0,92 s |
  | LLM few-shot | 559/559 | 8/8 | USD 0,144 | 0,97 s |

  - **Verificado:** `uv run pytest packages/extractor` en verde, y `ruff check` y `ruff format` sin errores.
- **Qué aprendí:**
  - **Fuga de datos, en tres formas:**
    - Un ejemplo del few-shot que también se evalúa.
    - Un legajo partido entre entrenamiento y prueba (comparten nombres y domicilios), incluida la misma semilla repetida en varias carpetas del set forzado.
    - El vocabulario y el IDF de TF-IDF ajustados con la prueba.
  - **Comparación pareada:** con diferencias de 1 o 2 errores, dos enfoques se comparan sobre los mismos documentos. Contra el few-shot, el zero-shot tenía 2 errores, no 3: uno de los títulos que fallaba quedó como ejemplo.
  - **El few-shot arregló los títulos, pero cuesta 3,7 veces más:** suma 1.880 tokens de ejemplos en cada llamada. Además, el ejemplo sale de la misma plantilla que lo evaluado, así que la mejora está inflada con respecto a documentos reales.
  - **TF-IDF y embeddings fallan en lo mismo:** los escaneos (no tienen texto) y las cauciones (2 de entrenamiento contra unos 40 títulos, y vocabulario de seguro). El "significado" no ayuda cuando la clase la define una regla del dominio (la función del documento) y no el tema.
  - **La probabilidad de la regresión logística separa aciertos de errores:** en TF-IDF, los aciertos tienen p de 0,73 como mínimo y los errores p de 0,50. Eso habilita una cascada: lo seguro, local y gratis; lo dudoso, al LLM. La escala de confianza es propia de cada método, así que el umbral se calibra por método.
- **Dudas abiertas:**
  - Paso 4: unificar el conjunto de evaluación (los legajos de prueba de la separación) para que los 5 enfoques se comparen sobre los mismos documentos, con F1 por clase y matriz de confusión.
  - Probar el zero-shot con una definición más precisa de `garantia` en el prompt: cuesta cero tokens extra y quizá iguala al few-shot.
  - `garantia` necesita subtipo (título o caución): ahora lo respaldan los errores de TF-IDF y de los embeddings.
  - `select_examples` y el subtipo dependen del nombre del archivo; con las fotos de la Fase 3 (`IMG_4821.jpg`) eso no va a funcionar.
  - Embeddings de imagen (CLIP o SigLIP) para que un clasificador local también lea escaneos y fotos.

### 2026-11-09 — Fase 2, paso 4: métricas y clasificador elegido
- **Qué construí:**
  - `splits.py`: la separación por legajo, que antes estaba en `vectors.py`. Así la comparación no depende del extra `ml`.
  - `metrics.py`: matriz de confusión, accuracy, F1 macro y `class_metrics`, con precisión, recall y F1 por clase (la escribió Claude, a pedido mío).
  - `compare.py` y la CLI `comparar-clasificadores`. Evalúan los enfoques sobre **el mismo conjunto**: la prueba de la separación por legajo más los escaneos, menos lo que algún enfoque no evaluó. Leen las corridas guardadas (sin gastar) y recalculan las reglas.
  - Experimento `clasificar-zero-shot-def`: el mismo prompt con una sola línea cambiada, la definición de `garantia`. Para eso, las definiciones pasaron a `DEFINICIONES` y el prompt v1 quedó congelado por un test.
  - `test_cli.py`: corre las CLIs del LLM de punta a punta con un cliente falso. Una corrida de USD 0,04 se perdió porque un nombre importado dos veces hizo caer el programa después de las llamadas. Desde ahora, los resultados se guardan apenas terminan las llamadas.
  - **Verificado:** `uv run pytest packages/extractor`, 107 passed.
  - **Resultados:**

  | enfoque | accuracy | F1 macro | escaneos | USD cada 1.000 docs | latencia |
  |---|---|---|---|---|---|
  | reglas | 96,1 % | 0,973 | 0/8 | 0 | 0,1 ms |
  | TF-IDF + RL | 95,1 % | 0,949 | 0/8 | 0 | 0,3 ms |
  | embeddings + RL | 95,1 % | 0,949 | 0/8 | 0 | 48,5 ms |
  | LLM zero-shot (v1) | 99,5 % | 0,991 | 8/8 | 0,075 | 953 ms |
  | **LLM zero-shot (definición nueva)** | **100 %** | **1,000** | **8/8** | **0,079** | **939 ms** |
  | LLM few-shot | 100 % | 1,000 | 8/8 | 0,263 | 1.018 ms |

  Son 204 documentos comunes. Sobre los 565 del set, el zero-shot con la definición nueva acierta 565 de 565 por USD 0,041.
- **Clasificador elegido: el LLM zero-shot con entrada híbrida y la definición nueva de `garantia`.**
  - Es el único enfoque barato que lee imágenes, y el producto es "legajos a partir de fotos". En la Fase 3, casi nada va a tener capa de texto.
  - Iguala al few-shot con 3,3 veces menos costo, sin ejemplos que mantener y sin el riesgo de que los ejemplos salgan de la misma plantilla que lo evaluado.
  - Un legajo de unas 15 fotos cuesta alrededor de USD 0,001.
  - Reglas y TF-IDF quedan como líneas de base para las evals de la Fase 6.
- **Qué aprendí:**
  - **Accuracy esconde las clases chicas.** Por clase, todos los errores fueron de recall, no de precisión: documentos que se escapan, que en un legajo son faltantes falsos.
  - **Una falsa alarma de una clase es un error de otra.** La caución que TF-IDF llama `seguro` le baja el recall a `garantia` y la precisión a `seguro`.
  - **El error del zero-shot estaba en la definición, no en el modelo.** El título dice "constancia de titularidad de inmueble" y la definición pedía "de un garante". Describir lo que se ve en el documento arregló lo mismo que 6 ejemplos, con 1.880 tokens menos por llamada.
  - **Un experimento con prompts cambia una sola cosa por vez**, y el prompt viejo se congela: las corridas guardadas valen solo para el prompt con el que se hicieron.
  - **Con 204 documentos, 1 error es 0,5 %:** la diferencia no es estadísticamente distinguible. La decisión se apoya en el costo, los escaneos y el tipo de error.
  - **En un proceso que gasta, primero se guarda y después se calcula.**
- **Dudas abiertas:**
  - Con la definición nueva, ¿el seguro de incendio de un set real se confunde con `garantia`? En el set sintético, no.
  - El set sintético se arma con plantillas, así que el 100 % es sobre documentos fáciles. La medición que importa es con las fotos de la Fase 3 y con la clase `otro` (intrusas), que este set no tiene.
  - Latencia: unos 0,9 s por documento en secuencia. En el servicio, paralelizar las llamadas de un legajo.
  - Progreso visible en las CLIs largas (un contador cada N documentos).

### Cierre de la Fase 2: clasificación de documentos
- **Terminado cuando:** "hay una tabla comparativa de los 4 enfoques y un clasificador elegido con su justificación". Se cumple con la tabla de arriba (los 4 enfoques del roadmap, más el few-shot y la variante con la definición nueva) y la elección del zero-shot híbrido con la definición nueva.
- **Lo que deja para las fases siguientes:** `call_llm` como única puerta, con costo exacto y logs sin contenido; la entrada híbrida; `comparar-clasificadores` como base de las evals; y la separación por legajo para todo lo que se entrene.
