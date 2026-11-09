"""Clasificación few-shot: el prompt zero-shot más documentos resueltos como ejemplos.

Los ejemplos salen del mismo set sintético, así que se sacan de la evaluación (si no, el modelo
"acierta" documentos que ya vio resueltos en el prompt: fuga de datos). Van solo como texto
recortado: un ejemplo en imagen costaría ~2.250 tokens por llamada.
"""

from collections import defaultdict

from core.models import TipoDocumento
from extractor.classify import SYSTEM_ZERO_SHOT
from extractor.experiment import Sample
from extractor.inputs import page_texts

# Caracteres por ejemplo: alcanza para el encabezado de cualquier documento (donde está lo que
# lo identifica) y corta el contrato, que es el único largo (~1.700 caracteres en la página 1).
MAX_EXAMPLE_CHARS = 600


def select_examples(samples: list[Sample]) -> list[Sample]:
    by_tipo: dict[TipoDocumento, list[Sample]] = defaultdict(list)
    for sample in samples:
        if not sample.scanned:
            by_tipo[sample.tipo].append(sample)

    examples: list[Sample] = []
    for tipo, members in by_tipo.items():
        if tipo == TipoDocumento.GARANTIA:
            # Las dos formas de la clase: un título y una caución (si hay).
            for prefix in ("titulo", "caucion"):
                match = next((s for s in members if s.pdf.name.startswith(prefix)), None)
                if match is not None:
                    examples.append(match)
        else:
            examples.append(members[0])
    return examples


def example_text(sample: Sample, max_chars: int = MAX_EXAMPLE_CHARS) -> str:
    """El texto de la primera página del ejemplo, recortado a `max_chars`."""
    text = "\n".join(page_texts(sample.pdf.read_bytes())).strip()
    return text[:max_chars]


def build_system_few_shot(examples: list[Sample]) -> str:
    """El system del zero-shot más un bloque <ejemplos>, cada uno con su documento y etiqueta.

    Los ejemplos van en el system (y no como turnos previos de la conversación) para que el
    prefijo sea idéntico en todas las llamadas: así se podría cachear si alguna vez conviene.
    """
    blocks = [
        f"<ejemplo>\n<documento>\n{example_text(s)}\n</documento>\n"
        f"<etiqueta>{s.tipo.value}</etiqueta>\n</ejemplo>"
        for s in examples
    ]
    return (
        f"{SYSTEM_ZERO_SHOT}\n"
        "Estos son ejemplos de documentos ya clasificados (recortados). Respondé solo con la "
        "etiqueta, sin las marcas <etiqueta>.\n\n"
        f"<ejemplos>\n{chr(10).join(blocks)}\n</ejemplos>\n"
    )


def without_examples(samples: list[Sample], examples: list[Sample]) -> list[Sample]:
    """El set de evaluación: todo menos los ejemplos."""
    used = {s.pdf for s in examples}
    return [s for s in samples if s.pdf not in used]
