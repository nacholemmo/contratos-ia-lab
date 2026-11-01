"""CLI del extractor.

- `llm-ping`: una llamada de prueba al LLM para ver tokens, costo y latencia.
- `experimento-entrada`: paso 2 de la Fase 2, texto vs. imagen vs. híbrido. Sin `--run` solo
  estima el costo (con `count_tokens`, gratis).
- `clasificar-reglas`: paso 3 de la Fase 2, el enfoque por reglas sobre todo el set (gratis).

Uso (desde la raíz):
  uv run --package extractor llm-ping
  uv run --package extractor experimento-entrada            # solo estima
  uv run --package extractor experimento-entrada --run      # corre si no supera --max-usd
  uv run --package extractor clasificar-reglas
"""

import argparse
import json
import logging
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from core.models import TipoDocumento
from extractor.experiment import (
    estimate_usd,
    load_all_samples,
    load_samples,
    run,
    summarize_all,
)
from extractor.inputs import page_texts
from extractor.llm import call_llm
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


def clasificar_reglas(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clasificar-reglas",
        description="Clasifica todo el set con reglas (sin LLM, gratis) y muestra los errores.",
    )
    parser.add_argument("--data", type=Path, default=Path("data/synthetic"))
    args = parser.parse_args(argv)

    samples = load_all_samples(args.data)
    totals: Counter[TipoDocumento] = Counter()
    hits: Counter[TipoDocumento] = Counter()
    errors: list[str] = []
    for sample in samples:
        predicted = classify_by_rules(page_texts(sample.pdf.read_bytes()))
        totals[sample.tipo] += 1
        if predicted == sample.tipo:
            hits[sample.tipo] += 1
        else:
            pdf = sample.pdf.relative_to(args.data)
            errors.append(f"{pdf}: {sample.tipo.value} → {predicted.value}")

    print(f"{'tipo':<14} {'aciertos':>12}")
    for tipo in TipoDocumento:
        if totals[tipo]:
            print(f"{tipo.value:<14} {hits[tipo]:>5}/{totals[tipo]:<6}")
    total_hits, total = sum(hits.values()), sum(totals.values())
    print(f"{'total':<14} {total_hits:>5}/{total:<6} ({total_hits / total:.1%})")
    print(f"\n{len(errors)} errores")
    for error in errors:
        print(f"  {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
