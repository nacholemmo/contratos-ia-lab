"""Desorden del legajo fotografiado: lo que pasa cuando una persona real manda las fotos.

Sobre un `LegajoGenerado` prolijo (fotos en el orden de los documentos):

1. **Duplicadas:** la misma foto mandada dos veces (mismos bytes).
2. **Re-sacadas:** el mismo documento fotografiado de nuevo (otras fotos de las mismas
   páginas). Cada foto nueva es duplicado de la página que le corresponde.
3. **Ilegibles:** una página sacada movida, además de la buena.
4. **Intrusas:** fotos que no son ningún documento (factura, chat, foto sin documento).
5. **Mezcla:** orden sorteado.
6. **Renombre:** nombres consecutivos nuevos en el orden final. Si se conservaran los
   nombres del legajo prolijo, la numeración delataría la agrupación.

Todo lo agregado queda en el ground truth como foto descartada, con su motivo. Se conserva
la foto original y se descarta la copia; las evals tienen que aceptar cualquiera de las dos
como la conservada (son la misma página).
"""

from dataclasses import dataclass, replace

from core.legajo import FotoEsperada, LegajoEsperado, MotivoDescarte
from synthetic.foto import NIVELES, Nivel, fotografiar, fotografiar_pdf, guardar_jpg, nombres_fotos
from synthetic.fotografiado import LegajoGenerado
from synthetic.intrusas import Intrusa, generate_intrusa
from synthetic.scan import rasterizar
from synthetic.source import Source

Rango = tuple[int, int]  # mínimo y máximo, inclusive


@dataclass(frozen=True)
class Desorden:
    """Cuánto de cada cosa se agrega. Cada cantidad se sortea dentro de su rango."""

    duplicadas: Rango = (0, 2)
    resacados: Rango = (0, 1)
    ilegibles: Rango = (0, 1)
    intrusas: Rango = (0, 2)


# El desorden de siempre. Es inmutable (frozen), así que compartirlo como default es seguro.
DESORDEN_HABITUAL = Desorden()
SIN_DESORDEN = Desorden((0, 0), (0, 0), (0, 0), (0, 0))


def renombrar(esperado: LegajoEsperado, nuevos: dict[str, str]) -> LegajoEsperado:
    """El mismo ground truth con cada archivo renombrado según `nuevos` (viejo → nuevo).

    El orden de `esperado.fotos` no cambia. Hay que renombrar todo lugar donde aparece un
    archivo: la foto misma, las fotos de cada documento y `duplicada_de`.
    """
    fotos = [
        f.model_copy(
            update={
                "archivo": nuevos[f.archivo],
                "duplicada_de": nuevos[f.duplicada_de] if f.duplicada_de else None,
            }
        )
        for f in esperado.fotos
    ]
    documentos = [
        d.model_copy(update={"fotos": [nuevos[a] for a in d.fotos]}) for d in esperado.documentos
    ]
    return esperado.model_copy(update={"fotos": fotos, "documentos": documentos})


def desordenar(
    legajo: LegajoGenerado, desorden: Desorden = DESORDEN_HABITUAL, nivel: Nivel = Nivel.LEVE
) -> LegajoGenerado:
    """El legajo con duplicadas, re-sacadas, ilegibles e intrusas, mezclado y renombrado.

    Determinístico: el azar sale de la semilla del legajo. Cada foto agregada usa su propia
    sub-fuente, así que cambiar una cantidad no cambia las otras fotos.
    """
    e = legajo.esperado
    source = Source(e.seed).derive("desorden")
    rng = source.rng
    fotos = dict(legajo.fotos)
    entradas = list(e.fotos)
    en_documentos = [a for d in e.documentos for a in d.fotos]
    n = 0

    def agregar(jpg: bytes, foto: FotoEsperada) -> None:
        fotos[foto.archivo] = jpg
        entradas.append(foto)

    def provisorio() -> str:
        nonlocal n
        n += 1
        return f"nuevo_{n}.jpg"

    def cantidad(rango: Rango) -> int:
        return rng.randint(*rango)

    # 1. La misma foto mandada dos veces.
    k = min(cantidad(desorden.duplicadas), len(en_documentos))
    for original in rng.sample(en_documentos, k):
        dup = FotoEsperada(
            archivo=provisorio(), descarte=MotivoDescarte.DUPLICADA, duplicada_de=original
        )
        agregar(legajo.fotos[original], dup)

    # 2. El mismo documento sacado de nuevo.
    for doc in rng.sample(e.documentos, min(cantidad(desorden.resacados), len(e.documentos))):
        sub = source.derive(f"resacado:{doc.id}")
        nuevas = fotografiar_pdf(legajo.pdfs[doc.id], sub, nivel)
        for original, jpg in zip(doc.fotos, nuevas, strict=True):
            dup = FotoEsperada(
                archivo=provisorio(), descarte=MotivoDescarte.DUPLICADA, duplicada_de=original
            )
            agregar(jpg, dup)

    # 3. Una página que salió movida (además de la buena).
    for i in range(cantidad(desorden.ilegibles)):
        doc = rng.choice(e.documentos)
        pagina = rng.randrange(len(doc.fotos))
        sub = source.derive(f"ilegible:{i}")
        foto = fotografiar(rasterizar(legajo.pdfs[doc.id])[pagina], sub, Nivel.ILEGIBLE)
        jpg = guardar_jpg(foto, 1, NIVELES[Nivel.ILEGIBLE].calidad_jpg)
        agregar(jpg, FotoEsperada(archivo=provisorio(), descarte=MotivoDescarte.ILEGIBLE))

    # 4. Lo que se cuela.
    for i in range(cantidad(desorden.intrusas)):
        tipo = rng.choice(list(Intrusa))
        jpg = generate_intrusa(tipo, source.derive(f"intrusa:{i}"), nivel)
        agregar(jpg, FotoEsperada(archivo=provisorio(), descarte=MotivoDescarte.INTRUSA))

    # 5. Mezcla y 6. renombre en el orden final.
    rng.shuffle(entradas)
    nombres = nombres_fotos(source.derive("nombres"), len(entradas))
    nuevos = {f.archivo: nombre for f, nombre in zip(entradas, nombres, strict=True)}
    esperado = renombrar(e.model_copy(update={"fotos": entradas}), nuevos)
    return replace(
        legajo,
        esperado=LegajoEsperado.model_validate(esperado.model_dump()),
        fotos={nuevos[f.archivo]: fotos[f.archivo] for f in entradas},
    )
