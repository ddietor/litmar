"""Las fuentes de litmar como herramientas que un modelo puede pedir (Clase 2).

Una sola herramienta de búsqueda para todas las fuentes: el modelo elige la
fuente con un parámetro y la herramienta reutiliza `crear_fuente`. Si mañana
llega una fuente nueva por PR, el agente ya puede usarla. `listar_fuentes` le
dice cuáles hay.

El modelo nunca ejecuta nada: pide una herramienta con unos argumentos, el
código la ejecuta y el texto que devuelve entra en la conversación. Por eso:

- **Los docstrings son para el modelo**: con `parse_docstring=True`, el texto
  y la sección `Args` se convierten en la descripción de la herramienta y de
  cada argumento. Dicen cuándo usarla y qué devuelve.
- **Los límites están en el código** (`MAX_RESULTADOS`), no en el prompt.
- **Los errores se devuelven como texto**, no como excepciones: el modelo lee
  qué ha fallado y puede probar otra fuente u otra consulta.
"""

from __future__ import annotations

from collections.abc import Iterable

from langchain_core.tools import tool

from litmar.articulo import Articulo
from litmar.busqueda import mensaje_de_error
from litmar.configuracion import crear_fuente, fuentes_disponibles, nombre_fuente
from litmar.seleccion import describir_citas

MAX_RESULTADOS = 10
LARGO_RESUMEN = 400  # caracteres del resumen que ve el modelo por artículo

AVISO_PANGAEA = (
    "Aviso: PANGAEA devuelve conjuntos de datos (datasets), no artículos. Úsalos como "
    "datos de apoyo, no como estudios publicados."
)

# Para que el modelo sepa qué buscar en cada sitio. Una fuente nueva sin
# descripción aparece igual en `listar_fuentes`.
DESCRIPCIONES = {
    "OpenAlex": "catálogo académico general de todas las disciplinas, con número de citas.",
    "Crossref": "metadatos que registran las editoriales; suele traer menos resúmenes.",
    "Europe PMC": "biomedicina y ciencias de la vida; casi siempre con resumen.",
    "arXiv": "preprints sin revisión por pares (física, informática, matemáticas…); "
    "sin número de citas.",
    "PANGAEA": "conjuntos de datos de ciencias de la Tierra y del mar. No son artículos.",
    "Zotero": "la biblioteca Zotero del usuario o de su grupo; sin número de citas.",
}


def _recortar(texto: str, largo: int = LARGO_RESUMEN) -> str:
    """Recorta sin partir palabras y marca el corte con «…»."""
    texto = " ".join(texto.split())
    if len(texto) <= largo:
        return texto
    return texto[:largo].rsplit(" ", 1)[0] + "…"


def formatear(articulos: Iterable[Articulo]) -> str:
    """Título, año, DOI, citas y resumen recortado de cada artículo, numerados."""
    bloques = []
    for i, articulo in enumerate(articulos, 1):
        resumen = _recortar(articulo.abstract) if articulo.abstract.strip() else "(sin resumen)"
        bloques.append(
            f"{i}. {articulo.title} ({articulo.year})\n"
            f"   DOI: {articulo.doi} | {describir_citas(articulo)}\n"
            f"   Resumen: {resumen}"
        )
    return "\n\n".join(bloques)


def buscar(
    consulta: str,
    fuente: str,
    n: int,
    *,
    permitidas: Iterable[str] | None = None,
    desde: int | None = None,
) -> tuple[str, list[Articulo]]:
    """Lo que hace `buscar_articulos`, devolviendo además los artículos encontrados.

    El texto es lo que lee el modelo; la lista permite al agente registrar qué
    artículos ha visto (para comprobar después los DOI que cite). `permitidas`
    limita las fuentes (por defecto, las disponibles) y `desde`, el año.
    """
    consulta = consulta.strip()
    if not consulta:
        return "Error: la consulta está vacía. Indica unas palabras clave.", []
    permitidas = list(fuentes_disponibles() if permitidas is None else permitidas)
    try:
        nombre = nombre_fuente(fuente)
    except ValueError:
        nombre = None
    if nombre not in permitidas:
        return (
            f"Error: la fuente {fuente!r} no está disponible. Usa una de: {', '.join(permitidas)}.",
            [],
        )
    n = max(1, min(n, MAX_RESULTADOS))  # el límite lo pone el código

    try:
        with crear_fuente(nombre) as fuente_:
            articulos = fuente_.buscar(consulta, n, desde=desde)
    except Exception as exc:  # cualquier fallo vuelve al modelo como texto
        return f"Error: {mensaje_de_error(nombre, exc)} Prueba con otra fuente.", []

    if not articulos:
        return (
            f"Sin resultados en {nombre} para «{consulta}». Prueba con otras palabras clave "
            "(en inglés) o con otra fuente.",
            [],
        )
    resultados = "1 resultado" if len(articulos) == 1 else f"{len(articulos)} resultados"
    cabecera = f"{resultados} de {nombre} para «{consulta}»:"
    if nombre == "PANGAEA":
        cabecera = f"{AVISO_PANGAEA}\n{cabecera}"
    return f"{cabecera}\n\n{formatear(articulos)}", articulos


def describir_fuentes(nombres: Iterable[str]) -> str:
    """El texto de `listar_fuentes` para las fuentes `nombres`."""
    lineas = [f"- {nombre}: {DESCRIPCIONES.get(nombre, 'sin descripción.')}" for nombre in nombres]
    return "Fuentes disponibles para buscar_articulos:\n" + "\n".join(lineas)


@tool(parse_docstring=True)
def buscar_articulos(consulta: str, fuente: str = "OpenAlex", n: int = 5) -> str:
    """Busca artículos científicos en una fuente bibliográfica.

    Devuelve, para cada uno, título, año, DOI, número de citas y el principio
    del resumen. Úsala para encontrar estudios sobre un tema. Para citar un artículo, usa
    exactamente el DOI que devuelve esta herramienta: no cites DOI que no hayas
    obtenido de ella. Si no hay resultados, prueba con otras palabras clave o
    con otra fuente. Usa listar_fuentes para ver qué fuentes hay y qué contiene
    cada una. PANGAEA devuelve conjuntos de datos, no artículos. Si la fuente
    falla, devuelve un mensaje que empieza por «Error».

    Args:
        consulta: palabras clave de la búsqueda, mejor en inglés
            (p. ej. "posidonia carbon sequestration"), sin operadores booleanos.
        fuente: nombre de la fuente tal como lo da listar_fuentes
            (p. ej. "OpenAlex" o "Europe PMC").
        n: cuántos resultados devolver, de 1 a 10.
    """
    texto, _ = buscar(consulta, fuente, n)
    return texto


@tool(parse_docstring=True)
def listar_fuentes() -> str:
    """Lista las fuentes bibliográficas disponibles para buscar_articulos y qué contiene cada una.

    Úsala antes de buscar para elegir las fuentes adecuadas al tema.
    """
    return describir_fuentes(fuentes_disponibles())


HERRAMIENTAS = [buscar_articulos, listar_fuentes]
