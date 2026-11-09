"""Paso 4 de la Fase 2: los cinco enfoques sobre el mismo conjunto de evaluación.

El conjunto es el de prueba de la separación por legajo (los mismos legajos que no vieron TF-IDF
ni los embeddings) más todos los documentos sin texto, y menos los que alguno de los enfoques no
evaluó (los ejemplos del few-shot). Sin llamadas nuevas: el LLM y los vectores se leen de las
corridas guardadas en `data/experimentos/`, y las reglas se recalculan (son gratis).
"""

import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from core.models import TipoDocumento
from extractor.experiment import Sample
from extractor.inputs import has_usable_text, page_texts
from extractor.metrics import ClassMetrics, Pair, accuracy, class_metrics, macro_f1
from extractor.rules import classify_by_rules
from extractor.splits import split_by_legajo

# Nombre del enfoque → prefijo de su corrida en data/experimentos/ (None: se calcula acá).
APPROACHES: dict[str, str | None] = {
    "reglas": None,
    "tfidf": "vectores-tfidf-",
    "embeddings": "vectores-embeddings-",
    # "zero-shot-2" (la fecha) y no "zero-shot-": si no, también matchea "zero-shot-def-…".
    "zero-shot": "zero-shot-2",
    "zero-shot-def": "zero-shot-def-",
    "few-shot": "few-shot-",
}


@dataclass
class Run:
    """Lo que un enfoque predijo, con su costo y latencia, por documento (ruta relativa)."""

    name: str
    source: str  # de dónde salió: el JSON de la corrida o "calculado"
    predicted: dict[str, TipoDocumento | None]
    cost_usd: dict[str, Decimal] = field(default_factory=dict)
    latency_s: dict[str, float] = field(default_factory=dict)


@dataclass
class Row:
    name: str
    n: int
    accuracy: float
    macro_f1: float
    scanned_correct: int
    scanned_n: int
    cost_usd: Decimal
    usd_per_1000: Decimal  # costo por cada 1.000 documentos (lo que pagaría Avisa a escala)
    mean_latency_s: float
    per_class: dict[TipoDocumento, ClassMetrics]
    errors: list[str]


def latest(out_dir: Path, prefix: str) -> Path:
    """La corrida más reciente con ese prefijo (los nombres terminan en fecha y hora)."""
    runs = sorted(out_dir.glob(f"{prefix}*.json"))
    if not runs:
        raise FileNotFoundError(f"no hay corridas {prefix}*.json en {out_dir}")
    return runs[-1]


def _tipo(value: str | None) -> TipoDocumento | None:
    return TipoDocumento(value) if value is not None else None


def load_llm_run(path: Path, name: str) -> Run:
    results = json.loads(path.read_text())["outcome"]["results"]
    return Run(
        name=name,
        source=path.name,
        predicted={r["pdf"]: _tipo(r["predicted"]) for r in results},
        cost_usd={r["pdf"]: Decimal(r["cost_usd"]) for r in results},
        latency_s={r["pdf"]: r["latency_s"] for r in results},
    )


def load_vector_run(path: Path, name: str) -> Run:
    """La latencia guardada es el total de vectorizar y predecir la prueba: se reparte entre los
    documentos con texto (los que no tienen se predicen `otro` sin calcular nada)."""
    data = json.loads(path.read_text())
    results = data["results"]
    with_text = [r for r in results if r["confidence"] > 0]
    per_doc = data["predict_s"] / max(1, len(with_text))
    return Run(
        name=name,
        source=path.name,
        predicted={r["pdf"]: _tipo(r["predicted"]) for r in results},
        latency_s={r["pdf"]: per_doc if r["confidence"] > 0 else 0.0 for r in results},
    )


def rules_run(samples: list[Sample], root: Path) -> Run:
    predicted, latency = {}, {}
    for sample in samples:
        texts = page_texts(sample.pdf.read_bytes())
        start = time.perf_counter()
        tipo = classify_by_rules(texts)
        latency[str(sample.pdf.relative_to(root))] = time.perf_counter() - start
        predicted[str(sample.pdf.relative_to(root))] = tipo
    return Run(name="reglas", source="calculado", predicted=predicted, latency_s=latency)


def eval_samples(samples: list[Sample]) -> list[Sample]:
    """La prueba de la separación por legajo más los documentos sin texto: el mismo criterio que
    `run_vectors`, así que salen los mismos documentos que evaluaron TF-IDF y los embeddings."""
    usable = {s.pdf: has_usable_text(page_texts(s.pdf.read_bytes())) for s in samples}
    _, test = split_by_legajo([s for s in samples if usable[s.pdf]])
    return test + [s for s in samples if not usable[s.pdf]]


def common_pdfs(candidates: list[str], runs: list[Run]) -> list[str]:
    """Los documentos que evaluaron todos los enfoques, en el orden de `candidates`."""
    return [pdf for pdf in candidates if all(pdf in run.predicted for run in runs)]


def summarize(run: Run, pdfs: list[str], truth: dict[str, TipoDocumento], scanned: set[str]) -> Row:
    pairs: list[Pair] = [(truth[pdf], run.predicted[pdf]) for pdf in pdfs]
    cost = sum((run.cost_usd.get(pdf, Decimal(0)) for pdf in pdfs), Decimal(0))
    present = sorted({real for real, _ in pairs}, key=lambda t: t.value)
    return Row(
        name=run.name,
        n=len(pdfs),
        accuracy=accuracy(pairs),
        macro_f1=macro_f1(pairs),
        scanned_correct=sum(run.predicted[p] == truth[p] for p in pdfs if p in scanned),
        scanned_n=sum(p in scanned for p in pdfs),
        cost_usd=cost,
        usd_per_1000=cost / len(pdfs) * 1000,
        mean_latency_s=sum(run.latency_s.get(pdf, 0.0) for pdf in pdfs) / len(pdfs),
        per_class={tipo: class_metrics(pairs, tipo) for tipo in present},
        errors=[
            f"{pdf}: {truth[pdf].value} → {p.value if (p := run.predicted[pdf]) else 'None'}"
            for pdf in pdfs
            if run.predicted[pdf] != truth[pdf]
        ],
    )
