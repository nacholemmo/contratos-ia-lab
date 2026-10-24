from datetime import date, timedelta
from io import BytesIO

import pytest
from pypdf import PdfReader

from core.models import PolizaCaucion, Rol, TituloPropiedad
from synthetic.cases import CasoDificil, datos_caucion
from synthetic.contracts import generate_contrato
from synthetic.dni import generate_dnis, sumar_anios
from synthetic.fichas import direccion
from synthetic.garantia import EDAD_MIN_ESCRITURA, generate_caucion, generate_titulos
from synthetic.legajo import contexto_legajo, fin_de_contrato, sumar_meses
from synthetic.pdf import AVISO, MARCA, prepare_sample

SEEDS = range(30)
CAUCION = [CasoDificil.SEGURO_DE_CAUCION]


def _texto(pdf: bytes) -> str:
    return " ".join(PdfReader(BytesIO(pdf)).pages[0].extract_text().split())


def _campos(modelo) -> list[str]:
    return [n for n in modelo.model_fields if not n.endswith("_evidencia")]


def _evidencia_en_la_ficha(pdf: bytes, doc) -> None:
    texto = _texto(pdf)
    assert len(PdfReader(BytesIO(pdf)).pages) == 1
    for campo in _campos(type(doc)):
        evidencia = getattr(doc, f"{campo}_evidencia")
        assert evidencia is not None, campo
        assert evidencia.pagina == 1
        assert " ".join(evidencia.texto.split()) in texto, (campo, evidencia.texto)
    assert AVISO in texto
    assert MARCA in texto
    assert PdfReader(BytesIO(pdf)).metadata.subject == AVISO


def _seed_con_garantes() -> int:
    return next(s for s in SEEDS if any(p.rol == Rol.GARANTE for p in generate_contrato(s).partes))


# --- fechas ---


def test_sumar_meses():
    assert sumar_meses(date(2025, 3, 1), 24) == date(2027, 3, 1)
    assert sumar_meses(date(2025, 11, 1), 3) == date(2026, 2, 1)
    assert sumar_meses(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert sumar_meses(date(2025, 1, 31), 1) == date(2025, 2, 28)


def test_fin_de_contrato():
    contrato = generate_contrato(0)
    fin = fin_de_contrato(contrato)
    assert fin + timedelta(days=1) == sumar_meses(contrato.fecha_inicio, contrato.plazo_meses)


# --- títulos de los garantes ---


@pytest.mark.parametrize("seed", SEEDS)
def test_un_titulo_por_garante_que_firma(seed):
    garantes = [p.id for p in prepare_sample(seed)[1].partes if p.rol == Rol.GARANTE]
    assert list(generate_titulos(seed)) == garantes


@pytest.mark.parametrize("seed", SEEDS)
def test_titulo_coherente_con_el_dni_y_el_contrato(seed):
    contexto = contexto_legajo(seed)
    dnis = generate_dnis(seed)
    for persona_id, (_, titulo) in generate_titulos(seed).items():
        _, dni = dnis[persona_id]
        assert titulo.titular_dni == dni.numero
        assert titulo.titular.upper() == f"{dni.nombre} {dni.apellido}"
        assert sumar_anios(dni.fecha_nacimiento, EDAD_MIN_ESCRITURA) <= titulo.fecha_escritura
        assert titulo.fecha_escritura <= contexto.referencia
        # El garante responde con otro inmueble, no con el que se alquila.
        assert titulo.inmueble != direccion(contexto.limpio.propiedad)


@pytest.mark.parametrize("seed", SEEDS)
def test_evidencia_de_cada_dato_en_el_titulo(seed):
    for pdf, titulo in generate_titulos(seed).values():
        _evidencia_en_la_ficha(pdf, titulo)


def test_con_caucion_no_hay_titulos():
    assert generate_titulos(_seed_con_garantes(), casos=CAUCION) == {}


# --- póliza de caución ---


def test_sin_el_caso_no_hay_caucion():
    assert generate_caucion(_seed_con_garantes(), casos=[]) is None


def test_caucion_coincide_con_la_clausula_del_contrato():
    seed = _seed_con_garantes()
    _, poliza = generate_caucion(seed, casos=CAUCION)
    _, _, clauses = prepare_sample(seed, CAUCION)
    garantia = next(c.texto for c in clauses if c.nombre == "garantia")
    datos = datos_caucion(seed)
    # El cruce: la póliza del legajo es la que nombra el contrato.
    assert (poliza.aseguradora, poliza.numero_poliza) == (datos.aseguradora, datos.poliza)
    assert poliza.aseguradora in garantia
    assert poliza.numero_poliza in garantia


def test_caucion_cubre_todo_el_contrato():
    seed = _seed_con_garantes()
    _, poliza = generate_caucion(seed, casos=CAUCION)
    contexto = contexto_legajo(seed, CAUCION)
    c = contexto.limpio
    assert poliza.vigencia_desde == c.fecha_inicio
    assert poliza.vigencia_hasta == fin_de_contrato(c)
    assert poliza.suma_asegurada == c.monto_inicial * c.plazo_meses
    assert poliza.moneda == c.moneda
    for inquilino in contexto.partes(Rol.INQUILINO):
        assert inquilino.nombre in poliza.tomador
    for propietario in contexto.partes(Rol.PROPIETARIO):
        assert propietario.nombre in poliza.asegurado


def test_evidencia_de_cada_dato_en_la_caucion():
    pdf, poliza = generate_caucion(_seed_con_garantes(), casos=CAUCION)
    _evidencia_en_la_ficha(pdf, poliza)


def test_misma_semilla_misma_garantia():
    seed = _seed_con_garantes()
    assert generate_titulos(seed) == generate_titulos(seed)
    assert generate_caucion(seed, casos=CAUCION) == generate_caucion(seed, casos=CAUCION)


def test_modelos_validan():
    seed = _seed_con_garantes()
    for _, titulo in generate_titulos(seed).values():
        assert TituloPropiedad.model_validate_json(titulo.model_dump_json()) == titulo
    _, poliza = generate_caucion(seed, casos=CAUCION)
    assert PolizaCaucion.model_validate_json(poliza.model_dump_json()) == poliza
