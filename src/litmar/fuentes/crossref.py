"""Fuente Crossref: https://www.crossref.org/documentation/retrieve-metadata/rest-api/"""

from __future__ import annotations

import html
import re
from typing import Any

from litmar.articulo import Articulo
from litmar.fuentes.base import Fuente

_TITULO_JATS = re.compile(r"<jats:title>(.*?)</jats:title>", re.IGNORECASE | re.DOTALL)
_ETIQUETA = re.compile(r"<[^>]+>")
_ESPACIOS = re.compile(r"\s+")


class Crossref(Fuente):
    """Búsqueda de artículos de revista en Crossref.

    No necesita clave. Sin identificarse se usa el pool público: 1 petición por
    segundo y 1 simultánea (cabeceras x-rate-limit-*). Con `mailto` se entra en el
    "polite pool", con límites más altos; el correo se envía a Crossref en cada
    petición, así que solo se usa si se indica.
    """

    BASE_URL = "https://api.crossref.org/works"
    MAX_ROWS = 1000
    FIELDS = "DOI,title,author,issued,container-title,abstract,is-referenced-by-count"

    def __init__(self, mailto: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.mailto = mailto

    def buscar(self, consulta: str, n: int = 10, *, desde: int | None = None) -> list[Articulo]:
        if n < 1:
            raise ValueError("n debe ser al menos 1")
        rows = min(n, self.MAX_ROWS)
        params: dict[str, Any] = {
            "query": consulta,
            # Articulo exige revista: se excluyen libros, capítulos, datasets...
            "filter": "type:journal-article"
            + (f",from-pub-date:{desde}" if desde is not None else ""),
            "rows": rows,
            # Con cursor, si no se pide el orden explícitamente, los resultados
            # dejan de ir por relevancia (comprobado contra la API).
            "sort": "relevance",
            "order": "desc",
            "select": self.FIELDS,
        }
        if self.mailto:
            params["mailto"] = self.mailto

        articulos: list[Articulo] = []
        cursor = "*"  # cursor y no offset: offset no pasa de 10 000
        # Se descartan obras sin DOI, título, año o autores, así que puede hacer falta
        # más de una página.
        while len(articulos) < n:
            datos = self._get_json(self.BASE_URL, params={**params, "cursor": cursor})
            mensaje = datos.get("message") or {}
            items = mensaje.get("items") or []
            for item in items:
                articulo = a_articulo(item)
                if self._admite(articulo, desde):
                    articulos.append(articulo)
                    if len(articulos) == n:
                        break
            siguiente = mensaje.get("next-cursor")
            if len(items) < rows or not siguiente:  # no hay más páginas
                break
            cursor = siguiente
        return articulos


def a_articulo(item: dict[str, Any]) -> Articulo | None:
    """Convierte una obra de Crossref en Articulo; None si le faltan datos obligatorios."""
    autores = [nombre for autor in item.get("author") or [] if (nombre := _nombre_autor(autor))]
    doi = item.get("DOI")
    titulo = limpiar_jats(_primero(item.get("title")))
    anio = _anio(item.get("issued"))
    if not (doi and titulo and anio and autores):
        return None
    try:
        return Articulo(
            title=titulo,
            authors=autores,
            year=anio,
            doi=doi,
            journal=limpiar_jats(_primero(item.get("container-title"))),
            abstract=limpiar_jats(item.get("abstract") or ""),
            citations=item.get("is-referenced-by-count"),
        )
    except ValueError:  # p. ej. DOI con formato inesperado
        return None


def limpiar_jats(texto: str) -> str:
    """Convierte el JATS XML de Crossref (``<jats:p>``, ``<jats:italic>``...) en texto plano.

    Los títulos de sección se conservan como prefijo («Methods: ...»), salvo el
    rótulo «Abstract», que no aporta nada.
    """

    def titulo(m: re.Match[str]) -> str:
        nombre = _ETIQUETA.sub("", m.group(1)).strip()
        return " " if nombre.lower() in ("", "abstract") else f" {nombre}: "

    texto = _TITULO_JATS.sub(titulo, texto)
    texto = _ETIQUETA.sub(" ", texto)
    return _ESPACIOS.sub(" ", html.unescape(texto)).strip()


def _nombre_autor(autor: dict[str, Any]) -> str | None:
    """«Apellido, Nombre» (formato que entiende `apellido`) o el nombre de la organización."""
    familia = (autor.get("family") or "").strip()
    nombre = (autor.get("given") or "").strip()
    if familia:
        return f"{familia}, {nombre}" if nombre else familia
    return (autor.get("name") or "").strip() or None


def _primero(valores: list[str] | None) -> str:
    """Crossref da título y revista como listas; nos quedamos con el primer valor."""
    return next((v for v in valores or [] if v and v.strip()), "")


def _anio(fecha: dict[str, Any] | None) -> int | None:
    """Año de un campo de fecha de Crossref: {"date-parts": [[2010, 1, 23]]}."""
    partes = (fecha or {}).get("date-parts") or [[]]
    primera = partes[0] or [None]
    return primera[0] if isinstance(primera[0], int) else None
