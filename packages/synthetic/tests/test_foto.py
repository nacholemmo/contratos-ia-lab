"""Tests del legajo fotografiado: fotos de celular deterministas, con EXIF y tres niveles."""

from io import BytesIO

import pytest
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

from synthetic.dni import generate_dnis
from synthetic.foto import (
    DESCRIPCION_EXIF,
    EXIF_DESCRIPCION,
    EXIF_ORIENTACION,
    LADO_LARGO,
    PESOS_ORIENTACION,
    Nivel,
    fotografiar,
    fotografiar_pdf,
    guardar_jpg,
    nombres_fotos,
    orientacion_al_azar,
)
from synthetic.scan import rasterizar
from synthetic.source import Source


@pytest.fixture(scope="module")
def pdf_dni() -> bytes:
    pdf, _ = next(iter(generate_dnis(0).values()))
    return pdf


@pytest.fixture(scope="module")
def pagina(pdf_dni) -> Image.Image:
    return rasterizar(pdf_dni)[0]


def nitidez(imagen: Image.Image) -> float:
    """Cuánto borde tiene la imagen: el texto nítido tiene muchos; desenfocado, pocos."""
    return ImageStat.Stat(imagen.convert("L").filter(ImageFilter.FIND_EDGES)).var[0]


# --- fotografiar ---


@pytest.mark.parametrize("nivel", list(Nivel))
def test_foto_en_color_con_el_lado_largo_de_una_foto_de_mensaje(pagina, nivel):
    foto = fotografiar(pagina, Source(1), nivel)
    assert foto.mode == "RGB"
    assert max(foto.size) == LADO_LARGO


def test_foto_determinista(pagina):
    a = fotografiar(pagina, Source(1), Nivel.FUERTE)
    b = fotografiar(pagina, Source(1), Nivel.FUERTE)
    assert a.tobytes() == b.tobytes()


def test_semillas_distintas_fotos_distintas(pagina):
    a = fotografiar(pagina, Source(1), Nivel.LEVE)
    b = fotografiar(pagina, Source(2), Nivel.LEVE)
    assert a.tobytes() != b.tobytes()


def test_fotografiar_no_toca_la_entrada(pagina):
    copia = pagina.copy()
    fotografiar(pagina, Source(1), Nivel.FUERTE)
    assert pagina.tobytes() == copia.tobytes()


def test_la_ilegible_es_mucho_menos_nitida_que_la_leve(pagina):
    """En promedio de varias semillas: una sola podría caer en un caso raro."""
    leves = [nitidez(fotografiar(pagina, Source(s), Nivel.LEVE)) for s in range(3)]
    ilegibles = [nitidez(fotografiar(pagina, Source(s), Nivel.ILEGIBLE)) for s in range(3)]
    assert sum(ilegibles) < sum(leves) / 4


# --- guardar_jpg y la orientación EXIF ---


@pytest.fixture(scope="module")
def foto_vertical(pagina) -> Image.Image:
    return fotografiar(pagina, Source(1), Nivel.LEVE)


@pytest.mark.parametrize("orientacion", sorted(PESOS_ORIENTACION))
def test_un_visor_que_respeta_el_exif_la_muestra_derecha(foto_vertical, orientacion):
    jpg = guardar_jpg(foto_vertical, orientacion, calidad=90)
    vista = ImageOps.exif_transpose(Image.open(BytesIO(jpg)))
    assert vista.size == foto_vertical.size
    # JPEG pierde un poco: la diferencia media por píxel tiene que ser chica.
    diferencia = ImageStat.Stat(ImageChops.difference(vista.convert("RGB"), foto_vertical))
    assert max(diferencia.mean) < 4


@pytest.mark.parametrize("orientacion", [6, 8])
def test_con_orientacion_6_u_8_los_pixeles_se_guardan_acostados(foto_vertical, orientacion):
    """Es la trampa que el servicio tiene que manejar: sin aplicar el EXIF, la foto de un
    documento vertical llega apaisada."""
    guardada = Image.open(BytesIO(guardar_jpg(foto_vertical, orientacion, calidad=90)))
    assert guardada.size == (foto_vertical.height, foto_vertical.width)


def test_el_exif_dice_la_orientacion_y_que_es_sintetica(foto_vertical):
    exif = Image.open(BytesIO(guardar_jpg(foto_vertical, 6, calidad=90))).getexif()
    assert exif[EXIF_ORIENTACION] == 6
    assert exif[EXIF_DESCRIPCION] == DESCRIPCION_EXIF


def test_guardar_jpg_determinista(foto_vertical):
    assert guardar_jpg(foto_vertical, 3, 80) == guardar_jpg(foto_vertical, 3, 80)


def test_orientaciones_con_sus_pesos():
    vistas = [orientacion_al_azar(Source(s)) for s in range(400)]
    assert set(vistas) == set(PESOS_ORIENTACION)
    assert 0.3 < vistas.count(6) / len(vistas) < 0.5


# --- fotografiar_pdf y nombres ---


def test_una_foto_por_pagina_del_dni(pdf_dni):
    fotos = fotografiar_pdf(pdf_dni, Source(5), Nivel.LEVE)
    assert len(fotos) == 2  # frente y dorso
    for jpg in fotos:
        assert jpg[:3] == b"\xff\xd8\xff"  # JPEG


def test_misma_semilla_mismos_bytes(pdf_dni):
    assert fotografiar_pdf(pdf_dni, Source(5), Nivel.FUERTE) == fotografiar_pdf(
        pdf_dni, Source(5), Nivel.FUERTE
    )


def test_frente_y_dorso_con_fotos_distintas(pdf_dni):
    frente, dorso = fotografiar_pdf(pdf_dni, Source(5), Nivel.LEVE)
    assert frente != dorso


def test_nombres_consecutivos_que_no_dicen_nada():
    nombres = nombres_fotos(Source(1), 12)
    assert len(set(nombres)) == 12
    numeros = [int(n.removeprefix("IMG_").removesuffix(".jpg")) for n in nombres]
    assert numeros == list(range(numeros[0], numeros[0] + 12))
    assert all(1000 <= n <= 9999 for n in numeros)
    assert nombres == nombres_fotos(Source(1), 12)
