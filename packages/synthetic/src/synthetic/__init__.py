"""Generador determinístico de contratos y documentos sintéticos (Faker es_AR, sin LLM)."""

from synthetic.contracts import generate_contrato
from synthetic.source import Source

__all__ = ["Source", "generate_contrato"]
