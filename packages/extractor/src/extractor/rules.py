"""Clasificación por reglas: el enfoque base del paso 3, sin LLM.

Busca palabras clave en el texto extraído. Cuesta cero y es instantáneo, pero solo ve lo que
tiene capa de texto: un escaneo o una foto no tiene, y cae en `OTRO`. Sirve de línea de base:
cada enfoque más caro tiene que justificar cuánto mejora sobre esto.
"""

import unicodedata

from core.models import TipoDocumento

# En orden: gana la primera que aparece. El contrato va primero porque cita a los demás en sus
# cláusulas (DNI de las partes, seguro de caución, seguro contra incendio). Frases y no palabras
# sueltas: "caucion" sola matchea al seguro de una "Aseguradora ... de Cauciones S.A.".
RULES: list[tuple[tuple[str, ...], TipoDocumento]] = [
    (("contrato de locacion",), TipoDocumento.CONTRATO),
    (("ficha de identidad", "documento nacional de identidad"), TipoDocumento.DNI),
    (("recibo de haberes", "recibo de sueldo"), TipoDocumento.RECIBO_SUELDO),
    (("seguro de caucion", "titularidad de inmueble"), TipoDocumento.GARANTIA),
    (("seguro contra incendio", "seguro de incendio"), TipoDocumento.SEGURO),
]


def normalize(text: str) -> str:
    """Minúsculas y sin tildes, para que "CAUCIÓN", "Caución" y "caucion" coincidan."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def classify_by_rules(texts: list[str]) -> TipoDocumento:
    """El tipo del documento según palabras clave de su texto; `OTRO` si ninguna regla aplica."""
    text = normalize("\n".join(texts))
    for phrases, tipo in RULES:
        if any(phrase in text for phrase in phrases):
            return tipo
    return TipoDocumento.OTRO
