# Roadmap — contratos-ia-lab

Alcance desde el 2026-10-18: este repo es el **servicio de IA sin estado** del módulo
Alquileres de Avisa. Hace dos cosas: genera contratos sintéticos y extrae datos de
documentos. Avisa es la única fuente de verdad: guarda inmobiliarias, contratos,
personas y propiedades, hace la revisión humana, calcula aumentos y vencimientos y
manda los avisos.

Ajuste del 2026-10-22: el roadmap se alinea con el path de carrera (AI Engineer / FDE).
La interfaz con Avisa es un **servidor MCP propio** (no una API REST), y se suman, como
paquetes aparte que consumen el servicio, un RAG sobre normativa y un agente con LangGraph.
El repo es público.

Calendario: oct.–nov. Fases 1 a 3 · dic. Fase 4 · ene. Fase 5 · feb. Fases 6 y 7 · mar. Fase 8.

Recursos: [Scrimba] = AI Engineer Path de Scrimba · [Path] = Path autodidacta: AI Engineer.

## Principios del servicio
- **Sin estado:** no guarda documentos ni su contenido, tampoco en logs. Entra un
  documento, sale una respuesta, y no queda nada.
- **Datos sugeridos:** todo lo extraído es una sugerencia con evidencia (fragmento y
  página). La confirmación la hace una persona en Avisa.
- **Documentos no confiables:** el texto de un documento es dato, nunca instrucción
  (prompt injection).
- **Sintético y marcado:** el repo solo tiene datos sintéticos (Ley 25.326) y todo lo
  generado viene marcado como sintético.
- **Determinismo donde se puede:** el generador no usa LLM; con la misma semilla sale
  el mismo contrato.

## Fuera de este repo
Base de datos, multi-tenant, usuarios y login, cálculo de aumentos y vencimientos,
series de índices, avisos (email y WhatsApp) y pantalla de revisión: todo eso vive en
Avisa. El fine-tuning también queda afuera por ahora.

RAG: no hace falta para extraer, porque un contrato entra entero en el contexto.
- Sobre normativa: en este repo, como paquete aparte (Fase 5): corpus público e índice
  de solo lectura, sin datos personales.
- Sobre contratos: no se hace acá; los contratos viven en Avisa.

## Paquetes
- `packages/core` — modelos pydantic: esquemas de salida de la extracción y ground
  truth del generador.
- `packages/synthetic` — generador de contratos y documentos sintéticos.
- `packages/extractor` — clasificación y extracción.
- `packages/evals` — evaluaciones contra el generador.
- `packages/normativa` — RAG sobre el Código Civil y el DNU 70/2023.
- `packages/mcp` — servidor MCP: la interfaz para Avisa y para Claude.
- `packages/agent` — agente con LangGraph, cliente del servidor MCP.

`core`, `synthetic`, `extractor` y `evals` forman el servicio sin estado. `normativa` y
`agent` lo consumen; el servicio no depende de ellos.

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

## Fase 1 — Generador sintético (packages/synthetic)
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
4. Casos difíciles, cada uno etiquetado: escaneo torcido (página como imagen con
   rotación y ruido), montos solo en letras, cláusulas raras y datos faltantes (con el
   campo en null en el ground truth).
5. Documentos complementarios simples: DNI, recibo de sueldo, garantía y seguro. Sus
   modelos pydantic se agregan a core.
6. CLI: `uv run --package synthetic generate --n 50 --seed 42 --out data/synthetic/`,
   que escribe cada PDF con su JSON de ground truth.
Terminado cuando: hay 50 contratos y sus complementarios con su JSON; un test verifica
que cada JSON valida contra su modelo y otro que la misma semilla produce el mismo
contrato (mismos datos y mismo PDF).

## Fase 2 — Clasificación de documentos (packages/extractor)
Objetivo: documento → tipo (contrato, DNI, recibo de sueldo, garantía, seguro u otro).
Recursos: [Scrimba] Intro to AI Engineering + Multimodality · [Path] semana 2.
Conceptos: APIs de LLM, texto extraído vs. visión, tokens y costos, métricas de clasificación.
Pasos:
1. Llamada mínima a la API con el SDK oficial; registrar tokens, costo y latencia (sin
   registrar el contenido del documento).
2. Entrada del documento: texto extraído del PDF vs. imágenes de las páginas. Comparar
   calidad y costo, incluyendo los escaneos torcidos.
3. Comparar 4 enfoques: reglas, LLM zero-shot, few-shot y embeddings + regresión logística.
4. Métricas sobre el set sintético: accuracy, F1 por clase, matriz de confusión, costo y latencia.
Terminado cuando: hay una tabla comparativa de los 4 enfoques y un clasificador elegido
con su justificación.

## Fase 3 — Extracción por tipo de documento, con evidencia (packages/extractor)
Objetivo: documento clasificado → campos de su modelo pydantic, evidencia por campo y advertencias.
Conceptos: salidas estructuradas, validación y reintentos, documentos largos, ruteo por tipo, prompt injection.
Pasos:
1. Esquema de extracción derivado de los modelos de core, sin los campos internos (ids)
   para que el LLM no los invente.
2. Extracción estructurada de contratos con evidencia por campo; validación con
   pydantic y reintento pasando el error al modelo.
3. Verificación determinística de la evidencia: el fragmento tiene que aparecer en la
   página indicada. Si no, el dato queda con una advertencia.
4. Advertencias: dato sin evidencia, dato faltante, valores incoherentes (ej. depósito
   en otra moneda que el alquiler).
5. Extractores para DNI, recibo de sueldo, garantía y seguro, elegidos según el tipo de la Fase 2.
6. Defensa contra prompt injection: el documento va como dato delimitado, nunca como
   instrucción; casos sintéticos con instrucciones escondidas.
Terminado cuando: `extract(documento)` devuelve tipo, campos, evidencia y advertencias
para los 5 tipos, con tests sobre documentos sintéticos.

## Fase 4 — Evaluaciones contra el generador (packages/evals)
Objetivo: saber cuán bien extrae el servicio, campo por campo, y detectar regresiones.
Recursos: [Path] semana 5.
Conceptos: ground truth, métricas por campo, comparación normalizada, evals de regresión, tracing.
Pasos:
1. Comparadores por tipo de campo: exacto (CUIT, fechas), numérico (montos como
   Decimal), texto normalizado (nombres, direcciones).
2. Precisión por campo y por tipo de documento, y desglose por caso difícil.
3. Evaluación de la evidencia: ¿el fragmento y la página coinciden con los del generador?
4. Robustez: tasa de éxito de los casos con prompt injection.
5. Costo y latencia por documento; reporte en Markdown.
6. Tracing con Langfuse: cada extracción deja su traza (llamadas, tokens, costo,
   latencia), sin contenido de documentos reales.
7. Comparar dos modelos o dos prompts sobre el mismo set y documentar cuál gana y por qué.
8. Set chico de regresión que corre en CI.
Terminado cuando: un comando genera el reporte de precisión por campo y por tipo, hay
una comparación documentada de dos modelos o prompts y el set de regresión corre en CI.

## Fase 5 — RAG sobre normativa (packages/normativa)
Objetivo: preguntas sobre la ley de alquileres respondidas con cita al artículo.
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

## Fase 6 — Servidor MCP (packages/mcp)
Objetivo: Avisa (y Claude) usan el servicio a través de un servidor MCP propio.
Recursos: [Scrimba] Model Context Protocol · Anthropic Academy: Introduction to MCP.
Conceptos: MCP (tools, esquemas, transportes), cliente vs. servidor, autenticación servicio a servicio.
Pasos:
1. Servidor mínimo con una tool, probado desde Claude Code (transporte stdio).
2. Tool `extract_document`: recibe PDF o imagen (base64, con límite de tamaño); devuelve
   tipo, campos, evidencia y advertencias como datos sugeridos, con `outputSchema`
   derivado de los modelos de core.
3. Tool `generate_synthetic_contract`: semilla opcional; devuelve el PDF y sus datos
   correctos, marcados como sintéticos.
4. Tool `search_normativa`: consulta el RAG de la Fase 5 con cita al artículo.
5. Transporte Streamable HTTP con token de servicio (comparación en tiempo constante, desde `.env`).
6. Sin estado: el documento solo vive en memoria durante la llamada; logs sin contenido.
   Tests que lo verifican.
7. Cliente de prueba que simula a Avisa (y guía para conectarlo desde el backend NestJS).
Terminado cuando: los tests del servidor pasan (auth, extracción, semilla reproducible,
logs sin contenido) y las tres tools funcionan desde Claude Code y desde el cliente de prueba.

## Fase 7 — Agente con LangGraph (packages/agent)
Objetivo: un flujo multi-agente con estado que usa las tools del servidor MCP.
Recursos: [Scrimba] Agents, Context Engineering · [Path] semana 4.
Conceptos: orquestación con estado, supervisor/worker, human-in-the-loop, agentes como clientes MCP.
Pasos:
1. Grafo mínimo en LangGraph con estado tipado.
2. Workers: clasificador, extractor y consultor de normativa, cada uno vía MCP.
3. Supervisor que decide el siguiente paso según el tipo de documento y las advertencias.
4. Human-in-the-loop: los casos dudosos se pausan para revisión y siguen con la respuesta.
5. Evals del agente sobre el set sintético (¿llega al resultado correcto? ¿cuántos pasos y cuánto cuesta?).
Terminado cuando: el agente procesa un lote sintético de punta a punta, con pausa de
revisión en los casos dudosos y un reporte de precisión, pasos y costo.

## Fase 8 — Deploy y LLMOps
Objetivo: el servidor MCP corre en un entorno al que solo llega Avisa, con costos y calidad a la vista.
Recursos: [Scrimba] Deployment · [Path] semana 7.
Conceptos: contenedores, secretos, red privada, versionado de prompts, evals en CI, observabilidad sin datos personales.
Pasos:
1. Imagen Docker reproducible a partir del workspace de uv.
2. Secretos (token de servicio, API key del LLM) fuera de la imagen.
3. Red privada: el servicio no queda expuesto al público.
4. CI/CD que corre los tests y el set de regresión de evals en cada cambio.
5. Versionado de prompts y modelos: cada extracción registra con qué versión se hizo.
6. Healthcheck y métricas (costo y latencia por contrato, errores) sin contenido de documentos.
7. Prueba de punta a punta desde el cliente que simula a Avisa, y post técnico con las
   decisiones y los números.
Terminado cuando: el servicio está desplegado, una extracción de punta a punta funciona
con un documento sintético y el costo y la latencia por contrato están a la vista.
