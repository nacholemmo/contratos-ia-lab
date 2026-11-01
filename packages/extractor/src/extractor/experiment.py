"""Experimento del paso 2: ¿texto extraído, imagen de la página o híbrido?

Cada documento se clasifica una vez en modo texto y otra en modo imagen. El híbrido no hace
llamadas propias: para cada documento toma el resultado del modo que habría elegido la regla.
Los resultados guardan solo metadatos (tipos, tokens, costo, latencia), nunca el contenido.
"""

import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import anthropic
from pydantic import BaseModel

from core.models import TipoDocumento
from extractor.classify import SYSTEM_ZERO_SHOT, classify
from extractor.inputs import Mode, Strategy, build_content, choose_mode, page_texts
from extractor.llm import PRICES, LlmRefusal, cost_usd

MODES: tuple[Mode, ...] = ("text", "image")
STRATEGIES: tuple[Strategy, ...] = ("text", "image", "hybrid")
# Salida estimada por llamada (la etiqueta más algo de pensamiento con effort low).
ESTIMATED_OUTPUT_TOKENS = 50


@dataclass(frozen=True)
class Sample:
    pdf: Path
    tipo: TipoDocumento
    scanned: bool


class Result(BaseModel):
    pdf: str
    tipo: TipoDocumento
    scanned: bool
    mode: Mode
    predicted: TipoDocumento | None
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    latency_s: float


class StrategySummary(BaseModel):
    strategy: Strategy
    n: int
    correct: int
    scanned_n: int
    scanned_correct: int
    cost_usd: Decimal
    mean_latency_s: float
    errors: list[str]  # "ruta: real → predicho"


def load_samples(root: Path, per_type: int) -> list[Sample]:
    """Hasta `per_type` documentos de cada tipo del set sorteado, más los contratos escaneados
    del set forzado (sin texto extraíble: el caso que el experimento quiere ver)."""
    counts: Counter[TipoDocumento] = Counter()
    samples: list[Sample] = []
    for legajo_path in sorted(root.glob("[0-9]*/legajo.json")):
        legajo = json.loads(legajo_path.read_text())
        for doc in legajo["documentos"]:
            tipo = TipoDocumento(doc["tipo"])
            if counts[tipo] >= per_type:
                continue
            counts[tipo] += 1
            scanned = tipo == TipoDocumento.CONTRATO and "escaneo_torcido" in legajo["casos"]
            samples.append(Sample(legajo_path.parent / doc["pdf"], tipo, scanned))
    for pdf in sorted(root.glob("forzados/escaneo_torcido/*/contrato.pdf")):
        samples.append(Sample(pdf, TipoDocumento.CONTRATO, scanned=True))
    return samples


def load_all_samples(root: Path) -> list[Sample]:
    """Todos los documentos del set, sorteado y forzado, para los enfoques que no cuestan."""
    samples: list[Sample] = []
    for legajo_path in sorted(root.rglob("legajo.json")):
        legajo = json.loads(legajo_path.read_text())
        escaneado = "escaneo_torcido" in legajo["casos"]
        for doc in legajo["documentos"]:
            tipo = TipoDocumento(doc["tipo"])
            scanned = tipo == TipoDocumento.CONTRATO and escaneado
            samples.append(Sample(legajo_path.parent / doc["pdf"], tipo, scanned))
    return samples


def estimate_usd(client: anthropic.Anthropic, samples: list[Sample], model: str) -> Decimal:
    """Costo estimado de correr todos los modos, con `count_tokens` (gratis)."""
    total = Decimal(0)
    for sample in samples:
        pdf_bytes = sample.pdf.read_bytes()
        for mode in MODES:
            count = client.messages.count_tokens(
                model=model,
                system=SYSTEM_ZERO_SHOT,
                messages=[{"role": "user", "content": build_content(pdf_bytes, mode)}],
            )
            total += cost_usd(PRICES[model], count.input_tokens, ESTIMATED_OUTPUT_TOKENS)
    return total


def run(client: anthropic.Anthropic, samples: list[Sample], model: str, root: Path) -> list[Result]:
    results = []
    for sample in samples:
        pdf_bytes = sample.pdf.read_bytes()
        for mode in MODES:
            try:
                classification = classify(client, build_content(pdf_bytes, mode), model)
                predicted, usage = classification.tipo, classification.usage
            except LlmRefusal:
                # Se registra como error de clasificación; la llamada igual se cobró.
                predicted, usage = None, None
            results.append(
                Result(
                    pdf=str(sample.pdf.relative_to(root)),
                    tipo=sample.tipo,
                    scanned=sample.scanned,
                    mode=mode,
                    predicted=predicted,
                    input_tokens=usage.input_tokens if usage else 0,
                    output_tokens=usage.output_tokens if usage else 0,
                    cost_usd=usage.cost_usd if usage else Decimal(0),
                    latency_s=usage.latency_s if usage else 0.0,
                )
            )
    return results


def pick_for_strategy(
    results: list[Result], strategy: Strategy, texts_by_pdf: dict[str, list[str]]
) -> list[Result]:
    """Un resultado por documento: el del modo que la estrategia habría usado."""
    by_key = {(r.pdf, r.mode): r for r in results}
    pdfs = list(dict.fromkeys(r.pdf for r in results))
    return [by_key[(pdf, choose_mode(strategy, texts_by_pdf[pdf]))] for pdf in pdfs]


def summarize(strategy: Strategy, picked: list[Result]) -> StrategySummary:
    correct = [r for r in picked if r.predicted == r.tipo]
    scanned = [r for r in picked if r.scanned]
    return StrategySummary(
        strategy=strategy,
        n=len(picked),
        correct=len(correct),
        scanned_n=len(scanned),
        scanned_correct=sum(r.predicted == r.tipo for r in scanned),
        cost_usd=sum((r.cost_usd for r in picked), Decimal(0)),
        mean_latency_s=sum(r.latency_s for r in picked) / len(picked) if picked else 0.0,
        errors=[
            f"{r.pdf}: {r.tipo.value} → {r.predicted.value if r.predicted else '?'}"
            for r in picked
            if r.predicted != r.tipo
        ],
    )


def summarize_all(results: list[Result], root: Path) -> list[StrategySummary]:
    texts_by_pdf = {
        pdf: page_texts((root / pdf).read_bytes()) for pdf in dict.fromkeys(r.pdf for r in results)
    }
    return [
        summarize(strategy, pick_for_strategy(results, strategy, texts_by_pdf))
        for strategy in STRATEGIES
    ]
