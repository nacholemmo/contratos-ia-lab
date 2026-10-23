"""Genera contratos de muestra en data/: PDF + ground truth JSON, y un resumen por consola.

Herramienta de desarrollo para mirar el generador a ojo. La reemplaza la CLI de la
Fase 1, paso 6 (`generate --n 50 --seed 42 --out ...`).

Uso (desde la raíz): uv run python scripts/muestra.py 7 12 42
"""

import sys
from pathlib import Path

from synthetic import generate_contract

out = Path("data/muestras")
out.mkdir(parents=True, exist_ok=True)

for seed in [int(s) for s in sys.argv[1:]] or [7]:
    pdf, contrato = generate_contract(seed)
    (out / f"contrato_{seed}.pdf").write_bytes(pdf)
    (out / f"contrato_{seed}.json").write_text(contrato.model_dump_json(indent=2))

    c, p = contrato, contrato.propiedad
    frecuencia = f" cada {c.frecuencia_ajuste_meses} meses" if c.frecuencia_ajuste_meses else ""
    print(f"--- semilla {seed} → {out}/contrato_{seed}.pdf")
    print(f"  {p.localidad}, {p.provincia} · {c.regimen_legal} · firma {c.fecha_firma}")
    print(f"  {c.moneda} {c.monto_inicial} · {c.indice}{frecuencia}")
    evidencias = {
        nombre.removesuffix("_evidencia"): ev
        for nombre, ev in contrato
        if nombre.endswith("_evidencia") and ev is not None
    }
    for campo, ev in evidencias.items():
        print(f"  pág. {ev.pagina}  {campo:<24} «{ev.texto[:60]}»")
