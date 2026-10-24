import re
from collections import Counter
from decimal import Decimal
from io import BytesIO

import pytest
from pypdf import PdfReader

from core.models import Contrato, Indice, Moneda, RegimenLegal, Rol
from synthetic.cases import P_CASO, CasoDificil, Muestra, elegir_casos, es_aplicable
from synthetic.clauses import escalones
from synthetic.contracts import generate_contrato
from synthetic.pdf import generate_contract, generate_sample, prepare_sample
from synthetic.source import Source

# elegir_casos es barato: muchas semillas para que las frecuencias no dependan del azar.
SEEDS_SORTEO = range(1000)
SEEDS = range(200)

CAMPOS_CON_EVIDENCIA = sorted(
    name.removesuffix("_evidencia") for name in Contrato.model_fields if name.endswith("_evidencia")
)


def _casos(seed: int) -> list[CasoDificil]:
    return elegir_casos(Source(seed).derive("casos"))


def _aplicables(seed: int) -> list[CasoDificil]:
    base = generate_contrato(seed)
    return [caso for caso in CasoDificil if es_aplicable(caso, base)]


def _seed_donde(condicion) -> int:
    return next(seed for seed in SEEDS if condicion(generate_contrato(seed)))


def _texto(pdf: bytes) -> list[str]:
    # El PDF corta líneas donde quiere: se comparan las palabras, no los saltos.
    return [" ".join(p.extract_text().split()) for p in PdfReader(BytesIO(pdf)).pages]


def _clausula(seed: int, casos: list[CasoDificil], nombre: str) -> str:
    _, _, clauses = prepare_sample(seed, casos)
    return next(c.texto for c in clauses if c.nombre == nombre)


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
    conteo = Counter(caso for seed in SEEDS_SORTEO for caso in _casos(seed))
    for caso, p in P_CASO.items():
        frecuencia = conteo[caso] / len(SEEDS_SORTEO)
        assert p / 2 <= frecuencia <= p * 2, (caso, frecuencia)


def test_la_mayoria_de_los_contratos_queda_limpia():
    # El set representativo (sin casos) tiene que seguir siendo la base.
    limpios = sum(1 for seed in SEEDS_SORTEO if not _casos(seed))
    assert limpios / len(SEEDS_SORTEO) > 0.5


def test_hay_contratos_con_mas_de_un_caso():
    assert any(len(_casos(seed)) >= 2 for seed in SEEDS_SORTEO)


# --- es_aplicable ---

# Casos de formato o de datos faltantes: pueden darse en cualquier contrato.
SIEMPRE_APLICABLES = {
    CasoDificil.FECHA_FIRMA_EN_BLANCO,
    CasoDificil.PERSONA_SIN_DOCUMENTO,
    CasoDificil.SIN_CODIGO_POSTAL,
    CasoDificil.MONTOS_SOLO_LETRAS,
    CasoDificil.GUIONES_DE_RELLENO,
    CasoDificil.CLAUSULA_LARGA,
}


@pytest.mark.parametrize("seed", SEEDS)
def test_casos_de_formato_aplican_siempre(seed):
    assert set(_aplicables(seed)) >= SIEMPRE_APLICABLES


@pytest.mark.parametrize("seed", SEEDS)
def test_canon_escalonado_solo_con_dnu_y_mas_de_un_anio(seed):
    c = generate_contrato(seed)
    if es_aplicable(CasoDificil.CANON_ESCALONADO, c):
        # Las leyes 27.551 y 27.737 fijaban el índice: escalonar el precio no era válido.
        assert c.regimen_legal == RegimenLegal.DNU_70_2023
        # Con un solo año no hay escalones.
        assert c.plazo_meses >= 24


def test_cada_caso_aplica_a_algun_contrato():
    for caso in CasoDificil:
        assert any(caso in _aplicables(seed) for seed in SEEDS), caso


def test_caso_sorteado_que_no_aplica_se_descarta():
    for seed in SEEDS:
        casos, _, _ = prepare_sample(seed)
        assert set(casos) <= set(_aplicables(seed)), seed


def test_caso_forzado_que_no_aplica_es_un_error():
    seed = _seed_donde(lambda c: c.regimen_legal == RegimenLegal.LEY_27551)
    with pytest.raises(ValueError, match="no aplican"):
        generate_sample(seed, casos=[CasoDificil.CANON_ESCALONADO])


# --- generate_sample ---


def test_muestra_marcada_como_sintetica_y_con_su_semilla():
    _, muestra = generate_sample(7)
    assert muestra.sintetico is True
    assert muestra.seed == 7


def test_muestra_se_serializa_y_vuelve_igual():
    _, muestra = generate_sample(3, casos=_aplicables(3))
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


@pytest.mark.parametrize("seed", range(30))
def test_todos_los_casos_juntos_con_evidencia_en_su_pagina(seed):
    pdf, muestra = generate_sample(seed, casos=_aplicables(seed))
    paginas = _texto(pdf)
    c = muestra.contrato
    evidencias = [getattr(c, f"{campo}_evidencia") for campo in CAMPOS_CON_EVIDENCIA]
    for evidencia in [e for e in evidencias if e is not None] + c.clausulas:
        texto = " ".join(evidencia.texto.split())
        assert texto in paginas[evidencia.pagina - 1], evidencia


@pytest.mark.parametrize("seed", range(20))
def test_casos_no_dejan_huecos_raros_en_el_texto(seed):
    # Sobre el texto de las cláusulas y no del PDF, que corta líneas donde quiere.
    _, _, clauses = prepare_sample(seed, _aplicables(seed))
    for clause in clauses:
        assert "None" not in clause.texto, clause.nombre
        assert ", ," not in clause.texto, clause.nombre
        assert ",  " not in clause.texto, clause.nombre


# --- 4a: datos faltantes y montos en letras ---


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
    assert "____" in _texto(pdf)[0]


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


# --- 4b: cláusulas raras ---


@pytest.mark.parametrize("seed", range(20))
def test_guiones_de_relleno_al_final_de_cada_clausula(seed):
    _, _, clauses = prepare_sample(seed, [CasoDificil.GUIONES_DE_RELLENO])
    for clause in clauses:
        assert re.search(r"-{8,}$", clause.texto), clause.nombre


def test_escalones_uno_por_anio_y_crecientes():
    for plazo in (24, 36, 60):
        montos = escalones(Decimal(500_000), Moneda.ARS, plazo, Source(1))
        assert len(montos) == plazo // 12
        assert montos[0] == 500_000
        assert all(b > a for a, b in zip(montos, montos[1:], strict=False))
        assert all(m % 1_000 == 0 for m in montos)


def test_canon_escalonado():
    seed = _seed_donde(lambda c: es_aplicable(CasoDificil.CANON_ESCALONADO, c))
    _, muestra = generate_sample(seed, casos=[CasoDificil.CANON_ESCALONADO])
    c = muestra.contrato
    # En el modelo: sin índice y el monto del primer año (el resto queda en el texto).
    assert c.indice == Indice.FIJO
    assert c.frecuencia_ajuste_meses is None
    assert c.monto_inicial == generate_contrato(seed).monto_inicial
    precio = _clausula(seed, [CasoDificil.CANON_ESCALONADO], "precio")
    assert c.monto_inicial_evidencia.texto in precio
    assert precio.count("mensuales") == c.plazo_meses // 12


def test_seguro_de_caucion_sin_persona_garante():
    seed = _seed_donde(lambda c: any(p.rol == Rol.GARANTE for p in c.partes))
    _, muestra = generate_sample(seed, casos=[CasoDificil.SEGURO_DE_CAUCION])
    assert all(p.rol != Rol.GARANTE for p in muestra.contrato.partes)
    garantia = _clausula(seed, [CasoDificil.SEGURO_DE_CAUCION], "garantia")
    assert "seguro de caución" in garantia
    assert "fiador" not in garantia


def test_clausula_larga_ocupa_mas_de_una_pagina():
    seed = 0
    pdf_limpio, _ = generate_sample(seed, casos=[])
    pdf_largo, _ = generate_sample(seed, casos=[CasoDificil.CLAUSULA_LARGA])
    assert len(_texto(pdf_largo)) >= len(_texto(pdf_limpio)) + 1
    inventario = _clausula(seed, [CasoDificil.CLAUSULA_LARGA], "inventario")
    assert len(inventario) > 5_000
