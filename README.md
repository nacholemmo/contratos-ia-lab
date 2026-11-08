# contratos-ia-lab

Servicio de IA **sin estado** que **arma legajos de alquiler a partir de fotos**, construido
como laboratorio de **aprendizaje de AI Engineering** en Python. Es el servicio de IA del
módulo Alquileres de [Avisa](https://avisa.com.ar).

La inmobiliaria o el inquilino suben fotos desordenadas (frente y dorso del DNI, recibos,
garantías, el contrato, alguna borrosa o de otra cosa) y el servicio devuelve un **legajo
sugerido**:

- documentos agrupados y asignados a cada persona y rol (inquilino, garante);
- datos extraídos, cada uno con su evidencia;
- fotos descartadas (duplicadas, ilegibles o de otra cosa);
- faltantes según los requisitos de la inmobiliaria;
- alertas de cruces entre documentos y la relación alquiler/ingresos.

Funciona en dos etapas con el mismo motor: **evaluación** (antes de firmar: DNI, recibos y
garantías) y **cierre** (se suman el contrato y el seguro). Una persona confirma el legajo
en Avisa, y lo confirmado se exporta en un formato versionado
([`schemas/`](schemas/)) que puede importar cualquier sistema.

Para medir todo eso, un **generador sintético** determinístico arma legajos fotografiados
con su ground truth: agrupación, asignación, faltantes y alertas esperadas.

La interfaz es un servidor **MCP** propio, que usan el backend de Avisa y Claude. Para
aprender, el repo suma un agente con LangGraph para los casos ambiguos.

## Principios

- **Sin estado:** no guarda documentos ni su contenido, tampoco en logs.
- **La IA sugiere, una persona confirma.** Los cruces y los cálculos de dinero y fechas los
  hace código determinístico, nunca un LLM.
- **Los documentos son texto no confiable** (prompt injection).
- **Solo datos sintéticos** en el repo (Ley 25.326).

## Estado

Ver la hoja de ruta en [docs/roadmap.md](docs/roadmap.md), el registro de cada paso en
[docs/progreso.md](docs/progreso.md) y las decisiones en [docs/adr/](docs/adr/).

## Stack

Python 3.12 · workspace de [uv](https://docs.astral.sh/uv/) · pydantic · pytest · ruff.

```bash
uv sync
uv run pytest
```

## Licencia

[MIT](LICENSE)
