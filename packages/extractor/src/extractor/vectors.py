"""Cuarto enfoque del paso 3: texto → vector → regresión logística.

Dos formas de armar el vector con el mismo clasificador, para medir si "entender" el texto
(embeddings) agrega algo sobre contar palabras (TF-IDF):

- `tfidf`: una dimensión por palabra (y par de palabras) del vocabulario de entrenamiento.
- `embeddings`: `multilingual-e5-small` de Hugging Face, local (los documentos no salen de la
  máquina). 384 dimensiones que representan el significado.

A diferencia del LLM, estos enfoques se entrenan: la evaluación es sobre documentos que el
clasificador no vio. Solo leen texto: un documento sin capa de texto no se entrena y se predice
`OTRO` (no se puede leer), como en las reglas.

Requiere el extra `ml`: `uv sync --extra ml`.
"""

import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from core.models import TipoDocumento
from extractor.experiment import Sample
from extractor.inputs import has_usable_text, page_texts

Vectorizer = Literal["tfidf", "embeddings"]

EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
# Parte del set que se reserva para evaluar (el resto entrena).
TEST_FRACTION = 0.3
SPLIT_SEED = 42


class VectorResult(BaseModel):
    pdf: str
    tipo: TipoDocumento
    scanned: bool
    predicted: TipoDocumento
    confidence: float  # probabilidad de la clase predicha (0 si no había texto)


class VectorOutcome(BaseModel):
    vectorizer: Vectorizer
    n_train: int
    train_legajos: list[str]
    results: list[VectorResult]
    fit_s: float  # vectorizar el entrenamiento y entrenar
    predict_s: float  # vectorizar la prueba y predecir


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


# Un vectorizador se arma con los textos de entrenamiento y devuelve la función que transforma
# cualquier lista de textos en una matriz (una fila por texto).
Transform = Callable[[list[str]], Any]


def tfidf_vectorizer(train: list[str]) -> Transform:
    """TF-IDF ajustado solo con el entrenamiento: el vocabulario y la rareza de cada palabra
    (IDF) no pueden salir de la prueba, o el clasificador "ve" la prueba de antemano."""
    vectorizer = TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 2), min_df=2)
    vectorizer.fit(train)
    return vectorizer.transform


def embedding_vectorizer(train: list[str], model_name: str = EMBEDDING_MODEL) -> Transform:
    """Embeddings locales. El modelo ya viene entrenado: no aprende nada de `train`.

    e5 espera un prefijo ("query: " para clasificar) y corta a 512 tokens: alcanza, porque lo
    que identifica a un documento está en su encabezado.
    """
    # Import adentro: cargar sentence-transformers (y torch) tarda segundos, y TF-IDF no lo usa.
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, device="cpu")

    def transform(texts: list[str]) -> np.ndarray:
        return model.encode([f"query: {t}" for t in texts], normalize_embeddings=True)

    return transform


VECTORIZERS: dict[Vectorizer, Callable[[list[str]], Transform]] = {
    "tfidf": tfidf_vectorizer,
    "embeddings": embedding_vectorizer,
}


def run_vectors(samples: list[Sample], vectorizer: Vectorizer, root: Path) -> VectorOutcome:
    """Separa por legajo, entrena con los documentos con texto y evalúa la prueba más todos los
    que no tienen texto (que no pueden ir al entrenamiento)."""
    texts = {s.pdf: "\n".join(page_texts(s.pdf.read_bytes())) for s in samples}
    readable = [s for s in samples if has_usable_text([texts[s.pdf]])]
    unreadable = [s for s in samples if not has_usable_text([texts[s.pdf]])]
    train, test = split_by_legajo(readable)

    train_texts = [texts[s.pdf] for s in train]
    start = time.perf_counter()
    transform = VECTORIZERS[vectorizer](train_texts)
    classifier = LogisticRegression(max_iter=1000)
    classifier.fit(transform(train_texts), [s.tipo.value for s in train])
    fit_s = time.perf_counter() - start

    # Vectorizar y predecir la prueba es lo que costaría cada documento en producción.
    start = time.perf_counter()
    probabilities = classifier.predict_proba(transform([texts[s.pdf] for s in test]))
    predict_s = time.perf_counter() - start

    results = [
        VectorResult(
            pdf=str(sample.pdf.relative_to(root)),
            tipo=sample.tipo,
            scanned=sample.scanned,
            predicted=TipoDocumento(classifier.classes_[row.argmax()]),
            confidence=float(row.max()),
        )
        for sample, row in zip(test, probabilities, strict=True)
    ]
    results += [
        VectorResult(
            pdf=str(s.pdf.relative_to(root)),
            tipo=s.tipo,
            scanned=s.scanned,
            predicted=TipoDocumento.OTRO,
            confidence=0.0,
        )
        for s in unreadable
    ]
    return VectorOutcome(
        vectorizer=vectorizer,
        n_train=len(train),
        train_legajos=sorted({legajo_key(s) for s in train}),
        results=results,
        fit_s=fit_s,
        predict_s=predict_s,
    )
