# ADR 0001 — Reenfoque a legajos de alquiler

- **Estado:** aceptado
- **Fecha:** 2026-11-07
- **Reemplaza:** el alcance del 2026-10-18 (servicio de IA para contratos del módulo
  Alquileres de Avisa). Del ajuste del 2026-10-22 se mantienen el MCP, el agente y el repo
  público; el RAG sobre normativa pasa a ser opcional.

## Contexto

Hasta acá el producto era la parte de IA de un sistema de gestión de contratos: leer el
contrato para que Avisa calcule aumentos y vencimientos y mande avisos. Tres cosas cambian
la mirada:

- **El trabajo manual pesado está antes de la firma.** La inmobiliaria junta y revisa los
  papeles del inquilino y de los garantes, que llegan como fotos sueltas por WhatsApp o
  mail: frente y dorso del DNI, recibos, títulos y pólizas, desordenados, a veces borrosos,
  duplicados o de otra cosa.
- **El valor está en los cruces, no en cada documento solo** (lo aprendido en la Fase 1,
  paso 5): ¿el recibo es de la misma persona que el DNI?, ¿el título es del garante?,
  ¿el ingreso alcanza para el alquiler?
- **La gestión de contratos es otro producto.** Aumentos, cobranza y liquidaciones son
  aritmética sobre datos ya cargados, con software establecido, y casi no necesitan IA.

Lo construido sirve tal cual. El generador ya arma un legajo coherente por semilla (DNI,
recibo, título o caución y seguro) con ground truth y evidencia, y la clasificación de la
Fase 2 es el primer paso del armado.

## Decisión

El producto pasa a ser **armar legajos de alquiler a partir de fotos, de forma fácil y
rápida**. Entran fotos o PDFs desordenados y sale un **Legajo sugerido** con:

- los documentos agrupados (las fotos que forman un mismo documento, como el frente y el
  dorso del DNI o las páginas de un título);
- cada documento asignado a una persona y a su rol (inquilino o garante);
- los datos extraídos, cada uno con su evidencia;
- las fotos descartadas (de otra cosa, duplicadas o ilegibles), con el motivo;
- los faltantes según los requisitos que manda la inmobiliaria;
- las alertas de cruces, calculadas con código determinístico.

El motor es el mismo para las dos etapas:

1. **Evaluación** (antes de firmar): DNI, recibos y garantías. La inmobiliaria aporta el
   alquiler propuesto para calcular la relación alquiler/ingresos. **Es la prioridad.**
2. **Cierre:** se suman el contrato y el seguro, cruzados contra el legajo de la etapa 1.

Una persona confirma el legajo en Avisa. Lo confirmado se exporta en un formato propio y
versionado (`LegajoExport`, JSON Schema con semver) para que lo pueda importar otro
sistema: Avisa, Spot, Barreeo o una futura app de gestión.

La interfaz sigue siendo el servidor MCP, ahora con las tools `extract_document`,
`build_legajo` y `generate_synthetic_legajo`.

### Lo que no cambia
Sin estado. La IA sugiere y una persona confirma en Avisa. Cada dato lleva su evidencia.
Los documentos son texto no confiable. Dinero y fechas con código determinístico. Solo datos
sintéticos en el repo. El generador es determinístico y no usa LLM. El DNI sintético no
imita el diseño oficial.

### Fuera de alcance
Aumentos, calendario de vencimientos, cartera, avisos, cobranza, liquidaciones y asistente
sobre la cartera. Si algún día existen, serán otra app, que recibe el `LegajoExport` como
entrada.

## Consecuencias

**Positivas**
- El problema que se ataca es el que más tiempo consume y donde la IA aporta más: leer
  fotos de mala calidad y ordenar el desorden.
- El generador de la Fase 1 se reutiliza casi entero: el legajo coherente por semilla ya
  trae los cruces en el ground truth.
- El export versionado desacopla el servicio de Avisa: cualquier sistema puede consumir un
  legajo confirmado sin conocer el modelo interno.
- Para el portfolio, el problema es más rico: pipeline de documentos, resolución de
  entidades, reglas determinísticas y contratos de datos versionados, además del LLM.

**Negativas o costos**
- Aparece un problema nuevo y más difícil que extraer: **agrupar y asignar**. Necesita
  ground truth propio (agrupación, asignación, faltantes y alertas) y métricas nuevas.
- `Contrato` pierde centralidad: su extracción pasa a la etapa 2. Las dudas de la Fase 1
  que solo importaban para los aumentos (escalones del canon) dejan de tener prioridad.
- Recibir referencias por URL abre riesgo de SSRF: hacen falta una lista de hosts
  permitidos, límites de tamaño y de cantidad, y tests de cada rechazo.
- Hay que mantener un contrato público (los schemas) con reglas de compatibilidad.
- Las fases se renumeran desde la 3, y el calendario se estira un mes.

**Neutras**
- El RAG sobre normativa queda como fase opcional al final: no lo necesita el producto,
  pero sirve para aprender búsqueda vectorial e híbrida. `search_normativa` sale del MCP
  del producto.
- La hipótesis de `docs/validacion.md` cambia: se validan legajos, no aumentos.
- La Fase 2 sigue igual. Se cierra con el set de PDFs actual, y la clasificación de fotos
  (con `otro` y el lado del DNI) se vuelve a medir dentro del armado.

## Alternativas consideradas

- **Seguir con la gestión de contratos.** Descartada: compite con software establecido, y
  la IA solo aporta en la carga inicial del contrato.
- **Legajo sin export propio, con el modelo interno como salida.** Descartada: ata a
  cualquier consumidor a los scores y alertas internas, que cambian seguido. Un formato
  confirmado y versionado se puede mantener estable.
- **Sacar el RAG del todo.** Posible. Se prefiere dejarlo como opcional porque no bloquea
  nada y cubre un tema del path de aprendizaje.

## Decisiones tomadas con este ADR

- **RAG sobre normativa:** queda como fase opcional al final, fuera del producto.
- **Paquete `legajo` aparte:** el armado vive en `packages/legajo`, que depende de
  `extractor`. `extractor` sigue trabajando un documento por vez y no sabe que existe un
  legajo (`legajo → extractor → core`). El armado, casi todo determinístico, se testea sin
  LLM.
- **El `LegajoExport` lo arma Avisa** con sus datos confirmados, validando contra el schema
  publicado. El servicio solo sugiere: nunca recibe ni devuelve datos confirmados.

## Decisiones abiertas

Se resuelven en la fase indicada, con `TODO(human)` en el código cuando corresponda.

| Decisión | Fase |
|---|---|
| Forma de los requisitos: lista declarativa por rol o presets con nombre | 5 |
| Qué se verifica de la evidencia en una foto, que no tiene capa de texto | 4 |
| Métrica de agrupación: F1 por pares, B-cubed o tasa de documentos perfectos | 6 |
| Agregar un valor a un enum del export: ¿cambio menor o mayor? | 5 |
| La evidencia en el export: no (minimización) o solo la referencia al documento | 5 |
| Cómo devuelve fotos `generate_synthetic_legajo`: recursos MCP, base64 o ruta | 7 |
