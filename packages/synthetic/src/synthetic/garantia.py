"""Garantía del contrato en el legajo: el título de propiedad de cada garante o la póliza
de caución.

Con el caso SEGURO_DE_CAUCION el contrato no tiene garantes y la garantía es una póliza,
con la misma aseguradora y el mismo número que dice la cláusula (`datos_caucion`): ese es
el cruce que se evalúa. Sin el caso, cada garante presenta el título de un inmueble propio,
distinto del alquilado. Presentación propia y aseguradoras inventadas: nada imita a un
registro de la propiedad ni a una empresa real.
"""

from datetime import timedelta
from uuid import UUID

from core.models import Evidencia, PolizaCaucion, Rol, TituloPropiedad
from synthetic import fichas
from synthetic.amounts import EstiloMonto, format_monto
from synthetic.cases import CasoDificil, datos_caucion
from synthetic.contracts import generate_propiedad
from synthetic.dni import dni_de, sumar_anios
from synthetic.legajo import ContextoLegajo, contexto_legajo, fin_de_contrato
from synthetic.source import Source
from synthetic.wording import frase_fecha

TITULO_TITULO = "CONSTANCIA DE TITULARIDAD DE INMUEBLE"
TITULO_CAUCION = "PÓLIZA DE SEGURO DE CAUCIÓN - GARANTÍA DE ALQUILER"

# Escritura: siendo mayor de edad y al menos un año antes de la firma (si el garante es tan
# joven que no entra, la fecha más temprana posible).
EDAD_MIN_ESCRITURA = 18
ANTIGUEDAD_MIN_ESCRITURA = timedelta(days=365)

ETIQUETAS_TITULO = {
    "titular": "Titular",
    "titular_dni": "DNI del titular",
    "inmueble": "Inmueble",
    "matricula": "Matrícula",
    "fecha_escritura": "Fecha de escritura",
}
# `moneda` no tiene fila propia: su evidencia es la misma suma asegurada ("USD 18.000").
ETIQUETAS_CAUCION = {
    "aseguradora": "Aseguradora",
    "numero_poliza": "Póliza N°",
    "tomador": "Tomador",
    "asegurado": "Asegurado",
    "suma_asegurada": "Suma asegurada",
    "vigencia_desde": "Vigencia desde",
    "vigencia_hasta": "Vigencia hasta",
}


# --- título de propiedad del garante ---


def generate_titulo_data(
    contexto: ContextoLegajo, persona_id: UUID, source: Source
) -> TituloPropiedad:
    """Título de un inmueble del garante, coherente con su DNI."""
    identidad = contexto.identidades[persona_id]
    nacimiento = dni_de(contexto, persona_id).fecha_nacimiento
    desde = sumar_anios(nacimiento, EDAD_MIN_ESCRITURA)
    hasta = max(desde, contexto.referencia - ANTIGUEDAD_MIN_ESCRITURA)
    escritura = desde + timedelta(days=source.rng.randint(0, (hasta - desde).days))
    return TituloPropiedad(
        # Como en una escritura: el nombre de pila y el apellido en mayúsculas.
        titular=f"{identidad.nombre_pila} {identidad.apellido.upper()}",
        inmueble=fichas.direccion(generate_propiedad(source)),
        titular_dni=identidad.persona.dni,
        matricula=f"{source.rng.randint(10_000, 299_999)}/{source.rng.randint(1, 9)}",
        fecha_escritura=escritura,
    )


def _valores_titulo(titulo: TituloPropiedad, source: Source) -> dict[str, str]:
    dni = titulo.titular_dni
    return {
        "titular": titulo.titular,
        "titular_dni": source.rng.choice((dni, f"{int(dni):,}".replace(",", "."))),
        "inmueble": titulo.inmueble,
        "matricula": titulo.matricula,
        "fecha_escritura": frase_fecha(source, titulo.fecha_escritura),
    }


def generate_titulo_doc(
    contexto: ContextoLegajo, persona_id: UUID, source: Source
) -> tuple[bytes, TituloPropiedad]:
    titulo = generate_titulo_data(contexto, persona_id, source)
    valores = _valores_titulo(titulo, source)
    filas = [(ETIQUETAS_TITULO[c], v) for c, v in valores.items()]
    pdf = fichas.render_ficha(TITULO_TITULO, "Constancia de titularidad", filas)
    update = {f"{c}_evidencia": Evidencia(texto=v, pagina=1) for c, v in valores.items()}
    return pdf, titulo.model_copy(update=update)


def generate_titulos(
    seed: int, casos: list[CasoDificil] | None = None
) -> dict[UUID, tuple[bytes, TituloPropiedad]]:
    """Título de propiedad de cada garante que firma el contrato (por `Persona.id`).

    Vacío si el contrato no tiene garantes (por ejemplo, con el caso SEGURO_DE_CAUCION).
    """
    contexto = contexto_legajo(seed, casos)
    return {
        p.id: generate_titulo_doc(contexto, p.id, Source(seed).derive(f"titulo:{p.id}"))
        for p in contexto.partes(Rol.GARANTE)
    }


# --- póliza de caución ---


def _nombres(contexto: ContextoLegajo, rol: Rol) -> str:
    return " y ".join(p.nombre for p in contexto.partes(rol))


def generate_caucion_data(contexto: ContextoLegajo) -> PolizaCaucion:
    """Póliza de caución con los datos de la cláusula, que cubre todo el plazo del contrato."""
    datos = datos_caucion(contexto.seed)
    c = contexto.limpio
    return PolizaCaucion(
        aseguradora=datos.aseguradora,
        numero_poliza=datos.poliza,
        vigencia_desde=c.fecha_inicio,
        vigencia_hasta=fin_de_contrato(c),
        tomador=_nombres(contexto, Rol.INQUILINO),
        asegurado=_nombres(contexto, Rol.PROPIETARIO),
        # Todos los alquileres del contrato al valor inicial, en su moneda.
        suma_asegurada=c.monto_inicial * c.plazo_meses,
        moneda=c.moneda,
    )


def _valores_caucion(poliza: PolizaCaucion, source: Source) -> dict[str, str]:
    suma = format_monto(poliza.suma_asegurada, poliza.moneda, EstiloMonto.NUMEROS)
    return {
        "aseguradora": poliza.aseguradora,
        "numero_poliza": poliza.numero_poliza,
        "tomador": poliza.tomador,
        "asegurado": poliza.asegurado,
        "suma_asegurada": suma,
        "moneda": suma,
        "vigencia_desde": frase_fecha(source, poliza.vigencia_desde),
        "vigencia_hasta": frase_fecha(source, poliza.vigencia_hasta),
    }


def generate_caucion(
    seed: int, casos: list[CasoDificil] | None = None
) -> tuple[bytes, PolizaCaucion] | None:
    """Póliza de caución del contrato de la semilla; None si no tiene el caso."""
    contexto = contexto_legajo(seed, casos)
    if CasoDificil.SEGURO_DE_CAUCION not in contexto.casos:
        return None
    poliza = generate_caucion_data(contexto)
    valores = _valores_caucion(poliza, Source(seed).derive("poliza_caucion"))
    filas = [(etiqueta, valores[campo]) for campo, etiqueta in ETIQUETAS_CAUCION.items()]
    pdf = fichas.render_ficha(TITULO_CAUCION, "Póliza de caución", filas)
    update = {f"{c}_evidencia": Evidencia(texto=v, pagina=1) for c, v in valores.items()}
    return pdf, poliza.model_copy(update=update)
