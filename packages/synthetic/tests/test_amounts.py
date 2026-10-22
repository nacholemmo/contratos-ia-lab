from decimal import Decimal

import pytest

from core.models import Moneda
from synthetic.amounts import EstiloMonto, format_monto, monto_en_letras, numero_ar


@pytest.mark.parametrize(
    ("monto", "esperado"),
    [
        ("500000", "500.000"),
        ("1234567", "1.234.567"),
        ("950", "950"),
        ("500000.50", "500.000,50"),
        ("1000.05", "1.000,05"),
    ],
)
def test_numero_ar(monto, esperado):
    assert numero_ar(Decimal(monto)) == esperado


@pytest.mark.parametrize(
    ("monto", "esperado"),
    [
        ("500000", "QUINIENTOS MIL"),
        ("1000000", "UN MILLÓN"),
        ("1234000", "UN MILLÓN DOSCIENTOS TREINTA Y CUATRO MIL"),
        ("1010", "MIL DIEZ"),
        # Apócope: delante de "mil" o "millón", "uno" pasa a "un" (num2words no lo hace).
        ("21000", "VEINTIÚN MIL"),
        ("31000", "TREINTA Y UN MIL"),
        ("101000", "CIENTO UN MIL"),
        ("321000", "TRESCIENTOS VEINTIÚN MIL"),
        ("1021000", "UN MILLÓN VEINTIÚN MIL"),
        # Sin "mil" detrás, "uno" queda como está.
        ("21", "VEINTIUNO"),
        ("1021", "MIL VEINTIUNO"),
        # Centavos al estilo de los contratos.
        ("500000.50", "QUINIENTOS MIL CON 50/100"),
        ("1500.05", "MIL QUINIENTOS CON 05/100"),
    ],
)
def test_monto_en_letras(monto, esperado):
    assert monto_en_letras(Decimal(monto)) == esperado


@pytest.mark.parametrize(
    ("moneda", "estilo", "esperado"),
    [
        (Moneda.ARS, EstiloMonto.NUMEROS, "$ 521.000"),
        (Moneda.ARS, EstiloMonto.LETRAS, "PESOS QUINIENTOS VEINTIÚN MIL"),
        (Moneda.ARS, EstiloMonto.AMBOS, "PESOS QUINIENTOS VEINTIÚN MIL ($ 521.000)"),
        (Moneda.USD, EstiloMonto.NUMEROS, "USD 521.000"),
        (
            Moneda.USD,
            EstiloMonto.AMBOS,
            "DÓLARES ESTADOUNIDENSES QUINIENTOS VEINTIÚN MIL (USD 521.000)",
        ),
    ],
)
def test_format_monto(moneda, estilo, esperado):
    assert format_monto(Decimal("521000"), moneda, estilo) == esperado


def test_letras_sin_apocope_pendiente_en_todo_el_rango():
    # Ningún monto generable (ARS de a miles hasta 1,4 M) puede quedar con "UNO MIL".
    for miles in range(15, 1_401):
        letras = monto_en_letras(Decimal(miles * 1000))
        assert "UNO MIL" not in letras, letras
        assert letras == letras.upper()
