"""Caso ESCANEO_TORCIDO: cada página del contrato pasa a ser la foto de una fotocopia.

El PDF resultante no tiene capa de texto: el extractor tiene que leer imágenes (visión
u OCR). El ground truth no cambia, porque escanear cambia la forma y no lo que dice:
la evidencia se verifica en el gemelo con texto (misma semilla, sin este caso).
"""

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFilter

from synthetic.source import Source

# Resolución típica de un escaneo de oficina: legible y de tamaño razonable.
DPI = 150
ANGULO_MAXIMO = 2.0
BLANCO_FOTOCOPIA = 230  # el papel fotocopiado ya no es blanco puro (255)
NEGRO_FOTOCOPIA = 40  # ni el tóner es negro puro (0)
PUNTOS_RUIDO = 4_000  # polvo y manchas de tóner en una página de ~1240×1754


def rasterizar(pdf: bytes, dpi: int = DPI) -> list[Image.Image]:
    """Una imagen en escala de grises ("L") por página del PDF."""
    documento = pdfium.PdfDocument(pdf)
    try:
        # pdfium mide en puntos (72 por pulgada): la escala lleva de puntos a píxeles.
        return [
            documento[i].render(scale=dpi / 72).to_pil().convert("L") for i in range(len(documento))
        ]
    finally:
        documento.close()


def degradar(pagina: Image.Image, source: Source) -> Image.Image:
    """La página como sale de una fotocopiadora y un escáner: torcida, gris y con ruido.

    Mismo tamaño y modo que la entrada. Todo el azar sale de `source` (misma semilla →
    mismos píxeles).
    """

    rng = source.rng
    # 1. Torcida: sin expand (mismo tamaño) y con las esquinas que quedan vacías en blanco.
    angulo = rng.uniform(-ANGULO_MAXIMO, ANGULO_MAXIMO)
    torcida = pagina.rotate(angulo, resample=Image.Resampling.BICUBIC, fillcolor=255)
    # 2. Gris de fotocopia: lleva el rango 0–255 a NEGRO–BLANCO
    rango = BLANCO_FOTOCOPIA - NEGRO_FOTOCOPIA
    gris = torcida.point(lambda v: round(NEGRO_FOTOCOPIA + v * rango / 255))

    # 3. Ruido: ImageDraw dibuja sobre `gris`, que ya es una copia (`pagina` no cambia).
    dibujo = ImageDraw.Draw(gris)
    for _ in range(PUNTOS_RUIDO):
        x, y = rng.randrange(gris.width), rng.randrange(gris.height)
        dibujo.point((x, y), fill=rng.randint(0, 200))

    # 4. Desenfoque leve: un escáner de oficina no es perfectamente nítido.
    return gris.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.8)))
