"""Legajo fotografiado de una semilla: los documentos como fotos sueltas y su `LegajoEsperado`.

Etapa de evaluación (antes de firmar, la prioridad del ADR 0001): DNI de inquilinos y
garantes, los últimos 3 recibos de cada inquilino (y a veces de un garante, como pasa en la
realidad) y la garantía (título de cada garante, o la póliza de caución). El contrato no se
entrega: todavía no existe. De él sale solo el alquiler propuesto.

Etapa de cierre: lo mismo, más el contrato y el seguro del inmueble.

Las fotos salen en el orden de los documentos y con nombres consecutivos. Mezclarlas,
duplicarlas y sumar intrusas es del paso 5.
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from core.legajo import (
    AlertaEsperada,
    DocumentoEsperado,
    Etapa,
    FotoEsperada,
    LegajoEsperado,
    PersonaEsperada,
    TipoAlerta,
)
from core.models import ReciboSueldo, Rol, TipoDocumento
from synthetic.cases import CasoDificil
from synthetic.dni import generate_dnis
from synthetic.foto import Nivel, fotografiar_pdf, nombres_fotos
from synthetic.garantia import generate_caucion, generate_titulos
from synthetic.legajo import ContextoLegajo, contexto_legajo
from synthetic.pdf import generate_sample
from synthetic.recibo import alquiler_en_pesos, generate_recibos_meses
from synthetic.seguro import generate_seguro
from synthetic.source import Source

# Probabilidad de que un garante también mande sus recibos, aunque la garantía sea su título.
P_RECIBOS_GARANTE = 0.5

# Requisito de ingresos más común en las inmobiliarias: el neto tiene que cubrir al menos
# tres alquileres. En la Fase 5 los requisitos llegan en cada llamada; acá es el fijo del
# generador, el mismo con el que se calcula la alerta esperada.
INGRESO_MINIMO_EN_ALQUILERES = Decimal(3)


@dataclass(frozen=True)
class DocumentoGenerado:
    tipo: TipoDocumento
    nombre: str  # "recibo_inquilino_1_mes_2": nombre del JSON de sus datos
    pdf: bytes
    datos: BaseModel
    persona_id: UUID | None  # None: del legajo (contrato, seguro, caución)


@dataclass(frozen=True)
class LegajoGenerado:
    esperado: LegajoEsperado
    fotos: dict[str, bytes]  # archivo → JPG, en el orden en que llegan
    datos: dict[str, BaseModel]  # "dni_inquilino_1.json" → ground truth de sus campos


def ingreso_insuficiente(alquiler: Decimal, netos: dict[str, list[Decimal]]) -> bool:
    """¿El ingreso de los inquilinos no alcanza para el alquiler propuesto?

    `alquiler`: el alquiler mensual en pesos. `netos`: por inquilino, el neto de cada recibo
    presentado, del más reciente al más viejo. La regla es INGRESO_MINIMO_EN_ALQUILERES.
    Dinero con Decimal, nunca con float.

    El ingreso mensual de cada inquilino es el neto de su recibo más reciente (no la suma de
    los meses), y los de todos los inquilinos se suman: alquilan juntos. Sin recibos no hay
    ingreso que medir: eso es un faltante, no esta alerta.
    """
    ultimos = [lista[0] for lista in netos.values() if lista]
    if not ultimos:
        return False
    return sum(ultimos, Decimal(0)) < alquiler * INGRESO_MINIMO_EN_ALQUILERES


def documentos_del_legajo(contexto: ContextoLegajo, etapa: Etapa) -> list[DocumentoGenerado]:
    """Los documentos de la etapa, agrupados por persona: inquilinos, garantes y el legajo."""
    seed, casos = contexto.seed, contexto.casos
    inquilinos = contexto.partes(Rol.INQUILINO)
    garantes = contexto.partes(Rol.GARANTE)
    rol_n = {p.id: f"{p.rol}_{i}" for rol in (inquilinos, garantes) for i, p in enumerate(rol, 1)}
    dnis = generate_dnis(seed, casos)
    titulos = generate_titulos(seed, casos)
    docs: list[DocumentoGenerado] = []

    def agregar(tipo: TipoDocumento, nombre: str, pdf: bytes, datos: BaseModel, pid: UUID | None):
        docs.append(DocumentoGenerado(tipo, nombre, pdf, datos, pid))

    def recibos(persona_id: UUID) -> None:
        source = Source(seed).derive(f"recibo:{persona_id}")
        for k, (pdf, recibo) in enumerate(generate_recibos_meses(contexto, persona_id, source)):
            nombre = f"recibo_{rol_n[persona_id]}_mes_{k + 1}"
            agregar(TipoDocumento.RECIBO_SUELDO, nombre, pdf, recibo, persona_id)

    for p in inquilinos:
        agregar(TipoDocumento.DNI, f"dni_{rol_n[p.id]}", *dnis[p.id], p.id)
        recibos(p.id)
    for p in garantes:
        agregar(TipoDocumento.DNI, f"dni_{rol_n[p.id]}", *dnis[p.id], p.id)
        if Source(seed).derive(f"recibos_garante:{p.id}").rng.random() < P_RECIBOS_GARANTE:
            recibos(p.id)
        agregar(TipoDocumento.GARANTIA, f"titulo_{rol_n[p.id]}", *titulos[p.id], p.id)

    caucion = generate_caucion(seed, casos)
    if caucion is not None:
        agregar(TipoDocumento.GARANTIA, "caucion", *caucion, None)
    if etapa == Etapa.CIERRE:
        agregar(TipoDocumento.CONTRATO, "contrato", *generate_sample(seed, casos), None)
        agregar(TipoDocumento.SEGURO, "seguro", *generate_seguro(seed, casos), None)
    return docs


def generate_legajo(
    seed: int,
    etapa: Etapa = Etapa.EVALUACION,
    nivel: Nivel = Nivel.LEVE,
    casos: list[CasoDificil] | None = None,
) -> LegajoGenerado:
    """Fotos, datos y ground truth del legajo de la semilla. Misma semilla, mismos bytes."""
    contexto = contexto_legajo(seed, casos)
    docs = documentos_del_legajo(contexto, etapa)

    # Personas en el orden del contrato (inquilinos y garantes), con ids fijos p1, p2…
    partes = contexto.partes(Rol.INQUILINO) + contexto.partes(Rol.GARANTE)
    pid = {p.id: f"p{i}" for i, p in enumerate(partes, 1)}
    identidades = contexto.identidades
    personas = [
        PersonaEsperada(
            id=pid[p.id],
            rol=p.rol,
            nombre=f"{identidades[p.id].nombre_pila} {identidades[p.id].apellido}",
            dni=identidades[p.id].persona.dni,
        )
        for p in partes
    ]

    # Una foto por página, con nombres consecutivos en el orden de los documentos.
    fotos_por_doc = [
        fotografiar_pdf(d.pdf, Source(seed).derive(f"foto:{d.nombre}"), nivel) for d in docs
    ]
    nombres = iter(nombres_fotos(Source(seed).derive("nombres"), sum(map(len, fotos_por_doc))))
    fotos: dict[str, bytes] = {}
    datos: dict[str, BaseModel] = {}
    documentos: list[DocumentoEsperado] = []
    for i, (doc, jpgs) in enumerate(zip(docs, fotos_por_doc, strict=True), 1):
        archivos = [next(nombres) for _ in jpgs]
        fotos.update(zip(archivos, jpgs, strict=True))
        datos[f"{doc.nombre}.json"] = doc.datos
        documentos.append(
            DocumentoEsperado(
                id=f"d{i}",
                tipo=doc.tipo,
                persona_id=pid[doc.persona_id] if doc.persona_id else None,
                fotos=archivos,
                datos=f"{doc.nombre}.json",
            )
        )

    # Alerta de ingresos: netos de los recibos de cada inquilino, del más reciente al más viejo.
    limpio = contexto.limpio
    netos: dict[str, list[Decimal]] = {}
    recibos_inquilinos: list[str] = []
    for doc, esperado in zip(docs, documentos, strict=True):
        es_inquilino = doc.persona_id in {p.id for p in contexto.partes(Rol.INQUILINO)}
        if isinstance(doc.datos, ReciboSueldo) and es_inquilino and doc.datos.neto is not None:
            netos.setdefault(pid[doc.persona_id], []).append(doc.datos.neto)
            recibos_inquilinos.append(esperado.id)
    alertas = []
    if ingreso_insuficiente(alquiler_en_pesos(limpio), netos):
        alertas.append(
            AlertaEsperada(
                tipo=TipoAlerta.INGRESO_INSUFICIENTE,
                documento_ids=recibos_inquilinos,
                detalle=f"El neto de los inquilinos no cubre {INGRESO_MINIMO_EN_ALQUILERES} "
                "alquileres",
            )
        )

    esperado = LegajoEsperado(
        seed=seed,
        etapa=etapa,
        alquiler_propuesto=limpio.monto_inicial,
        moneda=limpio.moneda,
        personas=personas,
        documentos=documentos,
        fotos=[FotoEsperada(archivo=a) for a in fotos],
        alertas=alertas,
    )
    return LegajoGenerado(esperado=esperado, fotos=fotos, datos=datos)
