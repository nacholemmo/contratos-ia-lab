"""Render del contrato a PDF y ground truth con la evidencia real (fragmento y página).

La página de cada fragmento se anota mientras se escribe: el generador es el único que
sabe con certeza dónde cayó cada dato, y eso es lo que después se le exige al extractor.
"""

from datetime import UTC, datetime

from fpdf import FPDF
from fpdf.enums import MethodReturnValue, XPos, YPos

from core.models import Contrato, Evidencia
from synthetic.clauses import Clause, render_clauses
from synthetic.contracts import generate_contrato
from synthetic.source import Source

MARCA = "SINTÉTICO"
AVISO = "DOCUMENTO SINTÉTICO - DATOS FICTICIOS - SIN VALIDEZ LEGAL"

# Fecha fija: fpdf2 usa la hora actual por defecto y el mismo contrato daría otros bytes.
FECHA_PDF = datetime(2026, 1, 1, tzinfo=UTC)

# Cláusulas que van a `Contrato.clausulas` (las relevantes para Avisa, sin dato propio).
CLAUSULAS_RELEVANTES = ("expensas", "rescision")

ALTO_LINEA = 6
TAMANIO_LETRA = 11


class ContratoPDF(FPDF):
    """A4 con la marca de agua y el aviso de sintético en cada página."""

    def header(self) -> None:
        # Marca de agua primero: queda debajo del texto y no se mezcla con él al extraerlo.
        self.set_font("Helvetica", "B", 90)
        self.set_text_color(235)
        ancho = self.get_string_width(MARCA)
        with self.rotation(45, x=self.w / 2, y=self.h / 2):
            self.text((self.w - ancho) / 2, self.h / 2, MARCA)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(130)
        self.cell(0, 5, AVISO, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(130)
        self.cell(0, 10, f"{MARCA} · Página {self.page_no()} de {{nb}}", align="C")


def _escribir_cuerpo(pdf: FPDF, clause: Clause) -> None:
    """Título (si tiene) y texto de la cláusula, con un espacio al final."""
    if clause.titulo:
        pdf.set_font("Helvetica", "B", TAMANIO_LETRA)
        pdf.multi_cell(0, ALTO_LINEA, clause.titulo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", TAMANIO_LETRA)
    pdf.multi_cell(0, ALTO_LINEA, clause.texto, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)


def _alto_cuerpo(pdf: FPDF, clause: Clause) -> float:
    """Alto que ocupan título y texto de la cláusula, medido sin escribir nada."""
    alto = 0.0
    if clause.titulo:
        pdf.set_font("Helvetica", "B", TAMANIO_LETRA)
        alto += pdf.multi_cell(
            0, ALTO_LINEA, clause.titulo, dry_run=True, output=MethodReturnValue.HEIGHT
        )
    pdf.set_font("Helvetica", "", TAMANIO_LETRA)
    alto += pdf.multi_cell(
        0, ALTO_LINEA, clause.texto, dry_run=True, output=MethodReturnValue.HEIGHT
    )
    return alto


def _write_clause(pdf: FPDF, clause: Clause) -> int:
    """Escribe la cláusula y devuelve el número de página donde quedó su texto."""
    # Sin pdf.unbreakable(): el header usa rotation(), que fpdf2 no permite adentro.
    if pdf.get_y() + _alto_cuerpo(pdf, clause) > pdf.page_break_trigger:
        pdf.add_page()
    _escribir_cuerpo(pdf, clause)
    return pdf.page_no()


def _write_firmas(pdf: FPDF) -> None:
    pdf.set_font("Helvetica", "", TAMANIO_LETRA)
    pdf.multi_cell(
        0,
        ALTO_LINEA,
        "En prueba de conformidad, se firman dos ejemplares de un mismo tenor y a un solo efecto.",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(18)
    pdf.cell(85, ALTO_LINEA, "______________________", align="C")
    pdf.cell(85, ALTO_LINEA, "______________________", align="C", new_x=XPos.LMARGIN)
    pdf.ln(ALTO_LINEA)
    pdf.cell(85, ALTO_LINEA, "LA PARTE LOCADORA", align="C")
    pdf.cell(85, ALTO_LINEA, "LA PARTE LOCATARIA", align="C", new_x=XPos.LMARGIN)


def render_pdf(clauses: list[Clause]) -> tuple[bytes, dict[str, int]]:
    """PDF del contrato y la página de cada cláusula (nombre → página)."""
    pdf = ContratoPDF(format="A4")
    pdf.set_creation_date(FECHA_PDF)
    pdf.set_title(f"Contrato de locación ({MARCA})")
    pdf.set_subject(AVISO)
    pdf.set_keywords("sintetico")
    pdf.set_creator("contratos-ia-lab/synthetic")
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "CONTRATO DE LOCACIÓN", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    paginas = {clause.nombre: _write_clause(pdf, clause) for clause in clauses}
    _write_firmas(pdf)
    return bytes(pdf.output()), paginas


def with_evidence(contrato: Contrato, clauses: list[Clause], paginas: dict[str, int]) -> Contrato:
    """Copia del contrato con cada `<campo>_evidencia` y las cláusulas relevantes."""
    update: dict[str, object] = {}
    for clause in clauses:
        pagina = paginas[clause.nombre]
        for campo, fragmento in clause.fragmentos.items():
            update[f"{campo}_evidencia"] = Evidencia(texto=fragmento, pagina=pagina)
    update["clausulas"] = [
        Evidencia(texto=c.texto, pagina=paginas[c.nombre])
        for c in clauses
        if c.nombre in CLAUSULAS_RELEVANTES
    ]
    return contrato.model_copy(update=update)


def generate_contract(seed: int) -> tuple[bytes, Contrato]:
    """PDF sintético y su ground truth con evidencia (misma semilla → mismos bytes)."""
    contrato = generate_contrato(seed)
    clauses = render_clauses(contrato, Source(seed).derive("redaccion"))
    pdf, paginas = render_pdf(clauses)
    return pdf, with_evidence(contrato, clauses, paginas)
