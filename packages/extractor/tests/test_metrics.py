"""Tests de las métricas, con un caso chico calculado a mano."""

import pytest

from core.models import TipoDocumento
from extractor.metrics import accuracy, class_metrics, confusion_matrix, macro_f1

G, S, D, C, OTRO = (
    TipoDocumento.GARANTIA,
    TipoDocumento.SEGURO,
    TipoDocumento.DNI,
    TipoDocumento.CONTRATO,
    TipoDocumento.OTRO,
)

# 3 garantías (una sale seguro), 2 seguros, 2 DNI (uno sin etiqueta válida).
PAIRS = [(G, G), (G, G), (G, S), (S, S), (S, S), (D, D), (D, None)]


def test_confusion_matrix_cuenta_pares():
    matrix = confusion_matrix(PAIRS)
    assert matrix[(G, G)] == 2
    assert matrix[(G, S)] == 1
    assert matrix[(D, None)] == 1
    assert matrix[(S, G)] == 0


def test_accuracy():
    assert accuracy(PAIRS) == pytest.approx(5 / 7)


def test_garantia_con_un_falso_negativo():
    """2 aciertos, 0 falsas alarmas, 1 que se escapó (salió seguro)."""
    m = class_metrics(PAIRS, G)
    assert m.precision == pytest.approx(1.0)
    assert m.recall == pytest.approx(2 / 3)
    assert m.f1 == pytest.approx(0.8)
    assert m.support == 3


def test_seguro_con_una_falsa_alarma():
    """2 aciertos y una garantía que el modelo llamó seguro: la precisión baja, el recall no."""
    m = class_metrics(PAIRS, S)
    assert m.precision == pytest.approx(2 / 3)
    assert m.recall == pytest.approx(1.0)
    assert m.f1 == pytest.approx(0.8)
    assert m.support == 2


def test_una_respuesta_invalida_baja_el_recall():
    m = class_metrics(PAIRS, D)
    assert m.precision == pytest.approx(1.0)
    assert m.recall == pytest.approx(0.5)
    assert m.f1 == pytest.approx(2 / 3)


def test_clase_ausente_y_nunca_predicha_da_cero():
    m = class_metrics(PAIRS, OTRO)
    assert (m.precision, m.recall, m.f1, m.support) == (0.0, 0.0, 0.0, 0)


def test_clase_predicha_sin_documentos_reales():
    """Un escaneo que sale `otro`: `otro` tiene una falsa alarma y ningún documento real."""
    m = class_metrics([(C, OTRO), (C, C)], OTRO)
    assert (m.precision, m.recall, m.f1, m.support) == (0.0, 0.0, 0.0, 0)


def test_todo_perfecto():
    m = class_metrics([(G, G), (S, S)], G)
    assert (m.precision, m.recall, m.f1) == (1.0, 1.0, 1.0)


def test_macro_f1_promedia_solo_las_clases_presentes():
    """garantía 0,8, seguro 0,8 y DNI 2/3. `otro` y `contrato` no tienen documentos: no entran."""
    assert macro_f1(PAIRS) == pytest.approx((0.8 + 0.8 + 2 / 3) / 3)


def test_macro_f1_castiga_la_clase_chica():
    """Con 98 DNI bien y 2 garantías mal, la accuracy es 98 % y el F1 macro baja a la mitad
    (DNI 1,0 y garantía 0,0)."""
    pairs = [(D, D)] * 98 + [(G, S)] * 2
    assert accuracy(pairs) == pytest.approx(0.98)
    assert macro_f1(pairs) == pytest.approx(0.5)
