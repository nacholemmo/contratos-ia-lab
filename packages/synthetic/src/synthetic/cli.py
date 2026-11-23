"""CLI del generador: escribe N legajos sintéticos con su ground truth.

Dos modos:
- `contratos` (Fase 1, por defecto): el contrato y cada documento en PDF + JSON.
  uv run --package synthetic generate --n 50 --seed 42 --out data/synthetic/
- `fotografiado` (Fase 3): el legajo como fotos de celular desordenadas, con su
  `LegajoEsperado` (ver `export_fotografiado.py`).
  uv run --package synthetic generate --modo fotografiado --etapa evaluacion --n 50

Además del set sorteado, cada modo escribe un set forzado: `--por-caso` contratos de cada
caso difícil, o `--por-inconsistencia` legajos de cada inconsistencia. 0 lo desactiva.
"""

import argparse
from pathlib import Path

from core.legajo import Etapa
from synthetic.export import write_forzados, write_legajo, write_manifest
from synthetic.export_fotografiado import (
    write_forzados_fotografiado,
    write_legajo_fotografiado,
    write_manifest_fotografiado,
)
from synthetic.foto import Nivel

SALIDA = {"contratos": Path("data/synthetic"), "fotografiado": Path("data/synthetic/fotografiado")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate",
        description="Contratos de locación sintéticos con su legajo (PDF + JSON de ground truth).",
    )
    parser.add_argument("--n", type=int, default=50, help="cantidad de contratos (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="semilla inicial (default: 42)")
    parser.add_argument(
        "--modo",
        choices=list(SALIDA),
        default="contratos",
        help="contratos (PDF + JSON) o fotografiado (fotos + LegajoEsperado)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="carpeta de salida (default: data/synthetic o data/synthetic/fotografiado)",
    )
    parser.add_argument(
        "--etapa",
        choices=[e.value for e in Etapa],
        default=Etapa.EVALUACION.value,
        help="solo fotografiado: evaluacion (sin contrato) o cierre",
    )
    parser.add_argument(
        "--nivel",
        choices=[n.value for n in Nivel if n != Nivel.ILEGIBLE],
        default=Nivel.LEVE.value,
        help="solo fotografiado: qué tan malas son las fotos (default: leve)",
    )
    parser.add_argument(
        "--por-inconsistencia",
        type=int,
        default=3,
        help="solo fotografiado: legajos del set forzado por inconsistencia (default: 3)",
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
    if args.por_inconsistencia < 0:
        parser.error("--por-inconsistencia no puede ser negativo")
    args.out = args.out or SALIDA[args.modo]
    args.out.mkdir(parents=True, exist_ok=True)
    if args.modo == "fotografiado":
        return fotografiado(args)

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


def fotografiado(args: argparse.Namespace) -> int:
    """Modo fotografiado: set sorteado, set forzado por inconsistencia y manifest."""
    etapa, nivel = Etapa(args.etapa), Nivel(args.nivel)
    indices = []
    for i, seed in enumerate(range(args.seed, args.seed + args.n), start=1):
        indice = write_legajo_fotografiado(seed, args.out, etapa, nivel)
        inconsistencias = ", ".join(indice.inconsistencias) or "cierra"
        print(f"[{i}/{args.n}] semilla {seed}: {indice.fotos} fotos ({inconsistencias})")
        indices.append(indice)

    # Las forzadas arrancan después del rango sorteado: ningún legajo está en los dos sets.
    forzados = {}
    if args.por_inconsistencia:
        print(f"\nSet forzado: {args.por_inconsistencia} por inconsistencia...")
        desde = args.seed + args.n
        forzados = write_forzados_fotografiado(
            args.out, desde, args.por_inconsistencia, etapa, nivel
        )

    m = write_manifest_fotografiado(args.out, args.seed, indices, forzados)
    print(f"\nListo: {m.n} legajos en {args.out} ({m.legajos_sin_inconsistencias} cierran).")
    print(f"  {'inconsistencia':<32} {'sorteado':>8} {'forzado':>8}")
    for inconsistencia, cantidad in m.legajos_por_inconsistencia.items():
        print(f"  {inconsistencia:<32} {cantidad:>8} {len(forzados.get(inconsistencia, [])):>8}")
    descartes = ", ".join(f"{motivo}: {n}" for motivo, n in m.fotos_descartadas.items())
    print(f"  {m.fotos} fotos; descartadas: {descartes}")
    return 0
