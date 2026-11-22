"""Tests de las inconsistencias inyectadas: sorteo, aplicabilidad, `quitar_documentos` y el
criterio central de la Fase 3: cada inconsistencia inyectada tiene su alerta (o su faltante)
en el ground truth."""

from collections import Counter
from uuid import UUID

import pytest
from pydantic import BaseModel

from core.legajo import Etapa
from core.models import Rol, TipoDocumento
from synthetic.cases import CasoDificil
from synthetic.fotografiado import DocumentoGenerado, generate_legajo, quitar_documentos
from synthetic.inconsistencias import (
    ALERTA_DE,
    IMPLEMENTADAS,
    P_INCONSISTENCIA,
    Inconsistencia,
    elegir_inconsistencias,
    es_aplicable,
)
from synthetic.legajo import contexto_legajo
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
    seed = next(s for s in range(100) if es_aplicable(inconsistencia, contexto_legajo(s)))
    legajo = generate_legajo(seed, inconsistencias=[inconsistencia])
    assert legajo.inconsistencias == [inconsistencia]
    alerta = ALERTA_DE[inconsistencia]
    if alerta is None:
        assert legajo.esperado.faltantes
    else:
        assert alerta in {a.tipo for a in legajo.esperado.alertas}
