"""Ground truth de un legajo fotografiado: la estructura que el servicio tiene que reconstruir.

El generador de la Fase 3 lo escribe junto a las fotos; las evals de la Fase 6 comparan contra
él. Responde lo que los modelos de un documento (DNI, ReciboSueldo, …) no pueden:

- agrupación: qué fotos forman cada documento (frente y dorso, páginas de un título);
- asignación: de qué persona es cada documento y con qué rol;
- descarte: qué fotos sobran y por qué (intrusa, duplicada o ilegible);
- faltantes y alertas que el servicio debería levantar.

Los ids son strings fijos ("p1", "d3", "IMG_4821.jpg") y no UUID: con la misma semilla el
legajo tiene que salir igual byte por byte, y un `uuid4` cambia en cada corrida.

La foto pertenece a un documento a través de `DocumentoEsperado.fotos` y solo ahí: guardar la
relación en los dos sentidos permitiría que se contradigan.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from core.models import Moneda, Monto, Rol, TipoDocumento


class Etapa(StrEnum):
    """Etapa del legajo (ADR 0001): el mismo motor con distintos documentos."""

    EVALUACION = "evaluacion"  # Antes de firmar: DNI, recibos y garantías.
    CIERRE = "cierre"  # Se suman el contrato y el seguro.


class MotivoDescarte(StrEnum):
    """Por qué una foto no forma parte de ningún documento del legajo."""

    INTRUSA = "intrusa"  # De otra cosa (una factura, una captura de chat): clase `otro`.
    DUPLICADA = "duplicada"  # La misma foto, o el mismo documento sacado dos veces.
    ILEGIBLE = "ilegible"  # No se puede leer: desenfocada, cortada, a oscuras.


class TipoAlerta(StrEnum):
    """Cruces que el servicio calcula con código determinístico (Fase 5). Cada inconsistencia
    que inyecta el generador (paso 6) tiene que producir una de estas."""

    RECIBO_DE_OTRA_PERSONA = "recibo_de_otra_persona"
    CUIL_NO_CORRESPONDE_AL_DNI = "cuil_no_corresponde_al_dni"
    DNI_VENCIDO = "dni_vencido"
    RECIBO_VIEJO = "recibo_viejo"
    NETO_NO_CIERRA = "neto_no_cierra"  # bruto - descuentos != neto
    TITULAR_NO_ES_GARANTE = "titular_no_es_garante"
    CAUCION_MAS_CORTA_QUE_EL_PLAZO = "caucion_mas_corta_que_el_plazo"
    INGRESO_INSUFICIENTE = "ingreso_insuficiente"


class PersonaEsperada(BaseModel):
    id: str = Field(..., min_length=1, description="Id fijo dentro del legajo (ej. 'p1')")
    rol: Rol = Field(..., description="Rol en el legajo: inquilino, garante o propietario")
    nombre: str = Field(..., min_length=1, description="Nombre completo, como en su DNI")
    dni: str | None = Field(None, description="Número de DNI sin puntos; null si no tiene")


class FotoEsperada(BaseModel):
    archivo: str = Field(..., min_length=1, description="Nombre del archivo (ej. 'IMG_4821.jpg')")
    descarte: MotivoDescarte | None = Field(
        None, description="Motivo si la foto no va en ningún documento; null si va en uno"
    )
    duplicada_de: str | None = Field(
        None, description="Archivo de la foto que se conserva, si esta es un duplicado"
    )


class DocumentoEsperado(BaseModel):
    id: str = Field(..., min_length=1, description="Id fijo dentro del legajo (ej. 'd3')")
    tipo: TipoDocumento = Field(..., description="Tipo de documento")
    persona_id: str | None = Field(
        None, description="Persona a la que pertenece; null para el contrato y el seguro"
    )
    fotos: list[str] = Field(
        ..., min_length=1, description="Archivos que lo forman, en orden (frente, dorso, págs.)"
    )
    datos: str | None = Field(
        None, description="JSON con el ground truth de sus campos (ej. 'dni_inquilino_1.json')"
    )


class FaltanteEsperado(BaseModel):
    tipo: TipoDocumento = Field(..., description="Tipo de documento que falta")
    persona_id: str | None = Field(
        None, description="Persona a la que le falta; null si es del legajo"
    )
    detalle: str = Field(
        ..., min_length=1, description="Qué falta, para una persona (ej. '3 recibos')"
    )


class AlertaEsperada(BaseModel):
    tipo: TipoAlerta
    persona_id: str | None = Field(None, description="Persona involucrada, si hay una")
    documento_ids: list[str] = Field(
        default_factory=list, description="Documentos que la originan (la evidencia del cruce)"
    )
    detalle: str = Field(..., min_length=1, description="Explicación para la persona que revisa")


class LegajoEsperado(BaseModel):
    """La respuesta correcta del armado de un legajo, para una semilla."""

    seed: int
    sintetico: Literal[True] = True
    etapa: Etapa
    alquiler_propuesto: Monto = Field(..., description="Alquiler mensual para el cruce de ingresos")
    moneda: Moneda
    personas: list[PersonaEsperada]
    documentos: list[DocumentoEsperado]
    fotos: list[FotoEsperada] = Field(..., description="Todas las fotos que entran, en orden")
    faltantes: list[FaltanteEsperado] = Field(default_factory=list)
    alertas: list[AlertaEsperada] = Field(default_factory=list)

    @model_validator(mode="after")
    def ids_y_personas(self) -> Self:
        """Ids únicos, y cada referencia a una persona o un documento apunta a uno que existe."""
        for nombre, ids in [
            ("personas", [p.id for p in self.personas]),
            ("documentos", [d.id for d in self.documentos]),
            ("fotos", [f.archivo for f in self.fotos]),
        ]:
            if len(ids) != len(set(ids)):
                raise ValueError(f"ids repetidos en {nombre}")

        personas = {p.id for p in self.personas}
        documentos = {d.id for d in self.documentos}
        referencias = (
            [d.persona_id for d in self.documentos]
            + [f.persona_id for f in self.faltantes]
            + [a.persona_id for a in self.alertas]
        )
        for persona_id in referencias:
            if persona_id is not None and persona_id not in personas:
                raise ValueError(f"persona inexistente: {persona_id}")
        for alerta in self.alertas:
            for documento_id in alerta.documento_ids:
                if documento_id not in documentos:
                    raise ValueError(f"documento inexistente en una alerta: {documento_id}")
        return self

    @model_validator(mode="after")
    def cada_foto_en_un_lugar(self) -> Self:
        """Cada foto está en exactamente un documento o está descartada; nunca en los dos ni en
        ninguno. Un duplicado apunta a una foto del legajo que sí se conserva."""
        archivos = {f.archivo for f in self.fotos}
        en_documentos: set[str] = set()
        for documento in self.documentos:
            for archivo in documento.fotos:
                if archivo in en_documentos:
                    raise ValueError(f"foto en dos documentos: {archivo}")
                if archivo not in archivos:
                    raise ValueError(f"foto inexistente en {documento.id}: {archivo}")
                en_documentos.add(archivo)

        for f in self.fotos:
            en_doc = f.archivo in en_documentos
            descartada = f.descarte is not None
            if en_doc == descartada:  # los dos True, o los dos False
                raise ValueError(f"foto en un documento y descartada, o en ninguno: {f.archivo}")
            es_duplicado = f.descarte == MotivoDescarte.DUPLICADA
            if es_duplicado != (f.duplicada_de is not None):
                raise ValueError(f"duplicada_de solo va en un duplicado: {f.archivo}")
            if f.duplicada_de is not None and f.duplicada_de not in en_documentos:
                raise ValueError(f"duplicado de una foto que no se conserva: {f.duplicada_de}")
        return self
            

