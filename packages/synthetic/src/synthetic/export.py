"""Escribe en disco el contrato de cada semilla con su legajo: PDF + JSON por documento.

Dos sets con propósitos distintos:
- **sorteado** (`out/<seed>/`): cada semilla elige sus casos; mide cómo le va al
  extractor en un día normal (la métrica representativa);
- **forzado** (`out/forzados/<caso>/<seed>/`): N contratos por caso, con ese caso solo;
  garantiza un mínimo de los casos raros (con P_CASO, el canon escalonado o la caución
  pueden salir 0 veces en 50) y permite atribuirle cada error a un caso.

Una carpeta por semilla (`0042/`) con todos sus documentos y un `legajo.json` que dice qué
es cada archivo, con qué modelo valida y a qué persona pertenece. El `persona_id` vive en
el índice y no en los modelos de core, porque esos son lo que extrae el LLM y el LLM no
sabe qué id tiene cada persona; los evals de la Fase 4 lo usan para cruzar documentos.
"""

from collections import Counter
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from core.models import (
    DNI,
    PolizaCaucion,
    ReciboSueldo,
    SeguroInmueble,
    TipoDocumento,
    TituloPropiedad,
)
from synthetic.cases import CasoDificil, Muestra, es_aplicable
from synthetic.contracts import generate_contrato
from synthetic.dni import generate_dnis
from synthetic.garantia import generate_caucion, generate_titulos
from synthetic.pdf import generate_sample
from synthetic.recibo import generate_recibos
from synthetic.seguro import generate_seguro

NombreModelo = Literal[
    "Muestra", "DNI", "ReciboSueldo", "TituloPropiedad", "PolizaCaucion", "SeguroInmueble"
]

# Con qué modelo valida cada JSON. Es también la tabla que va a usar el extractor de la
# Fase 3 para elegir el esquema de cada documento.
MODELOS: dict[str, type[BaseModel]] = {
    "Muestra": Muestra,
    "DNI": DNI,
    "ReciboSueldo": ReciboSueldo,
    "TituloPropiedad": TituloPropiedad,
    "PolizaCaucion": PolizaCaucion,
    "SeguroInmueble": SeguroInmueble,
}


class DocumentoLegajo(BaseModel):
    tipo: TipoDocumento = Field(..., description="Lo que el clasificador tiene que responder")
    modelo: NombreModelo = Field(..., description="Modelo contra el que valida el JSON")
    pdf: str = Field(..., description="Archivo PDF, relativo a la carpeta de la semilla")
    datos: str = Field(..., description="Archivo JSON con el ground truth")
    persona_id: UUID | None = Field(
        None, description="Parte del contrato a la que pertenece; null si es del contrato"
    )


class IndiceLegajo(BaseModel):
    seed: int
    sintetico: Literal[True] = True
    casos: list[CasoDificil]
    documentos: list[DocumentoLegajo]


class Manifest(BaseModel):
    """Resumen del set: para ver de un vistazo si cada caso y cada documento está representado."""

    seed_inicial: int
    n: int
    sintetico: Literal[True] = True
    semillas: list[int]
    contratos_por_caso: dict[CasoDificil, int]
    contratos_limpios: int
    documentos_por_modelo: dict[str, int]
    forzados: dict[CasoDificil, list[int]] = Field(
        default_factory=dict, description="Semillas del set forzado de cada caso"
    )

# Cuántas semillas revisar buscando una donde el caso aplique, antes de rendirse.
MAX_BUSQUEDA = 10_000


def carpeta_semilla(out: Path, seed: int) -> Path:
    return out / f"{seed:04d}"


def carpeta_forzado(out: Path, caso: CasoDificil) -> Path:
    return out / "forzados" / caso


def write_legajo(
    seed: int, out: Path, casos: list[CasoDificil] | None = None
) -> IndiceLegajo:
    """Escribe el contrato y su legajo en `out/<seed>/` y devuelve su índice.

    Sin `casos`, la semilla elige los suyos; con `casos`, se fuerzan (ver `generate_sample`).
    """
    carpeta = carpeta_semilla(out, seed)
    carpeta.mkdir(parents=True, exist_ok=True)
    documentos: list[DocumentoLegajo] = []

    def guardar(
        nombre: str, tipo: TipoDocumento, pdf: bytes, datos: BaseModel, persona_id: UUID | None
    ) -> None:
        (carpeta / f"{nombre}.pdf").write_bytes(pdf)
        (carpeta / f"{nombre}.json").write_text(datos.model_dump_json(indent=2), encoding="utf-8")
        documentos.append(
            DocumentoLegajo(
                tipo=tipo,
                modelo=type(datos).__name__,
                pdf=f"{nombre}.pdf",
                datos=f"{nombre}.json",
                persona_id=persona_id,
            )
        )

    pdf, muestra = generate_sample(seed, casos)
    guardar("contrato", TipoDocumento.CONTRATO, pdf, muestra, None)
    # Los mismos casos que el contrato, así el legajo sabe quién firma de verdad.
    casos = muestra.casos

    # Nombres legibles por rol ("dni_inquilino_2") en vez del UUID; el id va en el índice.
    por_rol: Counter[str] = Counter()
    nombre_de: dict[UUID, str] = {}
    for parte in muestra.contrato.partes:
        por_rol[parte.rol] += 1
        nombre_de[parte.id] = f"{parte.rol}_{por_rol[parte.rol]}"

    for persona_id, (pdf, dni) in generate_dnis(seed, casos).items():
        guardar(f"dni_{nombre_de[persona_id]}", TipoDocumento.DNI, pdf, dni, persona_id)
    for persona_id, (pdf, recibo) in generate_recibos(seed, casos).items():
        nombre = f"recibo_{nombre_de[persona_id]}"
        guardar(nombre, TipoDocumento.RECIBO_SUELDO, pdf, recibo, persona_id)
    for persona_id, (pdf, titulo) in generate_titulos(seed, casos).items():
        nombre = f"titulo_{nombre_de[persona_id]}"
        guardar(nombre, TipoDocumento.GARANTIA, pdf, titulo, persona_id)
    caucion = generate_caucion(seed, casos)
    if caucion is not None:
        guardar("caucion", TipoDocumento.GARANTIA, *caucion, None)
    guardar("seguro", TipoDocumento.SEGURO, *generate_seguro(seed, casos), None)

    indice = IndiceLegajo(seed=seed, casos=casos, documentos=documentos)
    (carpeta / "legajo.json").write_text(indice.model_dump_json(indent=2), encoding="utf-8")
    return indice


def semillas_forzadas(caso: CasoDificil, desde: int, cantidad: int) -> list[int]:
    """Las primeras `cantidad` semillas desde `desde` cuyo contrato admite el caso."""
    semillas: list[int] = []
    for seed in range(desde, desde + MAX_BUSQUEDA):
        if len(semillas) == cantidad:
            break
        if es_aplicable(caso, generate_contrato(seed)):
            semillas.append(seed)
    if len(semillas) < cantidad:
        raise ValueError(f"{caso}: solo {len(semillas)} semillas aplicables en {MAX_BUSQUEDA}")
    return semillas


def write_forzados(out: Path, desde: int, por_caso: int) -> dict[CasoDificil, list[int]]:
    """Set forzado: `por_caso` contratos con cada caso solo, desde la semilla `desde`."""
    forzados: dict[CasoDificil, list[int]] = {}
    for caso in CasoDificil:
        semillas = semillas_forzadas(caso, desde, por_caso)
        for seed in semillas:
            write_legajo(seed, carpeta_forzado(out, caso), casos=[caso])
        forzados[caso] = semillas
    return forzados


def write_manifest(
    out: Path,
    seed_inicial: int,
    indices: list[IndiceLegajo],
    forzados: dict[CasoDificil, list[int]] | None = None,
) -> Manifest:
    """Escribe `out/manifest.json` con el resumen del set (sorteado y forzado)."""
    por_caso = Counter(caso for indice in indices for caso in indice.casos)
    manifest = Manifest(
        seed_inicial=seed_inicial,
        n=len(indices),
        semillas=[indice.seed for indice in indices],
        # Todos los casos, también los que no salieron: un 0 es justo lo que hay que ver.
        contratos_por_caso={caso: por_caso[caso] for caso in CasoDificil},
        contratos_limpios=sum(1 for indice in indices if not indice.casos),
        documentos_por_modelo=dict(
            Counter(doc.modelo for indice in indices for doc in indice.documentos)
        ),
        forzados=forzados or {},
    )
    (out / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest
