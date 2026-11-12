"""Tests de punta a punta de las CLIs con LLM, sin red: todo lo que pasa después de las llamadas.

Un error ahí (por ejemplo, un nombre importado dos veces) aparece recién después de gastar.
"""

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.models import TipoDocumento
from extractor import cli
from extractor.benchmark import RunOutcome
from extractor.experiment import Result, Sample

DATA = Path("data/synthetic")


@pytest.fixture
def sin_red(monkeypatch):
    """Reemplaza el cliente, la carga del set y las llamadas por datos fijos."""
    samples = [
        Sample(DATA / "0042/contrato.pdf", TipoDocumento.CONTRATO, scanned=False),
        Sample(DATA / "0043/titulo_garante_1.pdf", TipoDocumento.GARANTIA, scanned=False),
    ]
    results = [
        Result(pdf="0042/contrato.pdf", tipo="contrato", scanned=False, mode="text",
               predicted="contrato", input_tokens=1000, output_tokens=5,
               cost_usd=Decimal("0.0001"), latency_s=0.5),
        Result(pdf="0043/titulo_garante_1.pdf", tipo="garantia", scanned=False, mode="text",
               predicted="otro", input_tokens=500, output_tokens=5,
               cost_usd=Decimal("0.00005"), latency_s=0.4),
    ]  # fmt: skip
    seen = {}

    def fake_run_hybrid(_client, _samples, _modes, _model, _root, _max_usd, system):
        seen["system"] = system
        return RunOutcome(results=results, stopped_early=False, spent_usd=Decimal("0.00015"))

    monkeypatch.setattr(cli, "Settings", lambda: SimpleNamespace(llm_model="claude-haiku-5-5"))
    monkeypatch.setattr(cli, "make_client", lambda _settings: None)
    monkeypatch.setattr(cli, "load_all_samples", lambda _root: samples)
    monkeypatch.setattr(cli, "hybrid_modes", lambda s: {x.pdf: "text" for x in s})
    monkeypatch.setattr(cli, "estimate_hybrid_usd", lambda *_a, **_k: Decimal("0.0002"))
    monkeypatch.setattr(cli, "run_hybrid", fake_run_hybrid)
    return seen


@pytest.mark.parametrize(
    ("command", "prefix"),
    [
        (cli.clasificar_zero_shot, "zero-shot-"),
        (cli.clasificar_zero_shot_def, "zero-shot-def-"),
    ],
)
def test_corre_y_guarda_resultados(sin_red, tmp_path, command, prefix, capsys):
    assert command(["--run", "--out", str(tmp_path)]) == 0

    (out,) = tmp_path.glob(f"{prefix}2*.json")
    saved = json.loads(out.read_text())
    assert len(saved["outcome"]["results"]) == 2
    assert saved["summary"]["correct"] == 1
    assert "1/2" in capsys.readouterr().out


def test_zero_shot_def_usa_el_prompt_del_experimento(sin_red, tmp_path):
    cli.clasificar_zero_shot_def(["--run", "--out", str(tmp_path)])
    assert sin_red["system"] == cli.SYSTEM_ZERO_SHOT_DEF


def test_sin_run_solo_estima_y_no_guarda(sin_red, tmp_path):
    assert cli.clasificar_zero_shot(["--out", str(tmp_path)]) == 0
    assert not list(tmp_path.iterdir())
    assert "system" not in sin_red
