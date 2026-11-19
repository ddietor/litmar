<<<<<<< HEAD
"""Herramientas de búsqueda para el agente revisor.

Una sola herramienta para todas las fuentes: el modelo elige la fuente con un
parámetro y aquí se reutiliza `crear_fuente`. Así, si mañana llega una fuente
nueva por PR, el agente puede usarla sin tocar este fichero.

Los límites están en el código, no en el prompt: como mucho 10 resultados y
solo las fuentes permitidas por la CLI. Los errores se devuelven como texto
para que el modelo pueda reaccionar (probar otra fuente, por ejemplo) en vez
de recibir una excepción que detenga el grafo.
=======
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
>>>>>>> upstream/main
"""

from __future__ import annotations

<<<<<<< HEAD
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx
from langchain_core.tools import BaseTool, tool

from litmar.articulo import Articulo
from litmar.configuracion import crear_fuente, fuentes_disponibles, id_fuente, nombre_fuente
from litmar.fuentes import Fuente

MAX_RESULTADOS = 10
LONGITUD_RESUMEN = 320
AVISO_PANGAEA = (
    "PANGAEA devuelve conjuntos de datos, no artículos revisados: "
    "úsalo solo si la pregunta admite datos."
)


@dataclass
class RegistroBusquedas:
    """Lo que las herramientas han entregado al modelo, para verificar después.

    Es la memoria compartida entre `herramientas.py` y la comprobación final:
    el agente puede citar solo los DOI que estén aquí. También guarda las
    llamadas para poder revisar qué hizo.
    """

    articulos: dict[str, Articulo] = field(default_factory=dict)
    llamadas: list[dict[str, Any]] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def registrar(self, llamada: dict[str, Any], articulos: list[Articulo] = ()) -> None:
        """Anota una llamada y añade sus artículos, sin sobrescribir los anteriores."""
        self.llamadas.append(llamada)
        for articulo in articulos:
            self.articulos.setdefault(articulo.doi, articulo)


def _detalle_error(exc: Exception) -> str:
    """Describe el fallo sin filtrar URL ni cabeceras (pueden llevar claves)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, ValueError):
        return str(exc)  # mensajes propios de litmar, sin secretos
    return type(exc).__name__


def crear_herramientas(
    *,
    crear: Callable[[str], Fuente] | None = None,
    entorno: Mapping[str, str] | None = None,
    registro: RegistroBusquedas | None = None,
    fuentes: list[str] | None = None,
    n: int = 6,
    desde: int | None = None,
) -> tuple[BaseTool, BaseTool, RegistroBusquedas]:
    """Construye `buscar_articulos` y `listar_fuentes` con los límites ya aplicados.

    `crear` y `entorno` se inyectan para poder probar sin red; `fuentes`, `n` y
    `desde` vienen de la CLI y no se negocian con el modelo. Devuelve también
    el registro compartido para que la CLI pueda comprobar las citas.
    """
    registro = registro or RegistroBusquedas()
    permitidas = list(fuentes) if fuentes is not None else fuentes_disponibles(entorno)
    tope = max(1, min(n, MAX_RESULTADOS))

    def fabricar(nombre: str) -> Fuente:
        if crear is not None:
            return crear(nombre)
        return crear_fuente(nombre, entorno)

    @tool
    def buscar_articulos(consulta: str, fuente: str, n: int = tope) -> str:
        """Busca artículos en una fuente: título, año, DOI, citas y resumen breve.

        Usa esta herramienta para responder preguntas sobre literatura científica.
        Antes llama a `listar_fuentes` si no sabes qué fuentes hay. El parámetro
        `fuente` admite el nombre de la fuente o su identificador (por ejemplo
        «Europe PMC» o «europepmc»). Pide varias consultas y, siempre que puedas,
        más de una fuente. Cita después solo los DOI que aparezcan en los
        resultados: son los únicos que puedes usar.

        El número máximo de resultados por llamada es 10; si pides más, se
        recorta. Si la fuente falla, devuelve un mensaje de error como texto:
        prueba otra fuente en lugar de repetir la misma. PANGAEA devuelve
        datos, no artículos revisados.
        """
        consulta = consulta.strip()
        if not consulta:
            registro.registrar(
                {"consulta": consulta, "fuente": fuente, "n": n, "error": "consulta vacía"}
            )
            return "Error: la consulta está vacía. Escribe términos de búsqueda."

        try:
            nombre = nombre_fuente(fuente)
        except ValueError:
            validas = ", ".join(id_fuente(f) for f in permitidas)
            registro.registrar(
                {"consulta": consulta, "fuente": fuente, "n": n, "error": "fuente desconocida"}
            )
            return f"Error: fuente desconocida {fuente!r}. Fuentes disponibles: {validas}."

        if nombre not in permitidas:
            validas = ", ".join(id_fuente(f) for f in permitidas)
            registro.registrar(
                {"consulta": consulta, "fuente": nombre, "n": n, "error": "fuente no permitida"}
            )
            return f"Error: {nombre} no está entre las fuentes permitidas ({validas})."

        solicitados = max(1, min(n, MAX_RESULTADOS))
        aviso_recorte = ""
        if n > MAX_RESULTADOS:
            aviso_recorte = (
                f" Has pedido {n}; el máximo es {MAX_RESULTADOS}, "
                f"así que te devuelvo {solicitados}."
            )

        fuente_obj = None
        try:
            fuente_obj = fabricar(nombre)
            articulos = fuente_obj.buscar(consulta, solicitados, desde=desde)
        except Exception as exc:  # httpx, ValueError de configuración, fallos de parseo...
            detalle = _detalle_error(exc)
            mensaje = f"{nombre} no ha podido buscar ({detalle}). Prueba otra fuente."
            registro.registrar(
                {"consulta": consulta, "fuente": nombre, "n": solicitados, "error": detalle},
            )
            registro.avisos.append(mensaje)
            return mensaje
        finally:
            # Solo cerramos las fuentes que hemos creado nosotros: una fábrica
            # inyectada (tests, UI) puede querer reutilizar la misma instancia.
            if crear is None and fuente_obj is not None:
                fuente_obj.close()

        # Un mismo DOI puede venir en varias fuentes o páginas: el modelo solo
        # necesita verlo una vez (y así no puede citarlo dos veces).
        vistos: set[str] = set()
        pedidos: list[Articulo] = []
        for articulo in articulos:
            if articulo.doi in vistos:
                continue
            vistos.add(articulo.doi)
            pedidos.append(articulo)
            if len(pedidos) == solicitados:
                break
        registro.registrar(
            {
                "consulta": consulta,
                "fuente": nombre,
                "n": solicitados,
                "doi": [articulo.doi for articulo in pedidos],
            },
            pedidos,
        )
        if not pedidos:
            return (
                f"{nombre}: sin resultados para «{consulta}».{aviso_recorte} "
                "Prueba otra consulta o fuente."
            )

        bloques = [
            f"{i}. {articulo.title}\n"
            f"   Año: {articulo.year} · DOI: [{articulo.doi}] · Citas: {articulo.citations}\n"
            f"   Resumen: {_recortar(articulo.abstract.strip() or 'sin resumen', LONGITUD_RESUMEN)}"
            for i, articulo in enumerate(pedidos, start=1)
        ]
        sufijo = "" if len(pedidos) == 1 else "s"
        cabecera = f"{nombre}: {len(pedidos)} artículo{sufijo} para «{consulta}».{aviso_recorte}"
        return "\n".join([cabecera, "", *bloques])

    @tool
    def listar_fuentes() -> str:
        """Devuelve las fuentes de literatura científica que puedes usar en `buscar_articulos`.

        Llama a esta herramienta antes de buscar si no sabes qué fuentes hay o
        cómo se llaman. Incluye el identificador corto y el nombre completo.
        PANGAEA devuelve datos, no artículos revisados.
        """
        if not permitidas:
            return "No hay fuentes disponibles con la configuración actual."
        lineas = [f"- {id_fuente(nombre)} ({nombre})" for nombre in permitidas]
        return "Fuentes disponibles:\n" + "\n".join([*lineas, "", AVISO_PANGAEA])

    return buscar_articulos, listar_fuentes, registro


def _recortar(texto: str, ancho: int) -> str:
    """Corta el resumen que ve el modelo: menos ruido, menos tokens."""
    texto = " ".join(texto.split())
    return texto if len(texto) <= ancho else texto[: ancho - 1].rstrip() + "…"
=======
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
>>>>>>> upstream/main
