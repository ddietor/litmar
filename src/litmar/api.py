"""API HTTP de litmar: otra puerta de entrada, como la CLI y la interfaz web.

El contrato (rutas, modelos y códigos de error) está en `DECISIONS.md` (D-24).
Las rutas reutilizan `buscar_en_fuentes`, `flujo.revisar` y `agente.revisar`:
aquí solo se valida la entrada, se traducen los errores a códigos HTTP y se
devuelve JSON. No se guarda nada en disco.

La API no pide token: está pensada para un uso interno, detrás de la web que
sirve ella misma en `/` (D-25), en el mismo origen. Para exponerla a Internet,
primero habría que añadir autenticación, límites de uso y HTTPS.
"""

from __future__ import annotations

from importlib.resources import files
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from litmar import agente, flujo
from litmar.articulo import Articulo
from litmar.busqueda import buscar_en_fuentes
from litmar.configuracion import FUENTES, fuentes_disponibles, id_fuente, nombre_fuente
from litmar.herramientas import DESCRIPCIONES
from litmar.llm import ErrorDeConfiguracion, crear_modelo

app = FastAPI(
    title="litmar",
    version="0.1.0",
    description=(
        "Busca literatura científica y revisa una pregunta de investigación. "
        "Sin autenticación: úsala en una red de confianza. "
        "Las revisiones son síncronas y pueden tardar varios minutos."
    ),
)

ANIO_MINIMO = 1900
ANIO_MAXIMO = 2100
MAX_RESULTADOS = 50
FUENTE_POR_DEFECTO = ["openalex"]


# --- Modelos de entrada y salida ------------------------------------------------


class ArticuloSalida(BaseModel):
    """Un artículo, con los mismos campos que el JSON de `Biblioteca`."""

    title: str
    authors: list[str]
    year: int
    doi: str
    journal: str
    abstract: str
    citations: int | None

    @classmethod
    def desde(cls, articulo: Articulo) -> ArticuloSalida:
        """Convierte el `dataclass` de litmar en un modelo de respuesta."""
        return cls(
            title=articulo.title,
            authors=list(articulo.authors),
            year=articulo.year,
            doi=articulo.doi,
            journal=articulo.journal,
            abstract=articulo.abstract,
            citations=articulo.citations,
        )


class SaludSalida(BaseModel):
    estado: Literal["ok"]


class FuenteSalida(BaseModel):
    id: str
    nombre: str
    descripcion: str
    disponible: bool


class FuentesSalida(BaseModel):
    fuentes: list[FuenteSalida]


class BusquedaSalida(BaseModel):
    """Artículos encontrados y avisos: una fuente puede fallar sin arruinar la búsqueda."""

    articulos: list[ArticuloSalida]
    errores: list[str]
    fuentes_fallidas: list[str]


class RevisionEntrada(BaseModel):
    """Cuerpo de `POST /revisiones`."""

    pregunta: str = Field(min_length=1, max_length=500)
    modo: Literal["flujo", "agente"] = "flujo"
    fuente: list[str] = Field(default_factory=lambda: ["openalex", "europepmc"], min_length=1)
    n: int = Field(default=6, ge=1, le=flujo.MAX_SELECCIONADOS)
    desde: int | None = Field(default=None, ge=ANIO_MINIMO, le=ANIO_MAXIMO)

    @field_validator("pregunta")
    @classmethod
    def _pregunta_no_vacia(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("la pregunta no puede estar vacía")
        return limpio


class RevisionSalida(BaseModel):
    """Informe y BibTeX como texto: la API no escribe archivos."""

    pregunta: str
    modo: Literal["flujo", "agente"]
    informe: str
    bibtex: str
    citados: list[str]
    avisos: list[str]


# --- Utilidades ------------------------------------------------------------------


def _nombres_fuentes(identificadores: list[str]) -> list[str]:
    """Ids de CLI (o nombres canónicos) → nombres canónicos, sin repetir.

    Una fuente que no se puede usar con esta configuración (Zotero sin id) es
    error del cliente: 422, antes de llamar a ninguna API externa.
    """
    try:
        nombres = [nombre_fuente(identificador) for identificador in identificadores]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    disponibles = set(fuentes_disponibles())
    no_disponibles = [nombre for nombre in nombres if nombre not in disponibles]
    if no_disponibles:
        raise HTTPException(
            status_code=422,
            detail=(
                f"fuentes no configuradas: {', '.join(no_disponibles)}. "
                "Revisa la sección correspondiente de .env.example."
            ),
        )
    return list(dict.fromkeys(nombres))


# --- Rutas ----------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Servir la web desde el paquete (también funciona instalada con uv)."""
    html = files("litmar").joinpath("web", "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/salud", response_model=SaludSalida)
def salud() -> SaludSalida:
    """Comprobar que el servidor responde; no consulta fuentes ni modelo."""
    return SaludSalida(estado="ok")


@app.get("/fuentes", response_model=FuentesSalida)
def fuentes() -> FuentesSalida:
    """Listar las fuentes conocidas y cuáles se pueden usar con el .env actual."""
    disponibles = set(fuentes_disponibles())
    return FuentesSalida(
        fuentes=[
            FuenteSalida(
                id=id_fuente(nombre),
                nombre=nombre,
                descripcion=DESCRIPCIONES.get(nombre, "sin descripción."),
                disponible=nombre in disponibles,
            )
            for nombre in FUENTES
        ]
    )


@app.get("/buscar", response_model=BusquedaSalida)
def buscar(
    consulta: Annotated[str, Query(min_length=1, max_length=500)],
    fuente: Annotated[list[str], Query()] = FUENTE_POR_DEFECTO,
    n: Annotated[int, Query(ge=1, le=MAX_RESULTADOS)] = 10,
    desde: Annotated[int | None, Query(ge=ANIO_MINIMO, le=ANIO_MAXIMO)] = None,
) -> BusquedaSalida:
    """Buscar en varias fuentes a la vez, con deduplicación por DOI.

    Si falla una fuente se devuelve 200 con el aviso en `errores`; solo si
    fallan todas se devuelve 502.
    """
    if not consulta.strip():
        raise HTTPException(status_code=422, detail="la consulta no puede estar vacía")
    nombres = _nombres_fuentes(fuente)
    resultado = buscar_en_fuentes(consulta.strip(), nombres, n, desde=desde)
    if len(resultado.failed) == len(nombres):
        raise HTTPException(
            status_code=502,
            detail={"mensaje": "Ninguna fuente respondió.", "errores": resultado.errors},
        )
    return BusquedaSalida(
        articulos=[ArticuloSalida.desde(a) for a in resultado.library],
        errores=resultado.errors,
        fuentes_fallidas=resultado.failed,
    )


@app.post("/revisiones", response_model=RevisionSalida)
def revisiones(datos: RevisionEntrada) -> RevisionSalida:
    """Responder a una pregunta con un informe que solo cita artículos reales.

    Llama a `flujo.revisar` o `agente.revisar` según `modo` y devuelve el
    informe en Markdown y el BibTeX de lo citado. No hay aprobación humana ni
    guardado en disco: para eso está la CLI.
    """
    nombres = _nombres_fuentes(datos.fuente)
    try:
        modelo = crear_modelo()
    except ErrorDeConfiguracion as exc:
        raise HTTPException(status_code=503, detail={"mensaje": str(exc)}) from exc

    try:
        revisar = agente.revisar if datos.modo == "agente" else flujo.revisar
        estado = revisar(
            modelo,
            datos.pregunta,
            fuentes=nombres,
            n=datos.n,
            desde=datos.desde,
        )
    except ErrorDeConfiguracion as exc:
        raise HTTPException(status_code=503, detail={"mensaje": str(exc)}) from exc
    except Exception as exc:
        # Solo el tipo: el mensaje del proveedor puede traer la petición o la clave.
        raise HTTPException(
            status_code=502,
            detail={"mensaje": f"Falló la revisión del modelo ({type(exc).__name__})."},
        ) from exc

    citados = flujo.citados(estado)
    return RevisionSalida(
        pregunta=estado.get("question", datos.pregunta),
        modo=datos.modo,
        informe=flujo.informe_markdown(estado),
        bibtex=citados.a_bibtex(),
        citados=[articulo.doi for articulo in citados],
        avisos=list(estado.get("warnings", [])),
    )
