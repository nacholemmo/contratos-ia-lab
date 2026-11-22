"""Tests de las inconsistencias inyectadas: sorteo, aplicabilidad, `quitar_documentos` y el
criterio central de la Fase 3: cada inconsistencia inyectada tiene su alerta (o su faltante)
en el ground truth."""

from collections import Counter
from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import BaseModel

from core.legajo import Etapa, TipoAlerta
from core.models import ReciboSueldo, Rol, TipoDocumento, cuit_valido
from synthetic.cases import CasoDificil
from synthetic.fotografiado import (
    DocumentoGenerado,
    documentos_del_legajo,
    generate_legajo,
    ingreso_insuficiente,
    quitar_documentos,
)
from synthetic.identity import cuit_from_dni
from synthetic.inconsistencias import (
    ALERTA_DE,
    ANTIGUEDAD_MAXIMA_RECIBO_MESES,
    IMPLEMENTADAS,
    P_INCONSISTENCIA,
    Inconsistencia,
    PlanRecibos,
    compatibles,
    correr_neto,
    cuil_ajeno,
    elegir_inconsistencias,
    es_aplicable,
    objetivo_recibos,
    plan_recibos,
)
from synthetic.legajo import contexto_legajo, sumar_meses
from synthetic.recibo import alquiler_en_pesos, generate_recibos_meses
from synthetic.source import Source

# 42: un inquilino, sin garantes (el legajo más chico). 43: dos inquilinos y dos garantes.
SEED_CHICO = 42
SEED_COMPLETO = 43


# --- definición ---


def test_cada_inconsistencia_tiene_su_alerta_o_es_un_faltante():
    assert set(ALERTA_DE) == set(Inconsistencia)
    assert [i for i, alerta in ALERTA_DE.items() if alerta is None] == [
        Inconsistencia.DOCUMENTO_FALTANTE
    ]


def test_todas_tienen_probabilidad():
    assert list(P_INCONSISTENCIA) == list(Inconsistencia)


# --- aplicabilidad y sorteo ---


def test_sin_garantes_no_hay_titular_que_no_sea_garante():
    assert not es_aplicable(Inconsistencia.TITULAR_NO_ES_GARANTE, contexto_legajo(SEED_CHICO))
    assert es_aplicable(Inconsistencia.TITULAR_NO_ES_GARANTE, contexto_legajo(SEED_COMPLETO))


def test_caucion_corta_solo_con_caucion():
    contexto = contexto_legajo(SEED_COMPLETO)
    assert not es_aplicable(Inconsistencia.CAUCION_MAS_CORTA_QUE_EL_PLAZO, contexto)
    con_caucion = contexto_legajo(SEED_COMPLETO, [CasoDificil.SEGURO_DE_CAUCION])
    assert es_aplicable(Inconsistencia.CAUCION_MAS_CORTA_QUE_EL_PLAZO, con_caucion)


def test_sorteo_determinista_y_solo_implementadas():
    vistas: Counter = Counter()
    for seed in range(200):
        contexto = contexto_legajo(seed)
        elegidas = elegir_inconsistencias(contexto)
        assert elegidas == elegir_inconsistencias(contexto)
        assert set(elegidas) <= IMPLEMENTADAS
        assert elegidas == [i for i in Inconsistencia if i in elegidas]  # orden del enum
        vistas.update(elegidas)
    # Con p = 0,06 en 200 legajos, cada implementada sale varias veces.
    for inconsistencia in IMPLEMENTADAS:
        assert vistas[inconsistencia] >= 3


# --- quitar_documentos (sin fotos: rápido) ---

P1, P2 = UUID(int=1), UUID(int=2)


class Datos(BaseModel):
    """Datos de mentira: pydantic no deja instanciar BaseModel directamente."""


def doc(tipo: TipoDocumento, nombre: str, persona: UUID | None) -> DocumentoGenerado:
    return DocumentoGenerado(tipo, nombre, b"%PDF", Datos(), persona)


DOCS = [
    doc(TipoDocumento.DNI, "dni_inquilino_1", P1),
    doc(TipoDocumento.RECIBO_SUELDO, "recibo_inquilino_1_mes_1", P1),
    doc(TipoDocumento.RECIBO_SUELDO, "recibo_inquilino_1_mes_2", P1),
    doc(TipoDocumento.RECIBO_SUELDO, "recibo_inquilino_1_mes_3", P1),
    doc(TipoDocumento.DNI, "dni_garante_1", P2),
    doc(TipoDocumento.GARANTIA, "titulo_garante_1", P2),
]


@pytest.mark.parametrize("seed", range(20))
def test_quitados_mas_restantes_son_todos(seed):
    restantes, quitados = quitar_documentos(DOCS, Source(seed))
    assert quitados
    assert sorted(d.nombre for d in restantes + quitados) == sorted(d.nombre for d in DOCS)


@pytest.mark.parametrize("seed", range(20))
def test_quitados_de_un_tipo_y_una_persona(seed):
    _, quitados = quitar_documentos(DOCS, Source(seed))
    assert len({(d.tipo, d.persona_id) for d in quitados}) == 1


@pytest.mark.parametrize("seed", range(20))
def test_restantes_en_el_orden_original(seed):
    restantes, _ = quitar_documentos(DOCS, Source(seed))
    orden = [d.nombre for d in DOCS]
    assert [d.nombre for d in restantes] == sorted(
        (d.nombre for d in restantes), key=orden.index
    )


def test_quitar_determinista():
    assert quitar_documentos(DOCS, Source(5)) == quitar_documentos(DOCS, Source(5))


def test_quitar_no_modifica_la_lista():
    copia = list(DOCS)
    quitar_documentos(copia, Source(3))
    assert copia == DOCS


def test_el_azar_reparte_entre_personas_y_tipos():
    grupos = {
        (q[0].tipo, q[0].persona_id)
        for q in (quitar_documentos(DOCS, Source(s))[1] for s in range(50))
    }
    assert len(grupos) >= 2


# --- el legajo generado ---


def test_sin_inconsistencias_no_hay_faltantes():
    legajo = generate_legajo(SEED_CHICO, Etapa.EVALUACION)
    assert legajo.inconsistencias == []
    assert legajo.esperado.faltantes == []


def test_pedir_una_sin_implementar_falla():
    pendiente = next(i for i in Inconsistencia if i not in IMPLEMENTADAS)
    with pytest.raises(NotImplementedError):
        generate_legajo(SEED_CHICO, inconsistencias=[pendiente])


@pytest.fixture(scope="module")
def con_faltante():
    return generate_legajo(SEED_CHICO, inconsistencias=[Inconsistencia.DOCUMENTO_FALTANTE])


def test_el_faltante_no_esta_en_el_legajo(con_faltante):
    faltante = con_faltante.esperado.faltantes[0]
    sano = generate_legajo(SEED_CHICO)
    contar = Counter((d.tipo, d.persona_id) for d in sano.esperado.documentos)
    quedan = Counter((d.tipo, d.persona_id) for d in con_faltante.esperado.documentos)
    clave = (faltante.tipo, faltante.persona_id)
    assert quedan[clave] < contar[clave]
    assert len(con_faltante.fotos) < len(sano.fotos)


def test_el_faltante_es_de_una_persona_del_legajo(con_faltante):
    personas = {p.id: p.rol for p in con_faltante.esperado.personas}
    faltante = con_faltante.esperado.faltantes[0]
    assert faltante.persona_id is None or faltante.persona_id in personas
    assert personas.get(faltante.persona_id, Rol.INQUILINO) in (Rol.INQUILINO, Rol.GARANTE)


# --- el criterio de la Fase 3: cada inconsistencia con su alerta ---


@pytest.mark.parametrize("inconsistencia", list(Inconsistencia))
def test_cada_inconsistencia_inyectada_tiene_su_alerta(inconsistencia):
    if inconsistencia not in IMPLEMENTADAS:
        pytest.xfail("se implementa en los pasos 6.2 y 6.3")
    candidatas = [SEED_CHICO, *range(100)]  # el legajo chico primero: menos fotos
    seed = next(s for s in candidatas if es_aplicable(inconsistencia, contexto_legajo(s)))
    legajo = generate_legajo(seed, inconsistencias=[inconsistencia])
    assert legajo.inconsistencias == [inconsistencia]
    alerta = ALERTA_DE[inconsistencia]
    if alerta is None:
        assert legajo.esperado.faltantes
    else:
        assert alerta in {a.tipo for a in legajo.esperado.alertas}


# --- paso 6.2: los recibos ---

RECIBO = ReciboSueldo(
    empleador="Bodegas del Valle Ficticio S.A.",
    empleado="PÉREZ, ANA",
    periodo="2025-09",
    remuneracion_bruta=Decimal("1000000.00"),
    total_descuentos=Decimal("170000.00"),
    neto=Decimal("830000.00"),
)


@pytest.mark.parametrize("seed", range(30))
def test_correr_neto_no_cierra(seed):
    corrido = correr_neto(RECIBO, Source(seed))
    assert corrido.neto != corrido.remuneracion_bruta - corrido.total_descuentos


@pytest.mark.parametrize("seed", range(30))
def test_correr_neto_solo_cambia_el_neto(seed):
    corrido = correr_neto(RECIBO, Source(seed))
    assert corrido.model_dump(exclude={"neto"}) == RECIBO.model_dump(exclude={"neto"})


@pytest.mark.parametrize("seed", range(30))
def test_correr_neto_es_un_monto_valido(seed):
    """Dos decimales y no negativo: el recibo sigue siendo un recibo válido."""
    corrido = correr_neto(RECIBO, Source(seed))
    ReciboSueldo.model_validate(corrido.model_dump())


def test_correr_neto_determinista_y_sin_tocar_el_original():
    assert correr_neto(RECIBO, Source(4)) == correr_neto(RECIBO, Source(4))
    assert RECIBO.neto == Decimal("830000.00")


def test_compatibles_sin_cuil_si_los_recibos_son_de_otra_persona():
    pedidas = [Inconsistencia.CUIL_NO_CORRESPONDE_AL_DNI, Inconsistencia.RECIBO_DE_OTRA_PERSONA]
    assert compatibles(pedidas) == [Inconsistencia.RECIBO_DE_OTRA_PERSONA]


def test_sin_inconsistencias_el_plan_no_cambia_nada():
    contexto = contexto_legajo(SEED_COMPLETO)
    for p in contexto.partes(Rol.INQUILINO):
        # La semilla solo se usa para correr el neto: no cuenta como cambio.
        assert replace(plan_recibos([], contexto, p.id), seed=0) == PlanRecibos()


def test_solo_el_objetivo_tiene_alertas():
    contexto = contexto_legajo(SEED_COMPLETO)
    objetivo = objetivo_recibos(contexto)
    for p in contexto.partes(Rol.INQUILINO):
        plan = plan_recibos([Inconsistencia.RECIBO_VIEJO], contexto, p.id)
        assert bool(plan.alertas) == (p.id == objetivo)


def test_cuil_ajeno_valido_y_distinto():
    propio = "20301234563"
    for seed in range(10):
        ajeno = cuil_ajeno(propio, Source(seed))
        assert ajeno != propio
        assert cuit_valido(ajeno)


def test_recibos_con_desfase_quedan_viejos_y_el_ingreso_antes():
    contexto = contexto_legajo(SEED_CHICO)
    p = contexto.partes(Rol.INQUILINO)[0]
    normales = generate_recibos_meses(contexto, p.id, Source(1))
    viejos = generate_recibos_meses(contexto, p.id, Source(1), desfase=5)
    assert [r.periodo for _, r in viejos] == [
        f"{sumar_meses(periodo_de(normales[0][1]), -(5 + k)):%Y-%m}" for k in range(3)
    ]
    assert viejos[-1][1].fecha_ingreso < periodo_de(viejos[-1][1])


def periodo_de(recibo: ReciboSueldo) -> date:
    return date.fromisoformat(f"{recibo.periodo}-01")


def docs_con(seed: int, *inconsistencias: Inconsistencia) -> list[DocumentoGenerado]:
    """Los documentos (PDF y datos, sin fotos: rápido) con las inconsistencias pedidas."""
    return documentos_del_legajo(contexto_legajo(seed), Etapa.EVALUACION, list(inconsistencias))


def recibos_del_objetivo(seed: int, docs: list[DocumentoGenerado]) -> list[DocumentoGenerado]:
    objetivo = objetivo_recibos(contexto_legajo(seed))
    return [
        d for d in docs if d.tipo == TipoDocumento.RECIBO_SUELDO and d.persona_id == objetivo
    ]


@pytest.mark.parametrize("seed", [SEED_CHICO, SEED_COMPLETO])
def test_recibo_de_otra_persona(seed):
    contexto = contexto_legajo(seed)
    nombres = {
        f"{i.apellido}, {i.nombre_pila}".upper() for i in contexto.identidades.values()
    }
    recibos = recibos_del_objetivo(seed, docs_con(seed, Inconsistencia.RECIBO_DE_OTRA_PERSONA))
    assert len(recibos) == 3
    for d in recibos:
        assert d.datos.empleado not in nombres
        assert TipoAlerta.RECIBO_DE_OTRA_PERSONA in d.alertas


@pytest.mark.parametrize("seed", [SEED_CHICO, SEED_COMPLETO])
def test_cuil_que_no_corresponde(seed):
    contexto = contexto_legajo(seed)
    objetivo = contexto.identidades[objetivo_recibos(contexto)]
    propio = cuit_from_dni(objetivo.persona.dni, objetivo.sexo)
    recibos = recibos_del_objetivo(
        seed, docs_con(seed, Inconsistencia.CUIL_NO_CORRESPONDE_AL_DNI)
    )
    for d in recibos:
        assert d.datos.empleado_cuil != propio
        assert d.datos.empleado == f"{objetivo.apellido}, {objetivo.nombre_pila}".upper()


@pytest.mark.parametrize("seed", [SEED_CHICO, SEED_COMPLETO])
def test_recibo_viejo(seed):
    referencia = contexto_legajo(seed).referencia.replace(day=1)
    recibos = recibos_del_objetivo(seed, docs_con(seed, Inconsistencia.RECIBO_VIEJO))
    limite = sumar_meses(referencia, -ANTIGUEDAD_MAXIMA_RECIBO_MESES)
    assert periodo_de(recibos[0].datos) < limite


def test_sin_inconsistencias_el_ultimo_recibo_esta_vigente():
    referencia = contexto_legajo(SEED_CHICO).referencia.replace(day=1)
    recibos = recibos_del_objetivo(SEED_CHICO, docs_con(SEED_CHICO))
    limite = sumar_meses(referencia, -ANTIGUEDAD_MAXIMA_RECIBO_MESES)
    assert periodo_de(recibos[0].datos) >= limite


@pytest.mark.parametrize("seed", [SEED_CHICO, SEED_COMPLETO])
def test_neto_que_no_cierra_en_un_solo_recibo(seed):
    recibos = recibos_del_objetivo(seed, docs_con(seed, Inconsistencia.NETO_NO_CIERRA))
    rotos = [
        d
        for d in recibos
        if d.datos.neto != d.datos.remuneracion_bruta - d.datos.total_descuentos
    ]
    assert len(rotos) == 1
    assert [d for d in recibos if TipoAlerta.NETO_NO_CIERRA in d.alertas] == rotos


@pytest.mark.parametrize("seed", [SEED_CHICO, SEED_COMPLETO])
def test_ingreso_insuficiente_forzado(seed):
    contexto = contexto_legajo(seed)
    docs = docs_con(seed, Inconsistencia.INGRESO_INSUFICIENTE)
    inquilinos = {p.id for p in contexto.partes(Rol.INQUILINO)}
    netos: dict[str, list[Decimal]] = {}
    for d in docs:
        if d.tipo == TipoDocumento.RECIBO_SUELDO and d.persona_id in inquilinos:
            netos.setdefault(str(d.persona_id), []).append(d.datos.neto)
    assert ingreso_insuficiente(alquiler_en_pesos(contexto.limpio), netos)


def test_el_faltante_no_quita_documentos_con_alertas():
    docs = [*DOCS[:1], replace(DOCS[1], alertas=(TipoAlerta.NETO_NO_CIERRA,)), *DOCS[2:]]
    for seed in range(30):
        _, quitados = quitar_documentos(docs, Source(seed))
        assert (quitados[0].tipo, quitados[0].persona_id) != (TipoDocumento.RECIBO_SUELDO, P1)


def test_el_faltante_no_quita_grupos_protegidos():
    protegidos = frozenset({(TipoDocumento.DNI, P1), (TipoDocumento.DNI, P2)})
    for seed in range(30):
        _, quitados = quitar_documentos(DOCS, Source(seed), protegidos)
        assert quitados[0].tipo != TipoDocumento.DNI
