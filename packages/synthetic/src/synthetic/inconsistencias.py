"""Inconsistencias del legajo: errores inyectados a propósito, cada uno con su alerta esperada.

A diferencia de `CasoDificil` (el documento es difícil de leer, pero dice la verdad), una
inconsistencia hace que el legajo **no cierre**: un recibo de otra persona, un DNI vencido,
un documento que falta. El servicio tiene que avisarlo, y el ground truth tiene que decir
qué aviso espera; si no, las evals castigarían al servicio por avisar algo cierto.

Se inyectan sobre los datos **antes de imprimirlos**: el dato roto está en el PDF (lo que se
fotografía) y en el JSON del ground truth a la vez.

Como los casos, las inconsistencias son metadatos del set: viajan en `LegajoGenerado` y en el
manifest, no en `LegajoEsperado` (que describe el legajo, no cómo se fabricó).
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from core.legajo import TipoAlerta
from core.models import ReciboSueldo, Rol, Sexo
from synthetic.cases import CasoDificil
from synthetic.identity import cuit_from_dni, generate_dni
from synthetic.legajo import ContextoLegajo
from synthetic.recibo import ALQUILER_SOBRE_NETO, _centavos
from synthetic.source import Source


class Inconsistencia(StrEnum):
    RECIBO_DE_OTRA_PERSONA = "recibo_de_otra_persona"
    CUIL_NO_CORRESPONDE_AL_DNI = "cuil_no_corresponde_al_dni"
    DNI_VENCIDO = "dni_vencido"
    RECIBO_VIEJO = "recibo_viejo"
    NETO_NO_CIERRA = "neto_no_cierra"
    TITULAR_NO_ES_GARANTE = "titular_no_es_garante"
    CAUCION_MAS_CORTA_QUE_EL_PLAZO = "caucion_mas_corta_que_el_plazo"
    INGRESO_INSUFICIENTE = "ingreso_insuficiente"
    DOCUMENTO_FALTANTE = "documento_faltante"


# La alerta que levanta cada una. DOCUMENTO_FALTANTE no es una alerta: es un faltante.
ALERTA_DE: dict[Inconsistencia, TipoAlerta | None] = {
    Inconsistencia.RECIBO_DE_OTRA_PERSONA: TipoAlerta.RECIBO_DE_OTRA_PERSONA,
    Inconsistencia.CUIL_NO_CORRESPONDE_AL_DNI: TipoAlerta.CUIL_NO_CORRESPONDE_AL_DNI,
    Inconsistencia.DNI_VENCIDO: TipoAlerta.DNI_VENCIDO,
    Inconsistencia.RECIBO_VIEJO: TipoAlerta.RECIBO_VIEJO,
    Inconsistencia.NETO_NO_CIERRA: TipoAlerta.NETO_NO_CIERRA,
    Inconsistencia.TITULAR_NO_ES_GARANTE: TipoAlerta.TITULAR_NO_ES_GARANTE,
    Inconsistencia.CAUCION_MAS_CORTA_QUE_EL_PLAZO: TipoAlerta.CAUCION_MAS_CORTA_QUE_EL_PLAZO,
    Inconsistencia.INGRESO_INSUFICIENTE: TipoAlerta.INGRESO_INSUFICIENTE,
    Inconsistencia.DOCUMENTO_FALTANTE: None,
}

# Explicación de cada alerta para la persona que revisa (va en `AlertaEsperada.detalle`).
DETALLE_ALERTA: dict[TipoAlerta, str] = {
    TipoAlerta.RECIBO_DE_OTRA_PERSONA: "Los recibos son de una persona que no está en el legajo",
    TipoAlerta.CUIL_NO_CORRESPONDE_AL_DNI: "El CUIL de los recibos no corresponde al DNI",
    TipoAlerta.RECIBO_VIEJO: "El último recibo es de hace más de "
    f"{3} meses",  # ANTIGUEDAD_MAXIMA_RECIBO_MESES, abajo
    TipoAlerta.NETO_NO_CIERRA: "El neto no es el bruto menos los descuentos",
}

# Las que ya se inyectan (pasos 6.1 y 6.2). Las demás llegan en 6.3.
IMPLEMENTADAS = frozenset(
    {
        Inconsistencia.RECIBO_DE_OTRA_PERSONA,
        Inconsistencia.CUIL_NO_CORRESPONDE_AL_DNI,
        Inconsistencia.RECIBO_VIEJO,
        Inconsistencia.NETO_NO_CIERRA,
        Inconsistencia.INGRESO_INSUFICIENTE,
        Inconsistencia.DOCUMENTO_FALTANTE,
    }
)

# Las que rompen los recibos de un inquilino.
DE_RECIBOS = frozenset(
    {
        Inconsistencia.RECIBO_DE_OTRA_PERSONA,
        Inconsistencia.CUIL_NO_CORRESPONDE_AL_DNI,
        Inconsistencia.RECIBO_VIEJO,
        Inconsistencia.NETO_NO_CIERRA,
        Inconsistencia.INGRESO_INSUFICIENTE,
    }
)

# Regla fija del generador (en la Fase 5 llega con los requisitos): el último recibo tiene
# que ser de hace a lo sumo 3 meses. El normal es el del mes anterior a la firma (1 mes).
ANTIGUEDAD_MAXIMA_RECIBO_MESES = 3
# Meses recientes que se saltean en un recibo viejo: el último queda de hace 5 a 11 meses.
DESFASE_VIEJO = (4, 10)
# Ingreso insuficiente: alquiler / neto de cada inquilino, multiplicado por la cantidad de
# inquilinos. Con n inquilinos, cada neto queda por debajo de 3 alquileres / (1,08 n), y la
# suma, por debajo de 2,78 alquileres: no alcanza nunca.
ALQUILER_SOBRE_NETO_INSUFICIENTE = (0.36, 0.50)

# Probabilidad de cada una por legajo. Con 9 sorteos independientes a 0,06, cerca del 57 %
# de los legajos sale sin ninguna (0,94⁹): el set sorteado sigue siendo mayormente sano.
# El orden importa: elegir_inconsistencias recorre este dict, así que una nueva va al final.
P_INCONSISTENCIA: dict[Inconsistencia, float] = dict.fromkeys(Inconsistencia, 0.06)


def es_aplicable(inconsistencia: Inconsistencia, contexto: ContextoLegajo) -> bool:
    """Si la inconsistencia puede darse en este legajo (ej. sin garantes no hay título)."""
    garantes = contexto.partes(Rol.GARANTE)
    if inconsistencia == Inconsistencia.TITULAR_NO_ES_GARANTE:
        return bool(garantes)
    if inconsistencia == Inconsistencia.CAUCION_MAS_CORTA_QUE_EL_PLAZO:
        return CasoDificil.SEGURO_DE_CAUCION in contexto.casos
    return True


def elegir_inconsistencias(contexto: ContextoLegajo) -> list[Inconsistencia]:
    """Las que le tocan a este legajo (set sorteado), solo entre las implementadas y
    aplicables, en el orden del enum."""
    source = Source(contexto.seed).derive("inconsistencias")
    elegidas = []
    for inconsistencia, p in P_INCONSISTENCIA.items():
        # Se sortea siempre, aunque no aplique: así agregar una no corre las demás.
        sale = source.rng.random() < p
        if sale and inconsistencia in IMPLEMENTADAS and es_aplicable(inconsistencia, contexto):
            elegidas.append(inconsistencia)
    return compatibles(elegidas)


def compatibles(inconsistencias: list[Inconsistencia]) -> list[Inconsistencia]:
    """Las que se pueden inyectar juntas, en el orden del enum y sin repetidas.

    Con los recibos de otra persona, el CUIL ya es ajeno: se inyecta solo la primera, y se
    registra solo esa (la etiqueta tiene que coincidir con la alerta esperada).
    """
    elegidas = [i for i in Inconsistencia if i in inconsistencias]
    if Inconsistencia.RECIBO_DE_OTRA_PERSONA in elegidas:
        elegidas = [i for i in elegidas if i != Inconsistencia.CUIL_NO_CORRESPONDE_AL_DNI]
    return elegidas


# --- recibos (paso 6.2) ---


def otra_persona(source: Source) -> tuple[str, str]:
    """Empleado y CUIL de alguien que no está en el legajo (ej. la pareja del inquilino)."""
    sexo = source.rng.choice(list(Sexo))
    fake = source.fake
    nombre = fake.first_name_male() if sexo == Sexo.M else fake.first_name_female()
    return f"{fake.last_name()}, {nombre}".upper(), cuit_from_dni(generate_dni(source.rng), sexo)


def cuil_ajeno(propio: str, source: Source) -> str:
    """Un CUIL válido (con su dígito verificador) que no es el propio: el de otro DNI."""
    sexo = Sexo.M if propio.startswith("20") else Sexo.F
    while True:
        cuil = cuit_from_dni(generate_dni(source.rng), sexo)
        if cuil != propio:
            return cuil


def correr_neto(recibo: ReciboSueldo, source: Source) -> ReciboSueldo:
    """Inconsistencia NETO_NO_CIERRA: el mismo recibo con un neto que no es bruto - descuentos.

    El bruto y los descuentos no cambian: el error está solo en el neto impreso.
    """
    # Se simula el error más útil para Avisa: el neto inflado (un recibo adulterado para
    # mostrar más ingreso), entre 5 % y 30 % hacia arriba. El rango no incluye el 1: el neto
    # siempre cambia.
    factor = Decimal(str(round(source.rng.uniform(1.05, 1.30), 3)))
    return recibo.model_copy(update={"neto": _centavos((recibo.neto or Decimal(0)) * factor)})


@dataclass(frozen=True)
class PlanRecibos:
    """Qué se le rompe a los recibos de un inquilino. Con los valores por defecto, nada."""

    desfase: int = 0
    rango: tuple[float, float] = ALQUILER_SOBRE_NETO
    empleado: tuple[str, str] | None = None  # (empleado, CUIL) de otra persona
    cuil: str | None = None  # CUIL ajeno
    mes_neto: int | None = None  # recibo con el neto corrido (0 es el más reciente)
    alertas: tuple[TipoAlerta, ...] = ()  # las de todos sus recibos
    seed: int = 0

    def ajustar(self, k: int, recibo: ReciboSueldo) -> ReciboSueldo:
        if self.empleado is not None:
            empleado, cuil = self.empleado
            recibo = recibo.model_copy(update={"empleado": empleado, "empleado_cuil": cuil})
        if self.cuil is not None:
            recibo = recibo.model_copy(update={"empleado_cuil": self.cuil})
        if k == self.mes_neto:
            recibo = correr_neto(recibo, Source(self.seed).derive(f"neto:{k}"))
        return recibo

    def alertas_del_mes(self, k: int) -> tuple[TipoAlerta, ...]:
        if k == self.mes_neto:
            return (*self.alertas, TipoAlerta.NETO_NO_CIERRA)
        return self.alertas


def objetivo_recibos(contexto: ContextoLegajo) -> UUID:
    """El inquilino al que se le rompen los recibos (siempre uno, el mismo para todas)."""
    inquilinos = contexto.partes(Rol.INQUILINO)
    return Source(contexto.seed).derive("objetivo_recibos").rng.choice(inquilinos).id


def plan_recibos(
    inconsistencias: list[Inconsistencia], contexto: ContextoLegajo, persona_id: UUID
) -> PlanRecibos:
    """El plan para los recibos de un inquilino según las inconsistencias del legajo.

    El ingreso insuficiente baja el sueldo de todos los inquilinos (lo que no alcanza es la
    suma); las demás rompen solo los recibos del objetivo.
    """
    n = len(contexto.partes(Rol.INQUILINO))
    rango = ALQUILER_SOBRE_NETO
    if Inconsistencia.INGRESO_INSUFICIENTE in inconsistencias:
        rango = (ALQUILER_SOBRE_NETO_INSUFICIENTE[0] * n, ALQUILER_SOBRE_NETO_INSUFICIENTE[1] * n)
    if persona_id != objetivo_recibos(contexto):
        return PlanRecibos(rango=rango)

    source = Source(contexto.seed).derive(f"plan_recibos:{persona_id}")
    rng = source.rng
    identidad = contexto.identidades[persona_id]
    propio = cuit_from_dni(identidad.persona.dni or "", identidad.sexo)
    plan: dict = {"rango": rango, "seed": contexto.seed}
    alertas: list[TipoAlerta] = []
    if Inconsistencia.RECIBO_DE_OTRA_PERSONA in inconsistencias:
        plan["empleado"] = otra_persona(source.derive("otra_persona"))
        alertas.append(TipoAlerta.RECIBO_DE_OTRA_PERSONA)
    elif Inconsistencia.CUIL_NO_CORRESPONDE_AL_DNI in inconsistencias:  # ver compatibles
        plan["cuil"] = cuil_ajeno(propio, source.derive("cuil"))
        alertas.append(TipoAlerta.CUIL_NO_CORRESPONDE_AL_DNI)
    if Inconsistencia.RECIBO_VIEJO in inconsistencias:
        plan["desfase"] = rng.randint(*DESFASE_VIEJO)
        alertas.append(TipoAlerta.RECIBO_VIEJO)
    if Inconsistencia.NETO_NO_CIERRA in inconsistencias:
        plan["mes_neto"] = rng.randrange(3)
    return PlanRecibos(alertas=tuple(alertas), **plan)
