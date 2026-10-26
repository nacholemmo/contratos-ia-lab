"""Configuración del extractor: se lee del entorno o de `.env` (nunca del código)."""

import anthropic
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # `.env` relativo a la carpeta desde donde se corre: los comandos se corren desde la raíz.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SecretStr: si alguien loguea o imprime la configuración, sale `**********`.
    anthropic_api_key: SecretStr
    llm_model: str = "claude-haiku-5-5"
    llm_timeout_s: float = 30.0
    llm_max_retries: int = 2


def make_client(settings: Settings) -> anthropic.Anthropic:
    """Cliente con timeout explícito; el SDK ya reintenta 429, 5xx y errores de conexión."""
    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        timeout=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
    )
