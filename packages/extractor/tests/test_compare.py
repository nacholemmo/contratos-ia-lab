"""Tests de la comparación del paso 4: lectura de corridas, conjunto común y resumen."""

import json
from decimal import Decimal

import pytest
from pdf_fixtures import image_pdf, text_pdf

from core.models import TipoDocumento
from extractor import compare
from extractor.compare import (
    Run,
    common_pdfs,
    eval_samples,
    latest,
    load_llm_run,
    load_vector_run,
    summarize,
)
from extractor.experiment import Sample

C, D, G, S, O = (
    TipoDocumento.CONTRATO,
    TipoDocumento.DNI,
    TipoDocumento.GARANTIA,
    TipoDocumento.SEGURO,
    TipoDocumento.OTRO,
)


def llm_result(pdf, tipo, predicted, cost="0.0001", latency=1.0):
    return {
        "pdf": pdf,
        "tipo": tipo,
        "scanned": False,
        "mode": "text",
        "predicted": predicted,
        "input_tokens": 1000,
        "output_tokens": 5,
        "cost_usd": cost,
        "latency_s": latency,
    }


def test_latest_toma_la_corrida_mas_nueva(tmp_path):
    for name in ["zero-shot-20261101-000000.json", "zero-shot-20261108-014319.json"]:
        (tmp_path / name).write_text("{}")
    (tmp_path / "few-shot-20261201-000000.json").write_text("{}")
    assert latest(tmp_path, "zero-shot-").name == "zero-shot-20261108-014319.json"


def test_latest_sin_corridas_falla_claro(tmp_path):
    with pytest.raises(FileNotFoundError, match="few-shot-"):
        latest(tmp_path, "few-shot-")


def test_load_llm_run(tmp_path):
    path = tmp_path / "zero-shot-1.json"
    results = [
        llm_result("0042/contrato.pdf", "contrato", "contrato", cost="0.0002", latency=0.5),
        llm_result("0043/titulo_garante_1.pdf", "garantia", None),
    ]
    path.write_text(json.dumps({"outcome": {"results": results}}))

    run = load_llm_run(path, "zero-shot")

    assert run.predicted == {"0042/contrato.pdf": C, "0043/titulo_garante_1.pdf": None}
    assert run.cost_usd["0042/contrato.pdf"] == Decimal("0.0002")
    assert run.latency_s["0042/contrato.pdf"] == 0.5
    assert run.source == "zero-shot-1.json"


def test_load_vector_run_reparte_la_latencia_entre_los_que_tienen_texto(tmp_path):
    path = tmp_path / "vectores-tfidf-1.json"
    results = [
        {"pdf": "0050/dni_inquilino_1.pdf", "tipo": "dni", "scanned": False,
         "predicted": "dni", "confidence": 0.9},
        {"pdf": "0050/seguro.pdf", "tipo": "seguro", "scanned": False,
         "predicted": "seguro", "confidence": 0.8},
        {"pdf": "forzados/escaneo_torcido/0092/contrato.pdf", "tipo": "contrato", "scanned": True,
         "predicted": "otro", "confidence": 0.0},
    ]  # fmt: skip
    path.write_text(json.dumps({"results": results, "predict_s": 0.02}))

    run = load_vector_run(path, "tfidf")

    assert run.latency_s["0050/seguro.pdf"] == pytest.approx(0.01)
    assert run.latency_s["forzados/escaneo_torcido/0092/contrato.pdf"] == 0.0
    assert run.cost_usd == {}


def test_common_pdfs_deja_solo_lo_que_evaluaron_todos():
    a = Run("a", "x", {"1.pdf": C, "2.pdf": D, "3.pdf": G})
    b = Run("b", "x", {"1.pdf": C, "3.pdf": G})  # como el few-shot, sin un documento ejemplo
    assert common_pdfs(["3.pdf", "1.pdf", "2.pdf"], [a, b]) == ["3.pdf", "1.pdf"]


def test_summarize():
    truth = {"1.pdf": C, "2.pdf": G, "3.pdf": G, "4.pdf": S}
    run = Run(
        "zero-shot",
        "x",
        predicted={"1.pdf": C, "2.pdf": G, "3.pdf": O, "4.pdf": S},
        cost_usd={p: Decimal("0.0001") for p in truth},
        latency_s=dict.fromkeys(truth, 1.0),
    )

    row = summarize(run, list(truth), truth, scanned={"1.pdf"})

    assert row.n == 4
    assert row.accuracy == pytest.approx(0.75)
    assert row.scanned_correct == 1
    assert row.scanned_n == 1
    assert row.cost_usd == Decimal("0.0004")
    assert row.usd_per_1000 == Decimal("0.1")
    assert row.mean_latency_s == pytest.approx(1.0)
    assert row.per_class[G].recall == pytest.approx(0.5)
    assert set(row.per_class) == {C, G, S}  # `otro` no tiene documentos reales
    assert row.errors == ["3.pdf: garantia → otro"]


# --- el conjunto de evaluación coincide con el de run_vectors ---


@pytest.fixture
def legajo_set(tmp_path, monkeypatch):
    """10 legajos con texto y un contrato escaneado. Una línea de texto no llega al umbral del
    híbrido: acá alcanza con "hay algo de texto" (el umbral tiene sus tests)."""
    monkeypatch.setattr(compare, "has_usable_text", lambda texts: any(t.strip() for t in texts))
    samples = []
    for seed in range(42, 52):
        folder = tmp_path / f"{seed:04d}"
        folder.mkdir()
        for name, tipo, texto in [
            ("contrato", C, "CONTRATO DE LOCACION entre partes"),
            ("dni_inquilino_1", D, "FICHA DE IDENTIDAD sintetica"),
            ("seguro", S, "POLIZA SEGURO CONTRA INCENDIO"),
        ]:
            (folder / f"{name}.pdf").write_bytes(text_pdf(f"{texto} {seed}"))
            samples.append(Sample(folder / f"{name}.pdf", tipo, scanned=False))
    scan = tmp_path / "forzados" / "escaneo_torcido" / "0092"
    scan.mkdir(parents=True)
    (scan / "contrato.pdf").write_bytes(image_pdf())
    samples.append(Sample(scan / "contrato.pdf", C, scanned=True))
    return samples


def test_eval_samples_incluye_los_escaneos_y_parte_de_los_legajos(legajo_set):
    evaluated = eval_samples(legajo_set)
    assert any(s.scanned for s in evaluated)
    folders = {s.pdf.parent.name for s in evaluated if not s.scanned}
    assert folders  # algún legajo de prueba
    assert len(folders) < 10  # pero no todos


def test_eval_samples_es_el_mismo_conjunto_que_evaluo_run_vectors(
    legajo_set, tmp_path, monkeypatch
):
    pytest.importorskip("sklearn", reason="necesita el extra ml: uv sync --extra ml")
    from extractor import vectors

    monkeypatch.setattr(vectors, "has_usable_text", lambda texts: any(t.strip() for t in texts))
    outcome = vectors.run_vectors(legajo_set, "tfidf", tmp_path)

    expected = {r.pdf for r in outcome.results}
    assert {str(s.pdf.relative_to(tmp_path)) for s in eval_samples(legajo_set)} == expected


def test_el_prefijo_del_zero_shot_no_toma_la_corrida_del_experimento(tmp_path):
    (tmp_path / "zero-shot-20261108-014319.json").write_text("{}")
    (tmp_path / "zero-shot-def-20261110-000000.json").write_text("{}")
    assert latest(tmp_path, compare.APPROACHES["zero-shot"]).name.startswith("zero-shot-2026")
    assert latest(tmp_path, compare.APPROACHES["zero-shot-def"]).name.startswith("zero-shot-def")
