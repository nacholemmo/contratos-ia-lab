"""Tests del modo fotografiado de la CLI: lo que queda en disco es lo que leen las evals.

Generar fotos tarda: la CLI corre una sola vez (2 legajos, sin set forzado) y el set forzado
se prueba con una sola inconsistencia.
"""

from pathlib import Path

import pytest

from core.legajo import Etapa
from synthetic.cli import main
from synthetic.export_fotografiado import (
    CARPETA_DATOS,
    CARPETA_FOTOS,
    IndiceFotografiado,
    ManifestFotografiado,
    carpeta_forzado,
    carpeta_semilla,
    leer_esperado,
    validar_datos,
    write_forzados_fotografiado,
    write_legajo_fotografiado,
)
from synthetic.inconsistencias import ALERTA_DE, Inconsistencia, elegir_inconsistencias
from synthetic.legajo import contexto_legajo

SEED = 42
N = 2


@pytest.fixture(scope="module")
def salida(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("fotografiado")
    args = ["--modo", "fotografiado", "--n", str(N), "--seed", str(SEED), "--out", str(out)]
    assert main([*args, "--por-inconsistencia", "0"]) == 0
    return out


def indice(carpeta: Path) -> IndiceFotografiado:
    return IndiceFotografiado.model_validate_json((carpeta / "legajo.json").read_text())


def carpetas(out: Path) -> list[Path]:
    return [carpeta_semilla(out, s) for s in range(SEED, SEED + N)]


def test_manifest(salida):
    manifest = ManifestFotografiado.model_validate_json((salida / "manifest.json").read_text())
    assert manifest.semillas == list(range(SEED, SEED + N))
    assert manifest.sintetico is True
    assert manifest.etapa == Etapa.EVALUACION
    assert set(manifest.legajos_por_inconsistencia) == set(Inconsistencia)
    assert manifest.fotos == sum(indice(c).fotos for c in carpetas(salida))
    assert manifest.forzados == {}


def test_esperado_valida_contra_core(salida):
    """Lo que van a hacer las evals: cargar el ground truth con el modelo de core."""
    for carpeta in carpetas(salida):
        assert leer_esperado(carpeta).seed == indice(carpeta).seed


def test_fotos_en_disco_son_las_del_ground_truth(salida):
    for carpeta in carpetas(salida):
        esperado = leer_esperado(carpeta)
        en_disco = sorted(p.name for p in (carpeta / CARPETA_FOTOS).iterdir())
        assert en_disco == sorted(f.archivo for f in esperado.fotos)
        assert len(en_disco) == indice(carpeta).fotos
        for nombre in en_disco:
            assert (carpeta / CARPETA_FOTOS / nombre).read_bytes()[:3] == b"\xff\xd8\xff"


def test_cada_dato_valida_contra_su_modelo(salida):
    for carpeta in carpetas(salida):
        validar_datos(carpeta)


def test_cada_documento_tiene_su_json(salida):
    for carpeta in carpetas(salida):
        en_disco = {p.name for p in (carpeta / CARPETA_DATOS).iterdir()}
        assert {d.datos for d in leer_esperado(carpeta).documentos} == en_disco


def test_inconsistencias_sorteadas_por_la_semilla(salida):
    for carpeta in carpetas(salida):
        i = indice(carpeta)
        assert i.inconsistencias == elegir_inconsistencias(contexto_legajo(i.seed))


def test_cada_inconsistencia_en_disco_tiene_su_alerta(salida, tmp_path):
    """El criterio de la Fase 3, sobre lo escrito: también para un legajo forzado."""
    write_forzados_fotografiado(tmp_path, 200, 1, inconsistencias=[Inconsistencia.RECIBO_VIEJO])
    forzadas = list(carpeta_forzado(tmp_path, Inconsistencia.RECIBO_VIEJO).iterdir())
    for carpeta in [*carpetas(salida), *forzadas]:
        esperado = leer_esperado(carpeta)
        alertas = {a.tipo for a in esperado.alertas}
        for inconsistencia in indice(carpeta).inconsistencias:
            alerta = ALERTA_DE[inconsistencia]
            assert esperado.faltantes if alerta is None else alerta in alertas


def test_set_forzado_con_la_inconsistencia_sola(tmp_path):
    forzados = write_forzados_fotografiado(
        tmp_path, 100, 1, inconsistencias=[Inconsistencia.DNI_VENCIDO]
    )
    [seed] = forzados[Inconsistencia.DNI_VENCIDO]
    i = indice(carpeta_semilla(carpeta_forzado(tmp_path, Inconsistencia.DNI_VENCIDO), seed))
    assert i.inconsistencias == [Inconsistencia.DNI_VENCIDO]
    assert i.casos == []


def test_misma_semilla_mismos_bytes(salida, tmp_path):
    write_legajo_fotografiado(SEED, tmp_path)
    antes, despues = carpeta_semilla(salida, SEED), carpeta_semilla(tmp_path, SEED)
    archivos = sorted(p.relative_to(antes) for p in antes.rglob("*") if p.is_file())
    assert archivos == sorted(p.relative_to(despues) for p in despues.rglob("*") if p.is_file())
    for archivo in archivos:
        assert (antes / archivo).read_bytes() == (despues / archivo).read_bytes(), archivo


def test_por_inconsistencia_negativo_falla(tmp_path):
    with pytest.raises(SystemExit):
        main(["--modo", "fotografiado", "--out", str(tmp_path), "--por-inconsistencia", "-1"])
