"""CLI del extractor.

- `llm-ping`: una llamada de prueba al LLM para ver tokens, costo y latencia.
- `experimento-entrada`: paso 2 de la Fase 2, texto vs. imagen vs. híbrido. Sin `--run` solo
  estima el costo (con `count_tokens`, gratis).
- `clasificar-reglas`: paso 3 de la Fase 2, el enfoque por reglas sobre todo el set (gratis).
- `clasificar-zero-shot`: paso 3 de la Fase 2, el LLM zero-shot híbrido sobre todo el set. Sin
  `--run` solo estima el costo (con una muestra de `count_tokens`, gratis).
- `clasificar-zero-shot-def`: paso 4 de la Fase 2, el zero-shot con otra definición de
  `garantia` (lo único que cambia). Sin `--run` solo estima.
- `clasificar-few-shot`: paso 3 de la Fase 2, el mismo LLM con ejemplos resueltos en el prompt.
  Los ejemplos salen del set y no se evalúan. Sin `--run` solo estima.
- `clasificar-vectores`: paso 3 de la Fase 2, TF-IDF y embeddings locales + regresión logística,
  con separación por legajo. Gratis; necesita el extra `ml` (`uv sync --extra ml`).
- `comparar-clasificadores`: paso 4 de la Fase 2, los 5 enfoques sobre el mismo conjunto de
  prueba, con F1 por clase y matriz de confusión. Lee las corridas guardadas: no gasta.

Uso (desde la raíz):
  uv run --package extractor llm-ping
  uv run --package extractor experimento-entrada            # solo estima
  uv run --package extractor experimento-entrada --run      # corre si no supera --max-usd
  uv run --package extractor clasificar-reglas
  uv run --package extractor clasificar-zero-shot           # solo estima
  uv run --package extractor clasificar-zero-shot --run     # corre si no supera --max-usd
  uv run --package extractor clasificar-zero-shot-def --run # corre si no supera --max-usd
  uv run --package extractor clasificar-few-shot            # solo estima
  uv run --package extractor clasificar-few-shot --run      # corre si no supera --max-usd
  uv run --package extractor clasificar-vectores            # tfidf y embeddings
  uv run --package extractor comparar-clasificadores        # --detalle few-shot, tfidf, …
"""

import argparse
import json
import logging
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from core.models import TipoDocumento
from extractor.benchmark import estimate_hybrid_usd, hybrid_modes, run_hybrid
from extractor.classify import GARANTIA_V2, SYSTEM_ZERO_SHOT, SYSTEM_ZERO_SHOT_DEF
from extractor.compare import (
    APPROACHES,
    common_pdfs,
    eval_samples,
    latest,
    load_llm_run,
    load_vector_run,
    rules_run,
)
from extractor.compare import summarize as summarize_run
from extractor.experiment import (
    Sample,
    estimate_usd,
    load_all_samples,
    load_samples,
    run,
    summarize,
    summarize_all,
)
from extractor.fewshot import build_system_few_shot, select_examples, without_examples
from extractor.inputs import page_texts
from extractor.llm import call_llm
from extractor.metrics import confusion_matrix
from extractor.rules import classify_by_rules
from extractor.settings import Settings, make_client


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="llm-ping", description="Llamada mínima al LLM (cuesta menos de USD 0,001)."
    )
    parser.add_argument("--model", help="modelo (default: el de la configuración)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    response = call_llm(
        make_client(settings),
        system="Respondé solo con la palabra OK.",
        content="ping",
        model=args.model or settings.llm_model,
    )
    print(f"respuesta: {response.text!r}")
    print(response.usage.model_dump_json(indent=2))
    return 0


def experimento_entrada(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="experimento-entrada",
        description="Clasifica un subset en modo texto e imagen y compara con el híbrido.",
    )
    parser.add_argument("--data", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--per-type", type=int, default=2, help="documentos por tipo")
    parser.add_argument("--run", action="store_true", help="hacer las llamadas (gasta saldo)")
    parser.add_argument("--max-usd", type=Decimal, default=Decimal("0.05"), help="tope de gasto")
    parser.add_argument("--out", type=Path, default=Path("data/experimentos"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    client = make_client(settings)
    model = settings.llm_model

    samples = load_samples(args.data, args.per_type)
    scanned = sum(s.scanned for s in samples)
    estimate = estimate_usd(client, samples, model)
    print(f"{len(samples)} documentos ({scanned} escaneados) × 2 modos con {model}")
    print(f"costo estimado: USD {estimate:.6f} (tope: USD {args.max_usd})")
    if not args.run:
        print("solo estimación: agregá --run para hacer las llamadas")
        return 0
    if estimate > args.max_usd:
        print("la estimación supera el tope: no se corre")
        return 1

    results = run(client, samples, model, args.data)
    summaries = summarize_all(results, args.data)

    print(f"\n{'estrategia':<10} {'aciertos':>9} {'escaneos':>9} {'USD':>10} {'latencia':>9}")
    for s in summaries:
        print(
            f"{s.strategy:<10} {s.correct:>4}/{s.n:<4} {s.scanned_correct:>4}/{s.scanned_n:<4}"
            f" {s.cost_usd:>10.6f} {s.mean_latency_s:>8.2f}s"
        )
    for s in summaries:
        for error in s.errors:
            print(f"  [{s.strategy}] {error}")

    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"entrada-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(
        json.dumps(
            {
                "model": model,
                "results": [r.model_dump(mode="json") for r in results],
                "summaries": [s.model_dump(mode="json") for s in summaries],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nresultados (solo metadatos): {out}")
    return 0


def print_hits(pairs: list[tuple[TipoDocumento, TipoDocumento | None]]) -> None:
    """Tabla de aciertos por tipo real, a partir de pares (real, predicho)."""
    totals = Counter(real for real, _ in pairs)
    hits = Counter(real for real, predicted in pairs if predicted == real)
    print(f"{'tipo':<14} {'aciertos':>12}")
    for tipo in TipoDocumento:
        if totals[tipo]:
            print(f"{tipo.value:<14} {hits[tipo]:>5}/{totals[tipo]:<6}")
    total_hits, total = sum(hits.values()), sum(totals.values())
    print(f"{'total':<14} {total_hits:>5}/{total:<6} ({total_hits / total:.1%})")


def clasificar_reglas(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clasificar-reglas",
        description="Clasifica todo el set con reglas (sin LLM, gratis) y muestra los errores.",
    )
    parser.add_argument("--data", type=Path, default=Path("data/synthetic"))
    args = parser.parse_args(argv)

    samples = load_all_samples(args.data)
    pairs: list[tuple[TipoDocumento, TipoDocumento | None]] = []
    errors: list[str] = []
    for sample in samples:
        predicted = classify_by_rules(page_texts(sample.pdf.read_bytes()))
        pairs.append((sample.tipo, predicted))
        if predicted != sample.tipo:
            pdf = sample.pdf.relative_to(args.data)
            errors.append(f"{pdf}: {sample.tipo.value} → {predicted.value}")

    print_hits(pairs)
    print(f"\n{len(errors)} errores")
    for error in errors:
        print(f"  {error}")
    return 0


def run_llm_classifier(
    argv: list[str] | None,
    prog: str,
    description: str,
    prepare: Callable[[list[Sample]], tuple[str, list[Sample], dict[str, Any]]],
) -> int:
    """Lo común a los enfoques con LLM: estimar, frenar por tope, correr, mostrar y guardar.

    `prepare` recibe todo el set y devuelve el system, los documentos a evaluar y metadatos
    extra para el JSON de resultados (por ejemplo, qué documentos fueron ejemplos).
    """
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("--data", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--run", action="store_true", help="hacer las llamadas (gasta saldo)")
    parser.add_argument("--max-usd", type=Decimal, default=Decimal("0.30"), help="tope de gasto")
    parser.add_argument("--out", type=Path, default=Path("data/experimentos"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    client = make_client(settings)
    model = settings.llm_model

    system, samples, extra = prepare(load_all_samples(args.data))
    modes = hybrid_modes(samples)
    images = sum(mode == "image" for mode in modes.values())
    estimate = estimate_hybrid_usd(client, samples, modes, model, system=system)
    print(f"{len(samples)} documentos ({images} por imagen) con {model}")
    print(f"costo estimado: USD {estimate:.6f} (tope: USD {args.max_usd})")
    if not args.run:
        print("solo estimación: agregá --run para hacer las llamadas")
        return 0
    if estimate > args.max_usd:
        print("la estimación supera el tope: no se corre")
        return 1

    outcome = run_hybrid(client, samples, modes, model, args.data, args.max_usd, system=system)

    # Se guarda apenas terminan las llamadas: si algo falla después, lo pagado no se pierde.
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"{prog.removeprefix('clasificar-')}-{datetime.now():%Y%m%d-%H%M%S}.json"
    record = {
        "model": model,
        "estimate_usd": str(estimate),
        **extra,
        "outcome": outcome.model_dump(mode="json"),
    }
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False))

    summary = summarize("hybrid", outcome.results)

    print_hits([(r.tipo, r.predicted) for r in outcome.results])
    print(
        f"escaneos {summary.scanned_correct}/{summary.scanned_n} · USD {outcome.spent_usd:.6f}"
        f" · latencia media {summary.mean_latency_s:.2f}s"
    )
    if outcome.stopped_early:
        print(f"CORTADO por el tope: {len(outcome.results)} de {len(samples)} documentos")
    print(f"\n{len(summary.errors)} errores")
    for error in summary.errors:
        print(f"  {error}")

    record["summary"] = summary.model_dump(mode="json")
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    print(f"\nresultados (solo metadatos): {out}")
    return 0


def clasificar_zero_shot(argv: list[str] | None = None) -> int:
    return run_llm_classifier(
        argv,
        prog="clasificar-zero-shot",
        description="Clasifica todo el set con el LLM zero-shot y entrada híbrida.",
        prepare=lambda samples: (SYSTEM_ZERO_SHOT, samples, {}),
    )


def clasificar_zero_shot_def(argv: list[str] | None = None) -> int:
    return run_llm_classifier(
        argv,
        prog="clasificar-zero-shot-def",
        description="El zero-shot con la definición de garantía del experimento del paso 4.",
        prepare=lambda samples: (SYSTEM_ZERO_SHOT_DEF, samples, {"garantia": GARANTIA_V2}),
    )


def prepare_few_shot(root_samples: list[Sample]) -> tuple[str, list[Sample], dict[str, Any]]:
    examples = select_examples(root_samples)
    print(f"{len(examples)} ejemplos (fuera de la evaluación):")
    for example in examples:
        print(f"  {example.tipo.value:<14} {example.pdf.parent.name}/{example.pdf.name}")
    extra = {"examples": [f"{e.pdf.parent.name}/{e.pdf.name}" for e in examples]}
    return build_system_few_shot(examples), without_examples(root_samples, examples), extra


def clasificar_few_shot(argv: list[str] | None = None) -> int:
    return run_llm_classifier(
        argv,
        prog="clasificar-few-shot",
        description="Clasifica el set (menos los ejemplos) con el LLM few-shot y entrada híbrida.",
        prepare=prepare_few_shot,
    )


def clasificar_vectores(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clasificar-vectores",
        description="TF-IDF y/o embeddings + regresión logística (local, gratis, extra `ml`).",
    )
    parser.add_argument("--data", type=Path, default=Path("data/synthetic"))
    parser.add_argument(
        "--metodo", choices=["tfidf", "embeddings", "ambos"], default="ambos", help="vectorizador"
    )
    parser.add_argument("--out", type=Path, default=Path("data/experimentos"))
    args = parser.parse_args(argv)

    from extractor.vectors import run_vectors  # necesita el extra `ml`

    samples = load_all_samples(args.data)
    methods = ["tfidf", "embeddings"] if args.metodo == "ambos" else [args.metodo]
    args.out.mkdir(parents=True, exist_ok=True)
    for method in methods:
        outcome = run_vectors(samples, method, args.data)
        results = outcome.results
        scanned = [r for r in results if r.scanned]
        print(
            f"\n=== {method}: entrenado con {outcome.n_train} documentos, "
            f"{len(outcome.train_legajos)} legajos; evaluado con {len(results)} ==="
        )
        print_hits([(r.tipo, r.predicted) for r in results])
        print(
            f"escaneos {sum(r.predicted == r.tipo for r in scanned)}/{len(scanned)}"
            f" · entrenar {outcome.fit_s:.2f}s"
            f" · predecir {outcome.predict_s / max(1, len(results)) * 1000:.1f} ms/doc"
        )
        errors = [r for r in results if r.predicted != r.tipo]
        print(f"{len(errors)} errores")
        for r in errors:
            print(f"  {r.pdf}: {r.tipo.value} → {r.predicted.value} (p={r.confidence:.2f})")

        out = args.out / f"vectores-{method}-{datetime.now():%Y%m%d-%H%M%S}.json"
        out.write_text(outcome.model_dump_json(indent=2))
        print(f"resultados (solo metadatos): {out}")
    return 0


def print_confusion(pairs: list[tuple[TipoDocumento, TipoDocumento | None]]) -> None:
    """Filas: clase real. Columnas: lo que predijo. La diagonal son los aciertos."""
    matrix = confusion_matrix(pairs)
    cols: list[TipoDocumento | None] = list(TipoDocumento)
    if any(predicted is None for _, predicted in pairs):
        cols.append(None)
    short = {t: t.value[:7] for t in TipoDocumento}
    print(f"{'real → pred':<14}" + "".join(f"{short.get(c, 'None'):>9}" for c in cols))
    for real in TipoDocumento:
        if not any(r == real for r, _ in pairs):
            continue
        print(f"{real.value:<14}" + "".join(f"{matrix[(real, c)] or '.':>9}" for c in cols))


def comparar_clasificadores(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="comparar-clasificadores",
        description="Los 5 enfoques sobre el mismo conjunto de prueba (sin llamadas nuevas).",
    )
    parser.add_argument("--data", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--runs", type=Path, default=Path("data/experimentos"))
    parser.add_argument(
        "--detalle", choices=list(APPROACHES), default="zero-shot", help="matriz de confusión"
    )
    args = parser.parse_args(argv)

    samples = load_all_samples(args.data)
    runs = [rules_run(samples, args.data)]
    for name, prefix in APPROACHES.items():
        if prefix is None:
            continue
        try:
            path = latest(args.runs, prefix)
        except FileNotFoundError:
            print(f"(sin corrida de {name}: queda afuera)")
            continue
        loader = load_vector_run if prefix.startswith("vectores-") else load_llm_run
        runs.append(loader(path, name))

    evaluated = eval_samples(samples)
    rel = {s.pdf: str(s.pdf.relative_to(args.data)) for s in evaluated}
    pdfs = common_pdfs([rel[s.pdf] for s in evaluated], runs)
    truth = {rel[s.pdf]: s.tipo for s in evaluated}
    scanned = {rel[s.pdf] for s in evaluated if s.scanned}
    rows = [summarize_run(run, pdfs, truth, scanned) for run in runs]

    print(
        f"{len(pdfs)} documentos comunes ({len(evaluated)} en la prueba, {len(scanned)} escaneos)"
    )
    for loaded in runs:
        print(f"  {loaded.name:<11} ← {loaded.source}")
    print(
        f"\n{'enfoque':<11} {'accuracy':>9} {'F1 macro':>9} {'escaneos':>9}"
        f" {'USD/1000':>9} {'latencia':>10}"
    )
    for r in rows:
        print(
            f"{r.name:<11} {r.accuracy:>9.1%} {r.macro_f1:>9.3f}"
            f" {r.scanned_correct:>4}/{r.scanned_n:<4}"
            f" {r.usd_per_1000:>9.4f} {r.mean_latency_s * 1000:>8.1f}ms"
        )

    present = list(rows[0].per_class)
    print(f"\nF1 por clase\n{'enfoque':<11}" + "".join(f"{t.value[:12]:>14}" for t in present))
    for r in rows:
        print(f"{r.name:<11}" + "".join(f"{r.per_class[t].f1:>14.3f}" for t in present))

    detail = next(r for r in rows if r.name == args.detalle)
    run = next(r for r in runs if r.name == args.detalle)
    print(f"\nMatriz de confusión: {detail.name}")
    print_confusion([(truth[p], run.predicted[p]) for p in pdfs])
    print(f"\nPrecisión y recall: {detail.name}")
    for tipo, m in detail.per_class.items():
        print(
            f"  {tipo.value:<14} P={m.precision:.3f} R={m.recall:.3f} F1={m.f1:.3f} (n={m.support})"
        )
    print(f"\n{len(detail.errors)} errores de {detail.name}")
    for error in detail.errors:
        print(f"  {error}")

    out = args.runs / f"comparacion-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(
        json.dumps(
            {
                "documentos": pdfs,
                "fuentes": {run.name: run.source for run in runs},
                "filas": [
                    {
                        "enfoque": r.name,
                        "n": r.n,
                        "accuracy": r.accuracy,
                        "macro_f1": r.macro_f1,
                        "escaneos": f"{r.scanned_correct}/{r.scanned_n}",
                        "usd": str(r.cost_usd),
                        "usd_por_1000": str(r.usd_per_1000),
                        "latencia_media_s": r.mean_latency_s,
                        "f1_por_clase": {t.value: m.f1 for t, m in r.per_class.items()},
                        "errores": r.errors,
                    }
                    for r in rows
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nresultados (solo metadatos): {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
