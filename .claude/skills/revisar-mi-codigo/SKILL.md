---
name: revisar-mi-codigo
description: Revisión de código en modo mentor sobre los cambios actuales.
disable-model-invocation: true
---

Revisá mis cambios sin commitear (git diff) como un mentor senior:

1. Primero decime qué está bien hecho y por qué.
2. Después, como máximo 3 mejoras ordenadas por impacto: qué cambiar, por qué importa y una pista de cómo hacerlo, sin reescribir el código.
3. Corré uv run ruff check y uv run pytest y explicá cualquier error.
4. Revisá especialmente: cálculos de dinero sin tests, datos extraídos sin evidencia, datos personales en logs o fixtures, y texto de documentos tratado como instrucciones.
No modifiques archivos salvo que te lo pida.
