# Fuentes de datos

## Comprobantes

- **Mis Comprobantes de ARCA**: export CSV/Excel de comprobantes recibidos y emitidos. El CSV sirve como ground truth para evaluar la extracción de los PDFs. Privado: va en `data/private/`, nunca se commitea (Fase 1C).
- **Tickets en papel**: fotos propias, etiquetadas a mano. Privadas.
- **Datasets públicos**: CORD (Hugging Face `naver-clova-ix/cord-v1`, CC BY 4.0) y SROIE, para volumen. No tienen formato argentino.
- **Facturas sintéticas**: generadas en la Fase 1A (`packages/invoice-generator`), cada una con su JSON de ground truth. Son las únicas que se usan en el repo público y en las demos.

## Normativa

- **Boletín Oficial** y **biblioteca normativa de ARCA** (Fase 1B, `packages/arca-scraper`).
- Guardar las relaciones entre normas (qué modifica a qué) y la vigencia de cada una.
- Scraping responsable: respetar `robots.txt` y términos de uso, pausas entre requests, User-Agent identificable y caché local en `data/raw/` para bajar cada documento una sola vez.
