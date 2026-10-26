"""Tests de la entrada del documento: texto, imagen y la regla del híbrido."""

import base64
import io

from pdf_fixtures import image_pdf, text_pdf
from PIL import Image

from extractor.inputs import (
    IMAGE_LONG_EDGE_PX,
    build_content,
    choose_mode,
    has_usable_text,
    page_images,
    page_texts,
)

PAGINA = (
    "CONTRATO DE LOCACION DE INMUEBLE CON DESTINO VIVIENDA. Entre el Sr. Juan Perez, "
    "DNI 20.111.222, en adelante EL LOCADOR, y la Sra. Ana Gomez, DNI 30.333.444, en "
    "adelante LA LOCATARIA, se celebra el presente contrato sujeto a las siguientes clausulas."
)


def test_texto_de_un_pdf_con_texto():
    assert "LOCACION" in page_texts(text_pdf(PAGINA))[0]


def test_escaneo_no_tiene_texto():
    assert page_texts(image_pdf())[0].strip() == ""


def test_imagen_es_png_con_el_lado_largo_pedido():
    png = page_images(text_pdf(PAGINA))[0]
    assert png.startswith(b"\x89PNG")
    assert max(Image.open(io.BytesIO(png)).size) == IMAGE_LONG_EDGE_PX


def test_max_pages_no_falla_si_el_pdf_tiene_menos():
    assert len(page_texts(text_pdf(PAGINA), max_pages=5)) == 1


def test_contenido_texto_va_envuelto():
    content = build_content(text_pdf(PAGINA), "text")
    assert isinstance(content, str)
    assert content.startswith("<documento>")
    assert content.endswith("</documento>")
    assert "LOCACION" in content


def test_contenido_imagen_es_bloque_base64():
    content = build_content(text_pdf(PAGINA), "image")
    assert isinstance(content, list)
    assert content[0]["type"] == "image"
    assert base64.standard_b64decode(content[0]["source"]["data"]).startswith(b"\x89PNG")


# --- la regla del híbrido: casos claros (el umbral entre medio es decisión de diseño) ---


def test_sin_paginas_no_alcanza():
    assert has_usable_text([]) is False


def test_texto_vacio_no_alcanza():
    assert has_usable_text([""]) is False


def test_solo_espacios_y_saltos_no_alcanza():
    assert has_usable_text(["\r\n  \r\n\t "]) is False


def test_una_pagina_de_texto_alcanza():
    assert has_usable_text([PAGINA]) is True


def test_estrategias_fijas_no_miran_el_texto():
    assert choose_mode("text", []) == "text"
    assert choose_mode("image", [PAGINA]) == "image"


def test_hibrido_elige_segun_el_texto():
    assert choose_mode("hybrid", [PAGINA]) == "text"
    assert choose_mode("hybrid", [""]) == "image"
