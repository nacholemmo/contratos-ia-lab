"""Paso 3 de la Fase 2: el LLM con entrada híbrida, sobre todo el set (zero-shot o few-shot,
según el `system`).

A diferencia del experimento del paso 2, hace una sola llamada por documento (el modo que elige
el híbrido) y tiene dos frenos de gasto: una estimación por muestra antes de correr y un tope que
se chequea durante la corrida. Los resultados guardan solo metadatos, nunca el contenido.
"""

from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import anthropic
from pydantic import BaseModel

from core.models import TipoDocumento
from extractor.classify import SYSTEM_ZERO_SHOT, classify
from extractor.experiment import ESTIMATED_OUTPUT_TOKENS, Result, Sample
from extractor.inputs import Mode, build_content, choose_mode, page_texts
from extractor.llm import PRICES, LlmRefusal, cost_usd

# Llamadas de `count_tokens` por grupo (tipo × modo) para estimar el costo del set.
ESTIMATE_PER_GROUP = 3


class RunOutcome(BaseModel):
    results: list[Result]
    stopped_early: bool  # True si el tope de gasto cortó la corrida antes de terminar
    spent_usd: Decimal


def hybrid_modes(samples: list[Sample]) -> dict[Path, Mode]:
    """El modo que el híbrido usaría para cada documento (local, sin llamadas)."""
    return {s.pdf: choose_mode("hybrid", page_texts(s.pdf.read_bytes())) for s in samples}


def estimate_hybrid_usd(
    client: anthropic.Anthropic,
    samples: list[Sample],
    modes: dict[Path, Mode],
    model: str,
    per_group: int = ESTIMATE_PER_GROUP,
    system: str = SYSTEM_ZERO_SHOT,
) -> Decimal:
    """Costo estimado de clasificar todo el set: `per_group` llamadas a `count_tokens` (gratis)
    por grupo tipo × modo, y el promedio del grupo por la cantidad de documentos que tiene."""
    groups: dict[tuple[TipoDocumento, Mode], list[Sample]] = defaultdict(list)
    for sample in samples:
        groups[(sample.tipo, modes[sample.pdf])].append(sample)

    total = Decimal(0)
    for (_, mode), members in groups.items():
        # Muestras espaciadas a lo largo del grupo, no las primeras (que son semillas vecinas).
        step = max(1, len(members) // per_group)
        chosen = members[::step][:per_group]
        costs = []
        for sample in chosen:
            content = build_content(sample.pdf.read_bytes(), mode)
            count = client.messages.count_tokens(
                model=model,
                system=system,
                messages=[{"role": "user", "content": content}],
            )
            costs.append(cost_usd(PRICES[model], count.input_tokens, ESTIMATED_OUTPUT_TOKENS))
        total += sum(costs, Decimal(0)) / len(costs) * len(members)
    return total


def classify_sample(
    client: anthropic.Anthropic,
    sample: Sample,
    mode: Mode,
    model: str,
    root: Path,
    system: str = SYSTEM_ZERO_SHOT,
) -> Result:
    """Una llamada para un documento. Una negativa del modelo cuenta como error (y se cobra,
    pero sin `usage` no se sabe cuánto: queda en 0)."""
    try:
        classification = classify(
            client, build_content(sample.pdf.read_bytes(), mode), model, system
        )
        predicted, usage = classification.tipo, classification.usage
    except LlmRefusal:
        predicted, usage = None, None
    return Result(
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


def run_hybrid(
    client: anthropic.Anthropic,
    samples: list[Sample],
    modes: dict[Path, Mode],
    model: str,
    root: Path,
    max_usd: Decimal,
    system: str = SYSTEM_ZERO_SHOT,
) -> RunOutcome:
    """Clasifica cada documento en el modo del híbrido, sin pasarse de `max_usd`."""
    results: list[Result] = []
    spent = Decimal(0)
    for sample in samples:
        # Freno con el gasto real, chequeado después de cada llamada: se puede pasar del tope
        # como mucho por una llamada (centésimos de centavo), sin estimar la próxima.
        result = classify_sample(client, sample, modes[sample.pdf], model, root, system)
        results.append(result)
        spent += result.cost_usd
        if spent > max_usd:
            return RunOutcome(results=results, stopped_early=True, spent_usd=spent)

    return RunOutcome(results=results, stopped_early=False, spent_usd=spent)
