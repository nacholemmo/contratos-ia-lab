"""Generación de personas, propiedades y contratos coherentes (el ground truth)."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from core.models import (
    Contrato,
    Indice,
    Moneda,
    Persona,
    Propiedad,
    RegimenLegal,
    Rol,
    Sexo,
    TipoPropiedad,
)
from synthetic.identity import cuit_from_dni, generate_dni
from synthetic.source import Source

# Faker es_AR no relaciona localidad, provincia y código postal (puede dar
# "Constitución, Mendoza"), así que usamos una tabla chica y coherente.
LOCALIDADES: tuple[tuple[str, str, str], ...] = (
    ("Palermo", "CABA", "1425"),
    ("Caballito", "CABA", "1405"),
    ("Villa Crespo", "CABA", "1414"),
    ("Belgrano", "CABA", "1428"),
    ("Almagro", "CABA", "1194"),
    ("La Plata", "Buenos Aires", "1900"),
    ("Mar del Plata", "Buenos Aires", "7600"),
    ("Quilmes", "Buenos Aires", "1878"),
    ("San Isidro", "Buenos Aires", "1642"),
    ("Córdoba", "Córdoba", "5000"),
    ("Rosario", "Santa Fe", "2000"),
    ("Mendoza", "Mendoza", "5500"),
    ("Godoy Cruz", "Mendoza", "5501"),
    ("Guaymallén", "Mendoza", "5521"),
    ("Las Heras", "Mendoza", "5539"),
    ("Luján de Cuyo", "Mendoza", "5507"),
    ("Maipú", "Mendoza", "5515"),
    ("San Rafael", "Mendoza", "5600"),
)

# Mayoría Mendoza (mercado de Avisa); el resto, variado para que el extractor no se
# acostumbre a un solo formato de dirección. Aproximado; ajustar con datos reales.
PESOS_PROVINCIA: dict[str, float] = {
    "Mendoza": 0.70,
    "CABA": 0.12,
    "Buenos Aires": 0.10,
    "Córdoba": 0.04,
    "Santa Fe": 0.04,
}

# Probabilidad de que una persona física tenga su CUIT/CUIL escrito en el contrato.
P_CON_CUIT = 0.6


@dataclass(frozen=True)
class Identidad:
    """Persona del contrato más los datos que el contrato no muestra y el DNI sí.

    `Persona` es lo que el LLM extrae (nombre completo en un campo, sin sexo). El DNI separa
    nombre y apellido y trae el sexo; no se pueden deducir después, porque hay nombres de
    pila con espacio ("Juan Ignacio") y nombres de los dos sexos ("Guadalupe").
    """

    persona: Persona
    nombre_pila: str
    apellido: str
    sexo: Sexo


def generate_identidad(source: Source, rol: Rol) -> Identidad:
    """Persona física con DNI y, a veces, CUIL derivado de ese DNI, con su nombre por partes."""
    sexo = source.rng.choice((Sexo.M, Sexo.F))
    # name_male()/name_female() fallan en es_AR (Faker 40.43): armamos el nombre por partes.
    nombre_pila = (
        source.fake.first_name_male() if sexo == Sexo.M else source.fake.first_name_female()
    )
    apellido = source.fake.last_name()

    dni = generate_dni(source.rng)
    cuit = cuit_from_dni(dni, sexo) if source.rng.random() < P_CON_CUIT else None
    persona = Persona(
        id=source.uuid(), nombre=f"{nombre_pila} {apellido}", rol=rol, dni=dni, cuit=cuit
    )
    return Identidad(persona=persona, nombre_pila=nombre_pila, apellido=apellido, sexo=sexo)


def generate_persona(source: Source, rol: Rol) -> Persona:
    """Persona física con DNI y, a veces, CUIL derivado de ese DNI."""
    return generate_identidad(source, rol).persona


def generate_propiedad(source: Source) -> Propiedad:
    """Propiedad con dirección coherente; piso y departamento solo si es departamento."""
    provincia = _elegir(source, PESOS_PROVINCIA)
    candidatas = [fila for fila in LOCALIDADES if fila[1] == provincia]
    localidad, provincia, codigo_postal = source.rng.choice(candidatas)
    tipo = source.rng.choice(list(TipoPropiedad))
    es_depto = tipo == TipoPropiedad.DEPARTAMENTO
    return Propiedad(
        tipo=tipo,
        calle=source.fake.street_name(),
        numero=source.fake.building_number(),
        piso=str(source.rng.randint(1, 15)) if es_depto else None,
        departamento=source.rng.choice("ABCDEF") if es_depto else None,
        localidad=localidad,
        provincia=provincia,
        codigo_postal=codigo_postal,
    )


# Ventana de fechas de firma: desde la Ley 27.551 hasta antes de "hoy" (fija, no date.today()).
FIRMA_DESDE = date(2020, 7, 1)
FIRMA_HASTA = date(2026, 9, 30)

# Entrada en vigencia de cada régimen (fechas de firma desde las que aplica).
VIGENCIA_27737 = date(2023, 10, 17)
VIGENCIA_DNU_70 = date(2023, 12, 29)

# Rango de alquiler mensual en ARS según el año de firma: con inflación, un monto de 2020
# no puede parecerse a uno de 2026. Aproximado; alcanza para que sea verosímil.
ALQUILER_ARS_POR_ANIO: dict[int, tuple[int, int]] = {
    2020: (15_000, 45_000),
    2021: (20_000, 60_000),
    2022: (35_000, 100_000),
    2023: (80_000, 300_000),
    2024: (250_000, 800_000),
    2025: (350_000, 1_100_000),
    2026: (450_000, 1_400_000),
}
ALQUILER_USD = (300, 1_500)

P_CON_DEPOSITO = 0.85

# Distribución de términos bajo el DNU 70/2023. Aproximada según el mercado, para que la
# base sea representativa; los casos raros se fuerzan aparte (paso 4, casos difíciles).
PESOS_MONEDA_DNU: dict[Moneda, float] = {Moneda.ARS: 0.85, Moneda.USD: 0.15}
PESOS_PLAZO_DNU: dict[int, float] = {24: 0.50, 36: 0.35, 12: 0.10, 48: 0.03, 60: 0.02}
PESOS_INDICE_DNU: dict[Indice, float] = {
    Indice.IPC: 0.55,
    Indice.ICL: 0.20,
    Indice.FIJO: 0.12,
    Indice.CASA_PROPIA: 0.06,
    Indice.UVA: 0.04,
    Indice.DOLAR: 0.03,
}
PESOS_FRECUENCIA_DNU: dict[int, float] = {3: 0.45, 6: 0.30, 4: 0.20, 12: 0.05}


def _elegir[T](source: Source, pesos: dict[T, float]) -> T:
    """Elige una opción según sus pesos, siempre con el rng de la semilla."""
    return source.rng.choices(list(pesos), weights=list(pesos.values()))[0]


@dataclass(frozen=True)
class Terms:
    """Términos del contrato que dependen del régimen legal."""

    plazo_meses: int
    moneda: Moneda
    indice: Indice
    frecuencia_ajuste_meses: int | None


def regimen_por_fecha(fecha_firma: date) -> RegimenLegal:
    """Régimen vigente a la fecha de firma (tabla legal fija, sin decisiones de diseño)."""
    if fecha_firma >= VIGENCIA_DNU_70:
        return RegimenLegal.DNU_70_2023
    if fecha_firma >= VIGENCIA_27737:
        return RegimenLegal.LEY_27737
    return RegimenLegal.LEY_27551


def choose_terms(source: Source, regimen: RegimenLegal) -> Terms:
    """Elige plazo, moneda, índice y frecuencia coherentes con el régimen.

    Ley 27.551: plazo mínimo 36 meses, ajuste anual por ICL.
    Ley 27.737: plazo mínimo 36 meses, ajuste semestral por Casa Propia.
    DNU 70/2023: índice, frecuencia, plazo y moneda libres (pesos o dólares).
    """
    # Bajo las leyes viejas casi todos los contratos se firmaban por el mínimo legal.
    if regimen == RegimenLegal.LEY_27551:
        return Terms(
            plazo_meses=36, moneda=Moneda.ARS, indice=Indice.ICL, frecuencia_ajuste_meses=12
        )
    if regimen == RegimenLegal.LEY_27737:
        return Terms(
            plazo_meses=36, moneda=Moneda.ARS, indice=Indice.CASA_PROPIA, frecuencia_ajuste_meses=6
        )

    moneda = _elegir(source, PESOS_MONEDA_DNU)
    plazo = _elegir(source, PESOS_PLAZO_DNU)

    # En USD no hay ajuste: el monto queda fijo en dólares.
    if moneda == Moneda.USD:
        indice = Indice.FIJO
        frecuencia = None
    else:
        indice = _elegir(source, PESOS_INDICE_DNU)
        frecuencia = None if indice == Indice.FIJO else _elegir(source, PESOS_FRECUENCIA_DNU)

    return Terms(
        plazo_meses=plazo, moneda=moneda, indice=indice, frecuencia_ajuste_meses=frecuencia
    )


def _monto_inicial(source: Source, moneda: Moneda, fecha_firma: date) -> Decimal:
    if moneda == Moneda.USD:
        return Decimal(source.rng.randrange(ALQUILER_USD[0], ALQUILER_USD[1] + 1, 10))
    minimo, maximo = ALQUILER_ARS_POR_ANIO[fecha_firma.year]
    # Redondeado a miles, como se escribe en un contrato real.
    return Decimal(source.rng.randrange(minimo, maximo + 1, 1_000))


def generate_contrato(seed: int) -> Contrato:
    """Contrato completo y coherente a partir de una semilla (misma semilla → mismo contrato)."""
    return generate_contrato_con_identidades(seed)[0]


def generate_contrato_con_identidades(seed: int) -> tuple[Contrato, dict[UUID, Identidad]]:
    """El contrato de la semilla y la identidad de cada parte (por `Persona.id`), para el legajo."""
    source = Source(seed)

    dias = (FIRMA_HASTA - FIRMA_DESDE).days
    fecha_firma = FIRMA_DESDE + timedelta(days=source.rng.randint(0, dias))
    # Normalmente arranca el día 1 de uno de los dos meses siguientes a la firma.
    mes_siguiente = (fecha_firma.replace(day=1) + timedelta(days=32)).replace(day=1)
    if source.rng.random() < 0.5:
        fecha_inicio = mes_siguiente
    else:
        fecha_inicio = (mes_siguiente + timedelta(days=32)).replace(day=1)

    regimen = regimen_por_fecha(fecha_firma)
    terms = choose_terms(source, regimen)
    monto = _monto_inicial(source, terms.moneda, fecha_firma)

    identidades = [generate_identidad(source, Rol.PROPIETARIO)]
    identidades += [
        generate_identidad(source, Rol.INQUILINO) for _ in range(source.rng.randint(1, 2))
    ]
    identidades += [
        generate_identidad(source, Rol.GARANTE) for _ in range(source.rng.randint(0, 2))
    ]
    partes = [i.persona for i in identidades]

    contrato = Contrato(
        id=source.uuid(),
        partes=partes,
        propiedad=generate_propiedad(source),
        fecha_firma=fecha_firma,
        fecha_inicio=fecha_inicio,
        plazo_meses=terms.plazo_meses,
        monto_inicial=monto,
        moneda=terms.moneda,
        indice=terms.indice,
        frecuencia_ajuste_meses=terms.frecuencia_ajuste_meses,
        # Un mes de alquiler, en la misma moneda: lo habitual (y el tope de la Ley 27.551).
        deposito=monto if source.rng.random() < P_CON_DEPOSITO else None,
        regimen_legal=regimen,
    )
    return contrato, {i.persona.id: i for i in identidades}
