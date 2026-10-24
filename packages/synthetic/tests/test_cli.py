from pathlib import Path

import pytest

from core.models import Rol, TipoDocumento
from synthetic.cases import CasoDificil, es_aplicable
from synthetic.cli import main
from synthetic.contracts import generate_contrato
from synthetic.export import (
    MODELOS,
    IndiceLegajo,
    Manifest,
    carpeta_forzado,
    carpeta_semilla,
    semillas_forzadas,
)

SEED = 40
N = 4
POR_CASO = 1


@pytest.fixture(scope="module")
def salida(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("synthetic")
    args = ["--n", str(N), "--seed", str(SEED), "--out", str(out), "--por-caso", str(POR_CASO)]
    assert main(args) == 0
    return out


def _indices(out: Path) -> list[IndiceLegajo]:
    return [
        IndiceLegajo.model_validate_json((carpeta_semilla(out, s) / "legajo.json").read_text())
        for s in range(SEED, SEED + N)
    ]


def test_manifest(salida):
    manifest = Manifest.model_validate_json((salida / "manifest.json").read_text())
    assert manifest.semillas == list(range(SEED, SEED + N))
    assert manifest.sintetico is True
    assert set(manifest.contratos_por_caso) == set(CasoDificil)
    assert manifest.documentos_por_modelo["Muestra"] == N


def test_cada_json_valida_contra_su_modelo(salida):
    # Criterio de "Terminado cuando" de la Fase 1.
    for indice in _indices(salida):
        carpeta = carpeta_semilla(salida, indice.seed)
        for doc in indice.documentos:
            MODELOS[doc.modelo].model_validate_json((carpeta / doc.datos).read_text())
            assert (carpeta / doc.pdf).read_bytes().startswith(b"%PDF"), doc.pdf


def test_legajo_completo_y_coherente(salida):
    for indice in _indices(salida):
        carpeta = carpeta_semilla(salida, indice.seed)
        por_tipo = {}
        for doc in indice.documentos:
            por_tipo.setdefault(doc.tipo, []).append(doc)
        assert len(por_tipo[TipoDocumento.CONTRATO]) == 1
        assert len(por_tipo[TipoDocumento.SEGURO]) == 1

        contrato = (
            MODELOS["Muestra"]
            .model_validate_json((carpeta / por_tipo[TipoDocumento.CONTRATO][0].datos).read_text())
            .contrato
        )
        assert (
            indice.casos
            == MODELOS["Muestra"].model_validate_json((carpeta / "contrato.json").read_text()).casos
        )
        # Un DNI por parte que firma y un recibo por inquilino, cada uno con su persona.
        assert {d.persona_id for d in por_tipo[TipoDocumento.DNI]} == {
            p.id for p in contrato.partes
        }
        inquilinos = {p.id for p in contrato.partes if p.rol == Rol.INQUILINO}
        assert {d.persona_id for d in por_tipo[TipoDocumento.RECIBO_SUELDO]} == inquilinos
        # Garantía: un título por garante, o la póliza de caución sin persona.
        garantes = {p.id for p in contrato.partes if p.rol == Rol.GARANTE}
        garantias = por_tipo.get(TipoDocumento.GARANTIA, [])
        if CasoDificil.SEGURO_DE_CAUCION in indice.casos:
            assert [(d.modelo, d.persona_id) for d in garantias] == [("PolizaCaucion", None)]
        else:
            assert {d.persona_id for d in garantias} == garantes
            assert all(d.modelo == "TituloPropiedad" for d in garantias)


def test_archivos_con_nombres_por_rol(salida):
    carpeta = carpeta_semilla(salida, SEED)
    assert (carpeta / "contrato.pdf").exists()
    assert (carpeta / "dni_propietario_1.pdf").exists()
    assert (carpeta / "dni_inquilino_1.json").exists()
    assert (carpeta / "recibo_inquilino_1.pdf").exists()
    assert (carpeta / "seguro.json").exists()


def test_misma_semilla_mismos_archivos(salida, tmp_path):
    # Criterio de "Terminado cuando": misma semilla, mismos datos y mismo PDF.
    args = ["--n", "2", "--seed", str(SEED), "--out", str(tmp_path), "--por-caso", "0"]
    assert main(args) == 0
    for seed in (SEED, SEED + 1):
        nueva, original = carpeta_semilla(tmp_path, seed), carpeta_semilla(salida, seed)
        archivos = sorted(p.name for p in nueva.iterdir())
        assert archivos == sorted(p.name for p in original.iterdir())
        for nombre in archivos:
            assert (nueva / nombre).read_bytes() == (original / nombre).read_bytes(), nombre


def test_n_invalido_falla(tmp_path):
    with pytest.raises(SystemExit):
        main(["--n", "0", "--out", str(tmp_path)])


# --- set forzado ---


def test_set_forzado_tiene_cada_caso_solo(salida):
    manifest = Manifest.model_validate_json((salida / "manifest.json").read_text())
    assert set(manifest.forzados) == set(CasoDificil)
    for caso, semillas in manifest.forzados.items():
        assert len(semillas) == POR_CASO
        for seed in semillas:
            # Después del rango sorteado: ningún contrato está en los dos sets.
            assert seed >= SEED + N
            carpeta = carpeta_semilla(carpeta_forzado(salida, caso), seed)
            indice = IndiceLegajo.model_validate_json((carpeta / "legajo.json").read_text())
            # Un solo caso por contrato: cada error se le atribuye a ese caso.
            assert indice.casos == [caso]
            for doc in indice.documentos:
                MODELOS[doc.modelo].model_validate_json((carpeta / doc.datos).read_text())


def test_semillas_forzadas_solo_donde_el_caso_aplica():
    for caso in (CasoDificil.CANON_ESCALONADO, CasoDificil.SEGURO_DE_CAUCION):
        semillas = semillas_forzadas(caso, 100, 5)
        assert len(semillas) == 5
        assert semillas == sorted(semillas)
        assert all(es_aplicable(caso, generate_contrato(s)) for s in semillas)


def test_por_caso_negativo_falla(tmp_path):
    with pytest.raises(SystemExit):
        main(["--n", "1", "--out", str(tmp_path), "--por-caso", "-1"])
