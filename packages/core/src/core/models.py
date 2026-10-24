"""Modelos de datos compartidos por todos los paquetes del laboratorio.

`Contrato` (y los modelos que lo componen) es el centro del proyecto: el generador
sintético lo usa como ground truth, el extractor como salida estructurada del LLM
y la base de datos guarda lo que estos modelos validan.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

# Monto: nunca negativo y con 2 decimales como máximo (centavos).
# La moneda va en un campo aparte: hay contratos en pesos y en dólares.
Monto = Annotated[Decimal, Field(ge=0, decimal_places=2)]

# Pesos oficiales para el dígito verificador del CUIT, aplicados a los primeros 10 dígitos.
PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


class Rol(StrEnum):
    """Rol de una persona dentro de un contrato."""

    PROPIETARIO = "propietario"
    INQUILINO = "inquilino"
    GARANTE = "garante"


class Moneda(StrEnum):
    ARS = "ARS"
    USD = "USD"


class Indice(StrEnum):
    """Índice con el que se ajusta el alquiler."""

    IPC = "IPC"  # Índice de Precios al Consumidor (INDEC).
    ICL = "ICL"  # Índice para Contratos de Locación (BCRA).
    CASA_PROPIA = "casa_propia"  # Coeficiente Casa Propia.
    UVA = "UVA"  # Unidad de Valor Adquisitivo (BCRA).
    DOLAR = "dolar"  # Monto atado a la cotización del dólar.
    FIJO = "fijo"  # Sin ajuste o con montos escalonados fijados en el contrato.


class RegimenLegal(StrEnum):
    """Marco legal vigente cuando se firmó el contrato."""

    LEY_27551 = "ley_27551"  # Jul 2020 a oct 2023: ajuste anual por ICL, plazo de 3 años.
    LEY_27737 = "ley_27737"  # Oct 2023 a dic 2023: ajuste semestral por Casa Propia.
    DNU_70_2023 = "dnu_70_2023"  # Desde dic 2023: índice, frecuencia y plazo libres.


def cuit_valido(cuit: str) -> bool:
    """Devuelve True si el dígito verificador del CUIT (11 dígitos) es correcto.

    Módulo 11: se multiplican los primeros 10 dígitos por PESOS_CUIT, se suma y
    se calcula 11 - (suma % 11). Si da 11 el dígito esperado es 0; si da 10 no
    entra en un dígito y el CUIT es inválido.
    """
    if len(cuit) != 11 or not cuit.isdigit():
        return False

    # strict=True falla si PESOS_CUIT deja de tener 10 elementos: sin él, zip
    # corta en el iterable más corto y la suma daría mal en silencio.
    suma = sum(int(d) * p for d, p in zip(cuit[:10], PESOS_CUIT, strict=True))
    digito = 11 - (suma % 11)

    if digito == 10:
        return False
    if digito == 11:
        digito = 0

    return digito == int(cuit[10])


class Persona(BaseModel):
    """Persona física o jurídica que participa en un contrato."""

    id: UUID = Field(default_factory=uuid4, description="ID interno; no lo genera el LLM")
    nombre: str = Field(
        ...,
        min_length=1,
        description="Nombre completo o razón social tal como figura en el contrato",
    )
    rol: Rol = Field(..., description="Rol en el contrato: propietario, inquilino o garante")
    dni: str | None = Field(
        None,
        pattern=r"^\d{7,8}$",
        description="DNI de 7 u 8 dígitos sin puntos (ej. 30123456); null si no figura",
    )
    cuit: str | None = Field(
        None,
        pattern=r"^\d{11}$",
        description="CUIT o CUIL de 11 dígitos sin guiones (ej. 20301234567); null si no figura",
    )

    @field_validator("cuit")
    @classmethod
    def _validar_digito_verificador(cls, v: str | None) -> str | None:
        # Corre después del pattern, así que v ya tiene 11 dígitos (o es None).
        if v is not None and not cuit_valido(v):
            raise ValueError("dígito verificador del CUIT inválido")
        return v


class TipoPropiedad(StrEnum):
    DEPARTAMENTO = "departamento"
    CASA = "casa"
    PH = "ph"  # Propiedad horizontal: casa dentro de un lote compartido.
    LOCAL = "local"
    OFICINA = "oficina"
    OTRO = "otro"


class Propiedad(BaseModel):
    """Inmueble alquilado. Dirección separada en partes para poder buscar y deduplicar."""

    tipo: TipoPropiedad = Field(..., description="Tipo de inmueble según el contrato")
    calle: str = Field(..., min_length=1, description="Nombre de la calle, sin el número")
    numero: str = Field(
        ...,
        min_length=1,
        description="Altura de la calle; texto porque puede ser 'S/N' o '1234 bis'",
    )
    piso: str | None = Field(None, description="Piso (ej. '3', 'PB'); null si no aplica")
    departamento: str | None = Field(
        None, description="Unidad o departamento (ej. 'B', '12'); null si no aplica"
    )
    localidad: str = Field(..., min_length=1, description="Localidad o barrio (ej. 'Palermo')")
    provincia: str = Field(..., min_length=1, description="Provincia (ej. 'Buenos Aires', 'CABA')")
    codigo_postal: str | None = Field(
        None,
        description="Código postal tal como figura (ej. '1425' o 'C1425ABC'); null si no figura",
    )


class Evidencia(BaseModel):
    texto: str = Field(
        ...,
        min_length=1,
        description=(
            "Fragmento copiado literal del documento, sin resumir, que respalda el dato extraído"
        ),
    )
    pagina: int = Field(..., ge=1, description="Número de página donde aparece el fragmento")


class Contrato(BaseModel):
    """Contrato de locación. Cada dato clave lleva al lado su campo `<dato>_evidencia`."""

    id: UUID = Field(default_factory=uuid4, description="ID interno; no lo genera el LLM")
    partes: list[Persona] = Field(
        ..., min_length=2, description="Propietarios, inquilinos y garantes del contrato"
    )
    propiedad: Propiedad = Field(..., description="Inmueble alquilado")
    fecha_firma: date | None = Field(
        None, description="Fecha de firma, AAAA-MM-DD; null si no figura o está en blanco"
    )
    fecha_inicio: date = Field(..., description="Fecha de inicio de la locación, AAAA-MM-DD")
    plazo_meses: int = Field(..., ge=1, description="Duración total en meses (ej. 24, 36)")
    monto_inicial: Monto = Field(..., description="Alquiler mensual del primer período")
    moneda: Moneda = Field(..., description="Moneda del alquiler: ARS o USD")
    indice: Indice = Field(..., description="Índice de ajuste; 'fijo' si no se ajusta")
    frecuencia_ajuste_meses: int | None = Field(
        None,
        ge=1,
        le=12,
        description="Cada cuántos meses se ajusta (3, 4, 6 o 12); null si el índice es 'fijo'",
    )
    deposito: Monto | None = Field(
        None, description="Depósito en garantía en la misma moneda; null si no hay"
    )
    regimen_legal: RegimenLegal = Field(..., description="Marco legal según la fecha de firma")
    clausulas: list[Evidencia] = Field(
        default_factory=list,
        description="Cláusulas relevantes (rescisión, expensas), cada una con su texto y página",
    )

    # Evidencias (opción 1: campo gemelo por cada dato clave)

    propiedad_evidencia: Evidencia | None = None
    monto_inicial_evidencia: Evidencia | None = None
    moneda_evidencia: Evidencia | None = None
    indice_evidencia: Evidencia | None = None
    frecuencia_ajuste_meses_evidencia: Evidencia | None = None
    deposito_evidencia: Evidencia | None = None
    fecha_inicio_evidencia: Evidencia | None = None
    plazo_meses_evidencia: Evidencia | None = None
    fecha_firma_evidencia: Evidencia | None = None


class Sexo(StrEnum):
    """Sexo tal como figura en el DNI."""

    M = "M"
    F = "F"
    X = "X"  # DNI no binario (Decreto 476/2021).


class DNI(BaseModel):
    """Datos del DNI argentino (frente y dorso), tal como figuran en el documento.

    Sin foto, firma, código de barras ni número de trámite: el servicio no los necesita y
    son los datos más sensibles (minimización, Ley 25.326). Solo número y apellido son
    obligatorios, porque sin ellos no es un DNI; el resto puede no leerse (foto mala, dorso
    que no vino) y queda en null en vez de inventarse. Cada dato lleva al lado su campo
    `<dato>_evidencia`, como en `Contrato`.
    """

    numero: str = Field(
        ...,
        pattern=r"^\d{7,8}$",
        description="Número de documento de 7 u 8 dígitos, sin puntos (ej. 30123456)",
    )
    apellido: str = Field(
        ...,
        min_length=1,
        description="Apellido o apellidos tal como figuran en el DNI, sin el nombre",
    )
    nombre: str | None = Field(
        None,
        min_length=1,
        description=(
            "Nombre o nombres de pila, sin el apellido (ej. 'Juan Ignacio'); null si no figura"
        ),
    )
    sexo: Sexo | None = Field(None, description="Sexo: M, F o X; null si no figura")
    fecha_nacimiento: date | None = Field(
        None, description="Fecha de nacimiento, AAAA-MM-DD; null si no figura"
    )
    fecha_emision: date | None = Field(
        None, description="Fecha de emisión, AAAA-MM-DD; null si no figura"
    )
    fecha_vencimiento: date | None = Field(
        None, description="Fecha de vencimiento, AAAA-MM-DD; null si no figura"
    )
    nacionalidad: str | None = Field(
        None, description="Nacionalidad tal como figura (ej. 'ARGENTINA'); null si no figura"
    )
    domicilio: str | None = Field(
        None, description="Domicilio del dorso, tal como figura; null si no figura"
    )

    numero_evidencia: Evidencia | None = None
    apellido_evidencia: Evidencia | None = None
    nombre_evidencia: Evidencia | None = None
    sexo_evidencia: Evidencia | None = None
    fecha_nacimiento_evidencia: Evidencia | None = None
    fecha_emision_evidencia: Evidencia | None = None
    fecha_vencimiento_evidencia: Evidencia | None = None
    nacionalidad_evidencia: Evidencia | None = None
    domicilio_evidencia: Evidencia | None = None


class TipoDocumento(StrEnum):
    """Tipo de archivo que entra al sistema; lo decide el clasificador de la Fase 3."""

    CONTRATO = "contrato"
    DNI = "dni"
    RECIBO_SUELDO = "recibo_sueldo"
    GARANTIA = "garantia"  # Garantía propietaria o seguro de caución.
    SEGURO = "seguro"  # Seguro del inmueble (incendio, responsabilidad civil).
    OTRO = "otro"


class Documento(BaseModel):
    """Archivo que entra al sistema y a qué persona o contrato está vinculado."""

    id: UUID = Field(default_factory=uuid4, description="Identificador interno")
    tipo: TipoDocumento = Field(..., description="Tipo de documento")

    persona_id: UUID | None = Field(
        None, description="ID de la persona a la que pertenece (si aplica)"
    )
    contrato_ids: list[UUID] = Field(
        default_factory=list, description="IDs de contratos a los que pertenece (si aplica)"
    )
    referencia_archivo: str = Field(
        min_length=1, description="Referencia al archivo original (path o URL)"
    )
    nombre_original: str = Field(min_length=1, description="Nombre original del archivo")


__all__ = [
    "DNI",
    "Contrato",
    "Documento",
    "Evidencia",
    "Indice",
    "Moneda",
    "Monto",
    "Persona",
    "Propiedad",
    "RegimenLegal",
    "Rol",
    "Sexo",
    "TipoDocumento",
    "TipoPropiedad",
    "cuit_valido",
]
