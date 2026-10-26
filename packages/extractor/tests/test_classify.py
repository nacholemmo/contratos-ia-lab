"""Tests del clasificador zero-shot: parseo de la etiqueta y el prompt."""

from types import SimpleNamespace

import pytest

from core.models import TipoDocumento
from extractor.classify import SYSTEM_ZERO_SHOT, classify, parse_tipo


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("dni", TipoDocumento.DNI),
        ("  Recibo_Sueldo.\n", TipoDocumento.RECIBO_SUELDO),
        ("CONTRATO", TipoDocumento.CONTRATO),
        ("otro", TipoDocumento.OTRO),
    ],
)
def test_parsea_etiquetas(answer, expected):
    assert parse_tipo(answer) == expected


@pytest.mark.parametrize("answer", ["", "es un contrato", "recibo", "factura"])
def test_respuesta_que_no_es_etiqueta_da_none(answer):
    assert parse_tipo(answer) is None


def test_el_prompt_lista_todas_las_etiquetas():
    for tipo in TipoDocumento:
        assert f"- {tipo.value}" in SYSTEM_ZERO_SHOT


def test_classify_devuelve_tipo_y_uso():
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="seguro")],
        usage=SimpleNamespace(input_tokens=500, output_tokens=10),
        stop_reason="end_turn",
        _request_id="req_test",
    )
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **_: response))

    result = classify(client, "<documento>x</documento>", "claude-haiku-5-5")

    assert result.tipo == TipoDocumento.SEGURO
    assert result.usage.input_tokens == 500
