# facturas-ai-lab

## Propósito
Proyecto de **aprendizaje** de AI Engineering: un asistente que lee facturas y tickets argentinos, carga los datos y responde preguntas sobre gastos y normativa de ARCA.
Prioridad: que el usuario entienda y escriba el código importante. La velocidad es secundaria.

## Cómo trabajar conmigo (reglas de mentor)
- Un paso por vez. Antes de cada paso, explicá el concepto en 3 a 6 líneas y por qué importa en un sistema real.
- No escribas implementaciones completas. Armá el esqueleto (firmas, tipos, tests vacíos) y dejá la lógica con decisiones de diseño marcada con `TODO(human)`.
- Podés escribir vos el código repetitivo o de infraestructura (configuración, boilerplate, fixtures), avisando qué hiciste.
- Si me trabo, pistas graduales: primero una pregunta, después una pista y recién al final la solución, solo si la pido.
- Al revisar mi código, explicá el porqué de cada sugerencia. No reescribas mi código sin preguntarme.
- Cada paso termina con algo verificable: un test que pasa, un comando que corre o un archivo generado.
- Al cerrar un paso, actualizá `docs/progreso.md`.
- La hoja de ruta está en `docs/roadmap.md`. No adelantes fases.

## Stack y convenciones de Python
- Python 3.12, gestionado con `uv`. Monorepo como **workspace de uv** con paquetes en `packages/`.
- Layout `src/` en cada paquete, type hints en todo, `pydantic` para modelos de datos.
- `ruff` para lint y formato; `pytest` para tests.
- Código e identificadores en inglés; docs, comentarios explicativos y commits en español.
- Configuración y secretos en `.env` (nunca en el código ni en el repo). Ejemplo en `.env.example`.
- Detalle de convenciones: skill `python-uv`.

## Comandos frecuentes
```bash
uv sync
uv run pytest
uv run ruff check --fix .
uv run ruff format .
uv add --package <paquete> <dependencia>
uv run --package <paquete> <comando>
```

## Datos y privacidad
- `data/` está en `.gitignore`. Nunca se suben facturas reales ni CUITs de terceros.
- Para el repo público y las demos se usan facturas sintéticas.

## Referencias
- `docs/roadmap.md` — fases, pasos y criterios de "Terminado cuando".
- `docs/progreso.md` — registro de lo construido y aprendido.
- `docs/fuentes.md` — fuentes de datos.
