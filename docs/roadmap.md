# Roadmap — contratos-ia-lab

Regla: primero la IA, después el producto.
Recursos: [Scrimba] = AI Engineer Path de Scrimba · [Path] = Path autodidacta: AI Engineer.
Track paralelo desde la semana 1: entrevistas con inmobiliarias (/entrevista, docs/validacion.md).

## Fase 0 — Setup del laboratorio
Objetivo: monorepo listo para trabajar.
Conceptos: uv, workspaces, lockfiles, lint, tests.
Pasos:
1. ✅ Instalar uv y fijar Python 3.12 (uv python pin). Heredado de facturas-ai-lab.
2. ✅ git init y .gitignore (data/, .env, .venv). Heredado de facturas-ai-lab.
3. ✅ Workspace: pyproject.toml raíz con [tool.uv.workspace]. Heredado de facturas-ai-lab.
4. ✅ ruff y pytest como dependencias de desarrollo, configurados en el pyproject raíz (excluir archive/).
5. Adaptar el paquete core (el Comprobante de facturas quedó en archive/facturas/models.py como referencia) con los modelos pydantic: Persona (rol: propietario, inquilino, garante; DNI o CUIT con validación), Propiedad, Contrato (partes, propiedad, inicio, plazo, monto inicial, moneda, índice, frecuencia de ajuste, depósito, régimen legal, cláusulas), Evidencia (texto, página) y Documento (tipo, archivo, vínculos).
6. Primeros tests: un Contrato válido; CUIT con dígito verificador inválido rechazado; dinero como Decimal.
Terminado cuando: uv sync funciona en limpio, uv run pytest pasa y ruff no reporta errores.

## Fase 1 — Datos
Recursos: [Path] semana 1 (fundamentos de LLMs). docs/fuentes.md.

### 1A — Generador de contratos sintéticos (packages/contract-generator)
Conceptos: datos sintéticos, ground truth, variación controlada.
Pasos:
1. Datos falsos coherentes con Faker (es_AR): personas, DNI y CUIT válidos, direcciones, montos.
2. Plantillas de contrato con Jinja2 para los tres regímenes y con variantes de redacción: índice (IPC, ICL, Casa Propia, UVA, dólares, monto fijo), frecuencia (3, 4, 6, 12 meses), depósito, cláusulas de rescisión y expensas. Que la misma información aparezca redactada de formas distintas.
3. Render a PDF de varias páginas y a "foto" (imagen con ruido y rotación).
4. Por cada contrato, su JSON con el modelo Contrato: es el ground truth.
5. CLI: uv run --package contract-generator generate --n 50 --out data/synthetic/
Terminado cuando: hay 50 contratos con su JSON, y un test verifica que cada JSON valida contra Contrato.

### 1B — Series de índices y normativa (packages/sources)
Conceptos: ingesta de datos oficiales, caché, versionado de datos.
Pasos:
1. Descargar las series de IPC (INDEC) e ICL (BCRA) a data/series/ con caché local y fecha de descarga.
2. Normalizar las series a un formato común (fecha, valor) con tests.
3. Bajar el texto del capítulo de locación del Código Civil y Comercial y del DNU 70/2023 (InfoLEG y Boletín Oficial), con scraping responsable (robots.txt, pausas, caché).
Terminado cuando: las series cargan desde caché sin red y hay tests de parseo con archivos guardados.

### 1C — Documentos complementarios sintéticos
DNI, recibos de sueldo y pólizas de seguro de caución sintéticos (simples), para el clasificador de la Fase 3.

## Fase 2 — Extracción de contratos (packages/extractor)
Objetivo: PDF o foto de contrato → Contrato con evidencia por campo.
Recursos: [Scrimba] Intro to AI Engineering + Multimodality · [Path] semana 2.
Conceptos: APIs de LLM, documentos largos, extracción de texto vs. visión, chunking, salidas estructuradas, validación y reintentos, tokens y costos.
Pasos:
1. Llamada mínima a la API con el SDK oficial; registrar tokens, costo y latencia.
2. Dos estrategias de entrada: texto extraído del PDF vs. imágenes de las páginas. Comparar calidad y costo en 5 contratos.
3. Extracción estructurada al modelo Contrato, con evidencia (fragmento y página) por cada campo.
4. Validación con pydantic y reintento pasando el error al modelo.
5. Lote de 50 contratos sintéticos y precisión por campo contra el ground truth. Prestar especial atención a índice, frecuencia, fecha de inicio y monto.
Terminado cuando: hay un reporte de precisión por campo y cada dato extraído tiene evidencia.

## Fase 3 — Clasificación de documentos y régimen — esbozo
Tipo de documento (contrato, DNI, recibo de sueldo, garantía o caución, seguro, otro) y régimen legal del contrato. Comparar 4 enfoques: reglas, LLM zero-shot, few-shot, embeddings + regresión logística. Métricas: accuracy, F1 por clase, matriz de confusión, costo y latencia. El tipo decide qué extractor se usa (ruteo).

## Fase 4 — Motor de ajustes y eventos (sin LLM) — esbozo
Cálculo determinístico de aumentos según índice y frecuencia con las series oficiales; calendario de eventos (aumentos, vencimiento del contrato, vencimiento de seguros); tests de casos reales verificados a mano y tests de propiedades. Lección: la IA solo donde aporta.

## Fase 5 — RAG sobre contrato y normativa — esbozo
[Scrimba] Embeddings and Vector Databases · [Path] semana 3.
Postgres + pgvector; preguntas sobre el contrato ("¿quién paga las expensas extraordinarias?") y sobre el Código Civil, siempre con cita a la cláusula o al artículo. Búsqueda híbrida.

## Fase 6 — Agente y MCP — esbozo
[Scrimba] Agents, Context Engineering, Model Context Protocol · [Path] semana 4.
Herramientas: buscar contrato o persona, calcular ajuste (motor de la Fase 4), próximos eventos, redactar aviso. Servidor MCP sobre la base de contratos.

## Fase 7 — App web, revisión humana y cartera — esbozo
[Scrimba] Deployment.
FastAPI y una interfaz simple: subir documentos, pantalla de revisión (dato extraído + evidencia + confirmar o corregir), fichas de propietarios, inquilinos, garantes y propiedades, multi-inmobiliaria (cada una ve solo lo suyo).

## Fase 8 — Canales: bot de WhatsApp y avisos — esbozo
Bot de WhatsApp (un número, solo administradores registrados): recibir documentos, responder con resumen y confirmar; resumen diario de avisos pendientes (plantilla de utilidad aprobada por Meta). Avisos a inquilinos: email automático y links wa.me con el mensaje prellenado (normalizar teléfonos a 549 + área + número). Registro de cada aviso.

## Fase 9 — Evals y observabilidad — esbozo
[Path] semana 5.
Evals de extracción por campo, de clasificación y de RAG (LLM como juez + revisión humana), trazas con Langfuse, evals en CI. Usar las correcciones de los administradores (Fase 7) como nuevos casos de eval.

## Fase 10 — Fine-tuning (opcional) — esbozo
[Scrimba] Open-source Models · [Path] semana 6.
Ajustar un modelo chico para el clasificador de la Fase 3 y sumarlo a su tabla comparativa.

## Fase 11 — Inferencia y costos — esbozo
[Path] semana 7.
Costo por contrato procesado, caching, ruteo de modelos (barato para clasificar, potente para extraer), modelo propio vs. API.

## Fase 12 — Seguridad y datos personales — esbozo
[Path] semana 8.
OWASP Top 10 para LLMs; contratos y PDFs sintéticos con prompt injection escondido; permisos por inmobiliaria y por usuario; cifrado; registro de accesos; cumplimiento de la Ley 25.326.

## Fase 13 — Piloto y portfolio — esbozo
Piloto con 1 o 2 inmobiliarias reales, README con arquitectura y decisiones, reporte de evals, video demo y post técnico.
