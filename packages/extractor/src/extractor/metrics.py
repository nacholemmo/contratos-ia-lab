"""Métricas de clasificación sobre pares (real, predicho), sin dependencias.

Accuracy sola esconde a las clases chicas: con 186 DNI y 4 cauciones, errar todas las cauciones
casi no la mueve. Por eso, por clase:

- precisión: de lo que el modelo llamó X, ¿cuánto era X? (baja = falsas alarmas)
- recall: de lo que era X, ¿cuánto encontró? (bajo = se le escapan)
- F1: la media armónica de las dos; cae si cualquiera de las dos es baja.

`predicho` puede ser `None` (el LLM respondió algo que no es una etiqueta): nunca coincide con
una clase, así que cuenta como error de la clase real.
"""

from collections import Counter
from dataclasses import dataclass

from core.models import TipoDocumento

Pair = tuple[TipoDocumento, TipoDocumento | None]


@dataclass(frozen=True)
class ClassMetrics:
    precision: float
    recall: float
    f1: float
    support: int  # documentos que de verdad son de la clase


def confusion_matrix(pairs: list[Pair]) -> Counter[Pair]:
    """Cuántas veces cada (real, predicho). La diagonal (real == predicho) son los aciertos."""
    return Counter(pairs)


def accuracy(pairs: list[Pair]) -> float:
    return sum(real == predicted for real, predicted in pairs) / len(pairs)


def class_metrics(pairs: list[Pair], tipo: TipoDocumento) -> ClassMetrics:
    """Precisión, recall y F1 de una clase.

    Convención para las divisiones por cero (la misma que scikit-learn con `zero_division=0`):
    si el modelo nunca predijo la clase, la precisión es 0; si la clase no tiene documentos, el
    recall es 0; si precisión y recall son 0, F1 es 0.
    """
    tp = sum(1 for real, pred in pairs if real == tipo and pred == tipo)
    fp = sum(1 for real, pred in pairs if real != tipo and pred == tipo)
    fn = sum(1 for real, pred in pairs if real == tipo and pred != tipo)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return ClassMetrics(precision=precision, recall=recall, f1=f1, support=tp + fn)


def macro_f1(pairs: list[Pair]) -> float:
    """Promedio de F1 entre las clases que tienen documentos, sin ponderar por tamaño: una clase
    chica pesa lo mismo que una grande. (`otro` no tiene documentos en el set: no entra.)"""
    present = sorted({real for real, _ in pairs}, key=lambda t: t.value)
    return sum(class_metrics(pairs, tipo).f1 for tipo in present) / len(present)
