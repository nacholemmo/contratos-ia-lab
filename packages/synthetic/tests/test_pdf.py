from io import BytesIO

import pytest
from pypdf import PdfReader

from core.models import Contrato
from synthetic.contracts import generate_contrato
from synthetic.pdf import AVISO, MARCA, generate_contract, generate_sample

SEEDS = range(50)

CAMPOS_CON_EVIDENCIA = sorted(
    name.removesuffix("_evidencia") for name in Contrato.model_fields if name.endswith("_evidencia")
)


def _normalizar(texto: str) -> str:
    # El PDF corta líneas donde quiere: se comparan las palabras, no los saltos.
    return " ".join(texto.split())


def _paginas(pdf: bytes) -> list[str]:
    return [_normalizar(p.extract_text()) for p in PdfReader(BytesIO(pdf)).pages]


def test_misma_semilla_mismo_pdf():
    for seed in range(5):
        assert generate_contract(seed) == generate_contract(seed)


def test_semillas_distintas_pdf_distinto():
    assert generate_contract(1)[0] != generate_contract(2)[0]


@pytest.mark.parametrize("seed", range(10))
def test_marca_sintetico_en_cada_pagina(seed):
    pdf, _ = generate_contract(seed)
    for numero, texto in enumerate(_paginas(pdf), start=1):
        assert AVISO in texto, numero
        assert f"{MARCA} · Página {numero}" in texto, numero
    assert PdfReader(BytesIO(pdf)).metadata.subject == AVISO


@pytest.mark.parametrize("seed", SEEDS)
def test_evidencia_aparece_en_su_pagina(seed):
    pdf, contrato = generate_contract(seed)
    paginas = _paginas(pdf)
    evidencias = [getattr(contrato, f"{c}_evidencia") for c in CAMPOS_CON_EVIDENCIA]
    for evidencia in [e for e in evidencias if e is not None] + contrato.clausulas:
        assert evidencia.pagina <= len(paginas)
        assert _normalizar(evidencia.texto) in paginas[evidencia.pagina - 1], evidencia


@pytest.mark.parametrize("seed", SEEDS)
def test_todo_dato_presente_tiene_evidencia(seed):
    _, contrato = generate_contract(seed)
    for campo in CAMPOS_CON_EVIDENCIA:
        presente = getattr(contrato, campo) is not None
        assert presente == (getattr(contrato, f"{campo}_evidencia") is not None), campo
    assert len(contrato.clausulas) == 2


@pytest.mark.parametrize("seed", range(10))
def test_ground_truth_no_cambia_los_datos(seed):
    # Sin casos difíciles: los faltantes sí cambian datos a propósito (test_cases.py).
    _, muestra = generate_sample(seed, casos=[])
    contrato = muestra.contrato
    excluir = {f"{c}_evidencia" for c in CAMPOS_CON_EVIDENCIA} | {"clausulas"}
    assert contrato.model_dump(exclude=excluir) == generate_contrato(seed).model_dump(
        exclude=excluir
    )


def test_hay_contratos_de_varias_paginas_con_evidencia_despues_de_la_primera():
    # Si todo entrara en una página, el test de evidencia no probaría nada sobre páginas.
    paginas_por_seed = {}
    evidencia_tardia = False
    for seed in SEEDS:
        pdf, contrato = generate_contract(seed)
        paginas_por_seed[seed] = len(PdfReader(BytesIO(pdf)).pages)
        evidencia_tardia |= any(e.pagina > 1 for e in contrato.clausulas)
    assert max(paginas_por_seed.values()) >= 2
    assert evidencia_tardia
