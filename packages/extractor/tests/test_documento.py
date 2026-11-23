"""Tests de la entrada de la extracción: formatos, EXIF, tamaño y límites."""

import io

import pytest
from PIL import Image

from extractor.documento import (
    LADO_LARGO_PX,
    MAX_BYTES,
    EntradaInvalida,
    Formato,
    cargar_archivo,
    cargar_documento,
    detectar_formato,
)
from pdf_fixtures import image_pdf, text_pdf

EXIF_ORIENTACION = 0x0112


def foto(
    ancho: int, alto: int, formato: str = "JPEG", orientacion: int | None = None
) -> bytes:
    """Una imagen con la mitad izquierda negra: así se ve hacia dónde quedó girada."""
    imagen = Image.new("RGB", (ancho, alto), "white")
    imagen.paste((0, 0, 0), (0, 0, ancho // 2, alto))
    buffer = io.BytesIO()
    if orientacion is None:
        imagen.save(buffer, format=formato)
    else:
        exif = Image.Exif()
        exif[EXIF_ORIENTACION] = orientacion
        imagen.save(buffer, format=formato, exif=exif.tobytes())
    return buffer.getvalue()


def abrir(jpg: bytes) -> Image.Image:
    return Image.open(io.BytesIO(jpg))


# --- detectar_formato ---


@pytest.mark.parametrize(
    ("datos", "formato"),
    [
        (b"%PDF-1.7\n...", Formato.PDF),
        (b"\xff\xd8\xff\xe0\x00\x10JFIF", Formato.JPEG),
        (b"\x89PNG\r\n\x1a\n\x00\x00", Formato.PNG),
        (b"\x00\x00\x00\x18ftypheic\x00\x00", Formato.HEIC),
        (b"\x00\x00\x00\x18ftypmif1\x00\x00", Formato.HEIC),
    ],
)
def test_detecta_por_los_primeros_bytes(datos, formato):
    assert detectar_formato(datos) == formato


@pytest.mark.parametrize(
    "datos",
    [
        b"GIF89a\x01\x00",  # GIF: no se admite
        b"<html><script>alert(1)</script>",  # un HTML renombrado a .jpg
        b"PK\x03\x04",  # un ZIP (o un .docx)
        b"\x00\x00\x00\x18ftypmp42",  # un video MP4: mismo contenedor que HEIC
        b"",
    ],
)
def test_rechaza_lo_que_no_es_pdf_jpg_png_ni_heic(datos):
    with pytest.raises(EntradaInvalida):
        detectar_formato(datos)


def test_la_extension_no_importa():
    """Un PNG llamado .jpg se lee como PNG; un HTML llamado .jpg se rechaza."""
    assert cargar_archivo("recibo.jpg", foto(100, 50, "PNG"))[0].archivo == "recibo.jpg"
    with pytest.raises(EntradaInvalida):
        cargar_archivo("recibo.jpg", b"<html></html>")


# --- fotos ---


def test_foto_chica_no_se_agranda():
    [pagina] = cargar_archivo("a.jpg", foto(800, 600))
    assert abrir(pagina.imagen).size == (800, 600)
    assert pagina.numero == 1
    assert pagina.texto is None


def test_foto_grande_se_reduce_al_lado_largo():
    [pagina] = cargar_archivo("a.jpg", foto(4000, 3000))
    assert abrir(pagina.imagen).size == (LADO_LARGO_PX, LADO_LARGO_PX * 3 // 4)


def test_png_sale_como_jpg():
    [pagina] = cargar_archivo("a.png", foto(300, 200, "PNG"))
    assert detectar_formato(pagina.imagen) == Formato.JPEG


@pytest.mark.parametrize(
    ("orientacion", "tamanio"),
    [(1, (400, 200)), (3, (400, 200)), (6, (200, 400)), (8, (200, 400))],
)
def test_se_endereza_segun_el_exif(orientacion, tamanio):
    """Con orientación 6 u 8 el teléfono guardó los píxeles acostados: al enderezarla, el
    ancho y el alto se intercambian."""
    [pagina] = cargar_archivo("a.jpg", foto(400, 200, orientacion=orientacion))
    assert abrir(pagina.imagen).size == tamanio


def test_orientacion_3_queda_dada_vuelta():
    """Girada 180°: la mitad negra pasa de la izquierda a la derecha."""
    [pagina] = cargar_archivo("a.jpg", foto(400, 200, orientacion=3))
    imagen = abrir(pagina.imagen).convert("L")
    assert imagen.getpixel((50, 100)) > 200  # izquierda, blanca
    assert imagen.getpixel((350, 100)) < 50  # derecha, negra


def test_la_salida_no_conserva_el_exif():
    """Ya está derecha: si conservara la orientación, un visor la volvería a girar."""
    [pagina] = cargar_archivo("a.jpg", foto(400, 200, orientacion=6))
    assert abrir(pagina.imagen).getexif().get(EXIF_ORIENTACION) in (None, 1)


def test_heic():
    pillow_heif = pytest.importorskip("pillow_heif")
    imagen = Image.new("RGB", (640, 480), "white")
    buffer = io.BytesIO()
    pillow_heif.from_pillow(imagen).save(buffer, format="HEIF")
    datos = buffer.getvalue()
    assert detectar_formato(datos) == Formato.HEIC
    [pagina] = cargar_archivo("IMG_0001.HEIC", datos)
    assert abrir(pagina.imagen).size == (640, 480)


# --- PDF ---


def test_pdf_con_texto_trae_la_capa_de_texto():
    [pagina] = cargar_archivo("contrato.pdf", text_pdf("Recibo de haberes"))
    assert pagina.texto == "Recibo de haberes"
    assert max(abrir(pagina.imagen).size) == LADO_LARGO_PX


def test_pdf_escaneado_no_trae_texto():
    [pagina] = cargar_archivo("escaneo.pdf", image_pdf())
    assert pagina.texto is None


# --- límites y archivos rotos ---


def test_archivo_vacio():
    with pytest.raises(EntradaInvalida):
        cargar_archivo("a.jpg", b"")


def test_archivo_demasiado_grande():
    with pytest.raises(EntradaInvalida):
        cargar_archivo("a.pdf", b"%PDF-" + b"0" * MAX_BYTES)


def test_imagen_rota():
    """Empieza como un JPG pero no lo es: no tiene que escaparse una excepción de Pillow."""
    with pytest.raises(EntradaInvalida):
        cargar_archivo("a.jpg", b"\xff\xd8\xff" + b"basura" * 100)


def test_pdf_roto():
    with pytest.raises(EntradaInvalida):
        cargar_archivo("a.pdf", b"%PDF-1.7 basura")


# Pillow avisa por su cuenta (DecompressionBombWarning) antes de que el límite propio la
# rechace: es justo el caso que se prueba.
@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_imagen_con_demasiados_pixeles():
    """Un PNG chico en bytes que declara 10.000 × 10.000 píxeles (100 MP)."""
    imagen = Image.new("1", (10_000, 10_000))
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    assert len(buffer.getvalue()) < 100_000
    with pytest.raises(EntradaInvalida):
        cargar_archivo("bomba.png", buffer.getvalue())


# --- documento ---


def test_documento_con_frente_y_dorso_en_orden():
    documento = cargar_documento([("frente.jpg", foto(400, 200)), ("dorso.jpg", foto(300, 200))])
    assert [p.archivo for p in documento.paginas] == ["frente.jpg", "dorso.jpg"]


def test_documento_mezcla_fotos_y_pdf():
    documento = cargar_documento([("a.jpg", foto(400, 200)), ("b.pdf", text_pdf("Hola"))])
    assert [(p.archivo, p.numero) for p in documento.paginas] == [("a.jpg", 1), ("b.pdf", 1)]


def test_documento_sin_archivos():
    with pytest.raises(EntradaInvalida):
        cargar_documento([])
