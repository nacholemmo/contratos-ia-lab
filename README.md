# contratos-ia-lab

Servicio de IA **sin estado** para contratos de alquiler en Argentina, construido como
laboratorio de **aprendizaje de AI Engineering** en Python. Es el servicio de IA del módulo
Alquileres de [Avisa](https://avisa.com.ar).

Hace dos cosas:

1. **Genera contratos sintéticos**: determinísticos (misma semilla, mismo contrato), con
   personas, DNI y CUIT válidos, redacción variada y casos difíciles. Son el ground truth
   para medir la extracción.
2. **Extrae datos de documentos** (contrato, DNI, recibo de sueldo, garantía, seguro): cada
   dato sale con su evidencia (fragmento y página) y como *sugerencia*; la confirma una persona.

La interfaz es un servidor **MCP** propio, que usan el backend de Avisa y Claude. Para
aprender, el repo suma un RAG sobre la normativa de alquileres y un agente con LangGraph.

## Principios

- **Sin estado:** no guarda documentos ni su contenido, tampoco en logs.
- **La IA sugiere, una persona confirma.** Los cálculos de dinero y fechas los hace código
  determinístico, nunca un LLM.
- **Los documentos son texto no confiable** (prompt injection).
- **Solo datos sintéticos** en el repo (Ley 25.326).

## Estado

Ver la hoja de ruta en [docs/roadmap.md](docs/roadmap.md) y el registro de cada paso en
[docs/progreso.md](docs/progreso.md).

## Stack

Python 3.12 · workspace de [uv](https://docs.astral.sh/uv/) · pydantic · pytest · ruff.

```bash
uv sync
uv run pytest
```

## Licencia

[MIT](LICENSE)
