"""Única puerta de salida al LLM: llama, mide (tokens, costo, latencia) y loguea sin contenido.

El resto del extractor no importa `anthropic`: si mañana cambia el proveedor, cambia este archivo.
"""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

import anthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)

Effort = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class Price:
    """Precio de un modelo en USD por millón de tokens.

    Algunos modelos cobran más cuando el prompt es largo: por encima de `long_threshold`
    tokens de entrada, toda la llamada se cobra con la tarifa larga.
    """

    input: Decimal
    output: Decimal
    long_threshold: int | None = None
    long_input: Decimal | None = None
    long_output: Decimal | None = None


# Fuente: página de precios de Anthropic (octubre de 2026). Verificar antes de confiar en un total.
PRICES: dict[str, Price] = {
    "claude-haiku-5-5": Price(
        input=Decimal("0.10"),
        output=Decimal("0.50"),
        long_threshold=100_000,
        long_input=Decimal("0.50"),
        long_output=Decimal("2.50"),
    ),
}


def cost_usd(price: Price, input_tokens: int, output_tokens: int) -> Decimal:
    """Costo exacto de una llamada en USD, sin redondear."""
    in_rate, out_rate = price.input, price.output
    if price.long_threshold is not None and input_tokens > price.long_threshold:
        in_rate = price.long_input
        out_rate = price.long_output
    return (Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate) / 1_000_000


class LlmUsage(BaseModel):
    """Lo único que se registra de una llamada: metadatos, nunca el texto."""

    model: str
    input_tokens: int
    output_tokens: int  # incluye los tokens de pensamiento
    cost_usd: Decimal
    latency_s: float
    stop_reason: str | None
    request_id: str | None


class LlmResponse(BaseModel):
    text: str
    usage: LlmUsage


class LlmError(Exception):
    """Falló la llamada al LLM (red, límite de uso, error de la API). Sin contenido."""


class LlmRefusal(LlmError):
    """El modelo se negó a responder (stop_reason == "refusal")."""


def call_llm(
    client: anthropic.Anthropic,
    *,
    system: str,
    content: str | list[dict[str, Any]],
    model: str,
    max_tokens: int = 1024,
    effort: Effort = "low",
) -> LlmResponse:
    """Una llamada al modelo. `content` es texto o bloques (por ejemplo, un PDF en base64)."""
    # Sin precio no se puede medir el costo: se corta antes de gastar.
    if model not in PRICES:
        raise ValueError(f"modelo sin precio en PRICES: {model}")

    start = time.perf_counter()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort},
        )
    except anthropic.APIError as e:
        latency = time.perf_counter() - start
        # Solo el tipo de error: el mensaje de la API podría citar parte del documento.
        logger.error("llm error model=%s error=%s latency=%.2fs", model, type(e).__name__, latency)
        raise LlmError(type(e).__name__) from e
    latency = time.perf_counter() - start

    usage = LlmUsage(
        model=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cost_usd=cost_usd(PRICES[model], response.usage.input_tokens, response.usage.output_tokens),
        latency_s=latency,
        stop_reason=response.stop_reason,
        request_id=getattr(response, "_request_id", None),
    )
    logger.info(
        "llm call model=%s in=%d out=%d cost_usd=%s latency=%.2fs stop=%s request_id=%s",
        usage.model,
        usage.input_tokens,
        usage.output_tokens,
        usage.cost_usd,
        usage.latency_s,
        usage.stop_reason,
        usage.request_id,
    )

    if response.stop_reason == "refusal":
        raise LlmRefusal(f"refusal request_id={usage.request_id}")
    if response.stop_reason == "max_tokens":
        logger.warning("llm respuesta cortada por max_tokens request_id=%s", usage.request_id)

    text = "".join(block.text for block in response.content if block.type == "text")
    return LlmResponse(text=text, usage=usage)
