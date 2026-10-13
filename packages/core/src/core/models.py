"""Modelos de datos compartidos por todos los paquetes del laboratorio.

`Contrato` (y los modelos que lo componen) es el centro del proyecto: el generador
sintético lo usa como ground truth, el extractor como salida estructurada del LLM
y la base de datos guarda lo que estos modelos validan.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

# Monto: nunca negativo y con 2 decimales como máximo (centavos).
# La moneda va en un campo aparte: hay contratos en pesos y en dólares.
Monto = Annotated[Decimal, Field(ge=0, decimal_places=2)]

# Pesos oficiales para el dígito verificador del CUIT, aplicados a los primeros 10 dígitos.
PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


class Rol(StrEnum):
    """Rol de una persona dentro de un contrato."""

    PROPIETARIO = "propietario"
    INQUILINO = "inquilino"
    GARANTE = "garante"


class Moneda(StrEnum):
    ARS = "ARS"
    USD = "USD"


class Indice(StrEnum):
    """Índice con el que se ajusta el alquiler."""

    IPC = "IPC"  # Índice de Precios al Consumidor (INDEC).
    ICL = "ICL"  # Índice para Contratos de Locación (BCRA).
    CASA_PROPIA = "casa_propia"  # Coeficiente Casa Propia.
    UVA = "UVA"  # Unidad de Valor Adquisitivo (BCRA).
    DOLAR = "dolar"  # Monto atado a la cotización del dólar.
    FIJO = "fijo"  # Sin ajuste o con montos escalonados fijados en el contrato.


class RegimenLegal(StrEnum):
    """Marco legal vigente cuando se firmó el contrato."""

    LEY_27551 = "ley_27551"  # Jul 2020 a oct 2023: ajuste anual por ICL, plazo de 3 años.
    LEY_27737 = "ley_27737"  # Oct 2023 a dic 2023: ajuste semestral por Casa Propia.
    DNU_70_2023 = "dnu_70_2023"  # Desde dic 2023: índice, frecuencia y plazo libres.


def cuit_valido(cuit: str) -> bool:
    """Devuelve True si el dígito verificador del CUIT (11 dígitos) es correcto.

    Módulo 11: se multiplican los primeros 10 dígitos por PESOS_CUIT, se suma y
    se calcula 11 - (suma % 11). Si da 11 el dígito esperado es 0; si da 10 no
    entra en un dígito y el CUIT es inválido.
    """
    if len(cuit) != 11 or not cuit.isdigit():
        return False

    # strict=True falla si PESOS_CUIT deja de tener 10 elementos: sin él, zip
    # corta en el iterable más corto y la suma daría mal en silencio.
    suma = sum(int(d) * p for d, p in zip(cuit[:10], PESOS_CUIT, strict=True))
    digito = 11 - (suma % 11)

    if digito == 10:
        return False
    if digito == 11:
        digito = 0

    return digito == int(cuit[10])


class Persona(BaseModel):
    """Persona física o jurídica que participa en un contrato."""

    nombre: str = Field(
        ...,
        min_length=1,
        description="Nombre completo o razón social tal como figura en el contrato",
    )
    rol: Rol = Field(..., description="Rol en el contrato: propietario, inquilino o garante")
    dni: str | None = Field(
        None,
        pattern=r"^\d{7,8}$",
        description="DNI de 7 u 8 dígitos sin puntos (ej. 30123456); null si no figura",
    )
    cuit: str | None = Field(
        None,
        pattern=r"^\d{11}$",
        description="CUIT o CUIL de 11 dígitos sin guiones (ej. 20301234567); null si no figura",
    )

    @field_validator("cuit")
    @classmethod
    def _validar_digito_verificador(cls, v: str | None) -> str | None:
        # Corre después del pattern, así que v ya tiene 11 dígitos (o es None).
        if v is not None and not cuit_valido(v):
            raise ValueError("dígito verificador del CUIT inválido")
        return v


__all__ = [
    "Indice",
    "Moneda",
    "Monto",
    "Persona",
    "RegimenLegal",
    "Rol",
    "cuit_valido",
]
