from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from pypdf import PdfReader

from core.models import Moneda, ReciboSueldo, Rol, cuit_valido
from synthetic.contracts import generate_contrato_con_identidades
from synthetic.dni import generate_dnis, sumar_anios
from synthetic.identity import cuit_empresa
from synthetic.pdf import AVISO, MARCA
from synthetic.recibo import (
    ALQUILER_SOBRE_NETO,
    APORTES,
    EDAD_MIN_EMPLEO,
    EMPLEADORES,
    alquiler_en_pesos,
    generate_recibos,
    montos,
    periodo_liquidado,
)
from synthetic.source import Source

SEEDS = range(30)

CAMPOS = [n for n in ReciboSueldo.model_fields if not n.endswith("_evidencia")]


def _texto(pdf: bytes) -> str:
    return " ".join(PdfReader(BytesIO(pdf)).pages[0].extract_text().split())


# --- piezas ---


def test_cuit_empresa_valido_y_de_persona_juridica():
    for seed in range(500):
        cuit = cuit_empresa(Source(seed).rng)
        assert cuit_valido(cuit), cuit
        assert cuit[:2] in ("30", "33")


@pytest.mark.parametrize("seed", range(200))
def test_montos_cierran_al_centavo(seed):
    bruto, aportes, neto = montos(Decimal(500_000), Source(seed))
    # Dinero con código determinístico: el neto es exactamente bruto - aportes.
    assert neto == bruto - sum(aportes)
    for (_, tasa), aporte in zip(APORTES, aportes, strict=True):
        assert abs(aporte - bruto * tasa) <= Decimal("0.005")
    for monto in (bruto, neto, *aportes):
        assert monto == monto.quantize(Decimal("0.01"))


@pytest.mark.parametrize("seed", range(200))
def test_alquiler_es_una_fraccion_creible_del_neto(seed):
    alquiler = Decimal(500_000)
    _, _, neto = montos(alquiler, Source(seed))
    minimo, maximo = ALQUILER_SOBRE_NETO
    # Margen chico por el redondeo de la proporción y los centavos.
    assert minimo - 0.005 <= float(alquiler / neto) <= maximo + 0.005


def test_periodo_es_el_mes_anterior_a_la_firma():
    assert periodo_liquidado(date(2025, 10, 21)) == date(2025, 9, 1)
    assert periodo_liquidado(date(2025, 1, 5)) == date(2024, 12, 1)
    assert periodo_liquidado(date(2024, 3, 1)) == date(2024, 2, 1)


# --- generate_recibos ---


@pytest.mark.parametrize("seed", SEEDS)
def test_un_recibo_por_inquilino(seed):
    contrato, _ = generate_contrato_con_identidades(seed)
    inquilinos = [p.id for p in contrato.partes if p.rol == Rol.INQUILINO]
    assert list(generate_recibos(seed)) == inquilinos


@pytest.mark.parametrize("seed", SEEDS)
def test_recibo_coherente_con_contrato_y_dni(seed):
    contrato, identidades = generate_contrato_con_identidades(seed)
    dnis = generate_dnis(seed)
    for persona_id, (_, recibo) in generate_recibos(seed).items():
        persona = next(p for p in contrato.partes if p.id == persona_id)
        identidad = identidades[persona_id]
        _, dni = dnis[persona_id]
        assert recibo.empleado == f"{dni.apellido}, {dni.nombre}"
        # El CUIL del recibo es el del contrato cuando el contrato lo muestra.
        if persona.cuit is not None:
            assert recibo.empleado_cuil == persona.cuit
        assert recibo.empleado_cuil[2:10] == persona.dni.zfill(8)
        assert recibo.empleador in EMPLEADORES
        # Trabaja ahí desde los 16 años como mínimo y desde antes del período liquidado.
        periodo = date.fromisoformat(f"{recibo.periodo}-01")
        assert sumar_anios(dni.fecha_nacimiento, EDAD_MIN_EMPLEO) <= recibo.fecha_ingreso
        assert recibo.fecha_ingreso < periodo
        assert periodo < contrato.fecha_firma
        assert recibo.neto == recibo.remuneracion_bruta - recibo.total_descuentos
        assert identidad.persona == persona


@pytest.mark.parametrize("seed", SEEDS)
def test_alquiler_en_pesos_frente_al_neto(seed):
    contrato, _ = generate_contrato_con_identidades(seed)
    alquiler = alquiler_en_pesos(contrato)
    if contrato.moneda == Moneda.ARS:
        assert alquiler == contrato.monto_inicial
    for _, recibo in generate_recibos(seed).values():
        assert 0.19 <= float(alquiler / recibo.neto) <= 0.41


def test_misma_semilla_mismos_recibos():
    assert generate_recibos(4) == generate_recibos(4)


@pytest.mark.parametrize("seed", SEEDS)
def test_evidencia_de_cada_dato_en_el_recibo(seed):
    for pdf, recibo in generate_recibos(seed).values():
        texto = _texto(pdf)
        assert len(PdfReader(BytesIO(pdf)).pages) == 1
        for campo in CAMPOS:
            evidencia = getattr(recibo, f"{campo}_evidencia")
            assert evidencia is not None, campo
            assert evidencia.pagina == 1
            assert " ".join(evidencia.texto.split()) in texto, (campo, evidencia.texto)


def test_recibo_marcado_como_sintetico():
    pdf, _ = next(iter(generate_recibos(0).values()))
    texto = _texto(pdf)
    assert AVISO in texto
    assert MARCA in texto
    assert PdfReader(BytesIO(pdf)).metadata.subject == AVISO
