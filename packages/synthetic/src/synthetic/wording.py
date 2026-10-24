"""Frases con variantes para cada dato: la misma información, escrita de formas distintas.

Cada función recibe una `Source` y devuelve el fragmento literal que va al contrato.
Ese fragmento es también la evidencia del ground truth.
"""

from datetime import date

from num2words import num2words

from core.models import Indice, Propiedad, TipoPropiedad
from synthetic.source import Source

# Nombres fijos en vez de locale/strftime: el locale depende de la máquina y rompería
# el determinismo (misma semilla, distinto texto en otro servidor).
MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)

NOMBRE_INDICE = {
    Indice.IPC: (
        "el Índice de Precios al Consumidor (IPC) publicado por el INDEC",
        "la variación del IPC (INDEC)",
    ),
    Indice.ICL: (
        "el Índice para Contratos de Locación (ICL) publicado por el BCRA",
        "el ICL del Banco Central de la República Argentina",
    ),
    Indice.CASA_PROPIA: (
        "el Coeficiente Casa Propia",
        "el índice Casa Propia publicado por el Ministerio de Desarrollo Territorial y Hábitat",
    ),
    Indice.UVA: (
        "el valor de la Unidad de Valor Adquisitivo (UVA) publicado por el BCRA",
        "la variación de las UVA",
    ),
    Indice.DOLAR: (
        "la cotización del dólar estadounidense tipo vendedor del Banco de la Nación Argentina",
        "la variación del dólar oficial (BNA, vendedor)",
    ),
}

ADVERBIO_FRECUENCIA = {
    3: "trimestralmente",
    4: "cuatrimestralmente",
    6: "semestralmente",
    12: "anualmente",
}

# (nombre, terminación para concordar "ubicad_" y "sit_" con el género).
NOMBRE_TIPO = {
    TipoPropiedad.DEPARTAMENTO: ("el departamento", "o"),
    TipoPropiedad.CASA: ("la casa", "a"),
    TipoPropiedad.PH: ("la unidad funcional (PH)", "a"),
    TipoPropiedad.LOCAL: ("el local", "o"),
    TipoPropiedad.OFICINA: ("la oficina", "a"),
    TipoPropiedad.OTRO: ("el inmueble", "o"),
}


def numero_con_letras(n: int) -> str:
    """'treinta y seis (36)': así se escriben plazos y frecuencias en los contratos."""
    return f"{num2words(n, lang='es')} ({n})"


def frase_fecha(source: Source, d: date) -> str:
    dia = "1°" if d.day == 1 else str(d.day)  # "1° de marzo": así se escribe el primer día.
    variantes = (
        f"{dia} de {MESES[d.month - 1]} de {d.year}",
        f"{d:%d/%m/%Y}",
        f"{d:%d.%m.%Y}",
    )
    return source.rng.choice(variantes)


def dia_en_letras(dia: int) -> str:
    """Día delante de 'días': 'veinte', 'veintiún', 'treinta y un' (apócope, como en montos)."""
    letras = num2words(dia, lang="es")
    if letras == "veintiuno":
        return "veintiún"
    return letras.removesuffix("uno") + "un" if letras.endswith("uno") else letras


def frase_fecha_cierre(source: Source, d: date) -> str:
    """Fecha como se escribe al cierre: 'a los veinte días del mes de marzo de 2025'."""
    mes = f"del mes de {MESES[d.month - 1]} de {d.year}"
    if d.day == 1:
        return f"al primer día {mes}"
    dia = source.rng.choice((dia_en_letras(d.day), str(d.day)))
    return f"a los {dia} días {mes}"


def frase_plazo(source: Source, meses: int) -> str:
    variantes = [f"{numero_con_letras(meses)} meses", f"{meses} meses"]
    if meses % 12 == 0:
        anios = meses // 12
        variantes.append(f"{numero_con_letras(anios)} año{'s' if anios > 1 else ''}")
    return source.rng.choice(variantes)


def frase_ajuste(source: Source, indice: Indice, frecuencia: int | None) -> str:
    """Fragmento que respalda índice y frecuencia a la vez (suelen venir en la misma frase)."""
    if indice == Indice.FIJO or frecuencia is None:
        return source.rng.choice(
            (
                "el precio se mantendrá fijo e inamovible durante toda la vigencia del contrato",
                "el precio pactado no estará sujeto a actualización alguna",
            )
        )
    nombre = source.rng.choice(NOMBRE_INDICE[indice])
    variantes = (
        f"se actualizará cada {numero_con_letras(frecuencia)} meses conforme {nombre}",
        f"se ajustará {ADVERBIO_FRECUENCIA[frecuencia]} según {nombre}",
        f"será actualizado en períodos de {frecuencia} meses aplicando {nombre}",
    )
    return source.rng.choice(variantes)


def frase_propiedad(source: Source, p: Propiedad) -> str:
    unidad = ""
    if p.piso is not None:
        unidad = f", piso {p.piso}, departamento {p.departamento}"
    provincia = "Ciudad Autónoma de Buenos Aires" if p.provincia == "CABA" else p.provincia
    nombre, g = NOMBRE_TIPO[p.tipo]
    cp = f" (CP {p.codigo_postal})" if p.codigo_postal is not None else ""
    variantes = (
        f"{nombre} ubicad{g} en {p.calle} {p.numero}{unidad}, {p.localidad}, {provincia}{cp}",
        f"{nombre} sit{g} en la calle {p.calle} N° {p.numero}{unidad}, "
        f"localidad de {p.localidad}, provincia de {provincia}",
    )
    return source.rng.choice(variantes)


def frase_documento(source: Source, dni: str | None, cuit: str | None) -> str:
    """DNI y CUIT con o sin separadores: el extractor tiene que normalizarlos."""
    partes = []
    if dni is not None:
        con_puntos = f"{int(dni):,}".replace(",", ".")
        partes.append(f"DNI {source.rng.choice((dni, con_puntos))}")
    if cuit is not None:
        con_guiones = f"{cuit[:2]}-{cuit[2:10]}-{cuit[10]}"
        partes.append(f"CUIT/CUIL {source.rng.choice((cuit, con_guiones))}")
    return ", ".join(partes)


def frase_tribunales(localidad: str, provincia: str) -> str:
    """Tribunales competentes según dónde está el inmueble.

    'CABA' → 'los Juzgados Nacionales de Primera Instancia en lo Civil de la Ciudad Autónoma
    de Buenos Aires' · ('San Rafael', 'Mendoza') → 'los Tribunales Ordinarios de la Segunda
    Circunscripción Judicial de Mendoza'
    """
    if provincia == "CABA":
        return (
            "los Juzgados Nacionales de Primera Instancia en lo Civil "
            "de la Ciudad Autónoma de Buenos Aires"
        )
    if provincia == "Mendoza":
        circunscripcion = "Segunda" if localidad == "San Rafael" else "Primera"
        return (
            f"los Tribunales Ordinarios de la {circunscripcion} Circunscripción Judicial de Mendoza"
        )
    if provincia == "Buenos Aires":
        return f"los Tribunales Ordinarios del Departamento Judicial de {localidad}"
    if provincia == "Córdoba":
        return "los Tribunales Ordinarios de la Primera Circunscripción Judicial de Córdoba"
    if provincia == "Santa Fe":
        return "los Tribunales Ordinarios de la Segunda Circunscripción Judicial de Santa Fe"
    raise ValueError(f"Sin tribunales para {localidad}, {provincia}")
