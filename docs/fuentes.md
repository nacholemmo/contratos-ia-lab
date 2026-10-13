# Fuentes de datos

## Contratos

- **Sintéticos** (Fase 1A, `packages/contract-generator`): para desarrollo y evals, cada uno con su JSON de ground truth. Son los únicos que se usan en el repo público y en las demos.
- **Reales**: solo con consentimiento de la inmobiliaria, anonimizados y en `data/private/`. Nunca se commitean.

## Índices

- **IPC** del INDEC e **ICL** del BCRA, descargados y cacheados con fecha de descarga (Fase 1B, `packages/sources`).
- **Índice Casa Propia**, para los contratos de la reforma de fines de 2023.

## Normativa

- **Código Civil y Comercial**, capítulo de locación, en InfoLEG.
- **DNU 70/2023**, en el Boletín Oficial.
- **Ley 27.551**, para contratos anteriores al DNU.

## Scraping responsable

Respetar `robots.txt` y términos de uso, pausas entre requests, caché local para bajar cada documento una sola vez y un User-Agent identificable.
