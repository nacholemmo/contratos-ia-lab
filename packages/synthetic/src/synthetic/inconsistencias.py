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

from enum import StrEnum

from core.legajo import TipoAlerta
from core.models import Rol
from synthetic.cases import CasoDificil
from synthetic.legajo import ContextoLegajo
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

# Las que ya se inyectan (paso 6.1). Las demás llegan en 6.2 y 6.3.
IMPLEMENTADAS = frozenset({Inconsistencia.DOCUMENTO_FALTANTE})

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
    return elegidas
