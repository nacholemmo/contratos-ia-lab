"""Modelos de datos compartidos por todos los paquetes del laboratorio.

`Comprobante` es el contrato central del proyecto: el generador de facturas
sintéticas lo usa como ground truth, el extractor lo usa como salida
estructurada del LLM y la base de datos guarda lo que este modelo valida.
"""

import datetime as dt
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

# Monto en pesos: nunca negativo y con 2 decimales como máximo (centavos).
# Annotated junta el tipo con sus restricciones para reusarlo en varios campos.
Monto = Annotated[Decimal, Field(ge=0, decimal_places=2)]


class TipoComprobante(StrEnum):
    """Tipo de comprobante según quién emite y a quién.

    StrEnum: cada miembro *es* un str, así que se serializa a JSON como "A"
    y acepta "A" al validar, sin conversiones extra.
    """

    A = "A"  # Responsable Inscripto a Responsable Inscripto: IVA discriminado.
    B = "B"  # Responsable Inscripto a consumidor final o exento.
    C = "C"  # Monotributista: sin IVA discriminado.
    TICKET = "ticket"  # Ticket de controlador fiscal.


class Item(BaseModel):
    """Una línea de detalle del comprobante."""

    descripcion: str = Field(..., min_length=1, description="Descripción del ítem tal como figura en el comprobante")
    cantidad: Decimal = Field(..., gt=0, description="Cantidad; puede tener decimales (ej. 1.350 kg)")
    # Sin decimal_places: hay precios por kg o por litro con más de 2 decimales.
    precio_unitario: Decimal = Field(..., ge=0, description="Precio unitario en pesos, punto como separador decimal")
    subtotal: Monto = Field(..., description="Subtotal del ítem en pesos, punto como separador decimal")


class Comprobante(BaseModel):
    """Factura o ticket argentino ya validado.

    Fuera de este paso (no adelantar):
    - Validar el dígito verificador del CUIT → paso 6.
    - Validar que neto + IVA = total → lo vemos con el generador (Fase 1A).
    """

    cuit_emisor: str = Field(..., pattern=r"^\d{11}$", description="CUIT del emisor: 11 dígitos sin guiones (ej. 20121234560)")
    razon_social_emisor: str = Field(..., min_length=1, description="Razón social del emisor")
    tipo: TipoComprobante = Field(..., description="Tipo de comprobante: A, B, C o ticket")
    punto_venta: int = Field(..., ge=1, le=99999, description="Punto de venta, sin ceros a la izquierda (00003 → 3)")
    numero: int = Field(..., ge=1, le=99999999, description="Número de comprobante, sin ceros a la izquierda")
    fecha: dt.date = Field(..., description="Fecha de emisión en formato AAAA-MM-DD")
    neto: Monto = Field(..., description="Importe neto gravado en pesos")
    iva: Monto = Field(..., description="IVA total en pesos; 0 en facturas C y tickets sin IVA discriminado")
    total: Monto = Field(..., description="Importe total en pesos")
    cae: str | None = Field(None, pattern=r"^\d{14}$", description="CAE de 14 dígitos; null si no figura (ej. tickets)")
    items: list[Item] = Field(..., description="Ítems del comprobante; lista vacía si no tiene detalle")


__all__ = ["Comprobante", "Item", "TipoComprobante"]