import re
from collections import Counter
from io import BytesIO

import pytest
from pypdf import PdfReader

from synthetic.cases import P_CASO, CasoDificil, Muestra, aplicar_faltantes, elegir_casos
from synthetic.clauses import render_clauses
from synthetic.contracts import generate_contrato
from synthetic.pdf import generate_contract, generate_sample
from synthetic.source import Source

SEEDS = range(300)


def _casos(seed: int) -> list[CasoDificil]:
    return elegir_casos(Source(seed).derive("casos"))


# --- elegir_casos ---


def test_cada_caso_tiene_probabilidad():
    # Un caso nuevo sin probabilidad no saldría nunca en el set, en silencio.
    assert set(P_CASO) == set(CasoDificil)


def test_elegir_casos_es_determinista():
    for seed in range(30):
        assert _casos(seed) == _casos(seed)


@pytest.mark.parametrize("seed", range(50))
def test_elegir_casos_sin_repetidos_y_en_orden_del_enum(seed):
    casos = _casos(seed)
    orden = list(CasoDificil)
    assert len(casos) == len(set(casos))
    assert casos == sorted(casos, key=orden.index)


def test_cada_caso_aparece_con_su_frecuencia():
    conteo = Counter(caso for seed in SEEDS for caso in _casos(seed))
    for caso, p in P_CASO.items():
        frecuencia = conteo[caso] / len(SEEDS)
        # Margen amplio: con 300 semillas, el azar mueve la frecuencia unos puntos.
        assert p / 2 <= frecuencia <= p * 2, (caso, frecuencia)


def test_la_mayoria_de_los_contratos_queda_limpia():
    # El set representativo (sin casos) tiene que seguir siendo la base.
    limpios = sum(1 for seed in SEEDS if not _casos(seed))
    assert limpios / len(SEEDS) > 0.5


def test_hay_contratos_con_mas_de_un_caso():
    assert any(len(_casos(seed)) >= 2 for seed in SEEDS)


# --- generate_sample ---


def test_muestra_marcada_como_sintetica_y_con_su_semilla():
    _, muestra = generate_sample(7)
    assert muestra.sintetico is True
    assert muestra.seed == 7
    assert muestra.casos == _casos(7)


def test_muestra_se_serializa_y_vuelve_igual():
    _, muestra = generate_sample(3, casos=list(CasoDificil))
    assert Muestra.model_validate_json(muestra.model_dump_json()) == muestra


def test_misma_semilla_misma_muestra():
    for seed in range(5):
        assert generate_sample(seed) == generate_sample(seed)


def test_casos_forzados_se_normalizan():
    pedido = [CasoDificil.MONTOS_SOLO_LETRAS, CasoDificil.FECHA_FIRMA_EN_BLANCO]
    _, muestra = generate_sample(1, casos=pedido + pedido)
    assert muestra.casos == [CasoDificil.FECHA_FIRMA_EN_BLANCO, CasoDificil.MONTOS_SOLO_LETRAS]


def test_casos_vacios_dan_el_contrato_limpio():
    _, muestra = generate_sample(5, casos=[])
    assert muestra.casos == []
    assert muestra.contrato.fecha_firma == generate_contrato(5).fecha_firma


def test_generate_contract_es_el_contrato_de_la_muestra():
    for seed in range(5):
        pdf, muestra = generate_sample(seed)
        assert generate_contract(seed) == (pdf, muestra.contrato)


# --- cada caso, forzado ---


@pytest.mark.parametrize("seed", range(20))
def test_fecha_firma_en_blanco(seed):
    _, muestra = generate_sample(seed, casos=[CasoDificil.FECHA_FIRMA_EN_BLANCO])
    c = muestra.contrato
    assert c.fecha_firma is None
    assert c.fecha_firma_evidencia is None
    # El régimen es el de la fecha real: el generador la conoce aunque el papel no.
    assert c.regimen_legal == generate_contrato(seed).regimen_legal


def test_fecha_firma_en_blanco_deja_el_hueco_en_el_pdf():
    pdf, _ = generate_sample(0, casos=[CasoDificil.FECHA_FIRMA_EN_BLANCO])
    texto = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert "____" in texto


@pytest.mark.parametrize("seed", range(20))
def test_persona_sin_documento(seed):
    _, muestra = generate_sample(seed, casos=[CasoDificil.PERSONA_SIN_DOCUMENTO])
    sin_doc = [p for p in muestra.contrato.partes if p.dni is None and p.cuit is None]
    assert len(sin_doc) == 1
    # Las demás partes conservan sus datos.
    originales = {p.id: p for p in generate_contrato(seed).partes}
    for p in muestra.contrato.partes:
        if p not in sin_doc:
            assert p == originales[p.id]


@pytest.mark.parametrize("seed", range(20))
def test_sin_codigo_postal(seed):
    _, muestra = generate_sample(seed, casos=[CasoDificil.SIN_CODIGO_POSTAL])
    assert muestra.contrato.propiedad.codigo_postal is None
    assert "CP" not in muestra.contrato.propiedad_evidencia.texto


@pytest.mark.parametrize("seed", range(20))
def test_montos_solo_en_letras(seed):
    _, muestra = generate_sample(seed, casos=[CasoDificil.MONTOS_SOLO_LETRAS])
    c = muestra.contrato
    montos = [c.monto_inicial_evidencia]
    if c.deposito is not None:
        montos.append(c.deposito_evidencia)
    for evidencia in montos:
        # Ni la cifra ni el símbolo: el extractor tiene que leer las letras.
        assert not re.search(r"\d|\$|USD", evidencia.texto), evidencia.texto


@pytest.mark.parametrize("seed", range(20))
def test_casos_no_dejan_huecos_raros_en_el_texto(seed):
    # Sobre el texto de las cláusulas y no del PDF, que corta líneas donde quiere.
    todos = list(CasoDificil)
    contrato = aplicar_faltantes(generate_contrato(seed), todos, Source(seed).derive("casos"))
    for clause in render_clauses(contrato, Source(seed).derive("redaccion"), solo_letras=True):
        assert "None" not in clause.texto, clause.nombre
        assert ", ," not in clause.texto, clause.nombre
        assert ",  " not in clause.texto, clause.nombre
