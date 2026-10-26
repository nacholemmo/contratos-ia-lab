"""Tests del experimento de entrada, sin red: selección del subset y resumen por estrategia."""

import json
from decimal import Decimal

from core.models import TipoDocumento
from extractor.experiment import Result, load_samples, pick_for_strategy, summarize


def write_legajo(folder, casos, documentos):
    folder.mkdir(parents=True)
    legajo = {
        "casos": casos,
        "documentos": [{"tipo": tipo, "pdf": pdf} for tipo, pdf in documentos],
    }
    (folder / "legajo.json").write_text(json.dumps(legajo))
    for _, pdf in documentos:
        (folder / pdf).write_bytes(b"%PDF")


def test_load_samples_limita_por_tipo_y_suma_los_escaneos(tmp_path):
    for seed in ("0001", "0002", "0003"):
        write_legajo(tmp_path / seed, [], [("contrato", "contrato.pdf"), ("dni", "dni.pdf")])
    write_legajo(
        tmp_path / "forzados/escaneo_torcido/0090",
        ["escaneo_torcido"],
        [("contrato", "contrato.pdf"), ("dni", "dni.pdf")],
    )

    samples = load_samples(tmp_path, per_type=2)

    tipos = [s.tipo for s in samples]
    assert tipos.count(TipoDocumento.CONTRATO) == 3  # 2 del sorteado + 1 escaneado
    assert tipos.count(TipoDocumento.DNI) == 2
    assert [s.scanned for s in samples].count(True) == 1


def test_load_samples_marca_escaneo_del_sorteado(tmp_path):
    write_legajo(tmp_path / "0001", ["escaneo_torcido"], [("contrato", "c.pdf"), ("dni", "d.pdf")])

    samples = load_samples(tmp_path, per_type=1)

    assert {(s.tipo, s.scanned) for s in samples} == {
        (TipoDocumento.CONTRATO, True),
        (TipoDocumento.DNI, False),
    }


def result(pdf, mode, tipo, predicted, scanned=False, cost="0.0001", latency=1.0):
    return Result(
        pdf=pdf,
        tipo=tipo,
        scanned=scanned,
        mode=mode,
        predicted=predicted,
        input_tokens=100,
        output_tokens=10,
        cost_usd=Decimal(cost),
        latency_s=latency,
    )


C, D = TipoDocumento.CONTRATO, TipoDocumento.DNI
# a.pdf tiene texto y el modo texto acierta; b.pdf es un escaneo y solo la imagen acierta.
RESULTS = [
    result("a.pdf", "text", D, D, cost="0.0001"),
    result("a.pdf", "image", D, C, cost="0.0003"),
    result("b.pdf", "text", C, TipoDocumento.OTRO, scanned=True, cost="0.0001"),
    result("b.pdf", "image", C, C, scanned=True, cost="0.0003"),
]
LONG_TEXT = "texto " * 100
TEXTS = {"a.pdf": [LONG_TEXT], "b.pdf": [""]}


def test_hibrido_toma_texto_o_imagen_segun_el_documento():
    picked = pick_for_strategy(RESULTS, "hybrid", TEXTS)
    assert [(r.pdf, r.mode) for r in picked] == [("a.pdf", "text"), ("b.pdf", "image")]


def test_resumen_por_estrategia():
    texto = summarize("text", pick_for_strategy(RESULTS, "text", TEXTS))
    imagen = summarize("image", pick_for_strategy(RESULTS, "image", TEXTS))
    hibrido = summarize("hybrid", pick_for_strategy(RESULTS, "hybrid", TEXTS))

    assert (texto.correct, texto.scanned_correct) == (1, 0)
    assert (imagen.correct, imagen.scanned_correct) == (1, 1)
    assert (hibrido.correct, hibrido.scanned_correct, hibrido.scanned_n) == (2, 1, 1)
    assert hibrido.cost_usd == Decimal("0.0004")
    assert texto.errors == ["b.pdf: contrato → otro"]


def test_resumen_vacio():
    assert summarize("text", []).mean_latency_s == 0.0
