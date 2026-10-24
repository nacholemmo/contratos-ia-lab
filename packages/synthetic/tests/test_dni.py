from datetime import date
from io import BytesIO

import pytest
from pypdf import PdfReader

from core.models import DNI, Rol
from synthetic.cases import CasoDificil
from synthetic.contracts import generate_contrato, generate_contrato_con_identidades
from synthetic.dni import (
    EDAD_MAX,
    EDAD_MIN,
    EDAD_ULTIMA_ACTUALIZACION,
    P_MISMA_PROVINCIA,
    VIGENCIA_DNI_ANIOS,
    fechas_dni,
    generate_dnis,
)
from synthetic.pdf import AVISO, MARCA, generate_sample, prepare_sample
from synthetic.source import Source

SEEDS = range(20)

CAMPOS = [n for n in DNI.model_fields if not n.endswith("_evidencia")]


def _edad(nacimiento: date, dia: date) -> int:
    # Años cumplidos: se resta uno si todavía no llegó el cumpleaños de ese año.
    return dia.year - nacimiento.year - ((dia.month, dia.day) < (nacimiento.month, nacimiento.day))


def _texto(pdf: bytes) -> str:
    return " ".join(PdfReader(BytesIO(pdf)).pages[0].extract_text().split())


# --- fechas_dni ---

REFERENCIA = date(2024, 6, 15)
# Muchas semillas: es barato y así aparece alguna emisión un 29 de febrero.
SEEDS_FECHAS = range(3000)


@pytest.fixture(scope="module")
def fechas() -> list[tuple[date, date, date]]:
    return [fechas_dni(Source(seed), REFERENCIA) for seed in SEEDS_FECHAS]


def test_fechas_dni_es_determinista():
    assert fechas_dni(Source(4), REFERENCIA) == fechas_dni(Source(4), REFERENCIA)


def test_persona_adulta_a_la_fecha_de_firma(fechas):
    for nacimiento, _, _ in fechas:
        assert EDAD_MIN <= _edad(nacimiento, REFERENCIA) <= EDAD_MAX, nacimiento


def test_emision_despues_de_la_ultima_actualizacion_y_antes_de_la_firma(fechas):
    for nacimiento, emision, _ in fechas:
        assert _edad(nacimiento, emision) >= EDAD_ULTIMA_ACTUALIZACION, (nacimiento, emision)
        assert emision <= REFERENCIA


def test_vencimiento_a_los_15_anios_de_la_emision(fechas):
    for _, emision, vencimiento in fechas:
        assert vencimiento.year == emision.year + VIGENCIA_DNI_ANIOS
        if (emision.month, emision.day) == (2, 29):
            # El año del vencimiento puede no ser bisiesto: 28/2 o 1/3, las dos valen.
            assert (vencimiento.month, vencimiento.day) in ((2, 28), (3, 1))
        else:
            assert (vencimiento.month, vencimiento.day) == (emision.month, emision.day)


def test_dni_vigente_a_la_fecha_de_firma(fechas):
    # Un DNI vencido sería un caso difícil del legajo (etiquetado), no un efecto colateral.
    for _, _, vencimiento in fechas:
        assert vencimiento > REFERENCIA


def test_fechas_coherentes_con_firma_un_29_de_febrero():
    # Firma un 29/2: hace 18 años no existe ese día, y el rango tiene que seguir valiendo.
    referencia = date(2024, 2, 29)
    for seed in range(500):
        nacimiento, emision, vencimiento = fechas_dni(Source(seed), referencia)
        assert EDAD_MIN <= _edad(nacimiento, referencia) <= EDAD_MAX
        assert emision <= referencia < vencimiento


def test_hay_variedad_de_edades(fechas):
    edades = {_edad(nacimiento, REFERENCIA) for nacimiento, _, _ in fechas}
    assert min(edades) < 30
    assert max(edades) > 60


# --- generate_dnis ---


@pytest.mark.parametrize("seed", SEEDS)
def test_un_dni_por_parte_coherente_con_el_contrato(seed):
    contrato, identidades = generate_contrato_con_identidades(seed)
    firmantes = [p.id for p in prepare_sample(seed)[1].partes]
    dnis = generate_dnis(seed)
    assert list(dnis) == firmantes
    for persona in [p for p in contrato.partes if p.id in firmantes]:
        _, dni = dnis[persona.id]
        identidad = identidades[persona.id]
        assert dni.numero == persona.dni
        assert dni.sexo == identidad.sexo
        # El cruce que se va a evaluar en la Fase 4: mismo nombre, en mayúsculas en el DNI.
        assert f"{dni.nombre} {dni.apellido}" == persona.nombre.upper()


def test_misma_semilla_mismos_dni():
    assert generate_dnis(3) == generate_dnis(3)


@pytest.mark.parametrize("seed", SEEDS)
def test_evidencia_de_cada_dato_en_la_ficha(seed):
    for pdf, dni in generate_dnis(seed).values():
        texto = _texto(pdf)
        assert len(PdfReader(BytesIO(pdf)).pages) == 1
        for campo in CAMPOS:
            evidencia = getattr(dni, f"{campo}_evidencia")
            assert (getattr(dni, campo) is None) == (evidencia is None), campo
            if evidencia is not None:
                assert evidencia.pagina == 1
                assert " ".join(evidencia.texto.split()) in texto, (campo, evidencia.texto)


def test_ficha_marcada_como_sintetica():
    pdf, _ = next(iter(generate_dnis(0).values()))
    texto = _texto(pdf)
    assert AVISO in texto
    assert MARCA in texto
    assert PdfReader(BytesIO(pdf)).metadata.subject == AVISO


def test_ficha_no_imita_el_documento_oficial():
    # Nada que la haga pasar por un DNI real: ni el emisor ni los textos de la tarjeta.
    for seed in range(5):
        for pdf, _ in generate_dnis(seed).values():
            texto = _texto(pdf).upper()
            for oficial in ("REPÚBLICA ARGENTINA", "RENAPER", "MERCOSUR", "REGISTRO NACIONAL"):
                assert oficial not in texto


def test_persona_sin_documento_en_el_contrato_lo_tiene_en_su_dni():
    # El cruce que completa un dato faltante: el contrato no trae el DNI, la ficha sí.
    seed = 2
    _, muestra = generate_sample(seed, casos=[CasoDificil.PERSONA_SIN_DOCUMENTO])
    sin_doc = next(p for p in muestra.contrato.partes if p.dni is None)
    _, dni = generate_dnis(seed)[sin_doc.id]
    original = next(p for p in generate_contrato(seed).partes if p.id == sin_doc.id)
    assert dni.numero == original.dni


def test_con_caucion_no_hay_dni_de_garantes():
    # Con el caso, el contrato no tiene garantes: el legajo tampoco trae sus DNI.
    seed = next(
        s for s in SEEDS if any(p.rol == Rol.GARANTE for p in generate_contrato(s).partes)
    )
    dnis = generate_dnis(seed, casos=[CasoDificil.SEGURO_DE_CAUCION])
    garantes = {p.id for p in generate_contrato(seed).partes if p.rol == Rol.GARANTE}
    assert garantes
    assert not garantes & set(dnis)


def test_domicilio_casi_siempre_en_la_provincia_del_inmueble():
    misma = total = mendoza = 0
    for seed in range(150):
        provincia = generate_contrato(seed).propiedad.provincia.upper()
        for _, dni in generate_dnis(seed).values():
            provincia_dni = dni.domicilio.rsplit(" - ", 1)[-1]
            misma += provincia_dni == provincia
            mendoza += provincia_dni == "MENDOZA"
            total += 1
    # Al menos P_MISMA_PROVINCIA (el resto también puede caer en la misma, por los pesos).
    assert P_MISMA_PROVINCIA - 0.05 <= misma / total <= 0.97
    # Y así los legajos quedan mayormente en Mendoza, como los inmuebles.
    assert mendoza / total > 0.6
