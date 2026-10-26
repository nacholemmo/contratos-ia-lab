"""CLI mínima del extractor: una llamada de prueba al LLM para ver tokens, costo y latencia.

Uso (desde la raíz): uv run --package extractor llm-ping
"""

import argparse
import logging

from extractor.llm import call_llm
from extractor.settings import Settings, make_client


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="llm-ping", description="Llamada mínima al LLM (cuesta menos de USD 0,001)."
    )
    parser.add_argument("--model", help="modelo (default: el de la configuración)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    response = call_llm(
        make_client(settings),
        system="Respondé solo con la palabra OK.",
        content="ping",
        model=args.model or settings.llm_model,
    )
    print(f"respuesta: {response.text!r}")
    print(response.usage.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
