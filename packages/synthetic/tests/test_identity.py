import random

import pytest

from core.models import cuit_valido
from synthetic.identity import DNI_MAX, DNI_MIN, cuit_from_dni, generate_dni


def test_dni_en_rango_y_formato():
    rng = random.Random(0)
    for _ in range(1000):
        dni = generate_dni(rng)
        assert dni.isdigit()
        assert len(dni) in (7, 8)
        assert DNI_MIN <= int(dni) <= DNI_MAX


@pytest.mark.parametrize(
    ("dni", "sexo", "esperado"),
    [
        ("30123456", "M", "20301234563"),
        ("30123456", "F", "27301234568"),
        # Con 20 o 27 el dígito verificador daría 10: el prefijo pasa a 23.
        ("30000002", "M", "23300000029"),
        ("30000013", "F", "23300000134"),
        # DNI de 7 dígitos: va con un cero a la izquierda dentro del CUIL.
        ("7654321", "M", "20076543217"),
    ],
)
def test_cuit_casos_conocidos(dni, sexo, esperado):
    assert cuit_from_dni(dni, sexo) == esperado


@pytest.mark.parametrize("sexo", ["M", "F"])
def test_cuit_siempre_valido_y_contiene_el_dni(sexo):
    rng = random.Random(42)
    for _ in range(2000):
        dni = generate_dni(rng)
        cuit = cuit_from_dni(dni, sexo)
        assert cuit_valido(cuit), (dni, sexo, cuit)
        assert cuit[2:10] == dni.zfill(8)
        assert cuit[:2] in {"20", "27", "23"}
