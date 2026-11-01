"""Tests del clasificador por reglas, con los encabezados que produce el generador."""

import pytest

from core.models import TipoDocumento
from extractor.rules import classify_by_rules, normalize

MARCA = "SINTÉTICO\nDOCUMENTO SINTÉTICO - DATOS FICTICIOS - SIN VALIDEZ LEGAL\n"


def test_normalize_saca_tildes_y_mayusculas():
    assert normalize("PÓLIZA DE CAUCIÓN") == "poliza de caucion"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "CONTRATO DE LOCACIÓN\nEn Guaymallén, entre Lucas Gonzalez, DNI 44627281, en adelante "
            "LA PARTE LOCADORA",
            TipoDocumento.CONTRATO,
        ),
        ("FICHA DE IDENTIDAD\nDocumento 44627281\nApellido GONZALEZ", TipoDocumento.DNI),
        (
            "RECIBO DE HABERES\nMetalúrgica Ficticia Mendocina S.R.L.\nCUIT 30-50291921-7",
            TipoDocumento.RECIBO_SUELDO,
        ),
        (
            "CONSTANCIA DE TITULARIDAD DE INMUEBLE\nTitular Lola AGUIRRE\n"
            "DNI del titular 13.637.197",
            TipoDocumento.GARANTIA,
        ),
        (
            "PÓLIZA DE SEGURO DE CAUCIÓN - GARANTÍA DE ALQUILER\nTomador Santino Cardozo",
            TipoDocumento.GARANTIA,
        ),
        ("PÓLIZA DE SEGURO CONTRA INCENDIO\nAsegurado Santiago Diaz", TipoDocumento.SEGURO),
    ],
)
def test_clasifica_los_encabezados_del_generador(text, expected):
    assert classify_by_rules([MARCA + text]) == expected


def test_seguro_de_una_aseguradora_de_cauciones_sigue_siendo_seguro():
    """La aseguradora del seguro de incendio puede llamarse "... de Cauciones S.A.": la palabra
    "caución" sola no alcanza para decir garantía."""
    text = (
        "PÓLIZA DE SEGURO CONTRA INCENDIO\n"
        "Aseguradora Aseguradora Modelo de Cauciones S.A.\n"
        "Asegurado Santiago Diaz"
    )
    assert classify_by_rules([MARCA + text]) == TipoDocumento.SEGURO


def test_contrato_que_menciona_dni_y_seguro_sigue_siendo_contrato():
    """Un contrato cita el DNI de las partes, el seguro y la garantía en sus cláusulas."""
    text = (
        "CONTRATO DE LOCACIÓN\nentre Lucas Gonzalez, DNI 44627281 ...\n"
        "OCTAVA: GARANTÍA. La parte locataria presenta una póliza de seguro de caución ...\n"
        "NOVENA: SEGURO. La parte locataria contratará un seguro contra incendio ..."
    )
    assert classify_by_rules([MARCA + text]) == TipoDocumento.CONTRATO


def test_las_reglas_no_dependen_de_mayusculas_ni_tildes():
    assert classify_by_rules(["recibo de haberes\nempleado diaz, santiago"]) == (
        TipoDocumento.RECIBO_SUELDO
    )


@pytest.mark.parametrize("texts", [[], [""], ["   \n  "], [MARCA]])
def test_sin_texto_util_da_otro(texts):
    """Un escaneo no tiene capa de texto; la marca de sintético sola no dice qué es."""
    assert classify_by_rules(texts) == TipoDocumento.OTRO


def test_texto_sin_palabras_clave_da_otro():
    assert classify_by_rules(["FACTURA B\nNúmero 0001-00001234"]) == TipoDocumento.OTRO
