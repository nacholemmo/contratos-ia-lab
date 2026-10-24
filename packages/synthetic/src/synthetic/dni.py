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

from fpdf.enums import XPos, YPos

from core.models import DNI, Evidencia, Sexo
from synthetic.contracts import LOCALIDADES, Identidad, generate_contrato_con_identidades
from synthetic.pdf import ContratoPDF, marcar_sintetico
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

ALTO_FILA = 9
ANCHO_ETIQUETA = 55


def _sumar_anios(d: date, anios: int) -> date:
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
        _sumar_anios(fecha_referencia, -(EDAD_MAX + 1)) + timedelta(days=1),
        _sumar_anios(fecha_referencia, -EDAD_MIN),
    )
    # DNI vigente a la firma: emitido en los últimos 15 años y nunca antes de los 14 de edad.
    emision = _fecha_entre(
        source,
        max(
            _sumar_anios(nacimiento, EDAD_ULTIMA_ACTUALIZACION),
            _sumar_anios(fecha_referencia, -VIGENCIA_DNI_ANIOS) + timedelta(days=1),
        ),
        fecha_referencia,
    )
    vencimiento = _sumar_anios(emision, VIGENCIA_DNI_ANIOS)
    return nacimiento, emision, vencimiento


def _domicilio(source: Source) -> str:
    # Mayúsculas, como en el dorso del DNI. Cualquier localidad: no tiene por qué ser la del
    # inmueble (el inquilino todavía vive en otro lado).
    localidad, provincia, _ = source.rng.choice(LOCALIDADES)
    calle = f"{source.fake.street_name()} {source.fake.building_number()}"
    return f"{calle} - {localidad} - {provincia}".upper()


def generate_dni_data(identidad: Identidad, fecha_referencia: date, source: Source) -> DNI:
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
        domicilio=_domicilio(source),
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
    pdf = ContratoPDF(format="A4")
    marcar_sintetico(pdf, "Ficha de identidad")
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, TITULO, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    arriba = pdf.get_y()
    for campo, valor in valores.items():
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(ANCHO_ETIQUETA, ALTO_FILA, ETIQUETAS[campo])
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, ALTO_FILA, valor, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    # Un recuadro simple alrededor de los datos: presentación propia, nada del diseño oficial.
    pdf.rect(pdf.l_margin - 4, arriba - 4, pdf.epw + 8, pdf.get_y() - arriba + 8)
    return bytes(pdf.output()), valores


def generate_dni_doc(
    identidad: Identidad, fecha_referencia: date, source: Source
) -> tuple[bytes, DNI]:
    """PDF de la ficha y su ground truth con evidencia (todo en la página 1)."""
    dni = generate_dni_data(identidad, fecha_referencia, source)
    pdf, valores = render_ficha(dni, source)
    update = {f"{c}_evidencia": Evidencia(texto=v, pagina=1) for c, v in valores.items()}
    return pdf, dni.model_copy(update=update)


def generate_dnis(seed: int) -> dict[UUID, tuple[bytes, DNI]]:
    """Ficha de DNI de cada parte del contrato de la semilla (por `Persona.id`).

    Sale de las identidades del contrato limpio: aunque el contrato no muestre el DNI de
    una parte (caso PERSONA_SIN_DOCUMENTO), su ficha sí lo trae. Cada parte usa su propia
    sub-fuente, así sumar un garante no cambia el DNI de los demás.
    """
    contrato, identidades = generate_contrato_con_identidades(seed)
    # El contrato limpio siempre tiene fecha de firma (el caso de fecha en blanco va aparte).
    referencia = contrato.fecha_firma or contrato.fecha_inicio
    return {
        persona_id: generate_dni_doc(
            identidad, referencia, Source(seed).derive(f"dni:{persona_id}")
        )
        for persona_id, identidad in identidades.items()
    }
