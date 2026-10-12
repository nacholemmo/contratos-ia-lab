---
name: revisar-mi-codigo
description: Revisión de código en modo mentor sobre los cambios actuales.
disable-model-invocation: true
---

Revisá mis cambios sin commitear (git diff) como un mentor senior:

1. Primero decime qué está bien hecho y por qué.
2. Después, como máximo 3 mejoras ordenadas por impacto. Para cada una: qué cambiar, por qué importa (corrección, legibilidad, rendimiento o seguridad) y una pista de cómo hacerlo, sin reescribir el código.
3. Corré `uv run ruff check` y `uv run pytest` y explicá cualquier error.
4. Si hay algo de AI Engineering relevante (manejo de errores del LLM, costos, validación de salidas, prompt injection), mencionalo.

No modifiques archivos salvo que te lo pida.
