"""Tests de LegajoEsperado: la estructura de un legajo fotografiado. Datos sintéticos."""

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from core.legajo import (
    AlertaEsperada,
    Etapa,
    LegajoEsperado,
    MotivoDescarte,
    TipoAlerta,
)
from core.models import Rol, TipoDocumento


def legajo_valido() -> dict[str, Any]:
    """Un inquilino y un garante, 7 fotos: el DNI en frente y dorso, un recibo, un título de
    dos páginas, una intrusa y un duplicado del recibo. Al garante le falta su DNI."""
    return {
        "seed": 42,
        "etapa": Etapa.EVALUACION,
        "alquiler_propuesto": Decimal("650000.00"),
        "moneda": "ARS",
        "personas": [
            {"id": "p1", "rol": Rol.INQUILINO, "nombre": "Lucía Fernández", "dni": "35123456"},
            {"id": "p2", "rol": Rol.GARANTE, "nombre": "Martín Gómez", "dni": "28987654"},
        ],
        "documentos": [
            {"id": "d1", "tipo": TipoDocumento.DNI, "persona_id": "p1",
             "fotos": ["IMG_4821.jpg", "IMG_4822.jpg"], "datos": "dni_inquilino_1.json"},
            {"id": "d2", "tipo": TipoDocumento.RECIBO_SUELDO, "persona_id": "p1",
             "fotos": ["IMG_4823.jpg"]},
            {"id": "d3", "tipo": TipoDocumento.GARANTIA, "persona_id": "p2",
             "fotos": ["IMG_4830.jpg", "IMG_4831.jpg"]},
        ],  # fmt: skip
        "fotos": [
            {"archivo": "IMG_4823.jpg"},
            {"archivo": "IMG_4830.jpg"},
            {"archivo": "IMG_4819.jpg", "descarte": MotivoDescarte.INTRUSA},
            {"archivo": "IMG_4821.jpg"},
            {"archivo": "IMG_4831.jpg"},
            {"archivo": "IMG_4824.jpg", "descarte": MotivoDescarte.DUPLICADA,
             "duplicada_de": "IMG_4823.jpg"},
            {"archivo": "IMG_4822.jpg"},
        ],  # fmt: skip
        "faltantes": [
            {"tipo": TipoDocumento.DNI, "persona_id": "p2", "detalle": "DNI del garante"},
        ],
        "alertas": [
            {"tipo": TipoAlerta.INGRESO_INSUFICIENTE, "persona_id": "p1", "documento_ids": ["d2"],
             "detalle": "El alquiler supera el 30 % del neto"},
        ],  # fmt: skip
    }


def test_legajo_valido():
    legajo = LegajoEsperado(**legajo_valido())
    assert legajo.sintetico is True
    assert len(legajo.fotos) == 7
    assert legajo.documentos[0].fotos == ["IMG_4821.jpg", "IMG_4822.jpg"]


def test_ida_y_vuelta_por_json():
    """El generador lo escribe como JSON y las evals lo leen: tiene que volver igual."""
    legajo = LegajoEsperado(**legajo_valido())
    assert LegajoEsperado.model_validate_json(legajo.model_dump_json()) == legajo


def test_no_se_puede_marcar_como_no_sintetico():
    with pytest.raises(ValidationError):
        LegajoEsperado(**{**legajo_valido(), "sintetico": False})


# --- ids y referencias ---


def test_ids_de_documento_repetidos():
    data = legajo_valido()
    data["documentos"][1]["id"] = "d1"
    with pytest.raises(ValidationError, match="ids repetidos en documentos"):
        LegajoEsperado(**data)


def test_documento_de_una_persona_inexistente():
    data = legajo_valido()
    data["documentos"][1]["persona_id"] = "p9"
    with pytest.raises(ValidationError, match="persona inexistente: p9"):
        LegajoEsperado(**data)


def test_alerta_con_documento_inexistente():
    data = legajo_valido()
    data["alertas"][0]["documento_ids"] = ["d9"]
    with pytest.raises(ValidationError, match="documento inexistente"):
        LegajoEsperado(**data)


def test_alerta_sin_detalle():
    with pytest.raises(ValidationError):
        AlertaEsperada(tipo=TipoAlerta.DNI_VENCIDO, detalle="")


# --- cada foto en un solo lugar (cada_foto_en_un_lugar) ---


def test_foto_suelta_sin_documento_ni_descarte():
    """Una foto que no está en ningún documento y no tiene motivo: el generador se olvidó."""
    data = legajo_valido()
    data["fotos"].append({"archivo": "IMG_4899.jpg"})
    with pytest.raises(ValidationError, match="IMG_4899.jpg"):
        LegajoEsperado(**data)


def test_foto_descartada_que_tambien_esta_en_un_documento():
    data = legajo_valido()
    data["fotos"][0]["descarte"] = MotivoDescarte.ILEGIBLE  # IMG_4823.jpg está en d2
    with pytest.raises(ValidationError, match="IMG_4823.jpg"):
        LegajoEsperado(**data)


def test_foto_en_dos_documentos():
    data = legajo_valido()
    data["documentos"][1]["fotos"] = ["IMG_4823.jpg", "IMG_4821.jpg"]  # IMG_4821 ya está en d1
    with pytest.raises(ValidationError, match="IMG_4821.jpg"):
        LegajoEsperado(**data)


def test_documento_con_una_foto_que_no_existe():
    data = legajo_valido()
    data["documentos"][1]["fotos"] = ["IMG_9999.jpg"]
    with pytest.raises(ValidationError, match="IMG_9999.jpg"):
        LegajoEsperado(**data)


def test_duplicado_de_una_foto_que_no_existe():
    data = legajo_valido()
    data["fotos"][5]["duplicada_de"] = "IMG_0000.jpg"
    with pytest.raises(ValidationError, match="IMG_0000.jpg"):
        LegajoEsperado(**data)


def test_duplicado_de_una_foto_descartada():
    """El duplicado tiene que apuntar a la foto que se conserva, no a otra descartada."""
    data = legajo_valido()
    data["fotos"][5]["duplicada_de"] = "IMG_4819.jpg"  # la intrusa
    with pytest.raises(ValidationError, match="IMG_4819.jpg"):
        LegajoEsperado(**data)


def test_duplicada_sin_decir_de_cual():
    data = legajo_valido()
    data["fotos"][5]["duplicada_de"] = None
    with pytest.raises(ValidationError, match="IMG_4824.jpg"):
        LegajoEsperado(**data)


def test_duplicada_de_en_una_foto_que_no_es_duplicado():
    data = legajo_valido()
    data["fotos"][2]["duplicada_de"] = "IMG_4823.jpg"  # la intrusa no es un duplicado
    with pytest.raises(ValidationError, match="IMG_4819.jpg"):
        LegajoEsperado(**data)
