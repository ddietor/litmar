"""Herramientas de búsqueda para el agente revisor.

Una sola herramienta para todas las fuentes: el modelo elige la fuente con un
parámetro y aquí se reutiliza `crear_fuente`. Así, si mañana llega una fuente
nueva por PR, el agente puede usarla sin tocar este fichero.

Los límites están en el código, no en el prompt: como mucho 10 resultados y
solo las fuentes permitidas por la CLI. Los errores se devuelven como texto
para que el modelo pueda reaccionar (probar otra fuente, por ejemplo) en vez
de recibir una excepción que detenga el grafo.
"""

from __future__ import annotations

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
