"""Recibo de sueldo sintético del inquilino, coherente con su DNI y con el alquiler.

Empleadores inventados a propósito (nada de empresas reales) con CUIT válido. Los montos
se calculan con `Decimal` y aportes fijos: el neto es exactamente bruto - descuentos, y
el alquiler es una fracción creíble del neto, para que en la Fase 4 se pueda evaluar la
relación alquiler/ingreso que mira una inmobiliaria.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fpdf.enums import XPos, YPos

from core.models import Contrato, Evidencia, Moneda, ReciboSueldo, Rol
from synthetic.amounts import numero_ar
from synthetic.cases import CasoDificil
from synthetic.contracts import ALQUILER_ARS_POR_ANIO
from synthetic.dni import dni_de, sumar_anios
from synthetic.identity import cuit_empresa, cuit_from_dni
from synthetic.legajo import ContextoLegajo, contexto_legajo
from synthetic.pdf import ContratoPDF, marcar_sintetico
from synthetic.source import Source
from synthetic.wording import MESES

TITULO = "RECIBO DE HABERES"

# Inventados a propósito: el repo es público y no se usan nombres de empresas reales.
EMPLEADORES = (
    "Bodegas del Valle Ficticio S.A.",
    "Servicios Andinos Simulados S.R.L.",
    "Comercial Ejemplo del Oeste S.A.",
    "Logística Modelo Cuyo S.A.",
    "Metalúrgica Ficticia Mendocina S.R.L.",
    "Consultora Sintética del Sur S.A.",
)

# Aportes del empleado en relación de dependencia (sobre el bruto): 17 % en total.
APORTES: tuple[tuple[str, Decimal], ...] = (
    ("Jubilación 11%", Decimal("0.11")),
    ("Ley 19.032 3%", Decimal("0.03")),
    ("Obra social 3%", Decimal("0.03")),
)
TOTAL_APORTES = sum(tasa for _, tasa in APORTES)

# Alquiler / neto: las inmobiliarias suelen pedir ingresos de 3 veces el alquiler (33 %);
# el rango deja algunos por encima, que son los que Avisa tendría que marcar.
ALQUILER_SOBRE_NETO = (0.20, 0.40)

# Antigüedad: al menos 3 meses (si no, no habría recibos para presentar) y hasta 20 años.
# Desde los 16 años: la edad mínima para trabajar (Ley 26.390).
ANTIGUEDAD_MIN = timedelta(days=90)
ANTIGUEDAD_MAX_ANIOS = 20
EDAD_MIN_EMPLEO = 16

CENTAVO = Decimal("0.01")
ALTO_FILA = 8


def _centavos(monto: Decimal) -> Decimal:
    return monto.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def alquiler_en_pesos(contrato: Contrato) -> Decimal:
    """Alquiler del contrato en pesos. En dólares se usa un alquiler típico en pesos de ese
    año: el recibo es en pesos y no queremos una cotización inventada."""
    if contrato.moneda == Moneda.ARS:
        return contrato.monto_inicial
    anio = (contrato.fecha_firma or contrato.fecha_inicio).year
    minimo, maximo = ALQUILER_ARS_POR_ANIO[anio]
    return Decimal((minimo + maximo) // 2)


def montos(alquiler: Decimal, source: Source) -> tuple[Decimal, list[Decimal], Decimal]:
    """Bruto, cada aporte y neto. El neto es exactamente bruto - suma de aportes."""
    proporcion = Decimal(str(round(source.rng.uniform(*ALQUILER_SOBRE_NETO), 3)))
    neto_objetivo = alquiler / proporcion
    bruto = _centavos(neto_objetivo / (1 - TOTAL_APORTES))
    aportes = [_centavos(bruto * tasa) for _, tasa in APORTES]
    return bruto, aportes, bruto - sum(aportes)


def periodo_liquidado(referencia: date) -> date:
    """Primer día del mes anterior al de la firma: el último recibo que se pudo presentar."""
    return (referencia.replace(day=1) - timedelta(days=1)).replace(day=1)


def fecha_ingreso(nacimiento: date, periodo: date, source: Source) -> date:
    desde = max(
        sumar_anios(nacimiento, EDAD_MIN_EMPLEO), sumar_anios(periodo, -ANTIGUEDAD_MAX_ANIOS)
    )
    hasta = periodo - ANTIGUEDAD_MIN
    return desde + timedelta(days=source.rng.randint(0, (hasta - desde).days))


def generate_recibo_data(
    contexto: ContextoLegajo, persona_id: UUID, source: Source
) -> tuple[ReciboSueldo, list[Decimal]]:
    """Datos del recibo (sin evidencia) y el detalle de aportes para imprimir."""
    identidad = contexto.identidades[persona_id]
    persona = identidad.persona
    if persona.dni is None:
        raise ValueError(f"la parte {persona.id} no tiene DNI en la identidad")
    # La misma fecha de nacimiento que su ficha de DNI: el legajo es coherente.
    dni = dni_de(contexto, persona_id)
    periodo = periodo_liquidado(contexto.referencia)
    bruto, aportes, neto = montos(alquiler_en_pesos(contexto.limpio), source)
    recibo = ReciboSueldo(
        empleador=source.rng.choice(EMPLEADORES),
        empleador_cuit=cuit_empresa(source.rng),
        empleado=f"{identidad.apellido}, {identidad.nombre_pila}".upper(),
        # Todo empleado tiene CUIL, aunque el contrato no lo muestre; es el mismo que se
        # deriva del DNI, así que coincide con el del contrato cuando figura.
        empleado_cuil=cuit_from_dni(persona.dni, identidad.sexo),
        periodo=f"{periodo:%Y-%m}",
        fecha_ingreso=fecha_ingreso(dni.fecha_nacimiento, periodo, source),
        remuneracion_bruta=bruto,
        total_descuentos=sum(aportes),
        neto=neto,
    )
    return recibo, aportes


def _pesos(monto: Decimal) -> str:
    return f"$ {numero_ar(monto)}"


def _cuit(source: Source, cuit: str) -> str:
    return source.rng.choice((cuit, f"{cuit[:2]}-{cuit[2:10]}-{cuit[10]}"))


def _valores(recibo: ReciboSueldo, source: Source) -> dict[str, str]:
    """Texto que se imprime para cada dato: es también su evidencia."""
    periodo = date.fromisoformat(f"{recibo.periodo}-01")
    return {
        "empleador": recibo.empleador,
        "empleador_cuit": _cuit(source, recibo.empleador_cuit),
        "empleado": recibo.empleado,
        "empleado_cuil": _cuit(source, recibo.empleado_cuil),
        "periodo": source.rng.choice(
            (f"{MESES[periodo.month - 1].upper()} {periodo.year}", f"{periodo:%m/%Y}")
        ),
        "fecha_ingreso": f"{recibo.fecha_ingreso:%d/%m/%Y}",
        "remuneracion_bruta": _pesos(recibo.remuneracion_bruta),
        "total_descuentos": _pesos(recibo.total_descuentos),
        "neto": _pesos(recibo.neto),
    }


def _fila(pdf: ContratoPDF, concepto: str, haberes: str = "", descuentos: str = "") -> None:
    ancho = pdf.epw / 3
    pdf.cell(ancho, ALTO_FILA, concepto, border="B")
    pdf.cell(ancho, ALTO_FILA, haberes, border="B", align="R")
    pdf.cell(ancho, ALTO_FILA, descuentos, border="B", align="R")
    pdf.ln(ALTO_FILA)


def render_recibo(
    recibo: ReciboSueldo, aportes: list[Decimal], source: Source
) -> tuple[bytes, dict[str, str]]:
    """PDF de una página con el recibo y el texto impreso de cada dato (campo → fragmento)."""
    v = _valores(recibo, source)
    pdf = ContratoPDF(format="A4")
    marcar_sintetico(pdf, "Recibo de haberes")
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, TITULO, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, v["empleador"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"CUIT {v['empleador_cuit']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    for etiqueta, campo in (
        ("Empleado", "empleado"),
        ("CUIL", "empleado_cuil"),
        ("Período liquidado", "periodo"),
        ("Fecha de ingreso", "fecha_ingreso"),
    ):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 7, etiqueta)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, v[campo], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    _fila(pdf, "Concepto", "Haberes", "Descuentos")
    pdf.set_font("Helvetica", "", 10)
    _fila(pdf, "Sueldo básico", v["remuneracion_bruta"])
    for (concepto, _), aporte in zip(APORTES, aportes, strict=True):
        _fila(pdf, concepto, descuentos=_pesos(aporte))
    pdf.set_font("Helvetica", "B", 10)
    _fila(pdf, "Totales", v["remuneracion_bruta"], v["total_descuentos"])
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"NETO A COBRAR: {v['neto']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(20)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "______________________", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, "Recibí conforme el importe neto", align="R")
    return bytes(pdf.output()), v


def generate_recibo_doc(
    contexto: ContextoLegajo, persona_id: UUID, source: Source
) -> tuple[bytes, ReciboSueldo]:
    """PDF del recibo y su ground truth con evidencia (todo en la página 1)."""
    recibo, aportes = generate_recibo_data(contexto, persona_id, source)
    pdf, valores = render_recibo(recibo, aportes, source)
    update = {f"{c}_evidencia": Evidencia(texto=t, pagina=1) for c, t in valores.items()}
    return pdf, recibo.model_copy(update=update)


def generate_recibos(
    seed: int, casos: list[CasoDificil] | None = None
) -> dict[UUID, tuple[bytes, ReciboSueldo]]:
    """Recibo de sueldo de cada inquilino del contrato de la semilla (por `Persona.id`)."""
    contexto = contexto_legajo(seed, casos)
    return {
        p.id: generate_recibo_doc(contexto, p.id, Source(seed).derive(f"recibo:{p.id}"))
        for p in contexto.partes(Rol.INQUILINO)
    }
