---
name: python-uv
description: Convenciones de Python y del workspace de uv de este repo. Usar al crear paquetes, agregar dependencias, escribir tests o configurar herramientas.
user-invocable: false
---

## Workspace
- La raíz tiene pyproject.toml con `[tool.uv.workspace]` y `members = ["packages/*"]`.
- Paquete nuevo: `uv init packages/<nombre> --lib` (desde la raíz). Revisar que `requires-python` quede en `>=3.12` (uv copia el pin exacto).
- Dependencia de un paquete: `uv add --package <nombre> <dep>`. Herramientas de desarrollo en la raíz: `uv add --dev <dep>`.
- Un paquete usa otro del workspace con `{ workspace = true }` en `[tool.uv.sources]`.
- Correr algo de un paquete: `uv run --package <nombre> <comando>`. El `uv.lock` se commitea.

## Código
- Layout `src/`, type hints completos, pydantic para modelos, pathlib para rutas, logging en vez de print en librerías.
- Los modelos compartidos (Contrato, Persona, Propiedad, Ajuste, Evento, Documento) viven en el paquete `core`.
- Dinero con `Decimal`, nunca `float`. Fechas con `date` y zona horaria `America/Argentina/Buenos_Aires` cuando importe la hora.
- APIs externas: timeouts explícitos, reintentos con backoff y errores tipados.
- Secretos por variables de entorno (pydantic-settings).

## Tests
- pytest, un `tests/` por paquete. Sin red por defecto; los que llaman a un LLM o a la web se marcan `@pytest.mark.slow` o `@pytest.mark.network`.
- Los cálculos de ajustes llevan tests con casos reales verificados a mano y tests de propiedades (hypothesis) para bordes: fin de mes, años bisiestos, índices faltantes.
