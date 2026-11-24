"""Tests del esquema de extracción: sin ids, con todo lo demás, y de vuelta a core."""

import json
from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

import core.models as core_models
from core.models import (
    DNI,
    Contrato,
    Documento,
    Evidencia,
    Indice,
    Moneda,
    Persona,
    PolizaCaucion,
    Propiedad,
    ReciboSueldo,
    RegimenLegal,
    Rol,
    SeguroInmueble,
    TipoPropiedad,
    TituloPropiedad,
)
from extractor.esquema import a_core, es_interno, esquema_extraccion

MODELOS_CORE = [
    m
    for m in vars(core_models).values()
    if isinstance(m, type) and issubclass(m, BaseModel) and m.__module__ == core_models.__name__
]


def schema(modelo: type[BaseModel]) -> dict:
    return esquema_extraccion(modelo).model_json_schema()


def test_los_ids_son_internos():
    assert es_interno(Persona.model_fields["id"])
    assert es_interno(Contrato.model_fields["id"])
    assert not es_interno(Persona.model_fields["dni"])
    # Tiene valor por defecto, pero es un dato del documento: no es interno.
    assert not es_interno(Contrato.model_fields["clausulas"])


def test_persona_sin_id():
    propiedades = schema(Persona)["properties"]
    assert "id" not in propiedades
    assert {"nombre", "rol", "dni", "cuit"} <= set(propiedades)


def test_contrato_sin_id_ni_en_las_partes():
    """Recursivo: `partes` es list[Persona] y cada Persona tenía su id."""
    s = schema(Contrato)
    assert "id" not in s["properties"]
    persona = s["$defs"]["Persona"]
    assert "id" not in persona["properties"]


def test_documento_sin_ids():
    propiedades = schema(Documento)["properties"]
    assert not {"id", "persona_id", "contrato_ids"} & set(propiedades)
    assert "tipo" in propiedades


@pytest.mark.parametrize("modelo", MODELOS_CORE, ids=lambda m: m.__name__)
def test_ningun_uuid_llega_al_llm(modelo):
    """Red de seguridad: si alguien agrega un UUID a core sin marcarlo, falla acá."""
    assert '"uuid"' not in json.dumps(schema(modelo))


@pytest.mark.parametrize(
    "modelo", [DNI, ReciboSueldo, TituloPropiedad, PolizaCaucion, SeguroInmueble, Evidencia]
)
def test_sin_internos_es_el_mismo_modelo(modelo):
    """Los documentos de la etapa 1 no tienen ids: se usan tal cual, con sus validadores."""
    assert esquema_extraccion(modelo) is modelo


def test_conserva_descripciones_y_restricciones():
    s = schema(Contrato)
    assert s["description"] == Contrato.__doc__
    assert s["properties"]["plazo_meses"]["minimum"] == 1
    assert s["properties"]["fecha_firma"]["description"].startswith("Fecha de firma")
    assert s["$defs"]["Persona"]["properties"]["dni"]["anyOf"][0]["pattern"] == r"^\d{7,8}$"
    # Monto = Annotated[Decimal, Field(ge=0)]: la restricción sobrevive a la derivación.
    with pytest.raises(ValidationError):
        esquema_extraccion(Contrato).model_validate({**contrato_extraido(), "monto_inicial": -1})


def test_mismo_esquema_cada_vez():
    """Cacheado: el schema que se manda es el mismo byte a byte (ayuda al prompt caching)."""
    assert esquema_extraccion(Contrato) is esquema_extraccion(Contrato)


def contrato_extraido() -> dict:
    return {
        "partes": [
            {"nombre": "Ana Gómez", "rol": Rol.PROPIETARIO, "dni": "30123456"},
            {"nombre": "Juan Pérez", "rol": Rol.INQUILINO, "cuit": "20301234563"},
        ],
        "propiedad": Propiedad(
            tipo=TipoPropiedad.DEPARTAMENTO,
            calle="Gurruchaga",
            numero="1234",
            localidad="Palermo",
            provincia="CABA",
        ).model_dump(),
        "fecha_inicio": date(2025, 3, 1),
        "plazo_meses": 24,
        "monto_inicial": Decimal("850000.00"),
        "moneda": Moneda.ARS,
        "indice": Indice.ICL,
        "regimen_legal": RegimenLegal.DNU_70_2023,
        "monto_inicial_evidencia": {"texto": "$ 850.000", "pagina": 1},
    }


def test_el_llm_no_puede_mandar_un_id():
    """Si el modelo inventa un id igual, no se usa: lo asigna core."""
    datos = {**contrato_extraido(), "id": "00000000-0000-0000-0000-000000000000"}
    extraido = esquema_extraccion(Contrato).model_validate(datos)
    assert "id" not in extraido.model_dump()


def test_a_core_genera_los_ids():
    extraido = esquema_extraccion(Contrato).model_validate(contrato_extraido())
    contrato = a_core(Contrato, extraido)
    assert isinstance(contrato, Contrato)
    assert contrato.id is not None
    assert len({p.id for p in contrato.partes}) == 2
    assert contrato.monto_inicial_evidencia == Evidencia(texto="$ 850.000", pagina=1)


def test_a_core_corre_los_validadores_de_core():
    """El esquema derivado no tiene el validador del CUIT: lo corre core al volver."""
    datos = contrato_extraido()
    datos["partes"][1]["cuit"] = "20301234567"  # dígito verificador mal (es 3)
    extraido = esquema_extraccion(Contrato).model_validate(datos)
    with pytest.raises(ValidationError, match="dígito verificador"):
        a_core(Contrato, extraido)
