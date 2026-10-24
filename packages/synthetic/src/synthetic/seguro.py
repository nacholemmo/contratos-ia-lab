"""Seguro contra incendio del inmueble alquilado, que contrata el inquilino.

Dos cruces con el contrato: la ubicación del riesgo es la dirección del inmueble alquilado
y la vigencia arranca con la locación (pólizas anuales, que se renuevan). Aseguradoras
inventadas, las mismas que las de caución.
"""

from datetime import timedelta
from decimal import Decimal

from core.models import Evidencia, Rol, SeguroInmueble
from synthetic import fichas
from synthetic.amounts import numero_ar
from synthetic.cases import ASEGURADORAS, CasoDificil
from synthetic.legajo import ContextoLegajo, contexto_legajo, sumar_meses
from synthetic.recibo import alquiler_en_pesos
from synthetic.source import Source
from synthetic.wording import frase_fecha

TITULO = "PÓLIZA DE SEGURO CONTRA INCENDIO"
VIGENCIA_MESES = 12

# Suma asegurada: entre 30 y 60 alquileres mensuales en pesos, redondeada a cien mil.
SUMA_EN_ALQUILERES = (30, 60)
REDONDEO_SUMA = Decimal(100_000)

ETIQUETAS = {
    "aseguradora": "Aseguradora",
    "numero_poliza": "Póliza N°",
    "asegurado": "Asegurado",
    "ubicacion_riesgo": "Ubicación del riesgo",
    "suma_asegurada": "Suma asegurada (incendio)",
    "vigencia_desde": "Vigencia desde",
    "vigencia_hasta": "Vigencia hasta",
}


def generate_seguro_data(contexto: ContextoLegajo, source: Source) -> SeguroInmueble:
    c = contexto.limpio
    alquileres = Decimal(source.rng.randint(*SUMA_EN_ALQUILERES))
    suma = (alquiler_en_pesos(c) * alquileres / REDONDEO_SUMA).quantize(Decimal(1)) * REDONDEO_SUMA
    return SeguroInmueble(
        aseguradora=source.rng.choice(ASEGURADORAS),
        numero_poliza=str(source.rng.randint(1_000_000, 9_999_999)),
        vigencia_desde=c.fecha_inicio,
        vigencia_hasta=sumar_meses(c.fecha_inicio, VIGENCIA_MESES) - timedelta(days=1),
        # La contrata el primer inquilino.
        asegurado=contexto.partes(Rol.INQUILINO)[0].nombre,
        ubicacion_riesgo=fichas.direccion(c.propiedad),
        suma_asegurada=suma,
    )


def _valores(seguro: SeguroInmueble, source: Source) -> dict[str, str]:
    return {
        "aseguradora": seguro.aseguradora,
        "numero_poliza": seguro.numero_poliza,
        "asegurado": seguro.asegurado,
        "ubicacion_riesgo": seguro.ubicacion_riesgo,
        "suma_asegurada": f"$ {numero_ar(seguro.suma_asegurada)}",
        "vigencia_desde": frase_fecha(source, seguro.vigencia_desde),
        "vigencia_hasta": frase_fecha(source, seguro.vigencia_hasta),
    }


def generate_seguro(
    seed: int, casos: list[CasoDificil] | None = None
) -> tuple[bytes, SeguroInmueble]:
    """PDF del seguro del inmueble del contrato de la semilla y su ground truth con evidencia."""
    contexto = contexto_legajo(seed, casos)
    source = Source(seed).derive("seguro")
    seguro = generate_seguro_data(contexto, source)
    valores = _valores(seguro, source)
    filas = [(ETIQUETAS[c], v) for c, v in valores.items()]
    pdf = fichas.render_ficha(TITULO, "Seguro contra incendio", filas)
    update = {f"{c}_evidencia": Evidencia(texto=v, pagina=1) for c, v in valores.items()}
    return pdf, seguro.model_copy(update=update)
