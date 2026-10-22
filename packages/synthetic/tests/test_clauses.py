from collections import defaultdict

import pytest

from synthetic.clauses import render_clauses
from synthetic.contracts import generate_contrato
from synthetic.source import Source

SEEDS = range(200)

# Campos del Contrato que tienen evidencia (`<campo>_evidencia`).
CAMPOS_CON_EVIDENCIA = {
    name.removesuffix("_evidencia")
    for name in generate_contrato(0).__class__.model_fields
    if name.endswith("_evidencia")
}


def _render(seed: int):
    contrato = generate_contrato(seed)
    return contrato, render_clauses(contrato, Source(seed).derive("redaccion"))


def test_derive_es_determinista_e_independiente():
    a, b = Source(5).derive("redaccion"), Source(5).derive("redaccion")
    assert [a.rng.random() for _ in range(5)] == [b.rng.random() for _ in range(5)]
    base = Source(5)
    otra = Source(5).derive("otra")
    assert base.rng.random() != Source(5).derive("redaccion").rng.random()
    assert otra.seed != Source(5).derive("redaccion").seed


def test_misma_semilla_mismas_clausulas():
    for seed in range(30):
        assert _render(seed)[1] == _render(seed)[1]


@pytest.mark.parametrize("seed", SEEDS)
def test_fragmentos_aparecen_literal_en_su_clausula(seed):
    _, clauses = _render(seed)
    for clause in clauses:
        for campo, fragmento in clause.fragmentos.items():
            assert fragmento in clause.texto, (clause.nombre, campo)


@pytest.mark.parametrize("seed", SEEDS)
def test_todo_dato_presente_tiene_fragmento(seed):
    contrato, clauses = _render(seed)
    cubiertos = {campo for c in clauses for campo in c.fragmentos}
    esperados = {campo for campo in CAMPOS_CON_EVIDENCIA if getattr(contrato, campo) is not None}
    assert cubiertos == esperados


@pytest.mark.parametrize("seed", SEEDS)
def test_clausulas_opcionales_segun_el_contrato(seed):
    contrato, clauses = _render(seed)
    nombres = [c.nombre for c in clauses]
    assert nombres[0] == "encabezado"
    assert ("deposito" in nombres) == (contrato.deposito is not None)
    tiene_garantes = any(p.rol == "garante" for p in contrato.partes)
    assert ("garantia" in nombres) == tiene_garantes


def test_hay_variedad_de_redaccion():
    textos = defaultdict(set)
    for seed in SEEDS:
        for clause in _render(seed)[1]:
            textos[clause.nombre].add(clause.texto)
    for nombre, variantes in textos.items():
        assert len(variantes) >= 2, nombre


def test_montos_en_numeros_y_en_letras():
    precios = [next(c for c in _render(s)[1] if c.nombre == "precio").texto for s in SEEDS]
    assert any("PESOS" in t or "DÓLARES" in t for t in precios)
    assert any(("$" in t or "USD" in t) and "PESOS" not in t for t in precios)


def test_redaccion_no_cambia_los_datos():
    # Renderizar no consume la Source de los datos: el contrato es el mismo con o sin render.
    for seed in range(20):
        contrato, _ = _render(seed)
        assert contrato == generate_contrato(seed)
