from io import BytesIO

import pytest
from PIL import Image, ImageChops, ImageStat
from pypdf import PdfReader

from synthetic.cases import CasoDificil
from synthetic.pdf import AVISO, generate_sample
from synthetic.scan import DPI, degradar, rasterizar
from synthetic.source import Source

ESCANEO = [CasoDificil.ESCANEO_TORCIDO]
SEEDS = range(5)  # rasterizar es lento: pocas semillas alcanzan


@pytest.fixture(scope="module")
def pagina() -> Image.Image:
    pdf, _ = generate_sample(0, casos=[])
    return rasterizar(pdf)[0]


# --- rasterizar ---


def test_rasterizar_una_imagen_por_pagina_en_grises():
    pdf, _ = generate_sample(1, casos=[])
    imagenes = rasterizar(pdf)
    assert len(imagenes) == len(PdfReader(BytesIO(pdf)).pages)
    for imagen in imagenes:
        assert imagen.mode == "L"
        # A4 (210 mm de ancho) a DPI puntos por pulgada (25,4 mm).
        assert abs(imagen.width - 210 / 25.4 * DPI) <= 2


# --- degradar ---


def test_degradar_mantiene_tamanio_y_modo(pagina):
    degradada = degradar(pagina, Source(1))
    assert degradada.size == pagina.size
    assert degradada.mode == pagina.mode


def test_degradar_es_determinista(pagina):
    a, b = degradar(pagina, Source(1)), degradar(pagina, Source(1))
    assert a.tobytes() == b.tobytes()


def test_degradar_cambia_la_pagina(pagina):
    degradada = degradar(pagina, Source(1))
    assert ImageChops.difference(pagina, degradada).getbbox() is not None
    # Semillas distintas, escaneos distintos (otro ángulo, otro ruido).
    assert degradada.tobytes() != degradar(pagina, Source(2)).tobytes()


def test_degradar_no_toca_la_entrada(pagina):
    copia = pagina.copy()
    degradar(pagina, Source(1))
    assert pagina.tobytes() == copia.tobytes()


def test_degradada_sigue_siendo_legible(pagina):
    # Una fotocopia es más gris, no una página negra: el fondo sigue siendo claro.
    brillo = ImageStat.Stat(degradar(pagina, Source(1))).mean[0]
    assert 150 < brillo < ImageStat.Stat(pagina).mean[0]


# --- contrato escaneado ---


@pytest.mark.parametrize("seed", SEEDS)
def test_escaneado_sin_capa_de_texto(seed):
    pdf, _ = generate_sample(seed, casos=ESCANEO)
    for pagina in PdfReader(BytesIO(pdf)).pages:
        assert pagina.extract_text().strip() == ""


@pytest.mark.parametrize("seed", SEEDS)
def test_escaneado_mismas_paginas_y_mismo_ground_truth_que_el_gemelo(seed):
    # La evidencia se verifica en el gemelo con texto: acá alcanza con que coincidan.
    pdf, muestra = generate_sample(seed, casos=ESCANEO)
    pdf_texto, muestra_texto = generate_sample(seed, casos=[])
    assert len(PdfReader(BytesIO(pdf)).pages) == len(PdfReader(BytesIO(pdf_texto)).pages)
    assert muestra.contrato == muestra_texto.contrato
    assert muestra.casos == ESCANEO


def test_escaneado_marcado_como_sintetico():
    pdf, _ = generate_sample(0, casos=ESCANEO)
    assert PdfReader(BytesIO(pdf)).metadata.subject == AVISO


def test_escaneado_misma_semilla_mismos_bytes():
    assert generate_sample(3, casos=ESCANEO)[0] == generate_sample(3, casos=ESCANEO)[0]
