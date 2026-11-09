"""Separación entrenamiento/prueba por legajo.

Vive aparte de `vectors.py` (que necesita scikit-learn) porque la usan también las comparaciones,
que no dependen del extra `ml`.
"""

import random

from extractor.experiment import Sample

# Parte del set que se reserva para evaluar (el resto entrena).
TEST_FRACTION = 0.3
SPLIT_SEED = 42


def legajo_key(sample: Sample) -> str:
    """El legajo de un documento: el nombre de su carpeta, que es la semilla.

    No la ruta completa: en el set forzado la misma semilla aparece en varios casos
    (`forzados/clausula_larga/0092` y `forzados/escaneo_torcido/0092` son el mismo contrato
    base, con las mismas personas).
    """
    return sample.pdf.parent.name


def split_by_legajo(
    samples: list[Sample], test_fraction: float = TEST_FRACTION, seed: int = SPLIT_SEED
) -> tuple[list[Sample], list[Sample]]:
    """(entrenamiento, prueba): todos los documentos de un legajo quedan del mismo lado.

    Determinística: con la misma lista y la misma semilla, la misma separación.
    """

    keys = sorted({legajo_key(s) for s in samples})
    rng = random.Random(seed)
    rng.shuffle(keys)
    n_test = round(len(keys) * test_fraction)
    test_keys = set(keys[:n_test])
    train = [s for s in samples if legajo_key(s) not in test_keys]
    test = [s for s in samples if legajo_key(s) in test_keys]
    return train, test
