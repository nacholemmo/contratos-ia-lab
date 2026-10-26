"""Tests del envoltorio del LLM: costo, registro de uso y logs sin contenido.

Sin red: un cliente falso devuelve respuestas armadas a mano. El único test que llama a la API
real está marcado `network` y `slow` (no corre por defecto).
"""

import logging
from decimal import Decimal
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from extractor.llm import PRICES, LlmError, LlmRefusal, Price, call_llm, cost_usd

HAIKU = "claude-haiku-5-5"
# Texto que no debe aparecer nunca en un log.
SECRETO = "DNI 30.123.456 de Juana Pérez"


class FakeMessages:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def fake_client(response=None, error: Exception | None = None) -> SimpleNamespace:
    return SimpleNamespace(messages=FakeMessages(response, error))


def fake_response(
    text: str = "contrato",
    input_tokens: int = 1_000,
    output_tokens: int = 200,
    stop_reason: str = "end_turn",
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason=stop_reason,
        _request_id="req_test",
    )


# --- cost_usd ---------------------------------------------------------------------------


def test_costo_tarifa_normal():
    # 1.000 de entrada a USD 0,10/M + 200 de salida a USD 0,50/M = 0,0001 + 0,0001
    assert cost_usd(PRICES[HAIKU], 1_000, 200) == Decimal("0.0002")


def test_costo_es_decimal_exacto_sin_redondear():
    # Una llamada de clasificación cuesta fracciones de centavo: redondear a centavos daría 0.
    costo = cost_usd(PRICES[HAIKU], 1, 1)
    assert isinstance(costo, Decimal)
    assert costo == Decimal("0.0000006")


def test_costo_cero_tokens():
    assert cost_usd(PRICES[HAIKU], 0, 0) == Decimal(0)


def test_costo_justo_en_el_umbral_usa_tarifa_normal():
    # "100K tokens o menos" es tarifa normal: el umbral es inclusivo.
    assert cost_usd(PRICES[HAIKU], 100_000, 0) == Decimal("0.01")


def test_costo_arriba_del_umbral_usa_tarifa_larga_en_entrada_y_salida():
    # 100.001 × 0,50/M + 1.000 × 2,50/M
    assert cost_usd(PRICES[HAIKU], 100_001, 1_000) == Decimal("0.0500005") + Decimal("0.0025")


def test_costo_modelo_sin_tarifa_larga():
    precio = Price(input=Decimal("4"), output=Decimal("20"))
    assert cost_usd(precio, 1_000_000, 1_000_000) == Decimal("24")


# --- call_llm -----------------------------------------------------------------------------


def test_devuelve_texto_y_uso():
    client = fake_client(fake_response(text="dni", input_tokens=1_000, output_tokens=200))
    response = call_llm(client, system="clasificá", content=SECRETO, model=HAIKU)

    assert response.text == "dni"
    assert response.usage.model == HAIKU
    assert response.usage.input_tokens == 1_000
    assert response.usage.output_tokens == 200
    assert response.usage.cost_usd == Decimal("0.0002")
    assert response.usage.latency_s >= 0
    assert response.usage.request_id == "req_test"


def test_manda_effort_y_modelo():
    client = fake_client(fake_response())
    call_llm(client, system="clasificá", content="x", model=HAIKU, effort="low")

    kwargs = client.messages.calls[0]
    assert kwargs["model"] == HAIKU
    assert kwargs["output_config"] == {"effort": "low"}
    assert kwargs["messages"] == [{"role": "user", "content": "x"}]


def test_log_sin_contenido(caplog):
    client = fake_client(fake_response(text=SECRETO))
    with caplog.at_level(logging.DEBUG):
        call_llm(client, system=SECRETO, content=SECRETO, model=HAIKU)

    assert "llm call" in caplog.text
    assert "in=1000" in caplog.text
    assert SECRETO not in caplog.text


def test_modelo_sin_precio_no_llama():
    client = fake_client(fake_response())
    with pytest.raises(ValueError, match="sin precio"):
        call_llm(client, system="s", content="c", model="modelo-inventado")
    assert client.messages.calls == []


def test_refusal_levanta_error():
    client = fake_client(fake_response(stop_reason="refusal"))
    with pytest.raises(LlmRefusal):
        call_llm(client, system="s", content="c", model=HAIKU)


def test_max_tokens_avisa_y_devuelve(caplog):
    client = fake_client(fake_response(text="contr", stop_reason="max_tokens"))
    with caplog.at_level(logging.WARNING):
        response = call_llm(client, system="s", content="c", model=HAIKU)
    assert response.text == "contr"
    assert "max_tokens" in caplog.text


def test_error_de_api_se_traduce_y_se_loguea_sin_contenido(caplog):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.APIConnectionError(message=SECRETO, request=request)
    client = fake_client(error=error)

    with caplog.at_level(logging.DEBUG), pytest.raises(LlmError) as excinfo:
        call_llm(client, system="s", content=SECRETO, model=HAIKU)

    assert "APIConnectionError" in caplog.text
    assert SECRETO not in caplog.text
    assert SECRETO not in str(excinfo.value)


# --- llamada real -------------------------------------------------------------------------


@pytest.mark.network
@pytest.mark.slow
def test_llamada_real_a_haiku():
    from extractor.settings import Settings, make_client

    settings = Settings()
    response = call_llm(
        make_client(settings),
        system="Respondé solo con la palabra OK.",
        content="ping",
        model=HAIKU,
    )
    assert response.text.strip()
    assert response.usage.input_tokens > 0
    assert Decimal(0) < response.usage.cost_usd < Decimal("0.001")
