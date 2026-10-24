"""Casos difíciles del set sintético: qué son, cuáles le tocan a cada semilla y cómo se aplican.

Las etiquetas no van en `Contrato` (lo que el LLM extrae, y el LLM no puede saber si un
contrato es "difícil"): son metadatos del set y viajan en `Muestra`. En la Fase 4 se
reporta la precisión por etiqueta y, aparte, la del set sin casos (el representativo).
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from core.models import Contrato, Indice, RegimenLegal, Rol
from synthetic.source import Source


class CasoDificil(StrEnum):
    # Datos faltantes: el campo queda en null en el ground truth y el extractor no debe
    # inventarlo. Solo campos donde null significa "no figura" y nada más.
    FECHA_FIRMA_EN_BLANCO = "fecha_firma_en_blanco"  # "____ de __________ de 20__"
    PERSONA_SIN_DOCUMENTO = "persona_sin_documento"  # una parte sin DNI ni CUIT
    SIN_CODIGO_POSTAL = "sin_codigo_postal"
    # Formato: todos los montos del contrato solo en letras, sin la cifra al lado.
    MONTOS_SOLO_LETRAS = "montos_solo_letras"
    GUIONES_DE_RELLENO = "guiones_de_relleno"  # ".-----" al final de cada párrafo
    # Cláusulas raras: el contrato dice lo mismo de otra forma, o algo que no es lo usual.
    CANON_ESCALONADO = "canon_escalonado"  # monto de cada año fijado de antemano, sin índice
    SEGURO_DE_CAUCION = "seguro_de_caucion"  # garantía con póliza, sin persona garante
    CLAUSULA_LARGA = "clausula_larga"  # inventario de más de una página
    # Documento: páginas como imagen de una fotocopia escaneada, sin capa de texto.
    ESCANEO_TORCIDO = "escaneo_torcido"


# Probabilidad de cada caso por semilla. Aproximada: alcanza para que cada uno aparezca
# varias veces en un set de 50 y que la mayoría quede limpia. Como los sorteos son
# independientes, la proporción limpia es el producto: 0,92⁴ × 0,95⁵ ≈ 55 %.
# El orden importa: elegir_casos recorre este dict, así que un caso nuevo va al final.
P_CASO: dict[CasoDificil, float] = {
    CasoDificil.FECHA_FIRMA_EN_BLANCO: 0.08,
    CasoDificil.PERSONA_SIN_DOCUMENTO: 0.08,
    CasoDificil.SIN_CODIGO_POSTAL: 0.08,
    CasoDificil.MONTOS_SOLO_LETRAS: 0.08,
    CasoDificil.GUIONES_DE_RELLENO: 0.05,
    CasoDificil.CANON_ESCALONADO: 0.05,
    CasoDificil.SEGURO_DE_CAUCION: 0.05,
    CasoDificil.CLAUSULA_LARGA: 0.05,
    CasoDificil.ESCANEO_TORCIDO: 0.05,
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


def es_aplicable(caso: CasoDificil, contrato: Contrato) -> bool:
    """Si el caso puede darse en este contrato real (ej. un canon escalonado solo donde la ley
    lo permite). Se evalúa sobre el contrato limpio, antes de aplicar ningún caso."""

    if caso == CasoDificil.CANON_ESCALONADO:
        return contrato.regimen_legal == RegimenLegal.DNU_70_2023 and contrato.plazo_meses >= 24
    if caso == CasoDificil.SEGURO_DE_CAUCION:
        return any(p.rol == Rol.GARANTE for p in contrato.partes)
    return True


def normalizar_casos(casos: list[CasoDificil]) -> list[CasoDificil]:
    """Sin repetidos y en el orden del enum, para que el JSON no dependa de cómo se pidieron."""
    return [caso for caso in CasoDificil if caso in casos]


def aplicar_casos(contrato: Contrato, casos: list[CasoDificil], source: Source) -> Contrato:
    """Copia del contrato con los datos que cambian por cada caso
    (los de formato no tocan datos)."""
    update: dict[str, object] = {}
    partes = contrato.partes
    if CasoDificil.FECHA_FIRMA_EN_BLANCO in casos:
        # El régimen sigue siendo el de la fecha real: el generador la conoce aunque el papel no.
        update["fecha_firma"] = None
    if CasoDificil.CANON_ESCALONADO in casos:
        # Los montos de cada año van en el texto; el modelo solo guarda el del primero.
        update["indice"] = Indice.FIJO
        update["frecuencia_ajuste_meses"] = None
    if CasoDificil.SEGURO_DE_CAUCION in casos:
        partes = [p for p in partes if p.rol != Rol.GARANTE]
    if CasoDificil.PERSONA_SIN_DOCUMENTO in casos:
        elegida = source.rng.randrange(len(partes))
        partes = [
            p.model_copy(update={"dni": None, "cuit": None}) if i == elegida else p
            for i, p in enumerate(partes)
        ]
    if partes is not contrato.partes:
        update["partes"] = partes
    if CasoDificil.SIN_CODIGO_POSTAL in casos:
        update["propiedad"] = contrato.propiedad.model_copy(update={"codigo_postal": None})
    return contrato.model_copy(update=update)
