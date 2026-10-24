"""CLI del generador: escribe N contratos sintéticos con su legajo y su ground truth.

Uso (desde la raíz): uv run --package synthetic generate --n 50 --seed 42 --out data/synthetic/

Además del set sorteado, escribe un set forzado con `--por-caso` contratos de cada caso
difícil (ver `export.py`). `--por-caso 0` lo desactiva.
"""

import argparse
from pathlib import Path

from synthetic.export import write_forzados, write_legajo, write_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate",
        description="Contratos de locación sintéticos con su legajo (PDF + JSON de ground truth).",
    )
    parser.add_argument("--n", type=int, default=50, help="cantidad de contratos (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="semilla inicial (default: 42)")
    parser.add_argument(
        "--out", type=Path, default=Path("data/synthetic"), help="carpeta de salida"
    )
    parser.add_argument(
        "--por-caso",
        type=int,
        default=3,
        help="contratos del set forzado por cada caso difícil; 0 lo desactiva (default: 3)",
    )
    args = parser.parse_args(argv)
    if args.n < 1:
        parser.error("--n tiene que ser 1 o más")
    if args.por_caso < 0:
        parser.error("--por-caso no puede ser negativo")

    args.out.mkdir(parents=True, exist_ok=True)
    indices = []
    for i, seed in enumerate(range(args.seed, args.seed + args.n), start=1):
        indice = write_legajo(seed, args.out)
        casos = ", ".join(indice.casos) or "limpio"
        print(f"[{i}/{args.n}] semilla {seed}: {len(indice.documentos)} documentos ({casos})")
        indices.append(indice)

    # Las forzadas arrancan después del rango sorteado: ningún contrato está en los dos sets.
    forzados = {}
    if args.por_caso:
        print(f"\nSet forzado: {args.por_caso} por caso...")
        forzados = write_forzados(args.out, args.seed + args.n, args.por_caso)

    manifest = write_manifest(args.out, args.seed, indices, forzados)
    print(f"\nListo: {manifest.n} contratos en {args.out} ({manifest.contratos_limpios} limpios).")
    print(f"  {'caso':<24} {'sorteado':>8} {'forzado':>8}")
    for caso, cantidad in manifest.contratos_por_caso.items():
        print(f"  {caso:<24} {cantidad:>8} {len(forzados.get(caso, [])):>8}")
    return 0
