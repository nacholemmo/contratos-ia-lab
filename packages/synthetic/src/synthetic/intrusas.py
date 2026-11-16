"""Fotos intrusas: lo que se cuela en un legajo y no es ningún documento (clase `otro`).

Tres tipos, como en la vida real: la foto de una factura de un servicio, la captura de un
chat y una foto sin documento (la mesa, el piso, una foto sacada sin querer). Todas son
sintéticas y llevan la marca: la factura es de una empresa ficticia y el chat no imita la
interfaz de ninguna aplicación.
"""

from datetime import date
from enum import StrEnum

import pypdfium2 as pdfium
from fpdf import FPDF
from PIL import ImageChops, ImageFilter

from synthetic.fichas import render_ficha
from synthetic.foto import (
    FONDOS,
    LADO_LARGO,
    Nivel,
    _reflejo,
    _sombra,
    _textura,
    fotografiar_pdf,
    guardar_jpg,
    orientacion_al_azar,
)
from synthetic.pdf import marcar_sintetico
from synthetic.source import Source
from synthetic.wording import MESES


class Intrusa(StrEnum):
    FACTURA = "factura"
    CHAT = "chat"
    SIN_DOCUMENTO = "sin_documento"


SERVICIOS = ["Electricidad", "Gas natural", "Agua corriente", "Internet y telefonía"]

# Mensajes de un chat entre quien alquila y la inmobiliaria: sin datos de nadie.
MENSAJES = [
    "Hola! Te paso los papeles que me pidieron",
    "Perfecto, gracias",
    "Ahí van los recibos",
    "Me falta el del garante, te lo mando a la noche",
    "Se ven bien?",
    "La del DNI salió un poco movida, si querés la saco de nuevo",
    "Dale, avisame si falta algo",
    "Buen día! Ya está todo?",
]


def factura_servicio(source: Source, nivel: Nivel) -> bytes:
    """Foto de la factura de un servicio de una empresa ficticia."""
    fake, rng = source.fake, source.rng
    mes = rng.randint(1, 12)
    filas = [
        ("Empresa", "Servicios Ficticios S.A."),
        ("Servicio", rng.choice(SERVICIOS)),
        ("Titular", fake.name()),
        ("Domicilio", fake.street_address()),
        ("Período", f"{MESES[mes - 1]} {rng.randint(2024, 2026)}"),
        ("Total a pagar", f"$ {rng.randint(8_000, 90_000):,}".replace(",", ".")),
        ("Vencimiento", f"{date(2026, mes, rng.randint(1, 28)):%d/%m/%Y}"),
    ]
    pdf = render_ficha("Factura de servicio", "Factura de servicio", filas)
    return fotografiar_pdf(pdf, source.derive("foto"), nivel)[0]


def captura_chat(source: Source) -> bytes:
    """Captura de pantalla de un chat: vertical, sin perspectiva y sin rotación EXIF.

    Se dibuja con fpdf (Helvetica, que trae acentos y es la misma en cualquier máquina) y se
    rasteriza en color. La fuente por defecto de Pillow no tiene tildes, y una fuente del
    sistema cambiaría los bytes de una máquina a otra.
    """
    rng = source.rng
    ancho, alto, margen = 100, 210, 4  # mm: proporción de un teléfono
    pdf = FPDF(format=(ancho, alto))
    marcar_sintetico(pdf, "Captura de chat")
    pdf.set_auto_page_break(auto=False)
    pdf.set_page_background((236, 229, 221))
    pdf.add_page()
    pdf.set_fill_color(60, 70, 90)
    pdf.rect(0, 0, ancho, 15, style="F")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(255)
    pdf.text(margen + 2, 9.5, "Inmobiliaria (SINTÉTICO)")

    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(20)
    y = 22.0
    for mensaje in rng.sample(MENSAJES, rng.randint(3, 6)):
        propio = rng.random() < 0.5
        w = pdf.get_string_width(mensaje) + 6
        x = ancho - w - margen if propio else margen
        pdf.set_fill_color(*((220, 248, 198) if propio else (255, 255, 255)))
        pdf.rect(x, y, w, 8, style="F", round_corners=True, corner_radius=2)
        pdf.text(x + 3, y + 5.2, mensaje)
        y += 11
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(150, 40, 40)
    pdf.text(margen + 2, alto - 6, "SINTÉTICO - captura ficticia")

    documento = pdfium.PdfDocument(bytes(pdf.output()))
    try:
        # 100 mm son 283 puntos: con esta escala, la captura mide 720 px de ancho.
        img = documento[0].render(scale=720 / (ancho * 72 / 25.4)).to_pil().convert("RGB")
    finally:
        documento.close()
    return guardar_jpg(img, orientacion=1, calidad=80)


def foto_sin_documento(source: Source) -> bytes:
    """Una foto sacada sin querer: la mesa, con la luz y el movimiento de una foto real."""
    rng = source.rng
    size = (LADO_LARGO, LADO_LARGO * 3 // 4)
    foto = _textura(source, size, rng.choice(FONDOS))
    foto = ImageChops.multiply(foto, _sombra(source, size, rng.uniform(0.2, 0.6)))
    foto = ImageChops.screen(foto, _reflejo(source, size, rng.uniform(0.1, 0.4)))
    foto = foto.filter(ImageFilter.GaussianBlur(rng.uniform(1, 4)))
    return guardar_jpg(foto, orientacion_al_azar(source), calidad=75)


def generate_intrusa(tipo: Intrusa, source: Source, nivel: Nivel = Nivel.LEVE) -> bytes:
    """JPG de una intrusa del tipo pedido."""
    match tipo:
        case Intrusa.FACTURA:
            return factura_servicio(source, nivel)
        case Intrusa.CHAT:
            return captura_chat(source)
        case Intrusa.SIN_DOCUMENTO:
            return foto_sin_documento(source)
