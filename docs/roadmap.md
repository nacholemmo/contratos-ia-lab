# Roadmap — contratos-ia-lab

Alcance desde el 2026-11-07 ([ADR 0001](adr/0001-reenfoque-a-legajos.md)): este repo es el
**servicio de IA sin estado que arma legajos de alquiler a partir de fotos**. Entran fotos o
PDFs desordenados (DNI en frente y dorso, recibos, garantías y, al cierre, contrato y
seguro) y sale un **legajo sugerido**: documentos agrupados y asignados a cada persona y
rol, datos con evidencia, faltantes según los requisitos y alertas de cruces. Una persona
lo confirma en Avisa, y lo confirmado se exporta en un formato versionado que puede
importar otro sistema.

Historia del alcance: el 2026-10-18, servicio de IA del módulo Alquileres de Avisa
(contratos); el 2026-10-22, interfaz MCP, agente con LangGraph y repo público.

Calendario: nov. Fases 2 y 3 · dic. Fases 4 y 5 · ene. Fase 6 · feb. Fases 7 y 8 ·
mar. Fases 9 y 10 · después, la fase opcional.

Recursos: [Scrimba] = AI Engineer Path de Scrimba · [Path] = Path autodidacta: AI Engineer.

## El legajo en dos etapas
- **Etapa 1, evaluación** (antes de firmar): DNI, recibos de sueldo y garantía (título o
  caución) del inquilino y de los garantes. La inmobiliaria manda el alquiler propuesto y
  el servicio calcula la relación alquiler/ingresos. **Es la prioridad.**
- **Etapa 2, cierre:** se suman el contrato y el seguro, cruzados contra el legajo.
El motor es el mismo para las dos; cambian los requisitos y los cruces.

## Principios del servicio
- **Sin estado:** no guarda documentos ni su contenido, tampoco en logs. Entran fotos, sale
  un legajo sugerido, y no queda nada (tampoco lo que se bajó de una URL).
- **Datos sugeridos:** todo lo extraído es una sugerencia con evidencia (fragmento, foto o
  página). La confirmación la hace una persona en Avisa.
- **Documentos no confiables:** el texto de un documento es dato, nunca instrucción
  (prompt injection).
- **Cruces y cuentas con código:** las alertas, los faltantes y la relación
  alquiler/ingresos los calcula código determinístico sobre los datos extraídos. El LLM
  extrae; no compara ni calcula.
- **Referencias controladas:** los documentos llegan por ruta (dentro de una carpeta
  permitida) o por URL firmada de un host permitido; nada más.
- **Sintético y marcado:** el repo solo tiene datos sintéticos (Ley 25.326) y todo lo
  generado viene marcado como sintético.
- **Determinismo donde se puede:** el generador no usa LLM; con la misma semilla sale el
  mismo legajo.

## Fuera de este repo
En Avisa: base de datos, multi-tenant, usuarios y login, y la revisión y confirmación del
legajo. Fuera del producto (ADR 0001): aumentos, calendario de vencimientos, cartera,
avisos, cobranza, liquidaciones y asistente sobre la cartera; si existen, serán otra app
que importa el `LegajoExport`. El fine-tuning también queda afuera por ahora.

RAG: no hace falta para extraer ni para armar el legajo, porque cada documento entra
entero en el contexto. El RAG sobre normativa queda como fase opcional al final.

## Paquetes
- `packages/core` — modelos pydantic: documentos, legajo sugerido, export y ground truth.
- `packages/synthetic` — generador de legajos (en PDF y fotografiados) y de contratos.
- `packages/extractor` — clasificación y extracción por documento.
- `packages/legajo` — armado: calidad de foto, agrupación, asignación, cruces y checklist.
- `packages/evals` — evaluaciones contra el generador.
- `packages/mcp` — servidor MCP: la interfaz para Avisa y para Claude.
- `packages/agent` — agente con LangGraph, cliente del servidor MCP.
- `packages/normativa` — RAG sobre el Código Civil y el DNU 70/2023 (opcional).
- `schemas/` — JSON Schema publicados y versionados: `legajo.v1.json` (el sugerido) y
  `legajo-export.v1.json` (el confirmado), con su documentación y ejemplos.

`core`, `synthetic`, `extractor`, `legajo` y `evals` forman el servicio sin estado.
`agent` y `normativa` lo consumen; el servicio no depende de ellos.

## Fase 0 — Setup del laboratorio ✅
Objetivo: monorepo listo para trabajar.
Conceptos: uv, workspaces, lockfiles, lint, tests.
Pasos:
1. ✅ Instalar uv y fijar Python 3.12 (uv python pin). Heredado de facturas-ai-lab.
2. ✅ git init y .gitignore (data/, .env, .venv). Heredado de facturas-ai-lab.
3. ✅ Workspace: pyproject.toml raíz con [tool.uv.workspace]. Heredado de facturas-ai-lab.
4. ✅ ruff y pytest como dependencias de desarrollo, configurados en el pyproject raíz (excluir archive/).
5. ✅ Modelos pydantic en core: Persona, Propiedad, Contrato, Evidencia y Documento.
6. ✅ Primeros tests: un Contrato válido; CUIT con dígito verificador inválido rechazado; dinero como Decimal.
Terminado cuando: uv sync funciona en limpio, uv run pytest pasa y ruff no reporta errores.

## Fase 1 — Generador sintético (packages/synthetic) ✅
Objetivo: `generate_contract(seed) -> (pdf, Contrato)` determinístico, con casos difíciles.
Recursos: [Path] semana 1 (fundamentos de LLMs, para entender qué le va a costar al extractor).
Conceptos: datos sintéticos, ground truth, semillas y reproducibilidad, variación controlada.
Pasos:
1. ✅ Datos falsos coherentes con Faker (es_AR) y una semilla: personas con DNI y CUIT
   válidos (el CUIT derivado del DNI), direcciones, fechas y montos coherentes entre sí.
   Sale un `Contrato` que valida.
2. ✅ Plantillas con Jinja2 y variantes de redacción: índice (IPC, ICL, Casa Propia, UVA,
   dólares, monto fijo), frecuencia (3, 4, 6, 12 meses), depósito, rescisión y
   expensas. La misma información, redactada de formas distintas. Montos en números,
   en letras o en ambos.
3. ✅ Render a PDF de varias páginas con la marca "SINTÉTICO" en cada página. El ground
   truth incluye la evidencia real de cada campo (fragmento y página), porque el
   generador sabe dónde puso cada dato.
4. ✅ Casos difíciles, cada uno etiquetado en el ground truth (`Muestra.casos`), para
   reportar la precisión por caso en la Fase 4. Cada semilla elige sus casos y un test
   puede forzarlos. En tres subpasos:
   - 4a. Etiquetas (`CasoDificil`), datos faltantes (fecha de firma en blanco, persona
     sin DNI ni CUIT, sin código postal; el campo en null en el ground truth) y montos
     solo en letras.
   - 4b. Cláusulas raras: canon escalonado por año, seguro de caución como garantía,
     guiones de relleno `.-----`, destino comercial para locales y oficinas, y una
     cláusula más larga que una página.
   - 4c. Escaneo torcido: páginas como imagen, con rotación, ruido y aspecto de
     fotocopia, sin capa de texto.
5. ✅ Documentos complementarios simples: DNI, recibo de sueldo, garantía y seguro. Sus
   modelos pydantic se agregan a core, con evidencia por campo gemelo (como `Contrato`).
   Se generan como un legajo coherente con el contrato de la misma semilla, para poder
   evaluar cruces (¿el DNI coincide con el del contrato?). Sin imitar el diseño de
   documentos oficiales: mismos datos, presentación propia y marca SINTÉTICO. En tres subpasos:
   - 5a. Modelo `DNI` y ficha de una página por cada parte del contrato.
   - 5b. Recibo de sueldo del inquilino: empleador inventado con CUIT válido, período,
     bruto, descuentos y neto coherentes con el alquiler.
   - 5c. Garantía (título del garante o póliza de caución, según el caso de 4b) y seguro
     del inmueble, con vigencia coherente con el plazo.
6. ✅ CLI: `uv run --package synthetic generate --n 50 --seed 42 --out data/synthetic/`,
   que escribe cada PDF con su JSON de ground truth.
Terminado cuando: hay 50 contratos y sus complementarios con su JSON; un test verifica
que cada JSON valida contra su modelo y otro que la misma semilla produce el mismo
contrato (mismos datos y mismo PDF).

## Fase 2 — Clasificación de documentos (packages/extractor) ✅
Objetivo: documento → tipo (contrato, DNI, recibo de sueldo, garantía, seguro u otro).
Recursos: [Scrimba] Intro to AI Engineering + Multimodality · [Path] semana 2.
Sin cambios por el reenfoque (ADR 0001): se cierra con el set de PDFs actual. La
clasificación de fotos (con `otro` y el lado del DNI) se mide en las Fases 5 y 6.
Conceptos: APIs de LLM, texto extraído vs. visión, tokens y costos, métricas de clasificación.
Pasos:
1. ✅ Llamada mínima a la API con el SDK oficial; registrar tokens, costo y latencia (sin
   registrar el contenido del documento).
2. ✅ Entrada del documento: texto extraído del PDF vs. imágenes de las páginas. Comparar
   calidad y costo, incluyendo los escaneos torcidos.
3. ✅ Comparar 4 enfoques: reglas, LLM zero-shot, few-shot y embeddings + regresión logística.
4. ✅ Métricas sobre el set sintético: accuracy, F1 por clase, matriz de confusión, costo y latencia.
Terminado cuando: hay una tabla comparativa de los 4 enfoques y un clasificador elegido
con su justificación.


## Fase 3 — Legajo fotografiado en el generador (packages/synthetic)
Objetivo: `generate_legajo(seed, modo, etapa) -> (fotos, LegajoEsperado)` determinístico,
con el desorden de la vida real y su ground truth.
Conceptos: augmentación realista, ground truth de estructura (no solo de campos),
inconsistencias inyectadas y etiquetadas, set sorteado y forzado.
Pasos:
1. ✅ Ground truth del legajo en core: `LegajoEsperado`, con la agrupación (foto →
   documento), la asignación (documento → persona y rol), las fotos descartadas con su
   motivo, los faltantes y las alertas esperadas.
2. ✅ DNI en frente y dorso: dos fichas de presentación propia (el dorso con el domicilio y
   los datos de emisión), sin imitar el diseño oficial ni su código de barras. La
   evidencia indica la foto (el lado) donde está cada dato.
3. ✅ Modo "legajo fotografiado": cada página como foto de celular, con perspectiva, sombra,
   brillo desparejo, desenfoque, recorte de bordes y fondo. JPG con rotación EXIF y
   nombres que no dicen nada (`IMG_4821.jpg`). Dos niveles (leve y fuerte) y alguna foto
   ilegible a propósito. Reutiliza `scan.py` y `Source`.
4. Modo "legajo sin contrato" (etapa 1): DNI de inquilinos y garantes, los últimos 3
   recibos por inquilino (y recibos de garantes, como pasa en la realidad) y título o
   caución. El alquiler propuesto sale del contrato de la semilla, que no se entrega. Modo
   "cierre" (etapa 2): suma el contrato y el seguro.
5. Desorden: fotos mezcladas (orden sorteado), duplicadas (la misma foto, o el mismo
   documento sacado dos veces) e intrusas de clase `otro` (sintéticas: una factura de un
   servicio, una captura de chat, una foto sin documento).
6. Inconsistencias inyectadas y etiquetadas (`Inconsistencia`, como `CasoDificil`), cada
   una con la alerta que el servicio debería levantar: recibo de otra persona, CUIL que no
   corresponde al DNI, DNI vencido, recibo viejo, neto que no cierra, titular del título
   que no es el garante, caución más corta que el plazo, ingreso insuficiente y documento
   faltante. Set sorteado y set forzado por inconsistencia.
7. CLI: `generate --modo fotografiado --etapa evaluacion`, con el manifest de casos e
   inconsistencias.
Terminado cuando: hay 50 legajos fotografiados de etapa 1 con su `LegajoEsperado` y un set
forzado por inconsistencia; la misma semilla da los mismos bytes; un test verifica que
cada inconsistencia inyectada tiene su alerta en el ground truth; y una muestra de fotos
se revisó a ojo.

## Fase 4 — Extracción de la etapa 1, con evidencia (packages/extractor)
Objetivo: documento (una o más fotos, o un PDF) → campos de su modelo pydantic, evidencia
por campo y advertencias, para DNI, recibo de sueldo y garantía.
Conceptos: salidas estructuradas, validación y reintentos, entrada multimodal, ruteo por
tipo, prompt injection.
Pasos:
1. Entrada de fotos: JPG, PNG y HEIC además de PDF; convertir HEIC, enderezar según EXIF y
   reducir a 1568 px de lado largo. Un documento puede ser varias fotos (frente y dorso).
2. Esquema de extracción derivado de los modelos de core, sin los campos internos (ids)
   para que el LLM no los invente.
3. Extracción estructurada del DNI (frente y dorso juntos) con evidencia por campo;
   validación con pydantic y reintento pasando el error al modelo.
4. Verificación determinística de la evidencia: en un PDF, el fragmento tiene que aparecer
   en la página indicada; en una foto, sin capa de texto, decidir qué se verifica. Si no
   se verifica, el dato queda con una advertencia.
5. Extractores de recibo de sueldo y de garantía (título o caución: decidir el subtipo,
   duda abierta de la Fase 1).
6. Advertencias por documento: dato sin evidencia, dato faltante, valores incoherentes
   (neto que no cierra).
7. Defensa contra prompt injection: el documento va como dato delimitado, nunca como
   instrucción; casos sintéticos con instrucciones escondidas.
8. Medir cuánto pierde la extracción con foto respecto del PDF.
Terminado cuando: `extract(documento)` devuelve tipo, campos, evidencia y advertencias
para DNI, recibo y garantía, en PDF y en foto, con tests sobre documentos sintéticos.

## Fase 5 — Armado del legajo (packages/legajo)
Objetivo: `build_legajo(referencias, requisitos, etapa, alquiler_propuesto) -> Legajo`
para la etapa 1, y el formato de export del legajo confirmado.
Conceptos: pipelines de documentos, filtro por calidad antes del LLM, agrupación,
resolución de entidades, reglas determinísticas, contratos de datos versionados.
Pasos:
1. Modelos en core: `Legajo`, `Etapa`, `Requisitos`, `Faltante` y `Alerta` (código,
   severidad y la evidencia de los dos lados del cruce), con `schema_version`. JSON Schema
   publicado en `schemas/legajo.v1.json`, para generar los tipos de Avisa.
2. Calidad de foto con código (resolución, desenfoque y brillo) antes de gastar en el LLM:
   las ilegibles salen como descartadas, con el pedido de otra foto.
3. Clasificación por foto con el clasificador de la Fase 2, sumando `otro` y el lado del
   DNI; duplicados por hash perceptual.
4. Agrupación de fotos en documentos: frente con dorso y páginas de un título juntas;
   recibos de meses distintos, separados.
5. Asignación de cada documento a una persona y su rol, resolviendo entidades por DNI,
   CUIL y nombre normalizado. Los casos dudosos quedan marcados; no se adivinan.
6. Cruces determinísticos: una regla por alerta de la Fase 3, sobre los datos extraídos.
   Relación alquiler/ingresos con `Decimal`.
7. Checklist por requisitos: los requisitos llegan en cada llamada (sin estado) y salen
   los faltantes por persona y rol.
8. `LegajoExport`, separado del `Legajo` sugerido: solo datos confirmados, sin scores ni
   alertas internas, con `schema_version` semver. Lo arma Avisa con lo confirmado (ADR 0001);
   acá viven el modelo, el schema y el ejemplo. Publicado en
   `schemas/legajo-export.v1.json`, documentado campo por campo
   (`schemas/legajo-export.md`, generado desde las `description` para que no se
   desactualice) y con un ejemplo generado desde una semilla sintética.
9. Reglas de compatibilidad (`schemas/COMPATIBILIDAD.md`): parche si cambian solo las
   descripciones; menor si se agrega un campo opcional; mayor si se renombra, se quita, se
   cambia un tipo o un campo pasa a obligatorio. Una versión mayor es un archivo nuevo
   (`v2.json`) y el anterior se mantiene. Test que falla si el schema generado difiere del
   publicado sin subir la versión, y si una versión menor quita o vuelve obligatorio algo.
Terminado cuando: `build_legajo` arma los 50 legajos fotografiados de etapa 1 de punta a
punta; los dos schemas validan sus ejemplos; y el test de compatibilidad falla con un
cambio de schema sin versión nueva.

## Fase 6 — Evaluaciones contra el generador (packages/evals)
Objetivo: saber cuán bien extrae y arma el servicio, y detectar regresiones.
Recursos: [Path] semana 5.
Conceptos: ground truth, métricas por campo y de estructura, comparación normalizada,
evals de regresión, tracing.
Pasos:
1. Comparadores por tipo de campo: exacto (CUIT, fechas), numérico (montos como
   Decimal), texto normalizado (nombres, direcciones).
2. Precisión por campo y por tipo de documento, con desglose por caso difícil y por
   calidad de foto. Set sorteado y forzado por separado.
3. Evaluación de la evidencia: ¿el fragmento y la foto o página coinciden con los del
   generador?
4. Clasificación por foto (con `otro`) y calidad: F1 por clase, ilegibles y duplicadas
   detectadas.
5. Agrupación: ¿las fotos de cada documento quedaron juntas? (métrica a elegir) y tasa de
   documentos perfectos.
6. Asignación: % de documentos con la persona y el rol correctos, alineando las personas
   sugeridas con las del ground truth.
7. Faltantes y alertas: precisión y recall por código contra lo esperado, con desglose por
   inconsistencia inyectada. Una alerta perdida cuesta más que una de más: reportar el
   recall aparte.
8. Robustez: tasa de éxito de los casos con prompt injection.
9. Costo y latencia por legajo (no solo por documento); reporte en Markdown.
10. Tracing con Langfuse: cada armado deja su traza (llamadas, tokens, costo, latencia),
    sin contenido de documentos reales.
11. Comparar dos modelos o dos prompts sobre el mismo set y documentar cuál gana y por qué.
12. Set chico de regresión que corre en CI.
Terminado cuando: un comando genera el reporte (campos, agrupación, asignación, faltantes,
alertas y costo por legajo), hay una comparación documentada de dos modelos o prompts y el
set de regresión corre en CI.

## Fase 7 — Servidor MCP (packages/mcp)
Objetivo: Avisa (y Claude) usan el servicio a través de un servidor MCP propio.
Recursos: [Scrimba] Model Context Protocol · Anthropic Academy: Introduction to MCP.
Conceptos: MCP (tools, esquemas, transportes), cliente vs. servidor, autenticación
servicio a servicio, SSRF.
Pasos:
1. Servidor mínimo con una tool, probado desde Claude Code (transporte stdio).
2. Referencias: `{ruta}` dentro de una carpeta permitida o `{url}` firmada. Solo https,
   hosts permitidos desde `.env`, sin seguir redirecciones a otro host, sin IPs privadas,
   con límite de tamaño y de cantidad, timeout y tipo de contenido. Un test por rechazo.
3. Tool `extract_document(referencia)`: tipo, campos, evidencia y advertencias como datos
   sugeridos, con `outputSchema` derivado de core.
4. Tool `build_legajo(referencias, requisitos, etapa, alquiler_propuesto)`: el `Legajo`
   sugerido, con `outputSchema` igual a `schemas/legajo.v1.json`.
5. Tool `generate_synthetic_legajo(seed, modo, etapa)`: fotos y `LegajoEsperado`, marcados
   como sintéticos.
6. Transporte Streamable HTTP con token de servicio (comparación en tiempo constante,
   desde `.env`).
7. Sin estado: los documentos (también los bajados por URL) solo viven en memoria durante
   la llamada; logs sin contenido. Tests que lo verifican.
8. Cliente de prueba que simula a Avisa, y guía para conectarlo desde el backend NestJS,
   con los tipos TypeScript generados desde `schemas/`.
Terminado cuando: los tests del servidor pasan (auth, referencias rechazadas, armado,
semilla reproducible, logs sin contenido) y las tres tools funcionan desde Claude Code y
desde el cliente de prueba.

## Fase 8 — Etapa 2: cierre con contrato y seguro
Objetivo: el mismo `build_legajo` con `etapa=cierre`.
Conceptos: documentos largos, cruces entre etapas.
Pasos:
1. Extracción del contrato (generador y ground truth ya hechos en la Fase 1) y del seguro.
2. Cruces contra el legajo: partes del contrato contra personas del legajo (nombre y DNI),
   alquiler del contrato contra el propuesto, garantía del contrato contra la del legajo, y
   seguro con el inicio y la ubicación del contrato.
3. Requisitos y faltantes del cierre.
4. Métricas de la etapa 2 en el reporte de la Fase 6.
Terminado cuando: `build_legajo(etapa=cierre)` arma los legajos de cierre sintéticos con
sus alertas y el reporte de evals suma la etapa 2.

## Fase 9 — Agente con LangGraph (packages/agent)
Objetivo: resolver con un agente solo lo que el armado determinístico deja ambiguo: la
agrupación y la asignación.
Recursos: [Scrimba] Agents, Context Engineering · [Path] semana 4.
Conceptos: orquestación con estado, herramientas acotadas, human-in-the-loop, agentes
como clientes MCP.
Alcance: el agente no extrae desde cero ni decide cruces, faltantes o la relación
alquiler/ingresos (eso sigue en código). Interviene cuando la Fase 5 marca una duda: un
dorso sin frente, dos personas con el mismo apellido, un recibo con el nombre abreviado o
un título con dos titulares.
Pasos:
1. Grafo mínimo en LangGraph con estado tipado.
2. Herramientas vía MCP: ver una foto, volver a extraer un documento, proponer un
   reagrupamiento o una asignación.
3. Si la evidencia no alcanza para resolver la duda, la deja para la persona
   (human-in-the-loop) con la pregunta concreta.
4. Set forzado de legajos ambiguos en el generador.
5. Evals: ¿mejora la agrupación y la asignación sobre el set ambiguo respecto del armado
   sin agente? ¿Con cuántos pasos y a qué costo?
Terminado cuando: el agente procesa el set ambiguo de punta a punta, con pausa de revisión
en los casos que no resuelve, y un reporte compara agrupación, asignación, pasos y costo
con y sin agente.

## Fase 10 — Deploy y LLMOps
Objetivo: el servidor MCP corre en un entorno al que solo llega Avisa, con costos y calidad a la vista.
Recursos: [Scrimba] Deployment · [Path] semana 7.
Conceptos: contenedores, secretos, red privada, versionado de prompts, evals en CI, observabilidad sin datos personales.
Pasos:
1. Imagen Docker reproducible a partir del workspace de uv.
2. Secretos (token de servicio, API key del LLM, hosts permitidos) fuera de la imagen.
3. Red privada: el servicio no queda expuesto al público.
4. CI/CD que corre los tests, el test de compatibilidad de schemas y el set de regresión
   de evals en cada cambio.
5. Versionado de prompts y modelos: cada legajo registra con qué versión se armó.
6. Healthcheck y métricas (costo y latencia por legajo, errores) sin contenido de documentos.
7. Prueba de punta a punta desde el cliente que simula a Avisa, y post técnico con las
   decisiones y los números.
Terminado cuando: el servicio está desplegado, un armado de punta a punta funciona con un
legajo sintético y el costo y la latencia por legajo están a la vista.

## Fase opcional — RAG sobre normativa (packages/normativa)
Fuera del producto (ADR 0001): para aprender y para el portfolio, si queda tiempo. El
servicio no depende de esta fase y `search_normativa` no es parte del MCP del producto.
Recursos: [Scrimba] Embeddings and Vector Databases · [Path] semana 3.
Conceptos: chunking, embeddings, búsqueda vectorial, búsqueda híbrida, reranking, citas.
Pasos:
1. Bajar el capítulo de locación del Código Civil y Comercial y el DNU 70/2023
   (InfoLEG y Boletín Oficial), con scraping responsable y caché.
2. Chunking por artículo (la unidad natural de la ley) e índice de solo lectura.
3. Búsqueda vectorial, después híbrida (vectorial + palabras clave).
4. Reranking de resultados.
5. Respuesta con cita al artículo; si la ley no lo dice, "no encontré" en vez de inventar.
6. Set de preguntas con su artículo correcto y métricas de recuperación y de respuesta,
   midiendo cuánto mejora cada técnica.
Terminado cuando: hay una tabla con la mejora de vectorial → híbrida → reranking sobre el
set de preguntas, y cada respuesta cita su artículo.
