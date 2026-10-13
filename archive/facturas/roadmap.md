# Roadmap — facturas-ai-lab

Cada fase: objetivo, conceptos, recursos, pasos y "Terminado cuando".
Recursos: [Scrimba] = AI Engineer Path de Scrimba · [Path] = Path autodidacta: AI Engineer.

## Fase 0 — Setup del laboratorio
Objetivo: dejar el monorepo listo para trabajar.
Conceptos: gestión de entornos y versiones con uv, workspaces, lockfiles, lint, tests.
Pasos:
1. Instalar uv y verificar la versión. Fijar Python 3.12 con uv python pin.
2. git init, .gitignore (incluye data/, .env, .venv), primer commit con los docs.
3. Crear el workspace: pyproject.toml raíz con [tool.uv.workspace].
4. Crear el paquete core (uv init packages/core --lib) con el modelo pydantic Comprobante: CUIT emisor, razón social, tipo (A, B, C, ticket), punto de venta, número, fecha, neto, IVA, total, CAE opcional, ítems.
5. Agregar ruff y pytest como dependencias de desarrollo y configurarlos en el pyproject raíz.
6. Primer test: validar un Comprobante válido y rechazar uno con CUIT inválido (dígito verificador).
Terminado cuando: uv sync funciona en limpio, uv run pytest pasa y uv run ruff check no reporta errores.

## Fase 1 — Datos
Objetivo: tener datos para todo lo que sigue.
Recursos: [Path] semana 1 (fundamentos de LLMs, videos de Karpathy). docs/fuentes.md.

### 1A — Generador de facturas sintéticas (packages/invoice-generator)
Conceptos: datos sintéticos, ground truth para evals, plantillas.
Pasos:
1. Generar datos falsos coherentes con Faker (locale es_AR), CUIT con dígito verificador válido y totales que cierren (neto + IVA = total).
2. Plantilla HTML de factura A, B y C con Jinja2.
3. Render a PDF (WeasyPrint) y a imagen.
4. Por cada factura, guardar su JSON con el modelo Comprobante: es el ground truth.
5. Variantes "sucias": rotación, ruido y baja resolución, para simular fotos.
6. CLI: uv run --package invoice-generator generate --n 100 --out data/synthetic/
Terminado cuando: hay 100 facturas con su JSON, y un test verifica que cada JSON valida contra Comprobante.

### 1B — Scraper de normativa ARCA (packages/arca-scraper)
Conceptos: scraping responsable, caché, metadatos y relaciones entre normas.
Pasos:
1. Revisar robots.txt y los términos de las fuentes (Boletín Oficial y biblioteca normativa de ARCA).
2. Cliente HTTP con httpx: timeouts, rate limiting y User-Agent identificable.
3. Bajar cada documento una sola vez a data/raw/ (caché en disco).
4. Parsear a un modelo Norma: número, tipo, fecha, vigencia, texto, normas que modifica y que la modifican.
5. Empezar acotado: resoluciones generales de facturación y emisión de comprobantes.
Terminado cuando: hay al menos 30 normas parseadas con metadatos, con tests de parseo usando HTML guardado (sin red).

### 1C — Datos reales (opcional, privados)
Exportar Mis Comprobantes (Recibidos) de ARCA a CSV y guardar los PDFs en data/private/. Nunca se commitean.

## Fase 2 — Extracción con visión (packages/extractor)
Objetivo: imagen o PDF de factura → Comprobante validado.
Recursos: [Scrimba] Intro to AI Engineering + Multimodality · [Path] semana 2.
Conceptos: APIs de LLM, modelos con visión, salidas estructuradas, validación y reintentos, tokens y costos.
Pasos:
1. Llamada mínima a la API con el SDK oficial; registrar tokens, costo y latencia.
2. Enviar la imagen de una factura y pedir JSON.
3. Validar contra Comprobante; si falla, reintentar pasándole el error al modelo.
4. Procesar un lote de 20 facturas sintéticas y guardar los resultados.
5. Primera comparación contra el ground truth: % de campos correctos.
Terminado cuando: el extractor procesa el lote y se reporta la precisión por campo.

## Fase 3 — Búsqueda y RAG — esbozo
[Scrimba] Embeddings and Vector Databases · [Path] semana 3.
Postgres + pgvector con Docker Compose; embeddings de comprobantes y de normativa; búsqueda híbrida (embeddings + BM25); RAG sobre normativa que respeta la vigencia.

## Fase 4 — Agente y MCP — esbozo
[Scrimba] Agents, Context Engineering, Model Context Protocol · [Path] semana 4.
Agente con herramientas (consulta SQL, categorizar, sumar por período); servidor MCP que expone la base de comprobantes.

## Fase 5 — App y deploy — esbozo
[Scrimba] Vercel AI SDK (conceptos), Deployment.
API con FastAPI, interfaz simple para subir comprobantes y chatear, Docker y deploy con link público.

## Fase 6 — Evals y observabilidad — esbozo
[Path] semana 5.
Métricas por campo contra ground truth (sintéticas + CSV de ARCA), análisis de errores, LLM como juez para el RAG, trazas con Langfuse, evals corriendo en CI.

## Fase 7 — Fine-tuning — esbozo
[Scrimba] Open-source Models · [Path] semana 6.
Clasificador de categorías de gasto con un modelo chico y LoRA en Colab; comparación contra el modelo grande.

## Fase 8 — Inferencia y costos — esbozo
[Path] semana 7.
Servir el modelo ajustado (Ollama o vLLM), costo por 1.000 comprobantes propio vs. API, caching y ruteo de modelos.

## Fase 9 — Seguridad — esbozo
[Path] semana 8.
OWASP Top 10 para LLMs, protección de CUITs y montos, facturas sintéticas con prompt injection escondido, límites de gasto.

## Fase 10 — Cierre y portfolio — esbozo
README con arquitectura y decisiones, reporte de evals, video demo, post técnico.
