"""Cláusulas del contrato renderizadas con Jinja2, con los fragmentos que respaldan cada dato.

Cada cláusula se renderiza por separado y guarda en `fragmentos` el texto literal de
cada dato del `Contrato` que contiene. En el paso 3, al armar el PDF, se le suma la
página y eso es la evidencia del ground truth.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal

from jinja2 import Environment, StrictUndefined

from core.models import Contrato, Moneda, Persona, RegimenLegal, Rol, TipoPropiedad
from synthetic.amounts import EstiloMonto, format_monto
from synthetic.cases import CasoDificil, DatosCaucion
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
        "con destino exclusivo de {{ destino }}.",
        "El objeto del presente es {{ propiedad }}, que LA PARTE LOCATARIA recibe en "
        "buen estado de conservación y destinará a {{ destino }}.",
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
    "inventario": (
        "El inmueble se entrega con los elementos que se detallan a continuación, que LA "
        "PARTE LOCATARIA declara recibir de plena conformidad: {{ items }}.",
        "Se deja constancia de que el inmueble cuenta con los siguientes elementos, que LA "
        "PARTE LOCATARIA se obliga a restituir en el mismo estado: {{ items }}.",
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

# Caso CANON_ESCALONADO: el monto de cada año va en la cláusula de precio y la de ajuste
# aclara que no hay otro. El fragmento de `monto_inicial` es el del primer año.
PLANTILLAS_PRECIO_ESCALONADO: tuple[str, ...] = (
    "El precio de la locación se pacta en forma escalonada: {{ escalones }}, pagaderos "
    "por mes adelantado del 1 al 10 de cada mes.",
    "LA PARTE LOCATARIA abonará un alquiler mensual escalonado, de la siguiente manera: "
    "{{ escalones }}, dentro de los primeros diez días de cada período.",
)
AJUSTE_ESCALONADO: tuple[str, ...] = (
    "no estará sujeto a otra actualización que la de los montos escalonados pactados",
    "quedará fijado según la escala de la cláusula de precio, sin aplicar índice alguno",
)
ANIOS = ("primer", "segundo", "tercer", "cuarto", "quinto")
# Aumento de un año al siguiente en un canon escalonado: aproximado, con la inflación de 2024-26.
AUMENTO_ESCALONADO = (0.25, 0.70)

# Caso SEGURO_DE_CAUCION: aseguradora y póliza vienen de `datos_caucion` (cases.py).
PLANTILLAS_CAUCION: tuple[str, ...] = (
    "LA PARTE LOCATARIA garantiza el cumplimiento de todas sus obligaciones mediante un "
    "seguro de caución emitido por {{ aseguradora }}, póliza N° {{ poliza }}, cuyo original "
    "se agrega al presente.",
    "En garantía de las obligaciones asumidas, LA PARTE LOCATARIA contrata a favor de LA "
    "PARTE LOCADORA un seguro de caución con {{ aseguradora }} (póliza N° {{ poliza }}), "
    "que deberá mantener vigente durante toda la locación.",
)
# Caso CLAUSULA_LARGA: un inventario que no entra en una página.
AMBIENTES = (
    "la cocina",
    "el living comedor",
    "el dormitorio principal",
    "el segundo dormitorio",
    "el baño",
    "el lavadero",
    "el balcón",
    "el pasillo",
)
ELEMENTOS = (
    "una mesada de granito",
    "una bacha de acero inoxidable",
    "un anafe de cuatro hornallas",
    "un horno eléctrico empotrado",
    "una alacena de melamina blanca",
    "un calefactor tiro balanceado",
    "dos ventanas con cortinas de enrollar",
    "una puerta placa con cerradura de doble paleta",
    "un placard de tres cuerpos con estantes",
    "un espejo con botiquín",
    "una ducha con mampara de vidrio",
    "un termotanque a gas de ochenta litros",
    "seis luminarias de techo con lámparas",
    "una canilla monocomando",
    "un aire acondicionado split frío/calor",
    "un portero eléctrico con frente de calle",
    "una llave de paso de gas",
    "tres tomacorrientes dobles",
)
ESTADOS = (
    "en buen estado",
    "en perfecto estado de funcionamiento",
    "con desgaste por uso normal",
    "a nuevo",
)
# Con letra 11 entran unas 3.600 letras por página: 5.000 aseguran que la cláusula la supere.
LARGO_MIN_INVENTARIO = 5_000

# Caso GUIONES_DE_RELLENO: guiones al final del párrafo para que no se agregue texto después.
GUIONES = (8, 30)

# Destino según el tipo de inmueble; los demás tipos van a vivienda.
DESTINO_POR_TIPO = {
    TipoPropiedad.LOCAL: "uso comercial",
    TipoPropiedad.OFICINA: "oficina de uso profesional",
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
    "inventario": "INVENTARIO",
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


def _persona(source: Source, p: Persona) -> str:
    # Sin DNI ni CUIT (caso difícil) queda solo el nombre, sin una coma colgando.
    documento = frase_documento(source, p.dni, p.cuit)
    return f"{p.nombre}, {documento}" if documento else p.nombre


def _personas(source: Source, personas: list[Persona]) -> str:
    return " y ".join(_persona(source, p) for p in personas)


def _render(source: Source, plantillas: tuple[str, ...], **variables: object) -> str:
    plantilla = source.rng.choice(plantillas)
    return ENV.from_string(plantilla).render(**variables)


def _estilo_monto(source: Source, solo_letras: bool) -> EstiloMonto:
    if solo_letras:
        return EstiloMonto.LETRAS
    return source.rng.choices(list(EstiloMonto), weights=[0.3, 0.2, 0.5])[0]


def escalones(
    monto_inicial: Decimal, moneda: Moneda, plazo_meses: int, source: Source
) -> list[Decimal]:
    """Alquiler mensual de cada año de un canon escalonado; el primero es `monto_inicial`.

    Redondeado como se escribe en un contrato: a miles en pesos y a decenas en dólares.
    """
    redondeo = Decimal(1_000) if moneda == Moneda.ARS else Decimal(10)
    montos = [monto_inicial]
    for _ in range(plazo_meses // 12 - 1):
        aumento = Decimal(str(round(source.rng.uniform(*AUMENTO_ESCALONADO), 2)))
        siguiente = montos[-1] * (1 + aumento)
        montos.append((siguiente / redondeo).quantize(Decimal(1)) * redondeo)
    return montos


def _inventario(source: Source) -> str:
    items: list[str] = []
    while len("; ".join(items)) < LARGO_MIN_INVENTARIO:
        elemento, ambiente = source.rng.choice(ELEMENTOS), source.rng.choice(AMBIENTES)
        items.append(f"({len(items) + 1}) {elemento} en {ambiente}, {source.rng.choice(ESTADOS)}")
    return "; ".join(items)


def render_clauses(
    contrato: Contrato,
    source: Source,
    casos: Sequence[CasoDificil] = (),
    caucion: DatosCaucion | None = None,
) -> list[Clause]:
    """Cláusulas del contrato en orden, con variantes elegidas por `source`.

    `casos` cambia la forma del texto (montos en letras, guiones, cláusulas raras). Los
    datos del contrato ya vienen con los casos aplicados (`aplicar_casos`). `caucion` es
    obligatorio con el caso SEGURO_DE_CAUCION: la póliza del legajo repite esos datos.
    """
    c = contrato
    solo_letras = CasoDificil.MONTOS_SOLO_LETRAS in casos
    escalonado = CasoDificil.CANON_ESCALONADO in casos
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
    destino = DESTINO_POR_TIPO.get(c.propiedad.tipo, "vivienda")
    cuerpo.append(
        ("objeto", {"propiedad": propiedad, "destino": destino}, {"propiedad": propiedad})
    )

    plazo = frase_plazo(source, c.plazo_meses)
    inicio = frase_fecha(source, c.fecha_inicio)
    cuerpo.append(
        (
            "plazo",
            {"plazo": plazo, "fecha_inicio": inicio},
            {"plazo_meses": plazo, "fecha_inicio": inicio},
        )
    )

    if escalonado:
        montos = escalones(c.monto_inicial, c.moneda, c.plazo_meses, source.derive("escalones"))
        periodo = source.rng.choice(
            (
                lambda i: f"durante el {ANIOS[i]} año",
                lambda i: f"del mes {12 * i + 1} al mes {12 * (i + 1)}",
            )
        )
        tramos = [
            f"{periodo(i)}, {format_monto(m, c.moneda, _estilo_monto(source, solo_letras))} "
            "mensuales"
            for i, m in enumerate(montos)
        ]
        texto_escalones = "; ".join(tramos)
        primero = tramos[0]
        cuerpo.append(
            (
                "precio",
                {"escalones": texto_escalones},
                {"monto_inicial": primero, "moneda": primero},
            )
        )
        ajuste = source.rng.choice(AJUSTE_ESCALONADO)
    else:
        monto = format_monto(c.monto_inicial, c.moneda, _estilo_monto(source, solo_letras))
        cuerpo.append(("precio", {"monto": monto}, {"monto_inicial": monto, "moneda": monto}))
        ajuste = frase_ajuste(source, c.indice, c.frecuencia_ajuste_meses)
    fragmentos_ajuste = {"indice": ajuste}
    if c.frecuencia_ajuste_meses is not None:
        fragmentos_ajuste["frecuencia_ajuste_meses"] = ajuste
    cuerpo.append(("ajuste", {"ajuste": ajuste}, fragmentos_ajuste))

    if c.deposito is not None:
        deposito = format_monto(c.deposito, c.moneda, _estilo_monto(source, solo_letras))
        cuerpo.append(("deposito", {"deposito": deposito}, {"deposito": deposito}))

    garantes = por_rol[Rol.GARANTE]
    if CasoDificil.SEGURO_DE_CAUCION in casos:
        if caucion is None:
            raise ValueError("el caso SEGURO_DE_CAUCION necesita los datos de la caución")
        variables = {"aseguradora": caucion.aseguradora, "poliza": caucion.poliza}
        cuerpo.append(("garantia", variables, {}))
    elif garantes:
        variables = {"garantes": _personas(source, garantes), "plural": len(garantes) > 1}
        cuerpo.append(("garantia", variables, {}))

    cuerpo.append(("expensas", {}, {}))
    cuerpo.append(("conservacion", {}, {}))
    if CasoDificil.CLAUSULA_LARGA in casos:
        cuerpo.append(("inventario", {"items": _inventario(source)}, {}))
    cuerpo.append(("prohibiciones", {}, {}))
    cuerpo.append(("rescision", {}, {}))
    tribunales = frase_tribunales(c.propiedad.localidad, c.propiedad.provincia)
    cuerpo.append(("jurisdiccion", {"tribunales": tribunales}, {}))

    # Cláusulas cuyo texto legal depende del contrato (no solo la forma).
    por_contrato = {"rescision": PLANTILLAS_RESCISION[c.regimen_legal]}
    if escalonado:
        por_contrato["precio"] = PLANTILLAS_PRECIO_ESCALONADO
    if CasoDificil.SEGURO_DE_CAUCION in casos:
        por_contrato["garantia"] = PLANTILLAS_CAUCION

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
    if CasoDificil.GUIONES_DE_RELLENO in casos:
        # Al final del párrafo: los fragmentos de evidencia siguen apareciendo literales.
        clauses = [
            replace(clause, texto=clause.texto + "-" * source.rng.randint(*GUIONES))
            for clause in clauses
        ]
    return clauses
