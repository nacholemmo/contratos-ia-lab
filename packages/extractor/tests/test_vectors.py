"""Tests de TF-IDF/embeddings + regresión logística: la separación por legajo y la corrida.

No descargan el modelo de Hugging Face: los embeddings se reemplazan por un vectorizador falso.
"""

import numpy as np
import pytest

pytest.importorskip("sklearn", reason="necesita el extra ml: uv sync --extra ml")

from pdf_fixtures import image_pdf, text_pdf  # noqa: E402

from core.models import TipoDocumento  # noqa: E402
from extractor import vectors  # noqa: E402
from extractor.experiment import Sample  # noqa: E402
from extractor.splits import legajo_key, split_by_legajo  # noqa: E402
from extractor.vectors import run_vectors  # noqa: E402

DOCUMENTOS = {
    "contrato": (TipoDocumento.CONTRATO, "CONTRATO DE LOCACION entre locador y locatario"),
    "dni_inquilino_1": (TipoDocumento.DNI, "FICHA DE IDENTIDAD sintetica apellido nombre"),
    "recibo_inquilino_1": (TipoDocumento.RECIBO_SUELDO, "RECIBO DE HABERES periodo neto"),
    "titulo_garante_1": (TipoDocumento.GARANTIA, "CONSTANCIA DE TITULARIDAD DE INMUEBLE"),
    "seguro": (TipoDocumento.SEGURO, "POLIZA SEGURO CONTRA INCENDIO edificio"),
}
SORTEADOS = [f"{seed:04d}" for seed in range(42, 52)]  # 10 legajos


def write_legajo(folder, documentos=DOCUMENTOS) -> list[Sample]:
    folder.mkdir(parents=True)
    samples = []
    for name, (tipo, texto) in documentos.items():
        pdf = folder / f"{name}.pdf"
        pdf.write_bytes(text_pdf(f"{texto} legajo {folder.name}"))
        samples.append(Sample(pdf, tipo, scanned=False))
    return samples


@pytest.fixture(autouse=True)
def texto_corto_alcanza(monkeypatch):
    """`text_pdf` escribe una sola línea: no llega a las 15 palabras largas de `MIN_LONG_WORDS`.
    El umbral tiene sus tests en `test_inputs.py`; acá alcanza con "hay algo de texto"."""
    monkeypatch.setattr(vectors, "has_usable_text", lambda texts: any(t.strip() for t in texts))


@pytest.fixture
def data_root(tmp_path):
    return tmp_path


@pytest.fixture
def legajo_set(data_root) -> list[Sample]:
    """10 legajos sorteados y la semilla 0092 en dos casos del set forzado: uno con texto
    (cláusula larga) y uno escaneado (solo el contrato, sin capa de texto)."""
    samples = []
    for seed in SORTEADOS:
        samples += write_legajo(data_root / seed)
    samples += write_legajo(data_root / "forzados" / "clausula_larga" / "0092")
    scan = data_root / "forzados" / "escaneo_torcido" / "0092"
    scan.mkdir(parents=True)
    (scan / "contrato.pdf").write_bytes(image_pdf())
    samples.append(Sample(scan / "contrato.pdf", TipoDocumento.CONTRATO, scanned=True))
    return samples


def text_samples(samples):
    return [s for s in samples if not s.scanned]


# --- legajo_key ---


def test_la_misma_semilla_en_dos_casos_es_el_mismo_legajo(legajo_set):
    keys = {legajo_key(s) for s in legajo_set if "forzados" in s.pdf.parts}
    assert keys == {"0092"}


# --- split_by_legajo: propiedades que cualquier separación correcta cumple ---


def test_cada_documento_queda_de_un_solo_lado(legajo_set):
    samples = text_samples(legajo_set)
    train, test = split_by_legajo(samples)

    assert len(train) + len(test) == len(samples)
    assert {s.pdf for s in train} | {s.pdf for s in test} == {s.pdf for s in samples}
    assert not {s.pdf for s in train} & {s.pdf for s in test}


def test_ningun_legajo_queda_partido(legajo_set):
    """Si el DNI de 0042 entrena y el recibo de 0042 se evalúa, el clasificador ya vio el
    nombre y el domicilio: fuga de datos. Incluye la 0092, repartida en dos carpetas."""
    train, test = split_by_legajo(text_samples(legajo_set))
    assert not {legajo_key(s) for s in train} & {legajo_key(s) for s in test}


def test_los_dos_lados_tienen_documentos(legajo_set):
    train, test = split_by_legajo(text_samples(legajo_set))
    assert train
    assert test


def test_respeta_la_fraccion_de_prueba_en_legajos(legajo_set):
    """11 legajos con texto (10 sorteados + 0092): con 0.3, unos 3 van a prueba."""
    _, test = split_by_legajo(text_samples(legajo_set), test_fraction=0.3)
    assert 2 <= len({legajo_key(s) for s in test}) <= 4


def test_separacion_deterministica(legajo_set):
    samples = text_samples(legajo_set)
    first = split_by_legajo(samples, seed=7)
    second = split_by_legajo(list(samples), seed=7)
    assert first == second


def test_no_depende_del_orden_de_entrada(legajo_set):
    """La misma semilla da los mismos legajos de prueba aunque los documentos lleguen en otro
    orden (por ejemplo, si cambia cómo se recorre `data/`)."""
    samples = text_samples(legajo_set)
    _, test = split_by_legajo(samples, seed=7)
    _, test_reversed = split_by_legajo(samples[::-1], seed=7)
    assert {legajo_key(s) for s in test} == {legajo_key(s) for s in test_reversed}


# --- run_vectors ---


def test_tfidf_entrena_y_evalua_lo_que_no_vio(legajo_set, data_root):
    outcome = run_vectors(legajo_set, "tfidf", data_root)

    evaluated = {r.pdf for r in outcome.results}
    trained = set(outcome.train_legajos)
    assert outcome.n_train > 0
    assert all(r.pdf.split("/")[-2] not in trained or r.scanned for r in outcome.results)
    # Todo con texto que no entrenó se evalúa, y nada se evalúa dos veces.
    assert len(evaluated) == len(outcome.results)


def test_tfidf_acierta_documentos_de_plantilla(legajo_set, data_root):
    outcome = run_vectors(legajo_set, "tfidf", data_root)
    for r in outcome.results:
        if not r.scanned:
            assert r.predicted == r.tipo
            assert 0 < r.confidence <= 1


def test_sin_texto_no_entrena_y_se_predice_otro(legajo_set, data_root):
    outcome = run_vectors(legajo_set, "tfidf", data_root)
    (scan,) = [r for r in outcome.results if r.scanned]
    assert scan.predicted == TipoDocumento.OTRO
    assert scan.confidence == 0.0


def test_embeddings_usa_el_vectorizador_sin_descargar(legajo_set, data_root, monkeypatch):
    """Un vectorizador falso: un vector por tipo según una palabra clave del texto."""
    claves = ["CONTRATO", "FICHA", "RECIBO", "TITULARIDAD", "POLIZA"]

    def fake_vectorizer(_train):
        return lambda texts: np.array([[float(k in t) for k in claves] for t in texts])

    monkeypatch.setitem(vectors.VECTORIZERS, "embeddings", fake_vectorizer)
    outcome = run_vectors(legajo_set, "embeddings", data_root)

    assert outcome.vectorizer == "embeddings"
    assert all(r.predicted == r.tipo for r in outcome.results if not r.scanned)
