---
name: python-uv
description: Convenciones de Python y del workspace de uv de este repo. Usar al crear paquetes, agregar dependencias, escribir tests o configurar herramientas.
user-invocable: false
---

## Workspace
- La raíz tiene pyproject.toml con `[tool.uv.workspace]` y `members = ["packages/*"]`.
- Paquete nuevo: `uv init packages/<nombre> --lib` (desde la raíz; uv lo agrega al workspace).
- Dependencia de un paquete: `uv add --package <nombre> <dep>`. Herramientas de desarrollo en la raíz: `uv add --dev <dep>`.
- Un paquete usa otro del workspace declarándolo como dependencia con `{ workspace = true }` en `[tool.uv.sources]`.
- Correr algo de un paquete: `uv run --package <nombre> <comando>`.
- El lockfile (`uv.lock`) se commitea siempre.

## Código
- Layout `src/`, type hints completos, pydantic para modelos, pathlib para rutas, logging en vez de print en código de librería.
- Modelos de datos compartidos (por ejemplo, el esquema de `Comprobante`) viven en el paquete `core`.
- Llamadas a APIs externas: timeouts explícitos, reintentos con backoff y errores tipados.
- Secretos por variables de entorno (pydantic-settings), nunca hardcodeados.

## Tests
- pytest, un directorio `tests/` por paquete.
- Tests rápidos y sin red por defecto; los que llaman a un LLM o a la web se marcan con `@pytest.mark.slow` o `@pytest.mark.network`.
