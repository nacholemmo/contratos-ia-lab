"""Cómo le llega un PDF al modelo: texto extraído, imagen de la página o un híbrido.

Todo documento es texto no confiable: se manda envuelto en <documento> y el prompt aclara que
es un dato a clasificar, no instrucciones.
"""

import base64
import io
from typing import Any, Literal

import pypdfium2 as pdfium

Mode = Literal["text", "image"]
Strategy = Literal["text", "image", "hybrid"]

# Lado largo de la imagen en píxeles: lo máximo que la API usa sin reducirla.
IMAGE_LONG_EDGE_PX = 1568
# Mínimo de palabras de más de 3 letras para confiar en el texto extraído. Medido en el set
# sintético: el documento real más corto (título de garante) tiene unas 30; un sello o una marca
# de agua, menos de 10 ("COPIA FIEL" 2, la marca de los sintéticos 6). Ante la duda, imagen:
# un falso "hay texto" cuesta un error de clasificación; un falso "no hay", centésimos de centavo.
MIN_LONG_WORDS = 15


def page_texts(pdf_bytes: bytes, max_pages: int = 1) -> list[str]:
    """Texto de las primeras `max_pages` páginas (vacío si la página es solo imagen)."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        return [pdf[i].get_textpage().get_text_bounded() for i in range(min(max_pages, len(pdf)))]
    finally:
        pdf.close()


def page_images(pdf_bytes: bytes, max_pages: int = 1) -> list[bytes]:
    """PNG de las primeras `max_pages` páginas, con el lado largo en IMAGE_LONG_EDGE_PX."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        images = []
        for i in range(min(max_pages, len(pdf))):
            page = pdf[i]
            scale = IMAGE_LONG_EDGE_PX / max(page.get_size())
            buffer = io.BytesIO()
            page.render(scale=scale).to_pil().save(buffer, format="PNG")
            images.append(buffer.getvalue())
        return images
    finally:
        pdf.close()


def has_usable_text(texts: list[str]) -> bool:
    """¿Alcanza el texto extraído para clasificar, o hay que mirar la imagen?"""
    words = " ".join(texts).split()
    long_words = sum(len(word) > 3 for word in words)
    return long_words >= MIN_LONG_WORDS


def choose_mode(strategy: Strategy, texts: list[str]) -> Mode:
    if strategy == "hybrid":
        return "text" if has_usable_text(texts) else "image"
    return strategy


def text_content(texts: list[str]) -> str:
    joined = "\n\n".join(texts)
    return f"<documento>\n{joined}\n</documento>"


def image_content(images: list[bytes]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.standard_b64encode(png).decode("ascii"),
            },
        }
        for png in images
    ]
    blocks.append({"type": "text", "text": "Las imágenes de arriba son el documento."})
    return blocks


def build_content(pdf_bytes: bytes, mode: Mode, max_pages: int = 1) -> str | list[dict[str, Any]]:
    """El `content` para `call_llm` en el modo pedido."""
    if mode == "text":
        return text_content(page_texts(pdf_bytes, max_pages))
    return image_content(page_images(pdf_bytes, max_pages))
