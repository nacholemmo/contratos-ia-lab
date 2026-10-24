"""Documentos de identidad sintéticos: DNI y CUIT/CUIL válidos y coherentes entre sí."""

import random

from core.models import (
    PESOS_CUIT,  # noqa: F401  (para calcular el dígito verificador)
    Sexo,
)

# Rango de DNI de personas adultas: los de 7 dígitos (< 10 millones) son de gente mayor.
DNI_MIN = 5_000_000
DNI_MAX = 45_999_999
# Prefijo del CUIL según el sexo registral. El generador no produce DNI no binarios (X).
PREFIJO_POR_SEXO: dict[Sexo, str] = {Sexo.M: "20", Sexo.F: "27"}


def generate_dni(rng: random.Random) -> str:
    """DNI de 7 u 8 dígitos, sin puntos, como lo espera `Persona.dni`."""
    return str(rng.randint(DNI_MIN, DNI_MAX))


def _digito_verificador(base: str) -> int:
    """Dígito verificador (módulo 11) para los primeros 10 dígitos del CUIT."""
    suma = sum(int(d) * p for d, p in zip(base, PESOS_CUIT, strict=True))
    digito = 11 - (suma % 11)
    if digito == 11:
        return 0
    return digito


def cuit_empresa(rng: random.Random) -> str:
    """CUIT de persona jurídica: prefijo 30 (33 si el verificador daría 10) + 8 dígitos + DV."""
    while True:
        base = str(rng.randint(50_000_000, 72_999_999))
        for prefijo in ("30", "33"):
            digito = _digito_verificador(prefijo + base)
            if digito != 10:
                return prefijo + base + str(digito)


def cuit_from_dni(dni: str, sexo: Sexo) -> str:
    """CUIL de 11 dígitos derivado del DNI: prefijo (2) + DNI con ceros a la izquierda (8) + DV (1).

    Prefijos de persona física: 20 (masculino), 27 (femenino) y 23 (caso especial).
    Ejemplos: DNI 30123456 → 20301234563 (M) y 27301234568 (F).
    """

    dni_8 = dni.zfill(8)
    prefijo = PREFIJO_POR_SEXO[sexo]
    digito = _digito_verificador(prefijo + dni_8)

    if digito == 10:
        prefijo = "23"
        digito = _digito_verificador(prefijo + dni_8)

    return prefijo + dni_8 + str(digito)
