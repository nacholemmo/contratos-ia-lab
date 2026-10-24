"""Casos difíciles del set sintético: qué son, cuáles le tocan a cada semilla y cómo se aplican.

Las etiquetas no van en `Contrato` (lo que el LLM extrae, y el LLM no puede saber si un
contrato es "difícil"): son metadatos del set y viajan en `Muestra`. En la Fase 4 se
reporta la precisión por etiqueta y, aparte, la del set sin casos (el representativo).
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from core.models import Contrato
from synthetic.source import Source


class CasoDificil(StrEnum):
    # Datos faltantes: el campo queda en null en el ground truth y el extractor no debe
    # inventarlo. Solo campos donde null significa "no figura" y nada más.
    FECHA_FIRMA_EN_BLANCO = "fecha_firma_en_blanco"  # "____ de __________ de 20__"
    PERSONA_SIN_DOCUMENTO = "persona_sin_documento"  # una parte sin DNI ni CUIT
    SIN_CODIGO_POSTAL = "sin_codigo_postal"
    # Formato: todos los montos del contrato solo en letras, sin la cifra al lado.
    MONTOS_SOLO_LETRAS = "montos_solo_letras"


# Probabilidad de cada caso por semilla. Aproximada: alcanza para que cada uno aparezca
# varias veces en un set de 50 y que la mayoría de los contratos quede limpia.
P_CASO: dict[CasoDificil, float] = {
    CasoDificil.FECHA_FIRMA_EN_BLANCO: 0.10,
    CasoDificil.PERSONA_SIN_DOCUMENTO: 0.10,
    CasoDificil.SIN_CODIGO_POSTAL: 0.10,
    CasoDificil.MONTOS_SOLO_LETRAS: 0.10,
}


class Muestra(BaseModel):
    """Ground truth de un contrato sintético: los datos correctos y sus etiquetas."""

    seed: int = Field(..., description="Semilla que reproduce el contrato exacto")
    sintetico: Literal[True] = Field(True, description="Siempre True: datos ficticios")
    casos: list[CasoDificil] = Field(
        default_factory=list, description="Casos difíciles aplicados; vacío si es limpio"
    )
    contrato: Contrato


def elegir_casos(source: Source) -> list[CasoDificil]:
    """Casos difíciles que le tocan a esta semilla, en el orden en que están declarados."""
    cases = []

    for caso, prob in P_CASO.items():
        if source.rng.random() < prob:
            cases.append(caso)
    return cases


def normalizar_casos(casos: list[CasoDificil]) -> list[CasoDificil]:
    """Sin repetidos y en el orden del enum, para que el JSON no dependa de cómo se pidieron."""
    return [caso for caso in CasoDificil if caso in casos]


def aplicar_faltantes(contrato: Contrato, casos: list[CasoDificil], source: Source) -> Contrato:
    """Copia del contrato con los datos faltantes en null (el resto de los casos no toca datos)."""
    update: dict[str, object] = {}
    if CasoDificil.FECHA_FIRMA_EN_BLANCO in casos:
        # El régimen sigue siendo el de la fecha real: el generador la conoce aunque el papel no.
        update["fecha_firma"] = None
    if CasoDificil.PERSONA_SIN_DOCUMENTO in casos:
        elegida = source.rng.randrange(len(contrato.partes))
        update["partes"] = [
            p.model_copy(update={"dni": None, "cuit": None}) if i == elegida else p
            for i, p in enumerate(contrato.partes)
        ]
    if CasoDificil.SIN_CODIGO_POSTAL in casos:
        update["propiedad"] = contrato.propiedad.model_copy(update={"codigo_postal": None})
    return contrato.model_copy(update=update)
