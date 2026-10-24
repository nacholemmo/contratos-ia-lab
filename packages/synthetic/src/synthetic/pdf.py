"""Render del contrato a PDF y ground truth con la evidencia real (fragmento y página).

La página de cada fragmento se anota mientras se escribe: el generador es el único que
sabe con certeza dónde cayó cada dato, y eso es lo que después se le exige al extractor.
"""

from datetime import UTC, datetime

from fpdf import FPDF
from fpdf.enums import MethodReturnValue, XPos, YPos
from PIL import Image

from core.models import Contrato, Evidencia
from synthetic.cases import (
    CasoDificil,
    Muestra,
    aplicar_casos,
    elegir_casos,
    es_aplicable,
    normalizar_casos,
)
from synthetic.clauses import Clause, render_clauses
from synthetic.contracts import generate_contrato
from synthetic.scan import degradar, rasterizar
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
    """A4 con la marca de agua y el aviso de sintético en cada página (también para el legajo)."""

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
    # La frase de cierre ("En prueba de conformidad…") es la última cláusula, con su fecha.
    pdf.set_font("Helvetica", "", TAMANIO_LETRA)
    pdf.ln(15)
    pdf.cell(85, ALTO_LINEA, "______________________", align="C")
    pdf.cell(85, ALTO_LINEA, "______________________", align="C", new_x=XPos.LMARGIN)
    pdf.ln(ALTO_LINEA)
    pdf.cell(85, ALTO_LINEA, "LA PARTE LOCADORA", align="C")
    pdf.cell(85, ALTO_LINEA, "LA PARTE LOCATARIA", align="C", new_x=XPos.LMARGIN)


def marcar_sintetico(pdf: FPDF, titulo: str = "Contrato de locación") -> None:
    """Metadatos que marcan el PDF como sintético, con fecha fija (mismos bytes por semilla)."""
    pdf.set_creation_date(FECHA_PDF)
    pdf.set_title(f"{titulo} ({MARCA})")
    pdf.set_subject(AVISO)
    pdf.set_keywords("sintetico")
    pdf.set_creator("contratos-ia-lab/synthetic")


def render_pdf(clauses: list[Clause]) -> tuple[bytes, dict[str, int]]:
    """PDF del contrato y la página de cada cláusula (nombre → página)."""
    pdf = ContratoPDF(format="A4")
    marcar_sintetico(pdf)
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "CONTRATO DE LOCACIÓN", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    paginas = {clause.nombre: _write_clause(pdf, clause) for clause in clauses}
    _write_firmas(pdf)
    return bytes(pdf.output()), paginas


def pdf_de_imagenes(paginas: list[Image.Image]) -> bytes:
    """PDF con una imagen A4 por página y sin capa de texto, como sale de un escáner.

    La marca "SINTÉTICO" ya está dibujada en cada imagen; los metadatos también la llevan.
    """
    pdf = FPDF(format="A4")
    marcar_sintetico(pdf)
    pdf.set_auto_page_break(auto=False)
    # JPEG, como guarda un escáner: más liviano y con sus propios artefactos de compresión.
    pdf.set_image_filter("DCTDecode")
    for pagina in paginas:
        pdf.add_page()
        pdf.image(pagina, x=0, y=0, w=pdf.w, h=pdf.h)
    return bytes(pdf.output())


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


def prepare_sample(
    seed: int, casos: list[CasoDificil] | None = None
) -> tuple[list[CasoDificil], Contrato, list[Clause]]:
    """Casos, datos y cláusulas del contrato de la semilla, antes de armar el PDF.

    Sin `casos`, la semilla elige los suyos y se descartan los que no aplican a su
    contrato. Con `casos`, se fuerzan esos (`[]` da un contrato limpio) y uno que no
    aplica es un error: el test pidió algo que no puede existir.
    """
    base = generate_contrato(seed)
    fuente_casos = Source(seed).derive("casos")
    if casos is None:
        casos = [caso for caso in elegir_casos(fuente_casos) if es_aplicable(caso, base)]
    else:
        no_aplicables = [caso for caso in casos if not es_aplicable(caso, base)]
        if no_aplicables:
            raise ValueError(f"no aplican al contrato de la semilla {seed}: {no_aplicables}")
    casos = normalizar_casos(casos)
    contrato = aplicar_casos(base, casos, fuente_casos)
    clauses = render_clauses(contrato, Source(seed).derive("redaccion"), casos)
    return casos, contrato, clauses


def generate_sample(seed: int, casos: list[CasoDificil] | None = None) -> tuple[bytes, Muestra]:
    """PDF sintético y su ground truth etiquetado (misma semilla → mismos bytes).

    Los casos usan su propia sub-fuente: elegirlos no cambia los datos ni la redacción
    del resto del contrato. Ver `prepare_sample` para cómo se eligen.
    """
    casos, contrato, clauses = prepare_sample(seed, casos)
    pdf, paginas = render_pdf(clauses)
    if CasoDificil.ESCANEO_TORCIDO in casos:
        # Las páginas no cambian: la evidencia sigue valiendo, solo que ahora es imagen.
        fuente = Source(seed).derive("escaneo")
        pdf = pdf_de_imagenes([degradar(p, fuente) for p in rasterizar(pdf)])
    muestra = Muestra(seed=seed, casos=casos, contrato=with_evidence(contrato, clauses, paginas))
    return pdf, muestra


def generate_contract(seed: int) -> tuple[bytes, Contrato]:
    """PDF sintético y su ground truth con evidencia, sin las etiquetas de casos."""
    pdf, muestra = generate_sample(seed)
    return pdf, muestra.contrato
