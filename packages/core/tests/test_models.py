"""Tests de los modelos de core. Todos los datos son sintéticos (Ley 25.326)."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from core.models import (
    DNI,
    Contrato,
    Evidencia,
    Indice,
    Moneda,
    Persona,
    RegimenLegal,
    Rol,
    Sexo,
)

# CUIT sintéticos con dígito verificador correcto (calculado con módulo 11).
CUIT_VALIDO_PROPIETARIO = "20301234563"
CUIT_VALIDO_INQUILINO = "27359876543"
# Mismo CUIT del propietario con el último dígito cambiado: formato correcto, verificador mal.
CUIT_DIGITO_INVALIDO = "20301234560"


@pytest.fixture
def datos_contrato() -> dict[str, Any]:
    """Datos mínimos de un contrato válido. Cada test cambia solo lo que quiere probar."""
    return {
        "partes": [
            {"nombre": "Ana Pérez", "rol": Rol.PROPIETARIO, "cuit": CUIT_VALIDO_PROPIETARIO},
            {"nombre": "Luis Gómez", "rol": Rol.INQUILINO, "cuit": CUIT_VALIDO_INQUILINO},
        ],
        "propiedad": {
            "tipo": "departamento",
            "calle": "Av. Siempreviva",
            "numero": "742",
            "localidad": "Palermo",
            "provincia": "CABA",
        },
        "fecha_firma": date(2025, 2, 15),
        "fecha_inicio": date(2025, 3, 1),
        "plazo_meses": 24,
        "monto_inicial": "450000.00",
        "moneda": Moneda.ARS,
        "indice": Indice.IPC,
        "frecuencia_ajuste_meses": 3,
        "regimen_legal": RegimenLegal.DNU_70_2023,
        "monto_inicial_evidencia": {
            "texto": "un alquiler mensual de PESOS CUATROCIENTOS CINCUENTA MIL ($450.000)",
            "pagina": 1,
        },
    }


def test_contrato_valido(datos_contrato: dict[str, Any]) -> None:
    contrato = Contrato(**datos_contrato)

    assert len(contrato.partes) == 2
    assert contrato.monto_inicial_evidencia == Evidencia(
        texto="un alquiler mensual de PESOS CUATROCIENTOS CINCUENTA MIL ($450.000)", pagina=1
    )
    # Sin evidencia cargada, el gemelo queda en None (opcional por diseño).
    assert contrato.fecha_inicio_evidencia is None


def test_contrato_sin_fecha_firma_es_valido(datos_contrato: dict[str, Any]) -> None:
    # La fecha puede estar en blanco en el papel: el LLM deja null en vez de inventarla.
    del datos_contrato["fecha_firma"]

    assert Contrato(**datos_contrato).fecha_firma is None


def test_cuit_con_digito_verificador_invalido_es_rechazado() -> None:
    # match asegura que lo rechaza el validador del dígito y no el pattern de 11 dígitos.
    with pytest.raises(ValidationError, match="dígito verificador"):
        Persona(nombre="Juan", rol=Rol.PROPIETARIO, cuit=CUIT_DIGITO_INVALIDO)


def test_monto_se_guarda_como_decimal_exacto(datos_contrato: dict[str, Any]) -> None:
    contrato = Contrato(**datos_contrato)

    assert isinstance(contrato.monto_inicial, Decimal)
    assert contrato.monto_inicial == Decimal("450000.00")


def test_monto_con_mas_de_dos_decimales_es_rechazado(datos_contrato: dict[str, Any]) -> None:
    datos_contrato["monto_inicial"] = "450000.005"

    with pytest.raises(ValidationError):
        Contrato(**datos_contrato)


def test_personas_distintas_tienen_ids_distintos() -> None:
    a = Persona(nombre="Ana Pérez", rol=Rol.PROPIETARIO)
    b = Persona(nombre="Ana Pérez", rol=Rol.PROPIETARIO)

    assert a.id != b.id


# --- DNI ---


def test_dni_minimo_con_numero_y_apellido():
    # El resto puede no leerse en una foto mala: queda en null y no se inventa.
    dni = DNI(numero="30123456", apellido="PÉREZ")
    assert dni.nombre is None
    assert dni.sexo is None
    assert dni.fecha_vencimiento is None


def test_dni_solo_numero_y_apellido_son_obligatorios():
    requeridos = set(DNI.model_json_schema()["required"])
    assert requeridos == {"numero", "apellido"}


def test_dni_completo_valido():
    dni = DNI(
        numero="30123456",
        apellido="PÉREZ",
        nombre="JUAN IGNACIO",
        sexo=Sexo.M,
        fecha_nacimiento=date(1983, 5, 12),
        fecha_emision=date(2015, 3, 1),
        fecha_vencimiento=date(2030, 3, 1),
        nacionalidad="ARGENTINA",
        numero_evidencia=Evidencia(texto="30.123.456", pagina=1),
    )
    assert dni.sexo == "M"


@pytest.mark.parametrize("numero", ["30.123.456", "123456", "301234567", "3012345a"])
def test_dni_numero_con_formato_invalido_rechazado(numero):
    with pytest.raises(ValidationError, match="numero"):
        DNI(numero=numero, apellido="PÉREZ")


def test_dni_sexo_fuera_del_enum_rechazado():
    with pytest.raises(ValidationError, match="sexo"):
        DNI(numero="30123456", apellido="PÉREZ", sexo="Masculino")


def test_dni_todo_dato_tiene_su_evidencia():
    datos = {n for n in DNI.model_fields if not n.endswith("_evidencia")}
    evidencias = {
        n.removesuffix("_evidencia") for n in DNI.model_fields if n.endswith("_evidencia")
    }
    assert datos == evidencias
