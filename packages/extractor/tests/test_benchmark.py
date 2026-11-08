"""Tests del benchmark zero-shot, sin red: estimación por muestra, freno de gasto y negativas."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from core.models import TipoDocumento
from extractor import benchmark
from extractor.benchmark import classify_sample, estimate_hybrid_usd, run_hybrid
from extractor.classify import Classification
from extractor.experiment import Sample
from extractor.llm import PRICES, LlmRefusal, LlmUsage, cost_usd

MODEL = "claude-haiku-5-5"
C, D = TipoDocumento.CONTRATO, TipoDocumento.DNI


def make_samples(tmp_path, n, tipo=D):
    samples = []
    for i in range(n):
        pdf = tmp_path / f"{tipo.value}_{i}.pdf"
        pdf.write_bytes(b"%PDF")
        samples.append(Sample(pdf, tipo, scanned=False))
    return samples


@pytest.fixture(autouse=True)
def sin_render(monkeypatch):
    """Los PDFs de los tests son falsos: el contenido que se manda es el modo, para poder
    distinguirlo en el cliente falso."""
    monkeypatch.setattr(benchmark, "build_content", lambda _bytes, mode: mode)


def fake_classify(cost: str, tipo=D):
    def _classify(_client, _content, model):
        usage = LlmUsage(
            model=model,
            input_tokens=1000,
            output_tokens=10,
            cost_usd=Decimal(cost),
            latency_s=1.0,
            stop_reason="end_turn",
            request_id=None,
        )
        return Classification(tipo=tipo, usage=usage)

    return _classify


def test_estimacion_extrapola_el_promedio_de_cada_grupo(tmp_path):
    textos = make_samples(tmp_path, 10, D)
    escaneos = make_samples(tmp_path, 2, C)
    modes = {s.pdf: "text" for s in textos} | {s.pdf: "image" for s in escaneos}
    tokens_por_modo = {"text": 500, "image": 2000}
    llamadas = []

    def count_tokens(*, model, system, messages):
        mode = messages[0]["content"]
        llamadas.append(mode)
        return SimpleNamespace(input_tokens=tokens_por_modo[mode])

    client = SimpleNamespace(messages=SimpleNamespace(count_tokens=count_tokens))

    estimate = estimate_hybrid_usd(client, textos + escaneos, modes, MODEL, per_group=3)

    price = PRICES[MODEL]
    esperado = 10 * cost_usd(price, 500, 50) + 2 * cost_usd(price, 2000, 50)
    assert estimate == esperado
    # 3 muestras del grupo de 10 y las 2 del grupo de 2: no se cuenta todo el set.
    assert llamadas.count("text") == 3
    assert llamadas.count("image") == 2


def test_sin_tope_alcanzado_clasifica_todo(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "classify", fake_classify("0.001"))
    samples = make_samples(tmp_path, 5)
    modes = {s.pdf: "text" for s in samples}

    outcome = run_hybrid(None, samples, modes, MODEL, tmp_path, max_usd=Decimal("1"))

    assert len(outcome.results) == 5
    assert outcome.stopped_early is False
    assert outcome.spent_usd == Decimal("0.005")
    assert all(r.predicted == D for r in outcome.results)


def test_el_tope_corta_la_corrida(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "classify", fake_classify("0.01"))
    samples = make_samples(tmp_path, 10)
    modes = {s.pdf: "text" for s in samples}

    outcome = run_hybrid(None, samples, modes, MODEL, tmp_path, max_usd=Decimal("0.025"))

    assert outcome.stopped_early is True
    assert len(outcome.results) < 10
    assert outcome.spent_usd == sum((r.cost_usd for r in outcome.results), Decimal(0))
    # Se puede pasar del tope, como mucho, por una llamada: la que estaba en curso.
    assert outcome.spent_usd <= Decimal("0.025") + Decimal("0.01")


def test_tope_justo_no_corta_si_alcanza(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "classify", fake_classify("0.01"))
    samples = make_samples(tmp_path, 3)
    modes = {s.pdf: "text" for s in samples}

    outcome = run_hybrid(None, samples, modes, MODEL, tmp_path, max_usd=Decimal("0.05"))

    assert outcome.stopped_early is False
    assert len(outcome.results) == 3


def test_negativa_cuenta_como_error_sin_costo(tmp_path, monkeypatch):
    def refusal(*_args, **_kwargs):
        raise LlmRefusal("refusal")

    monkeypatch.setattr(benchmark, "classify", refusal)
    [sample] = make_samples(tmp_path, 1)

    result = classify_sample(None, sample, "image", MODEL, tmp_path)

    assert result.predicted is None
    assert result.cost_usd == Decimal(0)
    assert result.mode == "image"
    assert result.pdf == sample.pdf.name
