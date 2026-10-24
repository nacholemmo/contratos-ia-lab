"""Ficha genérica de una página para los documentos complementarios del legajo.

Presentación propia y simple (título, filas etiqueta: valor y un recuadro), con la marca
SINTÉTICO en cada página: ningún documento imita el diseño de uno oficial o de una
empresa real.
"""

from fpdf.enums import XPos, YPos

from core.models import Propiedad
from synthetic.pdf import ContratoPDF, marcar_sintetico

ALTO_FILA = 9
ANCHO_ETIQUETA = 55


def render_ficha(titulo: str, titulo_pdf: str, filas: list[tuple[str, str]]) -> bytes:
    """PDF de una página con `titulo` y una fila por (etiqueta, valor)."""
    pdf = ContratoPDF(format="A4")
    marcar_sintetico(pdf, titulo_pdf)
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, titulo, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    arriba = pdf.get_y()
    for etiqueta, valor in filas:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(ANCHO_ETIQUETA, ALTO_FILA, etiqueta)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, ALTO_FILA, valor, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.rect(pdf.l_margin - 4, arriba - 4, pdf.epw + 8, pdf.get_y() - arriba + 8)
    return bytes(pdf.output())


def direccion(propiedad: Propiedad) -> str:
    """Dirección en una línea, como la escriben un título o una póliza."""
    unidad = ""
    if propiedad.piso is not None:
        unidad = f", piso {propiedad.piso}, depto. {propiedad.departamento}"
    p = propiedad
    return f"{p.calle} {p.numero}{unidad}, {p.localidad}, {p.provincia}"
