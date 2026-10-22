# Fuentes de datos

## Contratos

- **Sintéticos** (Fase 1A, `packages/contract-generator`): para desarrollo y evals, cada uno con su JSON de ground truth. Son los únicos que se usan en el repo público y en las demos.
- **Reales**: solo con consentimiento de la inmobiliaria, anonimizados y en `data/private/`. Nunca se commitean.

### Modelos de referencia (plantillas en blanco, sin datos personales)

Sirven para que las plantillas del generador se parezcan a contratos reales. Se leen; no se copian al repo.

- **GCBA, modelo de contrato de vivienda 2024** — https://vivienda.buenosaires.gob.ar/contratomodelo (el .doc está en `/modelo-contrato-2024`). 17 cláusulas: mora con tasa del BNA, falta de pago de 2 meses, inventario, entrega de llaves, rescisión con el 10% del saldo (arts. 1220 y 1221 del CCyC), domicilios electrónicos y Juzgados Nacionales en lo Civil.
- **Roomix, modelo 2026 posterior al DNU 70/2023** — https://roomix.ai/blog/modelo-contrato-alquiler-argentina-2026. Ajuste por IPC (trimestral, cuatrimestral o semestral), depósito devuelto actualizado, garantía propietaria o seguro de caución y rescisión con el 10% del saldo.
- **Gobierno de Mendoza, modelo de locación (2015)** — copia local en `data/` (ignorada). Es un contrato **administrativo**: el Estado es el inquilino (Ley provincial 8706), así que no representa a la vivienda. Sirve por el estilo: "ARTICULO N", canon en letras y números, canon escalonado por año, guiones de relleno `.-----` y cierre "a los __ días del mes de __". También como ejemplo de "contrato que no es de vivienda" para la Fase 2.

## Índices

- **IPC** del INDEC e **ICL** del BCRA, descargados y cacheados con fecha de descarga (Fase 1B, `packages/sources`).
- **Índice Casa Propia**, para los contratos de la reforma de fines de 2023.

## Normativa

- **Código Civil y Comercial**, capítulo de locación, en InfoLEG.
- **DNU 70/2023**, en el Boletín Oficial.
- **Ley 27.551**, para contratos anteriores al DNU.

## Scraping responsable

Respetar `robots.txt` y términos de uso, pausas entre requests, caché local para bajar cada documento una sola vez y un User-Agent identificable.
