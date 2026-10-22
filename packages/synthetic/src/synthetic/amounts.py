"""Montos como se escriben en un contrato argentino: en números, en letras o en ambos."""

from decimal import Decimal
from enum import StrEnum

from num2words import num2words

from core.models import Moneda


class EstiloMonto(StrEnum):
    NUMEROS = "numeros"  # $ 500.000
    LETRAS = "letras"  # PESOS QUINIENTOS MIL
    AMBOS = "ambos"  # PESOS QUINIENTOS MIL ($ 500.000)


PREFIJO_NUMEROS = {Moneda.ARS: "$", Moneda.USD: "USD"}
PREFIJO_LETRAS = {Moneda.ARS: "PESOS", Moneda.USD: "DÓLARES ESTADOUNIDENSES"}


def numero_ar(monto: Decimal) -> str:
    """Formato argentino: punto para miles, coma para decimales y sin ',00' si es entero.

    500000 → '500.000' · 500000.5 → '500.000,50'
    """
    entero = int(monto)
    centavos = int((monto - entero) * 100)
    texto = f"{entero:,}".replace(",", ".")
    return f"{texto},{centavos:02d}" if centavos else texto


def monto_en_letras(monto: Decimal) -> str:
    """Parte del monto en letras y en mayúsculas, sin la moneda.

    500000 → 'QUINIENTOS MIL' · 21000 → 'VEINTIÚN MIL' · 500000.5 → 'QUINIENTOS MIL CON 50/100'
    """
    entero = int(monto)
    centavos = int((monto - entero) * 100)
    letras = num2words(entero, lang="es")
    # Apócope: delante de "mil", "uno" pasa a "un" (num2words no lo hace).
    letras = letras.replace("veintiuno mil", "veintiún mil").replace("uno mil", "un mil")
    letras = letras.upper()
    return f"{letras} CON {centavos:02d}/100" if centavos else letras


def format_monto(monto: Decimal, moneda: Moneda, estilo: EstiloMonto) -> str:
    numeros = f"{PREFIJO_NUMEROS[moneda]} {numero_ar(monto)}"
    if estilo == EstiloMonto.NUMEROS:
        return numeros
    letras = f"{PREFIJO_LETRAS[moneda]} {monto_en_letras(monto)}"
    if estilo == EstiloMonto.LETRAS:
        return letras
    return f"{letras} ({numeros})"
