"""Legajo fotografiado: cada página de un PDF pasa a ser una foto de celular (JPG).

A diferencia de `scan.py` (una fotocopia escaneada, plana y pareja), una foto tiene
perspectiva, sombra de la mano, el reflejo del flash, algo de movimiento, la mesa alrededor o
un borde cortado, y los píxeles guardados de costado con la orientación en el EXIF, como hacen
los teléfonos. Tres niveles: leve, fuerte e ilegible (a propósito, para que el servicio la
descarte).

Solo Pillow y todo el azar desde `Source`: misma semilla → mismos bytes. No se usa
`Image.effect_noise`, que toma su azar de C y no de la semilla.

La marca "SINTÉTICO" ya viene dibujada en cada página; el EXIF también la lleva.
"""

from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO

from PIL import Image, ImageChops, ImageFilter, ImageOps

from synthetic.scan import rasterizar
from synthetic.source import Source

# Lado largo de la foto final: lo que deja una foto mandada por WhatsApp.
LADO_LARGO = 1600

# Etiquetas EXIF (estándar TIFF/EXIF).
EXIF_ORIENTACION = 0x0112
EXIF_DESCRIPCION = 0x010E
DESCRIPCION_EXIF = "SINTETICO - documento ficticio, sin validez legal"

# Orientación EXIF y su probabilidad. 1: los píxeles ya están derechos. 6: el teléfono vertical
# guarda la imagen acostada y pide girarla 90° en sentido horario al mostrarla (la más común
# en fotos de documentos). 3: dada vuelta. 8: acostada para el otro lado.
PESOS_ORIENTACION = {1: 0.4, 6: 0.4, 3: 0.1, 8: 0.1}

# Colores de mesa sobre la que se apoya la hoja (madera, gris, tela oscura, mantel claro).
FONDOS = [(120, 84, 52), (96, 98, 102), (45, 48, 60), (200, 196, 186)]


class Nivel(StrEnum):
    LEVE = "leve"
    FUERTE = "fuerte"
    ILEGIBLE = "ilegible"


@dataclass(frozen=True)
class Parametros:
    perspectiva: float  # desplazamiento máximo de cada esquina, como fracción del lado
    angulo: float  # rotación máxima en grados, para cualquier lado
    sombra: float  # oscurecimiento máximo del lado sombreado (0 a 1)
    reflejo: float  # aclarado máximo en el centro del reflejo (0 a 1)
    desenfoque: tuple[float, float]  # radio del desenfoque gaussiano, mínimo y máximo
    margen: float  # mesa visible alrededor de la hoja, como fracción del lado
    recorte: float  # fracción máxima que se corta de cada borde de la foto
    calidad_jpg: int


NIVELES: dict[Nivel, Parametros] = {
    Nivel.LEVE: Parametros(0.03, 3, 0.25, 0.15, (0.3, 0.8), 0.08, 0.02, 85),
    Nivel.FUERTE: Parametros(0.07, 7, 0.5, 0.3, (1.0, 1.6), 0.10, 0.05, 70),
    Nivel.ILEGIBLE: Parametros(0.10, 12, 0.85, 0.5, (6.0, 9.0), 0.10, 0.12, 40),
}


def _textura(source: Source, size: tuple[int, int], color: tuple[int, int, int]) -> Image.Image:
    """Mesa con variaciones suaves: ruido de 32×32 sembrado y agrandado (no `effect_noise`)."""
    chico = Image.frombytes("L", (32, 32), source.rng.randbytes(32 * 32))
    ruido = chico.resize(size, Image.Resampling.BICUBIC).point(lambda v: 225 + v // 8)
    return ImageChops.multiply(Image.new("RGB", size, color), ruido.convert("RGB"))


def _sombra(source: Source, size: tuple[int, int], intensidad: float) -> Image.Image:
    """Máscara para multiplicar: blanco (sin sombra) que se oscurece hacia un borde al azar."""
    gradiente = Image.linear_gradient("L").rotate(source.rng.choice([0, 90, 180, 270]))
    tope = round(255 * intensidad)
    mascara = gradiente.resize(size).point(lambda v: 255 - v * tope // 255)
    return mascara.convert("RGB")


def _reflejo(source: Source, size: tuple[int, int], intensidad: float) -> Image.Image:
    """Capa para `screen`: una mancha de luz (el flash) en un lugar al azar, negra el resto."""
    lado = round(min(size) * source.rng.uniform(0.5, 0.9))
    # radial_gradient es 0 en el centro y 255 en el borde: invertido, el centro es el brillo.
    mancha = ImageOps.invert(Image.radial_gradient("L")).resize((lado, lado))
    mancha = mancha.point(lambda v: round(v * intensidad))
    capa = Image.new("L", size, 0)
    x = source.rng.randint(-lado // 2, size[0] - lado // 2)
    y = source.rng.randint(-lado // 2, size[1] - lado // 2)
    capa.paste(mancha, (x, y))
    return capa.convert("RGB")


def fotografiar(pagina: Image.Image, source: Source, nivel: Nivel) -> Image.Image:
    """La página como una foto de celular, derecha (la orientación EXIF va al guardarla)."""
    p = NIVELES[nivel]
    rng = source.rng
    hoja = pagina.convert("RGB")

    # 1. La hoja sobre la mesa.
    margen = round(max(hoja.size) * p.margen)
    size = (hoja.width + 2 * margen, hoja.height + 2 * margen)
    fondo = rng.choice(FONDOS)
    foto = _textura(source, size, fondo)
    foto.paste(hoja, (margen + rng.randint(-margen // 3, margen // 3), margen))

    # 2. Perspectiva: QUAD lleva un cuadrilátero de la entrada al rectángulo de salida. Mover
    # las esquinas de ese cuadrilátero hace que la hoja se vea inclinada respecto del teléfono.
    w, h = size
    d = [round(rng.uniform(-p.perspectiva, p.perspectiva) * min(w, h)) for _ in range(8)]
    quad = (d[0], d[1], d[2], h + d[3], w + d[4], h + d[5], w + d[6], d[7])
    foto = foto.transform(
        size, Image.Transform.QUAD, quad, Image.Resampling.BICUBIC, fillcolor=fondo
    )

    # 3. Torcida: el teléfono nunca está derecho.
    angulo = rng.uniform(-p.angulo, p.angulo)
    foto = foto.rotate(angulo, resample=Image.Resampling.BICUBIC, fillcolor=fondo)

    # 4. Luz: sombra de la mano hacia un borde y reflejo del flash.
    foto = ImageChops.multiply(foto, _sombra(source, size, rng.uniform(0, p.sombra)))
    foto = ImageChops.screen(foto, _reflejo(source, size, rng.uniform(0, p.reflejo)))

    # 5. Movida o fuera de foco.
    foto = foto.filter(ImageFilter.GaussianBlur(rng.uniform(*p.desenfoque)))

    # 6. Encuadre: a veces se corta un borde de la hoja.
    cortes = [round(rng.uniform(0, p.recorte) * lado) for lado in (w, h, w, h)]
    foto = foto.crop((cortes[0], cortes[1], w - cortes[2], h - cortes[3]))

    # 7. Tamaño de foto mandada por mensaje.
    escala = LADO_LARGO / max(foto.size)
    return foto.resize((round(foto.width * escala), round(foto.height * escala)))


def guardar_jpg(foto: Image.Image, orientacion: int, calidad: int) -> bytes:
    """JPG con los píxeles guardados como los guarda el teléfono para esa orientación EXIF.

    `foto` está derecha (como se tiene que ver). Se guarda girada de modo que un visor que
    respeta el EXIF (`ImageOps.exif_transpose`) la vuelva a mostrar derecha. El EXIF también
    marca la foto como sintética.
    """
    # Cómo se guarda para cada orientación: al revés del giro que pide el EXIF para mostrarla.
    # Pillow gira en sentido antihorario: ROTATE_90 es 90° antihorario.
    giro = {
        1: None,
        3: Image.Transpose.ROTATE_180,
        6: Image.Transpose.ROTATE_90,  # el visor la gira 90° horario
        8: Image.Transpose.ROTATE_270,  # el visor la gira 90° antihorario
    }[orientacion]
    guardada = foto if giro is None else foto.transpose(giro)

    exif = Image.Exif()
    exif[EXIF_ORIENTACION] = orientacion
    exif[EXIF_DESCRIPCION] = DESCRIPCION_EXIF
    buffer = BytesIO()
    guardada.save(buffer, "JPEG", quality=calidad, exif=exif.tobytes())
    return buffer.getvalue()


def orientacion_al_azar(source: Source) -> int:
    orientaciones = list(PESOS_ORIENTACION)
    return source.rng.choices(orientaciones, weights=list(PESOS_ORIENTACION.values()))[0]


def fotografiar_pdf(pdf: bytes, source: Source, nivel: Nivel) -> list[bytes]:
    """Un JPG por página del PDF. Cada página usa su propia sub-fuente."""
    fotos = []
    for i, pagina in enumerate(rasterizar(pdf)):
        sub = source.derive(f"foto:{i}")
        foto = fotografiar(pagina, sub, nivel)
        fotos.append(guardar_jpg(foto, orientacion_al_azar(sub), NIVELES[nivel].calidad_jpg))
    return fotos


def nombres_fotos(source: Source, n: int) -> list[str]:
    """`n` nombres como los de un teléfono, consecutivos desde un número al azar (IMG_4821.jpg,
    IMG_4822.jpg…): no dicen qué hay en la foto."""
    base = source.rng.randint(1000, 9999 - n)
    return [f"IMG_{base + i}.jpg" for i in range(n)]
