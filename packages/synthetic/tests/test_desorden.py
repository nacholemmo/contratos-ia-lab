"""Tests del desorden del legajo: intrusas, duplicadas, ilegibles, mezcla y renombre.

Generar fotos tarda (~1 s cada una): se usa el legajo más chico y se reutiliza.
"""

from collections import Counter

import pytest

from core.legajo import (
    DocumentoEsperado,
    Etapa,
    FotoEsperada,
    LegajoEsperado,
    MotivoDescarte,
    PersonaEsperada,
)
from core.models import Moneda, Rol, TipoDocumento
from synthetic.desorden import SIN_DESORDEN, Desorden, desordenar, renombrar
from synthetic.foto import Nivel
from synthetic.fotografiado import generate_legajo
from synthetic.intrusas import Intrusa, generate_intrusa
from synthetic.source import Source

# 42: un inquilino, sin garantes: el legajo más chico.
SEED_CHICO = 42
# Una de cada cosa, para poder contarlas.
UNA_DE_CADA = Desorden(duplicadas=(1, 1), resacados=(1, 1), ilegibles=(1, 1), intrusas=(1, 1))


@pytest.fixture(scope="module")
def prolijo():
    return generate_legajo(SEED_CHICO, Etapa.EVALUACION)


@pytest.fixture(scope="module")
def desordenado(prolijo):
    return desordenar(prolijo, UNA_DE_CADA)


def descartes(esperado: LegajoEsperado) -> Counter:
    return Counter(f.descarte for f in esperado.fotos if f.descarte is not None)


def en_documentos(esperado: LegajoEsperado) -> list[str]:
    return [a for d in esperado.documentos for a in d.fotos]


# --- renombrar (sin fotos: rápido) ---


def legajo_minimo() -> LegajoEsperado:
    return LegajoEsperado(
        seed=1,
        etapa=Etapa.EVALUACION,
        alquiler_propuesto="500000.00",
        moneda=Moneda.ARS,
        personas=[PersonaEsperada(id="p1", rol=Rol.INQUILINO, nombre="Ana Pérez", dni="30111222")],
        documentos=[
            DocumentoEsperado(id="d1", tipo=TipoDocumento.DNI, persona_id="p1", fotos=["a", "b"])
        ],
        fotos=[
            FotoEsperada(archivo="a"),
            FotoEsperada(archivo="b"),
            FotoEsperada(archivo="c", descarte=MotivoDescarte.DUPLICADA, duplicada_de="a"),
            FotoEsperada(archivo="d", descarte=MotivoDescarte.INTRUSA),
        ],
    )


NUEVOS = {"a": "IMG_2.jpg", "b": "IMG_4.jpg", "c": "IMG_1.jpg", "d": "IMG_3.jpg"}


def test_renombrar_las_fotos_sin_cambiar_el_orden():
    e = renombrar(legajo_minimo(), NUEVOS)
    assert [f.archivo for f in e.fotos] == ["IMG_2.jpg", "IMG_4.jpg", "IMG_1.jpg", "IMG_3.jpg"]


def test_renombrar_las_fotos_de_cada_documento():
    e = renombrar(legajo_minimo(), NUEVOS)
    assert e.documentos[0].fotos == ["IMG_2.jpg", "IMG_4.jpg"]


def test_renombrar_duplicada_de():
    e = renombrar(legajo_minimo(), NUEVOS)
    assert e.fotos[2].duplicada_de == "IMG_2.jpg"
    assert e.fotos[3].duplicada_de is None


def test_renombrar_conserva_descartes_y_el_resto():
    original = legajo_minimo()
    e = renombrar(original, NUEVOS)
    assert [f.descarte for f in e.fotos] == [f.descarte for f in original.fotos]
    assert e.personas == original.personas
    assert e.documentos[0].id == "d1"


def test_renombrar_no_modifica_el_original():
    original = legajo_minimo()
    renombrar(original, NUEVOS)
    assert original.fotos[0].archivo == "a"
    assert original.documentos[0].fotos == ["a", "b"]


def test_renombrar_da_un_legajo_valido():
    e = renombrar(legajo_minimo(), NUEVOS)
    LegajoEsperado.model_validate(e.model_dump())


# --- intrusas ---


@pytest.mark.parametrize("tipo", list(Intrusa))
def test_cada_intrusa_es_un_jpg(tipo):
    jpg = generate_intrusa(tipo, Source(1))
    assert jpg[:3] == b"\xff\xd8\xff"


@pytest.mark.parametrize("tipo", list(Intrusa))
def test_intrusa_determinista(tipo):
    assert generate_intrusa(tipo, Source(7)) == generate_intrusa(tipo, Source(7))


# --- desordenar ---


def test_sin_desorden_mismas_fotos_y_documentos(prolijo):
    d = desordenar(prolijo, SIN_DESORDEN)
    assert sorted(d.fotos.values()) == sorted(prolijo.fotos.values())
    assert descartes(d.esperado) == Counter()
    assert len(d.esperado.documentos) == len(prolijo.esperado.documentos)


def test_una_de_cada_cosa(prolijo, desordenado):
    paginas_resacadas = len(desordenado.fotos) - len(prolijo.fotos) - 3
    assert paginas_resacadas >= 1
    assert descartes(desordenado.esperado) == Counter(
        {
            MotivoDescarte.DUPLICADA: 1 + paginas_resacadas,
            MotivoDescarte.ILEGIBLE: 1,
            MotivoDescarte.INTRUSA: 1,
        }
    )


def test_documentos_y_datos_no_cambian(prolijo, desordenado):
    antes, despues = prolijo.esperado.documentos, desordenado.esperado.documentos
    assert [(d.id, d.tipo, d.persona_id, d.datos) for d in antes] == [
        (d.id, d.tipo, d.persona_id, d.datos) for d in despues
    ]
    assert desordenado.datos == prolijo.datos
    assert desordenado.esperado.alertas == prolijo.esperado.alertas


def test_cada_documento_conserva_sus_bytes_en_orden(prolijo, desordenado):
    """Renombrar no cambia qué foto es cada página: los bytes de cada documento son los
    mismos y en el mismo orden (frente antes que dorso)."""
    for antes, despues in zip(
        prolijo.esperado.documentos, desordenado.esperado.documentos, strict=True
    ):
        assert [prolijo.fotos[a] for a in antes.fotos] == [
            desordenado.fotos[a] for a in despues.fotos
        ]


def test_la_duplicada_exacta_tiene_los_mismos_bytes(desordenado):
    e, fotos = desordenado.esperado, desordenado.fotos
    exactas = [
        f
        for f in e.fotos
        if f.duplicada_de is not None and fotos[f.archivo] == fotos[f.duplicada_de]
    ]
    assert len(exactas) >= 1


def test_nombres_consecutivos_en_el_orden_final(desordenado):
    archivos = [f.archivo for f in desordenado.esperado.fotos]
    numeros = [int(a.removeprefix("IMG_").removesuffix(".jpg")) for a in archivos]
    assert numeros == list(range(numeros[0], numeros[0] + len(numeros)))
    assert list(desordenado.fotos) == archivos


def test_los_nombres_no_delatan_los_documentos(prolijo, desordenado):
    """Con fotos mezcladas, las páginas de los documentos ya no son la primera tira de
    nombres: el orden de llegada no es el de los documentos."""
    archivos = [f.archivo for f in desordenado.esperado.fotos]
    paginas = en_documentos(desordenado.esperado)
    assert archivos[: len(paginas)] != paginas


def test_no_quedan_nombres_provisorios(desordenado):
    assert not any(a.startswith("nuevo_") for a in desordenado.fotos)


def test_misma_semilla_mismo_desorden(prolijo, desordenado):
    otra = desordenar(prolijo, UNA_DE_CADA)
    assert otra.fotos == desordenado.fotos
    assert otra.esperado == desordenado.esperado


def test_nivel_fuerte_tambien_desordena(prolijo):
    d = desordenar(prolijo, Desorden((0, 0), (0, 0), (0, 0), (1, 1)), Nivel.FUERTE)
    assert descartes(d.esperado) == Counter({MotivoDescarte.INTRUSA: 1})
