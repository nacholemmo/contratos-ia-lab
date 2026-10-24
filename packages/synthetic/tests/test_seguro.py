from datetime import timedelta
from io import BytesIO

import pytest
from pypdf import PdfReader

from core.models import Rol, SeguroInmueble
from synthetic.cases import ASEGURADORAS
from synthetic.fichas import direccion
from synthetic.legajo import contexto_legajo, sumar_meses
from synthetic.pdf import AVISO, MARCA
from synthetic.recibo import alquiler_en_pesos
from synthetic.seguro import SUMA_EN_ALQUILERES, VIGENCIA_MESES, generate_seguro

SEEDS = range(30)

CAMPOS = [n for n in SeguroInmueble.model_fields if not n.endswith("_evidencia")]


def _texto(pdf: bytes) -> str:
    return " ".join(PdfReader(BytesIO(pdf)).pages[0].extract_text().split())


@pytest.mark.parametrize("seed", SEEDS)
def test_seguro_coherente_con_el_contrato(seed):
    _, seguro = generate_seguro(seed)
    contexto = contexto_legajo(seed)
    c = contexto.limpio
    # Los dos cruces: el inmueble asegurado es el alquilado y la vigencia arranca con la locación.
    assert seguro.ubicacion_riesgo == direccion(c.propiedad)
    assert seguro.vigencia_desde == c.fecha_inicio
    assert seguro.vigencia_hasta + timedelta(days=1) == sumar_meses(c.fecha_inicio, VIGENCIA_MESES)
    assert seguro.asegurado == contexto.partes(Rol.INQUILINO)[0].nombre
    assert seguro.aseguradora in ASEGURADORAS


@pytest.mark.parametrize("seed", SEEDS)
def test_suma_asegurada_en_rango_y_redonda(seed):
    _, seguro = generate_seguro(seed)
    alquiler = alquiler_en_pesos(contexto_legajo(seed).limpio)
    minimo, maximo = SUMA_EN_ALQUILERES
    # El redondeo a cien mil corre la suma, como mucho, medio redondeo.
    assert alquiler * minimo - 50_000 <= seguro.suma_asegurada <= alquiler * maximo + 50_000
    assert seguro.suma_asegurada % 100_000 == 0
    assert seguro.suma_asegurada > 0


@pytest.mark.parametrize("seed", SEEDS)
def test_evidencia_de_cada_dato_en_el_seguro(seed):
    pdf, seguro = generate_seguro(seed)
    texto = _texto(pdf)
    assert len(PdfReader(BytesIO(pdf)).pages) == 1
    for campo in CAMPOS:
        evidencia = getattr(seguro, f"{campo}_evidencia")
        assert evidencia is not None, campo
        assert evidencia.pagina == 1
        assert " ".join(evidencia.texto.split()) in texto, (campo, evidencia.texto)


def test_seguro_marcado_como_sintetico():
    pdf, _ = generate_seguro(0)
    texto = _texto(pdf)
    assert AVISO in texto
    assert MARCA in texto
    assert PdfReader(BytesIO(pdf)).metadata.subject == AVISO


def test_misma_semilla_mismo_seguro():
    assert generate_seguro(5) == generate_seguro(5)


def test_seguro_valida_contra_su_modelo():
    _, seguro = generate_seguro(2)
    assert SeguroInmueble.model_validate_json(seguro.model_dump_json()) == seguro
