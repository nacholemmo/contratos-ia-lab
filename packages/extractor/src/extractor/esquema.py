"""Esquema de extracción: el modelo de core que ve el LLM, sin los campos internos.

Con salidas estructuradas, el JSON Schema decide qué puede devolver el modelo. Si incluye
`id: UUID`, el LLM está obligado a inventar un UUID. Por eso, de cada modelo de core se
deriva uno de extracción, con los mismos campos, descripciones, evidencias y restricciones
(`pattern`, `ge`), pero sin los campos marcados con `INTERNO`. La derivación es recursiva:
`Contrato.partes` es `list[Persona]` y cada `Persona` también tiene su `id`.

Lo extraído vuelve al modelo de core con `a_core`, que genera los ids y corre los
validadores de core (el dígito verificador del CUIT, por ejemplo). Si esa validación
falla, el error se le puede pasar al modelo para que reintente (paso 3).
"""

import operator
import types
from copy import copy
from functools import cache, reduce
from typing import Annotated, Any, Union, get_args, get_origin

from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo

from core.models import Interno


def es_interno(campo: FieldInfo) -> bool:
    """Un campo es interno si core lo marcó con `INTERNO`.

    Marca explícita y no una heurística por nombre (`id`, `*_id`) o por `default_factory`:
    un dato real puede llamarse `numero_id`, y un campo con valor por defecto (`clausulas`)
    puede ser justo lo que hay que extraer. La red de seguridad es un test que verifica que
    ningún UUID llegue a un esquema de extracción.
    """
    return any(isinstance(m, Interno) for m in campo.metadata)


def _sin_internos(anotacion: Any) -> Any:
    """La misma anotación con cada modelo reemplazado por su esquema de extracción."""
    if isinstance(anotacion, type) and issubclass(anotacion, BaseModel):
        return esquema_extraccion(anotacion)
    origen, args = get_origin(anotacion), get_args(anotacion)
    if origen is Annotated:  # Monto = Annotated[Decimal, Field(ge=0, ...)]
        return Annotated[_sin_internos(args[0]), *anotacion.__metadata__]
    if origen in (Union, types.UnionType):  # X | None
        return reduce(operator.or_, (_sin_internos(a) for a in args))
    if origen in (list, tuple, set, frozenset):
        return origen[tuple(_sin_internos(a) for a in args)]
    return anotacion


@cache
def esquema_extraccion(modelo: type[BaseModel]) -> type[BaseModel]:
    """El modelo que se le pide al LLM: el de core sin los campos internos, recursivo.

    Si no hay nada que sacar (DNI, recibo, título), devuelve el mismo modelo, con sus
    validadores. Si hay, uno nuevo con el mismo nombre y docstring: el nombre y la
    descripción también son parte del schema que lee el LLM.
    """
    campos: dict[str, Any] = {}
    cambio = False
    for nombre, campo in modelo.model_fields.items():
        if es_interno(campo):
            cambio = True
            continue
        anotacion = _sin_internos(campo.annotation)
        cambio |= anotacion != campo.annotation  # `is` no sirve: `X | None` se rearma
        nuevo = copy(campo)
        nuevo.annotation = anotacion
        campos[nombre] = (anotacion, nuevo)
    if not cambio:
        return modelo
    return create_model(modelo.__name__, __doc__=modelo.__doc__, **campos)


def a_core[M: BaseModel](modelo: type[M], extraido: BaseModel) -> M:
    """Lo extraído, validado como el modelo de core: genera los ids y corre sus validadores.

    Tira `pydantic.ValidationError` si no valida (ej. un CUIT con el dígito verificador mal).
    """
    return modelo.model_validate(extraido.model_dump())
