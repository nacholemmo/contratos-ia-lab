"""Legajo fotografiado de una semilla: los documentos como fotos sueltas y su `LegajoEsperado`.

Etapa de evaluación (antes de firmar, la prioridad del ADR 0001): DNI de inquilinos y
garantes, los últimos 3 recibos de cada inquilino (y a veces de un garante, como pasa en la
realidad) y la garantía (título de cada garante, o la póliza de caución). El contrato no se
entrega: todavía no existe. De él sale solo el alquiler propuesto.

Etapa de cierre: lo mismo, más el contrato y el seguro del inmueble.

Las fotos salen en el orden de los documentos y con nombres consecutivos. Mezclarlas,
duplicarlas y sumar intrusas lo hace `desorden.desordenar`.
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from core.legajo import (
    AlertaEsperada,
    DocumentoEsperado,
    Etapa,
    FaltanteEsperado,
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
from synthetic.inconsistencias import (
    DETALLE_ALERTA,
    Inconsistencia,
    PlanRecibos,
    acortar_caucion,
    compatibles,
    es_aplicable,
    objetivo_dni,
    objetivo_titulo,
    plan_recibos,
    titulo_ajeno,
    vencer_dni,
)
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
    alertas: tuple[TipoAlerta, ...] = ()  # las que levanta por una inconsistencia inyectada


@dataclass(frozen=True)
class LegajoGenerado:
    esperado: LegajoEsperado
    fotos: dict[str, bytes]  # archivo → JPG, en el orden en que llegan
    datos: dict[str, BaseModel]  # "dni_inquilino_1.json" → ground truth de sus campos
    pdfs: dict[str, bytes]  # id del documento ("d3") → PDF, para volver a fotografiarlo
    inconsistencias: list[Inconsistencia]  # las inyectadas; vacío si el legajo cierra


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


def quitar_documentos(
    docs: list[DocumentoGenerado],
    source: Source,
    protegidos: frozenset[tuple[TipoDocumento, UUID | None]] = frozenset(),
) -> tuple[list[DocumentoGenerado], list[DocumentoGenerado]]:
    """Inconsistencia DOCUMENTO_FALTANTE: saca del legajo lo que una persona no entregó.

    Devuelve (los que quedan, los quitados). Los quitados son todos del mismo tipo y de la
    misma persona: con eso se arma el `FaltanteEsperado`. Todo el azar sale de `source`.

    No se quita un grupo (tipo, persona) protegido ni uno con documentos que levantan una
    alerta inyectada: si faltaran, la alerta no tendría de dónde salir.
    """
    protegidos = protegidos | {(d.tipo, d.persona_id) for d in docs if d.alertas}
    docs_candidatos = [d for d in docs if (d.tipo, d.persona_id) not in protegidos]
    # Solo falta lo que entrega una persona (DNI, recibos, título): la caución, el contrato y
    # el seguro son del legajo y los pide la inmobiliaria, no la persona. Se quita el grupo
    # entero (los 3 recibos, no uno): "no trajo recibos" es el faltante más claro de medir.
    grupos = list(dict.fromkeys((d.tipo, d.persona_id) for d in docs_candidatos if d.persona_id))
    if not grupos:  # todo tiene una alerta: no hay nada que pueda faltar
        return list(docs), []
    elegido = source.rng.choice(grupos)
    restantes = [d for d in docs if (d.tipo, d.persona_id) != elegido]
    quitados = [d for d in docs if (d.tipo, d.persona_id) == elegido]
    return restantes, quitados


def documentos_del_legajo(
    contexto: ContextoLegajo, etapa: Etapa, inconsistencias: list[Inconsistencia] | None = None
) -> list[DocumentoGenerado]:
    """Los documentos de la etapa, agrupados por persona: inquilinos, garantes y el legajo.

    Las inconsistencias se inyectan acá, sobre los datos de cada documento y antes de
    imprimirlo; cada documento roto lleva la alerta que tiene que levantar."""
    inconsistencias = inconsistencias or []
    seed, casos = contexto.seed, contexto.casos
    inquilinos = contexto.partes(Rol.INQUILINO)
    garantes = contexto.partes(Rol.GARANTE)
    rol_n = {p.id: f"{p.rol}_{i}" for rol in (inquilinos, garantes) for i, p in enumerate(rol, 1)}

    # Documento con una alerta inyectada: (tipo de documento, persona) → alerta.
    rotos: dict[tuple[TipoDocumento, UUID | None], TipoAlerta] = {}
    ajustes_dni = {}
    if Inconsistencia.DNI_VENCIDO in inconsistencias:
        persona = objetivo_dni(contexto)
        sub = Source(seed).derive("dni_vencido")
        ajustes_dni[persona] = lambda dni: vencer_dni(dni, contexto.referencia, sub)
        rotos[(TipoDocumento.DNI, persona)] = TipoAlerta.DNI_VENCIDO
    ajustes_titulo = {}
    if Inconsistencia.TITULAR_NO_ES_GARANTE in inconsistencias:
        garante = objetivo_titulo(contexto)
        sub_titulo = Source(seed).derive("titulo_ajeno")
        ajustes_titulo[garante] = lambda titulo: titulo_ajeno(titulo, sub_titulo)
        rotos[(TipoDocumento.GARANTIA, garante)] = TipoAlerta.TITULAR_NO_ES_GARANTE
    ajuste_caucion = None
    if Inconsistencia.CAUCION_MAS_CORTA_QUE_EL_PLAZO in inconsistencias:
        sub_caucion = Source(seed).derive("caucion_corta")
        ajuste_caucion = lambda poliza: acortar_caucion(poliza, sub_caucion)  # noqa: E731
        rotos[(TipoDocumento.GARANTIA, None)] = TipoAlerta.CAUCION_MAS_CORTA_QUE_EL_PLAZO

    dnis = generate_dnis(seed, casos, ajustes_dni)
    titulos = generate_titulos(seed, casos, ajustes_titulo)
    docs: list[DocumentoGenerado] = []

    def agregar(
        tipo: TipoDocumento,
        nombre: str,
        pdf: bytes,
        datos: BaseModel,
        pid: UUID | None,
        alertas: tuple[TipoAlerta, ...] = (),
    ):
        if (tipo, pid) in rotos:
            alertas = (*alertas, rotos[(tipo, pid)])
        docs.append(DocumentoGenerado(tipo, nombre, pdf, datos, pid, alertas))

    def recibos(persona_id: UUID, plan: PlanRecibos) -> None:
        source = Source(seed).derive(f"recibo:{persona_id}")
        generados = generate_recibos_meses(
            contexto,
            persona_id,
            source,
            desfase=plan.desfase,
            rango=plan.rango,
            ajustar=plan.ajustar,
        )
        for k, (pdf, recibo) in enumerate(generados):
            nombre = f"recibo_{rol_n[persona_id]}_mes_{k + 1}"
            tipo = TipoDocumento.RECIBO_SUELDO
            agregar(tipo, nombre, pdf, recibo, persona_id, plan.alertas_del_mes(k))

    for p in inquilinos:
        agregar(TipoDocumento.DNI, f"dni_{rol_n[p.id]}", *dnis[p.id], p.id)
        recibos(p.id, plan_recibos(inconsistencias, contexto, p.id))
    for p in garantes:
        agregar(TipoDocumento.DNI, f"dni_{rol_n[p.id]}", *dnis[p.id], p.id)
        if Source(seed).derive(f"recibos_garante:{p.id}").rng.random() < P_RECIBOS_GARANTE:
            recibos(p.id, PlanRecibos())
        agregar(TipoDocumento.GARANTIA, f"titulo_{rol_n[p.id]}", *titulos[p.id], p.id)

    caucion = generate_caucion(seed, casos, ajuste_caucion)
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
    inconsistencias: list[Inconsistencia] | None = None,
) -> LegajoGenerado:
    """Fotos, datos y ground truth del legajo de la semilla. Misma semilla, mismos bytes.

    `inconsistencias`: las que se inyectan; None o vacío, ninguna (el legajo cierra). El set
    sorteado las pide con `elegir_inconsistencias`.
    """
    contexto = contexto_legajo(seed, casos)
    inconsistencias = compatibles(inconsistencias or [])
    # Pedir una que no puede darse (un título sin garantes) dejaría una etiqueta sin alerta.
    no_aplican = [i for i in inconsistencias if not es_aplicable(i, contexto)]
    if no_aplican:
        raise ValueError(f"inconsistencias que no aplican a la semilla {seed}: {no_aplican}")
    docs = documentos_del_legajo(contexto, etapa, inconsistencias)
    faltantes: list[FaltanteEsperado] = []

    # Personas en el orden del contrato (inquilinos y garantes), con ids fijos p1, p2…
    partes = contexto.partes(Rol.INQUILINO) + contexto.partes(Rol.GARANTE)
    pid = {p.id: f"p{i}" for i, p in enumerate(partes, 1)}
    identidades = contexto.identidades

    quitados: list[DocumentoGenerado] = []
    if Inconsistencia.DOCUMENTO_FALTANTE in inconsistencias:
        # Con ingreso insuficiente inyectado, los recibos de los inquilinos no pueden faltar.
        protegidos = frozenset(
            (TipoDocumento.RECIBO_SUELDO, p.id)
            for p in contexto.partes(Rol.INQUILINO)
            if Inconsistencia.INGRESO_INSUFICIENTE in inconsistencias
        )
        docs, quitados = quitar_documentos(docs, Source(seed).derive("faltante"), protegidos)
    if Inconsistencia.DOCUMENTO_FALTANTE in inconsistencias and not quitados:
        # Todo lo que se podía quitar tenía una alerta: el faltante no se inyecta.
        inconsistencias = [i for i in inconsistencias if i != Inconsistencia.DOCUMENTO_FALTANTE]
    elif Inconsistencia.DOCUMENTO_FALTANTE in inconsistencias:
        n = len(quitados)
        faltantes.append(
            FaltanteEsperado(
                tipo=quitados[0].tipo,
                persona_id=pid[quitados[0].persona_id] if quitados[0].persona_id else None,
                detalle=f"{n} documento{'s' if n > 1 else ''} de tipo {quitados[0].tipo}",
            )
        )

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

    # Alertas de las inconsistencias inyectadas: una por tipo y persona, con sus documentos.
    por_alerta: dict[tuple[TipoAlerta, str | None], list[str]] = {}
    for doc, esperado in zip(docs, documentos, strict=True):
        for tipo in doc.alertas:
            por_alerta.setdefault((tipo, esperado.persona_id), []).append(esperado.id)
    for (tipo, persona_id), ids in por_alerta.items():
        alertas.append(
            AlertaEsperada(
                tipo=tipo, persona_id=persona_id, documento_ids=ids, detalle=DETALLE_ALERTA[tipo]
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
        faltantes=faltantes,
        alertas=alertas,
    )
    pdfs = {e.id: d.pdf for d, e in zip(docs, documentos, strict=True)}
    return LegajoGenerado(esperado, fotos, datos, pdfs, inconsistencias)
