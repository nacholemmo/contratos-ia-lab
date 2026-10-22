"""Fuente de aleatoriedad del generador: todo lo que varía sale de acá, a partir de una semilla."""

import hashlib
import random
from uuid import UUID

from faker import Faker


class Source:
    """Agrupa el `random.Random` y el `Faker` sembrados con la misma semilla.

    Regla: ninguna función del generador usa `random`, `uuid4()` ni `date.today()`
    directamente; todo pasa por una `Source`. Así, misma semilla → mismo contrato.
    """

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.fake = Faker("es_AR")
        self.fake.seed_instance(seed)

    def derive(self, label: str) -> "Source":
        """Sub-fuente independiente para otra etapa (ej. "redaccion"), estable para la semilla.

        Si la redacción usara `Source(seed)` de nuevo, repetiría la misma secuencia de
        números que los datos y quedaría correlacionada con ellos. Se usa sha256 y no
        `hash()`, porque `hash()` de un str cambia entre ejecuciones de Python.
        """
        digest = hashlib.sha256(f"{self.seed}:{label}".encode()).digest()
        return Source(int.from_bytes(digest[:8], "big"))

    def uuid(self) -> UUID:
        """UUID v4 reproducible (reemplaza al `uuid4()` por defecto de los modelos de core)."""
        return UUID(int=self.rng.getrandbits(128), version=4)
