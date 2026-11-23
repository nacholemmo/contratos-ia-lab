"""Escribe en disco el legajo fotografiado de cada semilla: fotos, ground truth e índice.

Es lo que leen las evals de la Fase 6: las fotos son la entrada del servicio y
`esperado.json` es la respuesta correcta. Una carpeta por semilla:

    <seed>/
    ├── fotos/IMG_5007.jpg …   lo que recibe el servicio (desordenado, nombres sin pistas)
    ├── datos/dni_inquilino_1.json …   ground truth de los campos de cada documento
    ├── esperado.json          LegajoEsperado: agrupación, asignación, descartes, alertas
    └── legajo.json            índice: casos, inconsistencias y con qué modelo valida cada JSON

Dos sets, como en `export.py`:
- **sorteado** (`<seed>/`): cada semilla sortea sus casos y sus inconsistencias; mide un
  día normal (la mayoría de los legajos cierra);
- **forzado** (`forzados/<inconsistencia>/<seed>/`): N legajos por inconsistencia, con esa
  sola y sin casos difíciles (salvo los que necesita, como la caución), para atribuirle
  cada alerta perdida a una inconsistencia.
"""

from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from core.legajo import Etapa, LegajoEsperado, MotivoDescarte
from synthetic.cases import CasoDificil
from synthetic.desorden import DESORDEN_HABITUAL, Desorden, desordenar
from synthetic.export import MODELOS, NombreModelo
from synthetic.foto import Nivel
from synthetic.fotografiado import generate_legajo
from synthetic.inconsistencias import (
    CASOS_NECESARIOS,
    Inconsistencia,
    elegir_inconsistencias,
    semillas_forzadas,
)
from synthetic.legajo import contexto_legajo

CARPETA_FOTOS = "fotos"
CARPETA_DATOS = "datos"


class IndiceFotografiado(BaseModel):
    """Qué es cada archivo de la carpeta de una semilla (lo que no dice `LegajoEsperado`)."""

    seed: int
    sintetico: Literal[True] = True
    etapa: Etapa
    nivel: Nivel
    casos: list[CasoDificil]
    inconsistencias: list[Inconsistencia] = Field(
        ..., description="Inyectadas; cada una tiene su alerta o su faltante en esperado.json"
    )
    fotos: int = Field(..., description="Cantidad de fotos en fotos/")
    modelos: dict[str, NombreModelo] = Field(
        ..., description="JSON de datos/ → modelo de core con el que valida"
    )


class ManifestFotografiado(BaseModel):
    """Resumen del set: si cada inconsistencia y cada descarte está representado."""

    seed_inicial: int
    n: int
    sintetico: Literal[True] = True
    etapa: Etapa
    nivel: Nivel
    semillas: list[int]
    legajos_por_inconsistencia: dict[Inconsistencia, int]
    legajos_sin_inconsistencias: int
    legajos_por_caso: dict[CasoDificil, int]
    fotos: int
    fotos_descartadas: dict[MotivoDescarte, int]
    forzados: dict[Inconsistencia, list[int]] = Field(
        default_factory=dict, description="Semillas del set forzado de cada inconsistencia"
    )


def carpeta_semilla(out: Path, seed: int) -> Path:
    return out / f"{seed:04d}"


def carpeta_forzado(out: Path, inconsistencia: Inconsistencia) -> Path:
    return out / "forzados" / inconsistencia


def write_legajo_fotografiado(
    seed: int,
    out: Path,
    etapa: Etapa = Etapa.EVALUACION,
    nivel: Nivel = Nivel.LEVE,
    casos: list[CasoDificil] | None = None,
    inconsistencias: list[Inconsistencia] | None = None,
    desorden: Desorden = DESORDEN_HABITUAL,
) -> IndiceFotografiado:
    """Genera, desordena y escribe el legajo de la semilla en `out/<seed>/`.

    `casos` y `inconsistencias` en None: la semilla sortea los suyos (set sorteado). Con una
    lista (aunque sea vacía), se fuerzan.
    """
    if inconsistencias is None:
        inconsistencias = elegir_inconsistencias(contexto_legajo(seed, casos))
    legajo = generate_legajo(seed, etapa, nivel, casos, inconsistencias)
    legajo = desordenar(legajo, desorden, nivel)

    carpeta = carpeta_semilla(out, seed)
    fotos, datos = carpeta / CARPETA_FOTOS, carpeta / CARPETA_DATOS
    fotos.mkdir(parents=True, exist_ok=True)
    datos.mkdir(parents=True, exist_ok=True)
    for archivo, jpg in legajo.fotos.items():
        (fotos / archivo).write_bytes(jpg)
    for archivo, modelo in legajo.datos.items():
        (datos / archivo).write_text(modelo.model_dump_json(indent=2), encoding="utf-8")
    esperado = legajo.esperado.model_dump_json(indent=2)
    (carpeta / "esperado.json").write_text(esperado, encoding="utf-8")

    indice = IndiceFotografiado(
        seed=seed,
        etapa=etapa,
        nivel=nivel,
        casos=contexto_legajo(seed, casos).casos,
        inconsistencias=legajo.inconsistencias,
        fotos=len(legajo.fotos),
        modelos={archivo: type(m).__name__ for archivo, m in legajo.datos.items()},
    )
    (carpeta / "legajo.json").write_text(indice.model_dump_json(indent=2), encoding="utf-8")
    return indice


def write_forzados_fotografiado(
    out: Path,
    desde: int,
    por_inconsistencia: int,
    etapa: Etapa = Etapa.EVALUACION,
    nivel: Nivel = Nivel.LEVE,
    inconsistencias: list[Inconsistencia] | None = None,
) -> dict[Inconsistencia, list[int]]:
    """Set forzado: `por_inconsistencia` legajos con cada inconsistencia sola, desde `desde`.

    Sin casos difíciles, salvo los que la inconsistencia necesita: así una alerta perdida se
    le atribuye a la inconsistencia y no a un documento difícil de leer.
    """
    forzados: dict[Inconsistencia, list[int]] = {}
    for inconsistencia in inconsistencias or list(Inconsistencia):
        casos = CASOS_NECESARIOS.get(inconsistencia, [])
        semillas = semillas_forzadas(inconsistencia, desde, por_inconsistencia)
        for seed in semillas:
            carpeta = carpeta_forzado(out, inconsistencia)
            write_legajo_fotografiado(seed, carpeta, etapa, nivel, casos, [inconsistencia])
        forzados[inconsistencia] = semillas
    return forzados


def leer_esperado(carpeta: Path) -> LegajoEsperado:
    """El ground truth de la carpeta de una semilla, validado (lo que van a usar las evals)."""
    return LegajoEsperado.model_validate_json((carpeta / "esperado.json").read_text())


def validar_datos(carpeta: Path) -> None:
    """Valida cada JSON de datos/ contra su modelo de core; falla con el primero que no."""
    indice = IndiceFotografiado.model_validate_json((carpeta / "legajo.json").read_text())
    for archivo, modelo in indice.modelos.items():
        MODELOS[modelo].model_validate_json((carpeta / CARPETA_DATOS / archivo).read_text())


def write_manifest_fotografiado(
    out: Path,
    seed_inicial: int,
    indices: list[IndiceFotografiado],
    forzados: dict[Inconsistencia, list[int]] | None = None,
) -> ManifestFotografiado:
    """Escribe `out/manifest.json` con el resumen del set (sorteado y forzado)."""
    por_inconsistencia = Counter(i for indice in indices for i in indice.inconsistencias)
    por_caso = Counter(c for indice in indices for c in indice.casos)
    descartes: Counter[MotivoDescarte] = Counter()
    for indice in indices:
        for foto in leer_esperado(carpeta_semilla(out, indice.seed)).fotos:
            if foto.descarte is not None:
                descartes[foto.descarte] += 1
    etapa = indices[0].etapa if indices else Etapa.EVALUACION
    nivel = indices[0].nivel if indices else Nivel.LEVE
    manifest = ManifestFotografiado(
        seed_inicial=seed_inicial,
        n=len(indices),
        etapa=etapa,
        nivel=nivel,
        semillas=[indice.seed for indice in indices],
        # Todas, también las que no salieron: un 0 es justo lo que hay que ver.
        legajos_por_inconsistencia={i: por_inconsistencia[i] for i in Inconsistencia},
        legajos_sin_inconsistencias=sum(1 for indice in indices if not indice.inconsistencias),
        legajos_por_caso={c: por_caso[c] for c in CasoDificil},
        fotos=sum(indice.fotos for indice in indices),
        fotos_descartadas={m: descartes[m] for m in MotivoDescarte},
        forzados=forzados or {},
    )
    (out / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest
