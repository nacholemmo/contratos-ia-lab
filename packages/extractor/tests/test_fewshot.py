"""Tests del few-shot: armado del prompt, recorte de ejemplos, fuga de datos y la selección."""

from collections import Counter

import pytest
from pdf_fixtures import image_pdf, text_pdf

from core.models import TipoDocumento
from extractor.classify import SYSTEM_ZERO_SHOT
from extractor.experiment import Sample
from extractor.fewshot import (
    build_system_few_shot,
    example_text,
    select_examples,
    without_examples,
)

# Nombres como los del set real (`select_examples` puede mirarlos: título vs. caución).
ARCHIVOS = {
    TipoDocumento.CONTRATO: "contrato",
    TipoDocumento.DNI: "dni_inquilino_1",
    TipoDocumento.RECIBO_SUELDO: "recibo_inquilino_1",
    TipoDocumento.GARANTIA: "titulo_garante_1",
    TipoDocumento.SEGURO: "seguro",
}
TEXTOS = {
    TipoDocumento.CONTRATO: "CONTRATO DE LOCACION entre las partes",
    TipoDocumento.DNI: "FICHA DE IDENTIDAD sintetica numero 30111222",
    TipoDocumento.RECIBO_SUELDO: "RECIBO DE HABERES periodo marzo",
    TipoDocumento.GARANTIA: "CONSTANCIA DE TITULARIDAD DE INMUEBLE matricula 1234",
    TipoDocumento.SEGURO: "POLIZA SEGURO CONTRA INCENDIO",
}


@pytest.fixture
def legajo_set(tmp_path) -> list[Sample]:
    """Un set chico con la forma del real: 4 legajos con un documento de cada tipo (en el orden
    de `legajo.json`, el contrato primero) y 2 contratos escaneados del set forzado."""
    samples = []
    for seed in range(42, 46):
        folder = tmp_path / f"{seed:04d}"
        folder.mkdir()
        for tipo, texto in TEXTOS.items():
            pdf = folder / f"{ARCHIVOS[tipo]}.pdf"
            pdf.write_bytes(text_pdf(texto))
            samples.append(Sample(pdf, tipo, scanned=False))
    for seed in (9001, 9002):
        folder = tmp_path / "forzados" / "escaneo_torcido" / str(seed)
        folder.mkdir(parents=True)
        pdf = folder / "contrato.pdf"
        pdf.write_bytes(image_pdf())
        samples.append(Sample(pdf, TipoDocumento.CONTRATO, scanned=True))
    return samples


def test_example_text_recorta(legajo_set):
    contrato = legajo_set[0]
    assert example_text(contrato).startswith("CONTRATO DE LOCACION entre las partes")
    assert example_text(contrato, max_chars=20) == "CONTRATO DE LOCACION"


def test_el_system_suma_ejemplos_al_zero_shot(legajo_set):
    dni, garantia = legajo_set[1], legajo_set[3]
    system = build_system_few_shot([dni, garantia])

    assert system.startswith(SYSTEM_ZERO_SHOT)
    assert system.count("<ejemplo>") == 2
    assert "<documento>\nFICHA DE IDENTIDAD" in system
    assert "<etiqueta>garantia</etiqueta>" in system
    assert "<etiqueta>dni</etiqueta>" in system


def test_sin_ejemplos_es_el_zero_shot_con_bloque_vacio(legajo_set):
    assert build_system_few_shot([]).startswith(SYSTEM_ZERO_SHOT)


def test_los_ejemplos_no_se_evaluan(legajo_set):
    examples = [legajo_set[0], legajo_set[7]]
    evaluated = without_examples(legajo_set, examples)

    assert len(evaluated) == len(legajo_set) - 2
    assert not {s.pdf for s in examples} & {s.pdf for s in evaluated}


# Propiedades que cualquier selección razonable tiene que cumplir. La selección en sí (cuántos,
# cuáles) es una decisión de diseño de `select_examples`.


def test_seleccion_sale_del_set(legajo_set):
    examples = select_examples(legajo_set)
    assert examples
    assert {s.pdf for s in examples} <= {s.pdf for s in legajo_set}


def test_seleccion_sin_repetidos(legajo_set):
    examples = select_examples(legajo_set)
    assert len({s.pdf for s in examples}) == len(examples)


def test_seleccion_deterministica(legajo_set):
    assert select_examples(legajo_set) == select_examples(list(legajo_set))


def test_seleccion_solo_con_texto(legajo_set):
    assert not any(s.scanned for s in select_examples(legajo_set))


def test_seleccion_cubre_todas_las_clases_del_set(legajo_set):
    """Un ejemplo por clase como mínimo: si una clase no aparece, el modelo aprende del prompt
    que esa etiqueta casi no se usa (sesgo por los ejemplos)."""
    tipos = Counter(s.tipo for s in select_examples(legajo_set))
    assert set(tipos) == set(TEXTOS)


def test_seleccion_deja_casi_todo_para_evaluar(legajo_set):
    """Los ejemplos son unos pocos: el resto del set se sigue evaluando."""
    assert len(select_examples(legajo_set)) <= len(legajo_set) // 2
