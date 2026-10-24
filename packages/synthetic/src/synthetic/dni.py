"""Ficha sintética de DNI: los mismos datos que un DNI, con una presentación propia.

No imita el diseño oficial (sin escudo, colores, tipografía, holograma ni código de barras
de RENAPER): un DNI sintético con ese diseño sería un modelo de falsificación en un repo
público. Al extractor le alcanza con los datos, porque lo que aprende es a leer campos, no
a validar si un documento es auténtico.

Cada DNI sale de la `Identidad` de una parte del contrato (mismo número, nombre y sexo),
así el legajo es coherente y en la Fase 4 se pueden evaluar los cruces entre documentos.
"""

from datetime import date, timedelta
from uuid import UUID

from core.models import DNI, Evidencia, Sexo
from synthetic import fichas
from synthetic.cases import CasoDificil
from synthetic.contracts import LOCALIDADES, PESOS_PROVINCIA, Identidad
from synthetic.legajo import ContextoLegajo, contexto_legajo
from synthetic.source import Source

TITULO = "FICHA DE IDENTIDAD"
NACIONALIDAD = "ARGENTINA"

# La tarjeta del DNI de un adulto vence a los 15 años de emitida; la última actualización
# obligatoria es a los 14 años de edad.
VIGENCIA_DNI_ANIOS = 15
EDAD_ULTIMA_ACTUALIZACION = 14
# Edad de las partes a la fecha de firma: mayores de edad y un tope razonable.
EDAD_MIN = 18
EDAD_MAX = 80

# Probabilidad de que una parte viva en la provincia del inmueble que alquila.
P_MISMA_PROVINCIA = 0.85

# Meses abreviados en mayúsculas, como se imprimen en el DNI ("12 MAR 1985").
MESES_DNI = ("ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC")

ETIQUETAS = {
    "numero": "Documento",
    "apellido": "Apellido",
    "nombre": "Nombre",
    "sexo": "Sexo",
    "nacionalidad": "Nacionalidad",
    "fecha_nacimiento": "Fecha de nacimiento",
    "fecha_emision": "Fecha de emisión",
    "fecha_vencimiento": "Fecha de vencimiento",
    "domicilio": "Domicilio",
}

def sumar_anios(d: date, anios: int) -> date:
    """`d` corrida `anios` años (negativo: hacia atrás).

    Un 29 de febrero que cae en un año no bisiesto pasa al 1 de marzo si se avanza (el
    aniversario ya se cumplió) y al 28 de febrero si se retrocede.
    """
    try:
        return d.replace(year=d.year + anios)
    except ValueError:
        if anios > 0:
            return date(d.year + anios, 3, 1)
        return date(d.year + anios, 2, 28)


def _fecha_entre(source: Source, desde: date, hasta: date) -> date:
    """Fecha al azar entre `desde` y `hasta`, las dos incluidas."""
    return desde + timedelta(days=source.rng.randint(0, (hasta - desde).days))


def fechas_dni(source: Source, fecha_referencia: date) -> tuple[date, date, date]:
    """Nacimiento, emisión y vencimiento coherentes con una persona adulta a `fecha_referencia`.

    `fecha_referencia` es la fecha de firma del contrato y hace de "hoy" (nada depende del
    reloj): la persona tiene entre EDAD_MIN y EDAD_MAX años ese día, el DNI se emitió desde
    su última actualización (14 años) y está vigente, y vence VIGENCIA_DNI_ANIOS después.
    """
    # Entre EDAD_MIN y EDAD_MAX años cumplidos: quien cumple EDAD_MAX + 1 ese día ya no entra.
    nacimiento = _fecha_entre(
        source,
        sumar_anios(fecha_referencia, -(EDAD_MAX + 1)) + timedelta(days=1),
        sumar_anios(fecha_referencia, -EDAD_MIN),
    )
    # DNI vigente a la firma: emitido en los últimos 15 años y nunca antes de los 14 de edad.
    emision = _fecha_entre(
        source,
        max(
            sumar_anios(nacimiento, EDAD_ULTIMA_ACTUALIZACION),
            sumar_anios(fecha_referencia, -VIGENCIA_DNI_ANIOS) + timedelta(days=1),
        ),
        fecha_referencia,
    )
    vencimiento = sumar_anios(emision, VIGENCIA_DNI_ANIOS)
    return nacimiento, emision, vencimiento


def _domicilio(source: Source, provincia_inmueble: str) -> str:
    """Domicilio del dorso, en mayúsculas. Casi siempre en la provincia del inmueble (quien
    alquila en Godoy Cruz ya vive en el Gran Mendoza); si no, según PESOS_PROVINCIA. No es
    la dirección del inmueble: el inquilino todavía vive en otro lado."""
    if source.rng.random() < P_MISMA_PROVINCIA:
        provincia = provincia_inmueble
    else:
        provincia = source.rng.choices(list(PESOS_PROVINCIA), weights=list(PESOS_PROVINCIA.values()))[0]
    localidad, provincia, _ = source.rng.choice([f for f in LOCALIDADES if f[1] == provincia])
    calle = f"{source.fake.street_name()} {source.fake.building_number()}"
    return f"{calle} - {localidad} - {provincia}".upper()


def generate_dni_data(
    identidad: Identidad, fecha_referencia: date, source: Source, provincia_inmueble: str
) -> DNI:
    """Datos del DNI de una parte del contrato, sin evidencia (la pone `render_ficha`)."""
    persona = identidad.persona
    if persona.dni is None:
        raise ValueError(f"la parte {persona.id} no tiene DNI en la identidad")
    nacimiento, emision, vencimiento = fechas_dni(source, fecha_referencia)
    return DNI(
        numero=persona.dni,
        apellido=identidad.apellido.upper(),
        nombre=identidad.nombre_pila.upper(),
        sexo=identidad.sexo,
        fecha_nacimiento=nacimiento,
        fecha_emision=emision,
        fecha_vencimiento=vencimiento,
        nacionalidad=NACIONALIDAD,
        domicilio=_domicilio(source, provincia_inmueble),
    )


def _frase_fecha_dni(source: Source, d: date) -> str:
    return source.rng.choice((f"{d.day:02d} {MESES_DNI[d.month - 1]} {d.year}", f"{d:%d/%m/%Y}"))


def _frase_numero(source: Source, numero: str) -> str:
    return source.rng.choice((numero, f"{int(numero):,}".replace(",", ".")))


def _valores(dni: DNI, source: Source) -> dict[str, str]:
    """Texto que se imprime para cada dato presente: es también su evidencia."""
    valores: dict[str, str] = {}
    for campo in ETIQUETAS:
        valor = getattr(dni, campo)
        if valor is None:
            continue
        if campo == "numero":
            valores[campo] = _frase_numero(source, valor)
        elif isinstance(valor, date):
            valores[campo] = _frase_fecha_dni(source, valor)
        elif isinstance(valor, Sexo):
            valores[campo] = valor.value
        else:
            valores[campo] = valor
    return valores


def render_ficha(dni: DNI, source: Source) -> tuple[bytes, dict[str, str]]:
    """PDF de una página con la ficha y el texto impreso de cada dato (campo → fragmento)."""
    valores = _valores(dni, source)
    filas = [(ETIQUETAS[campo], valor) for campo, valor in valores.items()]
    return fichas.render_ficha(TITULO, "Ficha de identidad", filas), valores


def generate_dni_doc(
    identidad: Identidad, fecha_referencia: date, source: Source, provincia_inmueble: str
) -> tuple[bytes, DNI]:
    """PDF de la ficha y su ground truth con evidencia (todo en la página 1)."""
    dni = generate_dni_data(identidad, fecha_referencia, source, provincia_inmueble)
    pdf, valores = render_ficha(dni, source)
    update = {f"{c}_evidencia": Evidencia(texto=v, pagina=1) for c, v in valores.items()}
    return pdf, dni.model_copy(update=update)


def fuente_dni(seed: int, persona_id: UUID) -> Source:
    """Sub-fuente del DNI de una parte."""
    return Source(seed).derive(f"dni:{persona_id}")


def dni_de(contexto: ContextoLegajo, persona_id: UUID) -> DNI:
    """Datos del DNI de una parte, sin renderizar la ficha: para otros documentos del legajo
    que los necesitan (ej. la fecha de nacimiento en el recibo o en el título)."""
    return generate_dni_data(
        contexto.identidades[persona_id],
        contexto.referencia,
        fuente_dni(contexto.seed, persona_id),
        contexto.limpio.propiedad.provincia,
    )


def generate_dnis(
    seed: int, casos: list[CasoDificil] | None = None
) -> dict[UUID, tuple[bytes, DNI]]:
    """Ficha de DNI de cada parte que firma el contrato de la semilla (por `Persona.id`).

    Los datos salen de las identidades del contrato limpio: aunque el contrato no muestre el
    DNI de una parte (caso PERSONA_SIN_DOCUMENTO), su ficha sí lo trae. Con el caso
    SEGURO_DE_CAUCION no hay garantes, así que tampoco sus DNI. Cada parte usa su propia
    sub-fuente, así sumar un garante no cambia el DNI de los demás.
    """
    contexto = contexto_legajo(seed, casos)
    return {
        p.id: generate_dni_doc(
            contexto.identidades[p.id],
            contexto.referencia,
            fuente_dni(seed, p.id),
            contexto.limpio.propiedad.provincia,
        )
        for p in contexto.partes()
    }
