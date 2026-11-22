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
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from core.legajo import TipoAlerta
from core.models import DNI, PolizaCaucion, ReciboSueldo, Rol, Sexo, TituloPropiedad
from synthetic.cases import CasoDificil, es_aplicable as caso_aplicable
from synthetic.contracts import generate_contrato
from synthetic.dni import VIGENCIA_DNI_ANIOS, sumar_anios
from synthetic.identity import cuit_from_dni, generate_dni
from synthetic.legajo import ContextoLegajo, contexto_legajo, sumar_meses
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
    TipoAlerta.RECIBO_VIEJO: "El último recibo es de hace más de 3 meses",
    TipoAlerta.NETO_NO_CIERRA: "El neto no es el bruto menos los descuentos",
    TipoAlerta.DNI_VENCIDO: "El DNI está vencido",
    TipoAlerta.TITULAR_NO_ES_GARANTE: "El titular del inmueble no es el garante",
    TipoAlerta.CAUCION_MAS_CORTA_QUE_EL_PLAZO: "La caución vence antes que el contrato",
}

# Regla fija del generador (en la Fase 5 llega con los requisitos): el último recibo tiene
# que ser de hace a lo sumo 3 meses. El normal es el del mes anterior a la firma (1 mes).
ANTIGUEDAD_MAXIMA_RECIBO_MESES = 3
# Meses recientes que se saltean en un recibo viejo: el último queda de hace 5 a 11 meses.
DESFASE_VIEJO = (4, 10)
# Ingreso insuficiente: alquiler / neto de cada inquilino, multiplicado por la cantidad de
# inquilinos. Con n inquilinos, cada neto queda por debajo de 3 alquileres / (1,08 n), y la
# suma, por debajo de 2,78 alquileres: no alcanza nunca.
ALQUILER_SOBRE_NETO_INSUFICIENTE = (0.36, 0.50)
# DNI vencido: venció entre 1 mes y 3 años antes de la fecha del legajo.
VENCIDO_HACE_DIAS = (30, 3 * 365)
# Caución corta: vence entre 1 y 12 meses antes del fin del contrato.
CAUCION_CORTA_MESES = (1, 12)

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
    """Las que le tocan a este legajo (set sorteado), solo entre las aplicables, en el orden
    del enum."""
    source = Source(contexto.seed).derive("inconsistencias")
    elegidas = []
    for inconsistencia, p in P_INCONSISTENCIA.items():
        # Se sortea siempre, aunque no aplique: así agregar una no corre las demás.
        sale = source.rng.random() < p
        if sale and es_aplicable(inconsistencia, contexto):
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


@dataclass(frozen=True)
class PersonaAjena:
    """Alguien que no está en el legajo (la pareja del inquilino, un familiar del garante)."""

    nombre: str
    apellido: str
    dni: str
    sexo: Sexo


def persona_ajena(source: Source) -> PersonaAjena:
    sexo = source.rng.choice([Sexo.M, Sexo.F])
    fake = source.fake
    nombre = fake.first_name_male() if sexo == Sexo.M else fake.first_name_female()
    return PersonaAjena(nombre, fake.last_name(), generate_dni(source.rng), sexo)


def otra_persona(source: Source) -> tuple[str, str]:
    """Empleado y CUIL de alguien que no está en el legajo, como figuran en un recibo."""
    p = persona_ajena(source)
    return f"{p.apellido}, {p.nombre}".upper(), cuit_from_dni(p.dni, p.sexo)


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


# --- DNI, título y caución (paso 6.3) ---


def vencer_dni(dni: DNI, referencia: date, source: Source) -> DNI:
    """Inconsistencia DNI_VENCIDO: el mismo DNI, vencido a la fecha del legajo.

    Se corren la emisión y el vencimiento juntos (15 años de vigencia), para que el único
    dato que no cierre sea el vencimiento contra la fecha del legajo.
    """
    vencimiento = referencia - timedelta(days=source.rng.randint(*VENCIDO_HACE_DIAS))
    emision = sumar_anios(vencimiento, -VIGENCIA_DNI_ANIOS)
    return dni.model_copy(update={"fecha_emision": emision, "fecha_vencimiento": vencimiento})


def titulo_ajeno(titulo: TituloPropiedad, source: Source) -> TituloPropiedad:
    """Inconsistencia TITULAR_NO_ES_GARANTE: el título de un inmueble de otra persona."""
    p = persona_ajena(source)
    return titulo.model_copy(
        update={"titular": f"{p.nombre} {p.apellido.upper()}", "titular_dni": p.dni}
    )


def acortar_caucion(poliza: PolizaCaucion, source: Source) -> PolizaCaucion:
    """Inconsistencia CAUCION_MAS_CORTA_QUE_EL_PLAZO: la póliza vence antes que el contrato.

    Siempre después del inicio: una póliza que vence antes de empezar no sería creíble.
    """
    hasta = poliza.vigencia_hasta
    desde = poliza.vigencia_desde
    if hasta is None or desde is None:
        raise ValueError("la caución no tiene vigencia")
    corta = sumar_meses(hasta, -source.rng.randint(*CAUCION_CORTA_MESES))
    return poliza.model_copy(update={"vigencia_hasta": max(corta, desde + timedelta(days=30))})


def objetivo_dni(contexto: ContextoLegajo) -> UUID:
    """La persona (inquilino o garante) cuyo DNI está vencido."""
    partes = contexto.partes(Rol.INQUILINO) + contexto.partes(Rol.GARANTE)
    return Source(contexto.seed).derive("objetivo_dni").rng.choice(partes).id


def objetivo_titulo(contexto: ContextoLegajo) -> UUID:
    """El garante cuyo título es de otra persona."""
    garantes = contexto.partes(Rol.GARANTE)
    return Source(contexto.seed).derive("objetivo_titulo").rng.choice(garantes).id


# --- set forzado ---

# Casos difíciles que una inconsistencia necesita para darse (la caución corta necesita
# caución). El set forzado los pide; en el sorteado, `es_aplicable` deja afuera el resto.
CASOS_NECESARIOS: dict[Inconsistencia, list[CasoDificil]] = {
    Inconsistencia.CAUCION_MAS_CORTA_QUE_EL_PLAZO: [CasoDificil.SEGURO_DE_CAUCION],
}

MAX_BUSQUEDA = 1_000


def semillas_forzadas(inconsistencia: Inconsistencia, desde: int, cantidad: int) -> list[int]:
    """Las primeras `cantidad` semillas desde `desde` donde la inconsistencia puede darse,
    con los casos que necesita (`CASOS_NECESARIOS`)."""
    casos = CASOS_NECESARIOS.get(inconsistencia, [])
    semillas: list[int] = []
    for seed in range(desde, desde + MAX_BUSQUEDA):
        if len(semillas) == cantidad:
            break
        # El caso tiene que poder darse en el contrato (ej. la caución necesita garantes).
        if all(caso_aplicable(c, generate_contrato(seed)) for c in casos) and es_aplicable(
            inconsistencia, contexto_legajo(seed, casos)
        ):
            semillas.append(seed)
    if len(semillas) < cantidad:
        raise ValueError(f"{inconsistencia}: solo {len(semillas)} semillas en {MAX_BUSQUEDA}")
    return semillas
