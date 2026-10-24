"""Generador determinístico de contratos y documentos sintéticos (Faker es_AR, sin LLM)."""

from synthetic.cases import CasoDificil, Muestra
from synthetic.contracts import generate_contrato
from synthetic.pdf import generate_contract, generate_sample
from synthetic.source import Source

__all__ = [
    "CasoDificil",
    "Muestra",
    "Source",
    "generate_contract",
    "generate_contrato",
    "generate_sample",
]
