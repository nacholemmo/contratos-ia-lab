"""Cláusulas del contrato renderizadas con Jinja2, con los fragmentos que respaldan cada dato.

Cada cláusula se renderiza por separado y guarda en `fragmentos` el texto literal de
cada dato del `Contrato` que contiene. En el paso 3, al armar el PDF, se le suma la
página y eso es la evidencia del ground truth.
"""

from dataclasses import dataclass, field

from jinja2 import Environment, StrictUndefined

from core.models import Contrato, Persona, RegimenLegal, Rol
from synthetic.amounts import EstiloMonto, format_monto
from synthetic.source import Source
from synthetic.wording import (
    frase_ajuste,
    frase_documento,
    frase_fecha,
    frase_fecha_cierre,
    frase_plazo,
    frase_propiedad,
    frase_tribunales,
)

# StrictUndefined: una variable mal escrita en una plantilla falla en vez de quedar vacía.
# Sin autoescape: el resultado es texto plano, no HTML.
ENV = Environment(undefined=StrictUndefined, autoescape=False)

# Probabilidad de que la fecha de firma vaya al cierre y no al encabezado (estilo del
# modelo de Mendoza: "a los … días del mes de …").
P_FECHA_EN_CIERRE = 0.4

ORDINALES = (
    "PRIMERA",
    "SEGUNDA",
    "TERCERA",
    "CUARTA",
    "QUINTA",
    "SEXTA",
    "SÉPTIMA",
    "OCTAVA",
    "NOVENA",
    "DÉCIMA",
    "UNDÉCIMA",
    "DUODÉCIMA",
)

# Variantes por cláusula. Las variables son los fragmentos ya redactados en wording.py.
PLANTILLAS: dict[str, tuple[str, ...]] = {
    "encabezado": (
        "En {{ localidad }}, el {{ fecha_firma }}, entre {{ locadores }}, en adelante "
        "LA PARTE LOCADORA, por una parte, y {{ locatarios }}, en adelante LA PARTE "
        "LOCATARIA, por la otra, convienen celebrar el presente contrato de locación, "
        "sujeto a las siguientes cláusulas:",
        "CONTRATO DE LOCACIÓN. Entre {{ locadores }} (LOCADOR/A) y {{ locatarios }} "
        "(LOCATARIO/A), se celebra el presente contrato el {{ fecha_firma }} en "
        "{{ localidad }}, que se regirá por las cláusulas que siguen.",
    ),
    # Si la fecha de firma va al cierre ("a los … días del mes de …"), el encabezado no la lleva.
    "encabezado_sin_fecha": (
        "En {{ localidad }}, entre {{ locadores }}, en adelante LA PARTE LOCADORA, por una "
        "parte, y {{ locatarios }}, en adelante LA PARTE LOCATARIA, por la otra, convienen "
        "celebrar el presente contrato de locación, sujeto a las siguientes cláusulas:",
        "Entre {{ locadores }}, en adelante EL LOCADOR, y {{ locatarios }}, en adelante EL "
        "LOCATARIO, se conviene celebrar el presente contrato de locación, que se regirá por "
        "las cláusulas siguientes:",
    ),
    "cierre": (
        "En prueba de conformidad, se firman dos (2) ejemplares de un mismo tenor y a un solo "
        "efecto, en {{ localidad }}, {{ fecha_firma }}.",
        "Leído y ratificado, las partes firman dos (2) ejemplares de un mismo tenor en "
        "{{ localidad }}, {{ fecha_firma }}.",
    ),
    "cierre_sin_fecha": (
        "En prueba de conformidad, se firman dos (2) ejemplares de un mismo tenor y a un solo "
        "efecto.",
        "Leído y ratificado, las partes firman dos (2) ejemplares de un mismo tenor y a un "
        "solo efecto.",
    ),
    "objeto": (
        "LA PARTE LOCADORA da en locación a LA PARTE LOCATARIA {{ propiedad }}, "
        "con destino exclusivo de vivienda.",
        "El objeto del presente es {{ propiedad }}, que LA PARTE LOCATARIA recibe en "
        "buen estado de conservación y destinará a vivienda familiar.",
    ),
    "plazo": (
        "El plazo de la locación se pacta en {{ plazo }}, a partir del {{ fecha_inicio }}.",
        "La locación tendrá vigencia desde el {{ fecha_inicio }} y por el término de "
        "{{ plazo }}, venciendo de pleno derecho sin necesidad de interpelación alguna.",
    ),
    "precio": (
        "El precio de la locación se fija en la suma de {{ monto }} mensuales, pagaderos "
        "por adelantado del 1 al 10 de cada mes.",
        "LA PARTE LOCATARIA abonará un alquiler mensual de {{ monto }}, por mes adelantado, "
        "dentro de los primeros diez días de cada período.",
    ),
    "ajuste": (
        "El precio {{ ajuste }}.",
        "Las partes acuerdan que el canon locativo {{ ajuste }}.",
    ),
    "deposito": (
        "En garantía del cumplimiento de sus obligaciones, LA PARTE LOCATARIA entrega en "
        "este acto la suma de {{ deposito }}, que le será restituida al finalizar la locación.",
        "Se deja constancia de que LA PARTE LOCATARIA entrega en concepto de depósito en "
        "garantía {{ deposito }}, sirviendo el presente de suficiente recibo.",
    ),
    "garantia": (
        "{{ garantes }} se constituye{{ 'n' if plural }} en fiador{{ 'es' if plural }} "
        "solidario{{ 's' if plural }}, liso{{ 's' if plural }} y llano{{ 's' if plural }} "
        "pagador{{ 'es' if plural }} de todas las obligaciones de LA PARTE LOCATARIA.",
    ),
    "expensas": (
        "Las expensas ordinarias estarán a cargo de LA PARTE LOCATARIA; las extraordinarias, "
        "a cargo de LA PARTE LOCADORA.",
        "Serán a cargo de LA PARTE LOCATARIA los servicios de luz, gas, agua y las expensas "
        "comunes ordinarias. Las expensas extraordinarias corresponden a LA PARTE LOCADORA.",
    ),
    "conservacion": (
        "LA PARTE LOCATARIA se obliga a mantener el inmueble en el estado en que lo recibe, "
        "siendo a su cargo las reparaciones originadas en el uso normal. Las reparaciones "
        "que no sean consecuencia del uso estarán a cargo de LA PARTE LOCADORA.",
        "Las mejoras que LA PARTE LOCATARIA introduzca quedarán en beneficio del inmueble, "
        "sin derecho a reclamo alguno. Toda reparación urgente deberá ser comunicada a LA "
        "PARTE LOCADORA dentro de las cuarenta y ocho (48) horas de advertida.",
    ),
    "prohibiciones": (
        "Queda prohibido a LA PARTE LOCATARIA ceder el presente contrato, subarrendar total "
        "o parcialmente el inmueble o darle un destino distinto del pactado.",
        "LA PARTE LOCATARIA no podrá subalquilar, ceder ni prestar el inmueble, ni "
        "introducir en él sustancias peligrosas o actividades que perturben a los vecinos.",
    ),
    "jurisdiccion": (
        "Para todos los efectos legales, las partes constituyen domicilio en los indicados en "
        "el encabezado y se someten a la jurisdicción de {{ tribunales }}, renunciando a "
        "cualquier otro fuero.",
        "Las partes fijan domicilios especiales en los denunciados en el presente, donde serán "
        "válidas todas las notificaciones, y se someten a {{ tribunales }}.",
    ),
}

# La rescisión cambia de contenido según el régimen, no solo de forma (art. 1221 del CCyC).
# Leyes 27.551 y 27.737: desde los 6 meses, con indemnización salvo preaviso de 3 meses.
RESCISION_LEY: tuple[str, ...] = (
    "Transcurridos los primeros seis (6) meses, LA PARTE LOCATARIA podrá resolver "
    "anticipadamente la locación, abonando un mes y medio de alquiler si lo hace durante el "
    "primer año y un mes si lo hace después. No corresponderá indemnización si notifica "
    "con una anticipación de tres (3) meses o más.",
    "LA PARTE LOCATARIA podrá rescindir el contrato una vez cumplidos seis (6) meses de "
    "vigencia, notificando en forma fehaciente. Deberá abonar en concepto de indemnización "
    "un mes y medio de alquiler en el primer año y un mes a partir del segundo, salvo que "
    "el preaviso sea de tres (3) meses o más.",
)
# DNU 70/2023: en cualquier momento, pagando el 10 % del canon que falta hasta el final.
RESCISION_DNU: tuple[str, ...] = (
    "LA PARTE LOCATARIA podrá resolver anticipadamente la locación en cualquier momento, "
    "abonando el equivalente al diez por ciento (10%) del saldo del canon locativo futuro, "
    "calculado desde la notificación hasta la fecha de finalización pactada.",
    "En cualquier momento de la vigencia, LA PARTE LOCATARIA podrá rescindir el presente "
    "contrato, debiendo pagar una indemnización del diez por ciento (10%) del saldo de los "
    "alquileres que restan hasta el vencimiento.",
)

PLANTILLAS_RESCISION: dict[RegimenLegal, tuple[str, ...]] = {
    RegimenLegal.LEY_27551: RESCISION_LEY,
    RegimenLegal.LEY_27737: RESCISION_LEY,
    RegimenLegal.DNU_70_2023: RESCISION_DNU,
}

TITULOS = {
    "objeto": "OBJETO",
    "plazo": "PLAZO",
    "precio": "PRECIO",
    "ajuste": "ACTUALIZACIÓN",
    "deposito": "DEPÓSITO EN GARANTÍA",
    "garantia": "GARANTÍA",
    "expensas": "EXPENSAS Y SERVICIOS",
    "conservacion": "CONSERVACIÓN Y REPARACIONES",
    "prohibiciones": "PROHIBICIONES",
    "rescision": "RESCISIÓN",
    "jurisdiccion": "DOMICILIOS Y JURISDICCIÓN",
}


@dataclass(frozen=True)
class Clause:
    """Una cláusula renderizada. `fragmentos` mapea campo del Contrato → texto literal."""

    nombre: str
    titulo: str | None
    texto: str
    fragmentos: dict[str, str] = field(default_factory=dict)


def _personas(source: Source, personas: list[Persona]) -> str:
    return " y ".join(f"{p.nombre}, {frase_documento(source, p.dni, p.cuit)}" for p in personas)


def _render(source: Source, plantillas: tuple[str, ...], **variables: object) -> str:
    plantilla = source.rng.choice(plantillas)
    return ENV.from_string(plantilla).render(**variables)


def _estilo_monto(source: Source) -> EstiloMonto:
    return source.rng.choices(list(EstiloMonto), weights=[0.3, 0.2, 0.5])[0]


def render_clauses(contrato: Contrato, source: Source) -> list[Clause]:
    """Cláusulas del contrato en orden, con variantes elegidas por `source`."""
    c = contrato
    por_rol = {rol: [p for p in c.partes if p.rol == rol] for rol in Rol}
    numerar = source.rng.choice(
        (
            lambda i, t: f"{ORDINALES[i]}: {t}",
            lambda i, t: f"CLÁUSULA {i + 1} - {t}",
            lambda i, t: f"ARTÍCULO {i + 1}: {t}",
        )
    )

    # La fecha de firma va en el encabezado o en el cierre, nunca en los dos.
    fecha_encabezado = fecha_cierre = None
    if c.fecha_firma is not None:
        if source.rng.random() < P_FECHA_EN_CIERRE:
            fecha_cierre = frase_fecha_cierre(source, c.fecha_firma)
        else:
            fecha_encabezado = frase_fecha(source, c.fecha_firma)
    encabezado = _render(
        source,
        PLANTILLAS["encabezado_sin_fecha" if fecha_cierre else "encabezado"],
        localidad=c.propiedad.localidad,
        fecha_firma=fecha_encabezado or "____ de __________ de 20__",
        locadores=_personas(source, por_rol[Rol.PROPIETARIO]),
        locatarios=_personas(source, por_rol[Rol.INQUILINO]),
    )
    clauses = [
        Clause(
            "encabezado",
            None,
            encabezado,
            {"fecha_firma": fecha_encabezado} if fecha_encabezado else {},
        )
    ]

    # (nombre, variables para la plantilla, fragmentos que respaldan campos del Contrato)
    cuerpo: list[tuple[str, dict[str, object], dict[str, str]]] = []

    propiedad = frase_propiedad(source, c.propiedad)
    cuerpo.append(("objeto", {"propiedad": propiedad}, {"propiedad": propiedad}))

    plazo = frase_plazo(source, c.plazo_meses)
    inicio = frase_fecha(source, c.fecha_inicio)
    cuerpo.append(
        (
            "plazo",
            {"plazo": plazo, "fecha_inicio": inicio},
            {"plazo_meses": plazo, "fecha_inicio": inicio},
        )
    )

    monto = format_monto(c.monto_inicial, c.moneda, _estilo_monto(source))
    cuerpo.append(("precio", {"monto": monto}, {"monto_inicial": monto, "moneda": monto}))

    ajuste = frase_ajuste(source, c.indice, c.frecuencia_ajuste_meses)
    fragmentos_ajuste = {"indice": ajuste}
    if c.frecuencia_ajuste_meses is not None:
        fragmentos_ajuste["frecuencia_ajuste_meses"] = ajuste
    cuerpo.append(("ajuste", {"ajuste": ajuste}, fragmentos_ajuste))

    if c.deposito is not None:
        deposito = format_monto(c.deposito, c.moneda, _estilo_monto(source))
        cuerpo.append(("deposito", {"deposito": deposito}, {"deposito": deposito}))

    garantes = por_rol[Rol.GARANTE]
    if garantes:
        variables = {"garantes": _personas(source, garantes), "plural": len(garantes) > 1}
        cuerpo.append(("garantia", variables, {}))

    cuerpo.append(("expensas", {}, {}))
    cuerpo.append(("conservacion", {}, {}))
    cuerpo.append(("prohibiciones", {}, {}))
    cuerpo.append(("rescision", {}, {}))
    tribunales = frase_tribunales(c.propiedad.localidad, c.propiedad.provincia)
    cuerpo.append(("jurisdiccion", {"tribunales": tribunales}, {}))

    # Cláusulas cuyo texto legal depende del contrato (no solo la forma).
    por_contrato = {"rescision": PLANTILLAS_RESCISION[c.regimen_legal]}

    for i, (nombre, variables, fragmentos) in enumerate(cuerpo):
        plantillas = por_contrato[nombre] if nombre in por_contrato else PLANTILLAS[nombre]
        texto = _render(source, plantillas, **variables)
        clauses.append(Clause(nombre, numerar(i, TITULOS[nombre]), texto, fragmentos))

    cierre = _render(
        source,
        PLANTILLAS["cierre" if fecha_cierre else "cierre_sin_fecha"],
        localidad=c.propiedad.localidad,
        fecha_firma=fecha_cierre,
    )
    clauses.append(
        Clause("cierre", None, cierre, {"fecha_firma": fecha_cierre} if fecha_cierre else {})
    )
    return clauses
