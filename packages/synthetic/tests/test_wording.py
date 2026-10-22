from datetime import date

import pytest

from synthetic.contracts import LOCALIDADES
from synthetic.source import Source
from synthetic.wording import dia_en_letras, frase_fecha_cierre, frase_tribunales


@pytest.mark.parametrize(
    ("dia", "esperado"),
    [
        (2, "dos"),
        (15, "quince"),
        (20, "veinte"),
        # Apócope delante de "días", igual que delante de "mil" en los montos.
        (21, "veintiún"),
        (31, "treinta y un"),
    ],
)
def test_dia_en_letras(dia, esperado):
    assert dia_en_letras(dia) == esperado


def test_fecha_cierre_primer_dia():
    frase = frase_fecha_cierre(Source(0), date(2025, 3, 1))
    assert frase == "al primer día del mes de marzo de 2025"


def test_fecha_cierre_en_letras_o_en_numeros():
    d = date(2025, 3, 21)
    frases = {frase_fecha_cierre(Source(seed), d) for seed in range(20)}
    assert frases == {
        "a los veintiún días del mes de marzo de 2025",
        "a los 21 días del mes de marzo de 2025",
    }


@pytest.mark.parametrize(
    ("localidad", "provincia", "esperado"),
    [
        ("Palermo", "CABA", "Juzgados Nacionales de Primera Instancia en lo Civil"),
        ("Godoy Cruz", "Mendoza", "Primera Circunscripción Judicial de Mendoza"),
        ("Mendoza", "Mendoza", "Primera Circunscripción Judicial de Mendoza"),
        ("San Rafael", "Mendoza", "Segunda Circunscripción Judicial de Mendoza"),
        ("La Plata", "Buenos Aires", "Departamento Judicial de La Plata"),
        ("San Isidro", "Buenos Aires", "Departamento Judicial de San Isidro"),
        ("Córdoba", "Córdoba", "Primera Circunscripción Judicial de Córdoba"),
        ("Rosario", "Santa Fe", "Segunda Circunscripción Judicial de Santa Fe"),
    ],
)
def test_tribunales_segun_el_inmueble(localidad, provincia, esperado):
    assert esperado in frase_tribunales(localidad, provincia)


def test_tribunales_para_toda_la_tabla():
    # Toda localidad generable tiene tribunales, y la frase encaja en "se someten a …".
    for localidad, provincia, _ in LOCALIDADES:
        frase = frase_tribunales(localidad, provincia)
        assert frase.startswith("los "), (localidad, frase)
