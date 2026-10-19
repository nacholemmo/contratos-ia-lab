"""Fuente de aleatoriedad del generador: todo lo que varía sale de acá, a partir de una semilla."""

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

    def uuid(self) -> UUID:
        """UUID v4 reproducible (reemplaza al `uuid4()` por defecto de los modelos de core)."""
        return UUID(int=self.rng.getrandbits(128), version=4)
