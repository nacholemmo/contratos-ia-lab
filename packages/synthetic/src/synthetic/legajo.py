"""Lo que comparten los documentos complementarios de un contrato (el legajo).

Cada documento del legajo sale de la misma semilla que el contrato. Usa dos versiones:
- el contrato **con los casos aplicados**, para saber quién firma de verdad (con el caso
  SEGURO_DE_CAUCION no hay garantes, así que tampoco hay DNI ni título de garantes);
- el contrato **limpio** y sus identidades, para los datos completos de cada persona y
  del inmueble (el DNI trae el número aunque el contrato no lo muestre).
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from core.models import Contrato, Persona, Rol
from synthetic.cases import CasoDificil
from synthetic.contracts import Identidad, generate_contrato_con_identidades
from synthetic.pdf import prepare_sample


@dataclass(frozen=True)
class ContextoLegajo:
    seed: int
    casos: list[CasoDificil]
    contrato: Contrato
    limpio: Contrato
    identidades: dict[UUID, Identidad]

    @property
    def referencia(self) -> date:
        """Fecha que hace de "hoy" en el legajo: la firma del contrato limpio."""
        # El limpio siempre tiene fecha de firma (el caso de fecha en blanco va aparte).
        return self.limpio.fecha_firma or self.limpio.fecha_inicio

    def partes(self, rol: Rol | None = None) -> list[Persona]:
        """Partes que firman el contrato (con los casos aplicados), en su orden."""
        return [p for p in self.contrato.partes if rol is None or p.rol == rol]


def contexto_legajo(seed: int, casos: list[CasoDificil] | None = None) -> ContextoLegajo:
    """Contexto del legajo de la semilla; `casos` se fuerza igual que en `generate_sample`."""
    casos_aplicados, contrato, _ = prepare_sample(seed, casos)
    limpio, identidades = generate_contrato_con_identidades(seed)
    return ContextoLegajo(seed, casos_aplicados, contrato, limpio, identidades)


def sumar_meses(d: date, meses: int) -> date:
    """`d` corrida `meses` meses; si el día no existe en el mes de destino, el último del mes."""
    anios, mes = divmod(d.month - 1 + meses, 12)
    anio = d.year + anios
    dia = min(d.day, calendar.monthrange(anio, mes + 1)[1])
    return date(anio, mes + 1, dia)


def fin_de_contrato(contrato: Contrato) -> date:
    """Último día de la locación: inicio + plazo, menos un día (del 1/3/2025 por 24 meses
    al 28/2/2027)."""
    return sumar_meses(contrato.fecha_inicio, contrato.plazo_meses) - timedelta(days=1)
