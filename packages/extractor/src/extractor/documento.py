"""Entrada de la extracción: archivos subidos (fotos o PDF) → páginas listas para el modelo.

Un documento puede ser varias fotos (frente y dorso del DNI) o un PDF de varias páginas.
Cada página sale como una imagen normalizada y, si venía de un PDF con capa de texto,
también con ese texto:

- **El formato se decide por los primeros bytes, no por la extensión:** el archivo viene de
  afuera y `recibo.jpg` puede ser cualquier cosa. Lo que no es PDF, JPG, PNG o HEIC se
  rechaza.
- **Las fotos se enderezan según el EXIF:** un teléfono guarda una foto vertical con los
  píxeles acostados y la orientación aparte. Sin `exif_transpose`, el modelo lee el
  documento de costado (ver `synthetic/foto.py`, que genera justamente esas fotos).
- **Se reducen a 1568 px de lado largo:** lo máximo que la API usa sin achicarla ella misma.
  Mandar más es pagar tokens que no suman detalle. Nunca se agrandan.
- **Límites contra archivos maliciosos:** tamaño, cantidad de páginas y píxeles. Una imagen
  de 20 KB puede declarar 100.000 × 100.000 píxeles (decompression bomb).

Nada de esto se guarda ni se registra en logs: el servicio no tiene estado.
"""

import io
from dataclasses import dataclass
from enum import StrEnum

import pypdfium2 as pdfium
from PIL import Image, ImageOps

# HEIC (fotos de iPhone): Pillow lo lee con el plugin de pillow-heif, si está instalado.
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC_DISPONIBLE = True
except ImportError:  # pragma: no cover - depende del entorno
    HEIC_DISPONIBLE = False

LADO_LARGO_PX = 1568
CALIDAD_JPG = 85
MAX_BYTES = 25 * 1024 * 1024  # 25 MB por archivo: una foto de 48 MP en HEIC pesa ~8 MB
MAX_PAGINAS_PDF = 20
MAX_PIXELES = 60_000_000  # 60 MP: más que cualquier cámara de teléfono


class Formato(StrEnum):
    PDF = "pdf"
    JPEG = "jpeg"
    PNG = "png"
    HEIC = "heic"


class EntradaInvalida(ValueError):
    """El archivo no se puede usar: formato no admitido, roto o fuera de los límites."""


@dataclass(frozen=True)
class Pagina:
    """Una página del documento, como la va a ver el modelo."""

    archivo: str  # nombre con el que llegó (ej. "IMG_4821.jpg"): la evidencia lo cita
    numero: int  # página dentro del archivo, desde 1 (una foto tiene una sola)
    imagen: bytes  # JPG normalizado: derecho y con el lado largo en LADO_LARGO_PX o menos
    texto: str | None  # capa de texto del PDF; None en una foto o en un PDF escaneado


@dataclass(frozen=True)
class Documento:
    """Las páginas de un documento, en el orden en que llegaron sus archivos."""

    paginas: list[Pagina]


def detectar_formato(datos: bytes) -> Formato:
    """El formato del archivo según sus primeros bytes ("magic bytes"), no su extensión.

    Tira `EntradaInvalida` si no es PDF, JPG, PNG ni HEIC.
    """
    if datos.startswith(b"%PDF-"):
        return Formato.PDF
    if datos.startswith(b"\xff\xd8\xff"):
        return Formato.JPEG
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return Formato.PNG
    # HEIC es un contenedor ISO BMFF: 4 bytes de tamaño, "ftyp" y la marca del formato.
    if datos[4:8] == b"ftyp" and datos[8:12] in {b"heic", b"heix", b"heim", b"heis", b"mif1"}:
        return Formato.HEIC
    raise EntradaInvalida("formato no admitido: se aceptan PDF, JPG, PNG y HEIC")


def _a_jpg(imagen: Image.Image) -> bytes:
    """Derecha, en RGB y con el lado largo en LADO_LARGO_PX o menos, como JPG."""
    imagen = ImageOps.exif_transpose(imagen)
    imagen = imagen.convert("RGB")
    imagen.thumbnail((LADO_LARGO_PX, LADO_LARGO_PX), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=CALIDAD_JPG)
    return buffer.getvalue()


def _paginas_de_foto(nombre: str, datos: bytes, formato: Formato) -> list[Pagina]:
    if formato == Formato.HEIC and not HEIC_DISPONIBLE:
        raise EntradaInvalida("HEIC no disponible: falta instalar pillow-heif")
    try:
        imagen = Image.open(io.BytesIO(datos))
        # `open` solo lee el encabezado: se controla el tamaño antes de decodificar.
        if imagen.width * imagen.height > MAX_PIXELES:
            raise EntradaInvalida(f"imagen demasiado grande: {imagen.width}×{imagen.height}")
        imagen.load()
    except EntradaInvalida:
        raise
    except Exception as error:  # Pillow tira varios tipos ante un archivo roto
        raise EntradaInvalida(f"imagen ilegible: {type(error).__name__}") from error
    return [Pagina(archivo=nombre, numero=1, imagen=_a_jpg(imagen), texto=None)]


def _paginas_de_pdf(nombre: str, datos: bytes) -> list[Pagina]:
    try:
        pdf = pdfium.PdfDocument(datos)
    except pdfium.PdfiumError as error:
        raise EntradaInvalida("PDF ilegible") from error
    try:
        if len(pdf) > MAX_PAGINAS_PDF:
            raise EntradaInvalida(f"PDF con demasiadas páginas: {len(pdf)}")
        paginas = []
        for i in range(len(pdf)):
            pagina = pdf[i]
            escala = LADO_LARGO_PX / max(pagina.get_size())
            imagen = pagina.render(scale=escala).to_pil()
            texto = pagina.get_textpage().get_text_bounded().strip()
            paginas.append(Pagina(nombre, i + 1, _a_jpg(imagen), texto or None))
        return paginas
    finally:
        pdf.close()


def cargar_archivo(nombre: str, datos: bytes) -> list[Pagina]:
    """Las páginas de un archivo subido. Tira `EntradaInvalida` si no se puede usar."""
    if not datos:
        raise EntradaInvalida("archivo vacío")
    if len(datos) > MAX_BYTES:
        raise EntradaInvalida(f"archivo demasiado grande: {len(datos)} bytes")
    formato = detectar_formato(datos)
    if formato == Formato.PDF:
        return _paginas_de_pdf(nombre, datos)
    return _paginas_de_foto(nombre, datos, formato)


def cargar_documento(archivos: list[tuple[str, bytes]]) -> Documento:
    """Un documento a partir de sus archivos (nombre, bytes), en orden: frente y dorso,
    o las páginas de un recibo sacadas por separado."""
    if not archivos:
        raise EntradaInvalida("un documento necesita al menos un archivo")
    return Documento([p for nombre, datos in archivos for p in cargar_archivo(nombre, datos)])
