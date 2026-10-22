from collections import Counter
from datetime import date

import pytest

from core.models import Indice, Moneda, RegimenLegal, Rol, TipoPropiedad
from synthetic.contracts import (
    FIRMA_DESDE,
    FIRMA_HASTA,
    LOCALIDADES,
    PESOS_PROVINCIA,
    choose_terms,
    generate_contrato,
    generate_persona,
    generate_propiedad,
    regimen_por_fecha,
)
from synthetic.source import Source

SEEDS = range(300)


def test_misma_semilla_misma_persona():
    # Incluye el id: si algo usara uuid4() directo, este test fallaría.
    assert generate_persona(Source(7), Rol.INQUILINO) == generate_persona(Source(7), Rol.INQUILINO)


def test_semillas_distintas_personas_distintas():
    a = generate_persona(Source(1), Rol.INQUILINO)
    b = generate_persona(Source(2), Rol.INQUILINO)
    assert a.id != b.id
    assert a.dni != b.dni


def test_cuit_coherente_con_dni():
    con_cuit = 0
    for seed in range(200):
        persona = generate_persona(Source(seed), Rol.PROPIETARIO)
        assert persona.dni is not None
        if persona.cuit is not None:
            con_cuit += 1
            assert persona.cuit[2:10] == persona.dni.zfill(8)
    # Hay personas con y sin CUIT (P_CON_CUIT = 0.6).
    assert 0 < con_cuit < 200


def test_propiedad_coherente():
    tablas = set(LOCALIDADES)
    for seed in range(200):
        prop = generate_propiedad(Source(seed))
        assert (prop.localidad, prop.provincia, prop.codigo_postal) in tablas
        es_depto = prop.tipo == TipoPropiedad.DEPARTAMENTO
        assert (prop.piso is not None) == es_depto
        assert (prop.departamento is not None) == es_depto


def test_pesos_provincia_cubren_la_tabla():
    # Una provincia sin peso nunca saldría; una con peso y sin localidades rompería la elección.
    assert set(PESOS_PROVINCIA) == {provincia for _, provincia, _ in LOCALIDADES}
    assert sum(PESOS_PROVINCIA.values()) == pytest.approx(1)


def test_mayoria_mendoza_y_resto_variado():
    props = [generate_propiedad(Source(seed)) for seed in range(2000)]
    por_provincia = Counter(p.provincia for p in props)
    assert 0.65 < por_provincia["Mendoza"] / len(props) < 0.75
    assert set(por_provincia) == set(PESOS_PROVINCIA)
    # Todas las localidades de la tabla salen alguna vez (no solo la capital de cada provincia).
    assert {p.localidad for p in props} == {loc for loc, _, _ in LOCALIDADES}


def test_misma_semilla_misma_propiedad():
    assert generate_propiedad(Source(3)) == generate_propiedad(Source(3))


# --- regimen_por_fecha ---


@pytest.mark.parametrize(
    ("fecha", "esperado"),
    [
        (date(2020, 7, 1), RegimenLegal.LEY_27551),
        (date(2023, 10, 16), RegimenLegal.LEY_27551),
        (date(2023, 10, 17), RegimenLegal.LEY_27737),
        (date(2023, 12, 28), RegimenLegal.LEY_27737),
        (date(2023, 12, 29), RegimenLegal.DNU_70_2023),
        (date(2026, 9, 30), RegimenLegal.DNU_70_2023),
    ],
)
def test_regimen_por_fecha_en_los_bordes(fecha, esperado):
    assert regimen_por_fecha(fecha) == esperado


# --- choose_terms ---


@pytest.mark.parametrize("regimen", [RegimenLegal.LEY_27551, RegimenLegal.LEY_27737])
def test_leyes_viejas_solo_en_pesos_y_36_meses_o_mas(regimen):
    for seed in SEEDS:
        terms = choose_terms(Source(seed), regimen)
        assert terms.moneda == Moneda.ARS
        assert terms.plazo_meses >= 36


def test_ley_27551_ajuste_anual_por_icl():
    for seed in SEEDS:
        terms = choose_terms(Source(seed), RegimenLegal.LEY_27551)
        assert terms.indice == Indice.ICL
        assert terms.frecuencia_ajuste_meses == 12


def test_ley_27737_ajuste_semestral_por_casa_propia():
    for seed in SEEDS:
        terms = choose_terms(Source(seed), RegimenLegal.LEY_27737)
        assert terms.indice == Indice.CASA_PROPIA
        assert terms.frecuencia_ajuste_meses == 6


def test_dnu_frecuencia_coherente_con_el_indice():
    for seed in SEEDS:
        terms = choose_terms(Source(seed), RegimenLegal.DNU_70_2023)
        if terms.indice == Indice.FIJO:
            assert terms.frecuencia_ajuste_meses is None
        else:
            assert terms.frecuencia_ajuste_meses in {3, 4, 6, 12}
        assert terms.plazo_meses >= 1


def test_dnu_tiene_variedad():
    # Sin variedad, el extractor se evaluaría siempre contra el mismo caso.
    terms = [choose_terms(Source(seed), RegimenLegal.DNU_70_2023) for seed in SEEDS]
    assert len({t.indice for t in terms}) >= 4
    assert len({t.frecuencia_ajuste_meses for t in terms}) >= 3
    assert {t.moneda for t in terms} == {Moneda.ARS, Moneda.USD}
    assert len({t.plazo_meses for t in terms}) >= 2


# --- generate_contrato ---


def test_misma_semilla_mismo_contrato():
    for seed in range(50):
        assert generate_contrato(seed) == generate_contrato(seed)


def test_semillas_distintas_contratos_distintos():
    assert len({generate_contrato(seed).id for seed in SEEDS}) == len(SEEDS)


def test_contrato_coherente():
    for seed in SEEDS:
        c = generate_contrato(seed)
        assert c.fecha_firma is not None
        assert FIRMA_DESDE <= c.fecha_firma <= FIRMA_HASTA
        assert c.fecha_inicio > c.fecha_firma
        assert c.fecha_inicio.day == 1
        assert c.regimen_legal == regimen_por_fecha(c.fecha_firma)
        if c.deposito is not None:
            assert c.deposito == c.monto_inicial
        roles = Counter(p.rol for p in c.partes)
        assert roles[Rol.PROPIETARIO] == 1
        assert roles[Rol.INQUILINO] >= 1


def test_contratos_cubren_los_tres_regimenes():
    regimenes = {generate_contrato(seed).regimen_legal for seed in range(1000)}
    assert regimenes == set(RegimenLegal)


def test_contrato_valida_contra_el_modelo_al_serializar():
    # Ida y vuelta por JSON: así se va a guardar el ground truth en disco.
    from core.models import Contrato

    for seed in range(50):
        c = generate_contrato(seed)
        assert Contrato.model_validate_json(c.model_dump_json()) == c


def test_dnu_distribucion_representativa():
    # Con pesos, IPC domina y USD es minoría (no 50/50 como con una elección uniforme).
    terms = [choose_terms(Source(seed), RegimenLegal.DNU_70_2023) for seed in range(2000)]
    indices = Counter(t.indice for t in terms)
    assert indices.most_common(1)[0][0] == Indice.IPC
    usd = sum(t.moneda == Moneda.USD for t in terms) / len(terms)
    assert 0.10 < usd < 0.20
