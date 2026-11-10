"""Tests del legajo fotografiado: documentos por etapa, fotos, datos, ground truth y la alerta
de ingresos. Generar fotos tarda (~1 s cada una): se generan pocos legajos y se reutilizan."""

from datetime import date
from decimal import Decimal

import pytest

from core.legajo import Etapa, LegajoEsperado, TipoAlerta
from core.models import DNI, ReciboSueldo, Rol, TipoDocumento
from synthetic.cases import CasoDificil
from synthetic.contracts import generate_contrato
from synthetic.export import semillas_forzadas
from synthetic.fotografiado import (
    INGRESO_MINIMO_EN_ALQUILERES,
    generate_legajo,
    ingreso_insuficiente,
)
from synthetic.recibo import RECIBOS_POR_PERSONA, alquiler_en_pesos

# 43: dos inquilinos y dos garantes, y uno de los garantes manda sus recibos.
SEED_COMPLETO = 43
# 42: un inquilino, sin garantes: el legajo más chico (rápido para el determinismo).
SEED_CHICO = 42


@pytest.fixture(scope="module")
def evaluacion():
    return generate_legajo(SEED_COMPLETO, Etapa.EVALUACION)


@pytest.fixture(scope="module")
def cierre():
    return generate_legajo(SEED_CHICO, Etapa.CIERRE)


def tipos(esperado: LegajoEsperado) -> list[TipoDocumento]:
    return [d.tipo for d in esperado.documentos]


# --- ingreso_insuficiente (la regla de la alerta) ---

ALQUILER = Decimal("500000.00")


def test_neto_que_cubre_justo_tres_alquileres_alcanza():
    netos = {"p1": [ALQUILER * INGRESO_MINIMO_EN_ALQUILERES] * 3}
    assert ingreso_insuficiente(ALQUILER, netos) is False


def test_un_centavo_menos_no_alcanza():
    neto = ALQUILER * INGRESO_MINIMO_EN_ALQUILERES - Decimal("0.01")
    assert ingreso_insuficiente(ALQUILER, {"p1": [neto] * 3}) is True


def test_los_ingresos_de_dos_inquilinos_se_suman():
    """Dos inquilinos alquilan juntos: cada uno con 1,5 alquileres cubren los 3."""
    mitad = ALQUILER * INGRESO_MINIMO_EN_ALQUILERES / 2
    assert ingreso_insuficiente(ALQUILER, {"p1": [mitad] * 3, "p2": [mitad] * 3}) is False


def test_holgado_alcanza():
    assert ingreso_insuficiente(ALQUILER, {"p1": [ALQUILER * 10] * 3}) is False


def test_sin_recibos_no_es_esta_alerta():
    """Sin recibos no hay ingreso que medir: eso es un faltante, no un ingreso insuficiente."""
    assert ingreso_insuficiente(ALQUILER, {}) is False


# --- documentos por etapa ---


def test_evaluacion_sin_contrato_ni_seguro(evaluacion):
    assert evaluacion.esperado.etapa == Etapa.EVALUACION
    assert TipoDocumento.CONTRATO not in tipos(evaluacion.esperado)
    assert TipoDocumento.SEGURO not in tipos(evaluacion.esperado)


def test_cierre_suma_contrato_y_seguro(cierre):
    assert tipos(cierre.esperado).count(TipoDocumento.CONTRATO) == 1
    assert tipos(cierre.esperado).count(TipoDocumento.SEGURO) == 1
    contrato = next(d for d in cierre.esperado.documentos if d.tipo == TipoDocumento.CONTRATO)
    assert contrato.persona_id is None


def test_personas_inquilinos_y_garantes_sin_propietario(evaluacion):
    roles = [p.rol for p in evaluacion.esperado.personas]
    assert roles == [Rol.INQUILINO, Rol.INQUILINO, Rol.GARANTE, Rol.GARANTE]
    assert [p.id for p in evaluacion.esperado.personas] == ["p1", "p2", "p3", "p4"]


def test_cada_persona_tiene_su_dni_en_frente_y_dorso(evaluacion):
    e = evaluacion.esperado
    for persona in e.personas:
        (dni,) = [
            d for d in e.documentos if d.tipo == TipoDocumento.DNI and d.persona_id == persona.id
        ]
        assert len(dni.fotos) == 2
        datos = evaluacion.datos[dni.datos]
        assert isinstance(datos, DNI)
        assert datos.numero == persona.dni


def test_tres_recibos_por_inquilino_de_meses_consecutivos(evaluacion):
    e = evaluacion.esperado
    for persona in (p for p in e.personas if p.rol == Rol.INQUILINO):
        recibos = [
            evaluacion.datos[d.datos]
            for d in e.documentos
            if d.tipo == TipoDocumento.RECIBO_SUELDO and d.persona_id == persona.id
        ]
        assert len(recibos) == RECIBOS_POR_PERSONA
        assert all(isinstance(r, ReciboSueldo) for r in recibos)
        periodos = [date.fromisoformat(f"{r.periodo}-01") for r in recibos]
        assert periodos == sorted(periodos, reverse=True)  # del más reciente al más viejo
        assert len({(p.year * 12 + p.month) for p in periodos}) == 3
        assert (periodos[0].year * 12 + periodos[0].month) - (
            periodos[-1].year * 12 + periodos[-1].month
        ) == 2
        assert len({r.neto for r in recibos}) == 1  # mismo sueldo
        assert all(r.fecha_ingreso < periodos[-1] for r in recibos)


def test_un_garante_puede_traer_sus_recibos(evaluacion):
    e = evaluacion.esperado
    garantes = {p.id for p in e.personas if p.rol == Rol.GARANTE}
    con_recibos = {
        d.persona_id for d in e.documentos if d.tipo == TipoDocumento.RECIBO_SUELDO
    } & garantes
    assert con_recibos  # en esta semilla, uno sí


def test_cada_garante_trae_su_titulo(evaluacion):
    e = evaluacion.esperado
    for persona in (p for p in e.personas if p.rol == Rol.GARANTE):
        assert any(
            d.tipo == TipoDocumento.GARANTIA and d.persona_id == persona.id for d in e.documentos
        )


def test_con_caucion_no_hay_garantes_y_la_poliza_es_del_legajo():
    seed = semillas_forzadas(CasoDificil.SEGURO_DE_CAUCION, 0, 1)[0]
    e = generate_legajo(seed, casos=[CasoDificil.SEGURO_DE_CAUCION]).esperado
    assert all(p.rol == Rol.INQUILINO for p in e.personas)
    (caucion,) = [d for d in e.documentos if d.tipo == TipoDocumento.GARANTIA]
    assert caucion.persona_id is None


# --- fotos y datos ---


def test_una_foto_jpg_por_cada_foto_del_ground_truth_y_en_orden(evaluacion):
    assert [f.archivo for f in evaluacion.esperado.fotos] == list(evaluacion.fotos)
    for jpg in evaluacion.fotos.values():
        assert jpg[:3] == b"\xff\xd8\xff"


def test_nombres_que_no_dicen_nada(evaluacion):
    for archivo in evaluacion.fotos:
        assert archivo.startswith("IMG_")
        assert archivo.endswith(".jpg")


def test_cada_documento_tiene_sus_datos(evaluacion):
    for doc in evaluacion.esperado.documentos:
        assert doc.datos in evaluacion.datos


def test_alquiler_propuesto_del_contrato_de_la_semilla(evaluacion):
    contrato = generate_contrato(SEED_COMPLETO)
    assert evaluacion.esperado.alquiler_propuesto == contrato.monto_inicial
    assert evaluacion.esperado.moneda == contrato.moneda


def test_marcado_como_sintetico(evaluacion):
    assert evaluacion.esperado.sintetico is True


def test_misma_semilla_mismos_bytes():
    a, b = generate_legajo(SEED_CHICO), generate_legajo(SEED_CHICO)
    assert a.fotos == b.fotos
    assert a.esperado == b.esperado
    assert a.datos == b.datos


# --- la alerta en el ground truth ---


def test_la_alerta_de_ingresos_coincide_con_la_regla(evaluacion):
    """La alerta esperada es la que da la regla con los recibos de los inquilinos, y apunta a
    esos recibos como evidencia."""
    e = evaluacion.esperado
    inquilinos = {p.id for p in e.personas if p.rol == Rol.INQUILINO}
    recibos = [
        d
        for d in e.documentos
        if d.tipo == TipoDocumento.RECIBO_SUELDO and d.persona_id in inquilinos
    ]
    netos: dict[str, list[Decimal]] = {}
    for d in recibos:
        netos.setdefault(d.persona_id, []).append(evaluacion.datos[d.datos].neto)
    esperada = ingreso_insuficiente(alquiler_en_pesos(generate_contrato(SEED_COMPLETO)), netos)
    alertas = [a for a in e.alertas if a.tipo == TipoAlerta.INGRESO_INSUFICIENTE]
    assert bool(alertas) == esperada
    for alerta in alertas:
        assert set(alerta.documento_ids) == {d.id for d in recibos}
