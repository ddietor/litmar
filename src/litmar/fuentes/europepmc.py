"""Fuente Europe PMC: https://europepmc.org/RestfulWebService"""

from __future__ import annotations

from typing import Any

from litmar.articulo import Articulo
from litmar.fuentes.base import Fuente


class EuropePMC(Fuente):
    """Búsqueda de artículos en Europe PMC.

    Europe PMC es un repositorio abierto mantenido por EMBL-EBI.
    No requiere clave de API.
    Endpoint: https://www.ebi.ac.uk/europepmc/webservices/rest/search
    """

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    MAX_PAGE_SIZE = 1000
    DEFAULT_PAGE_SIZE = 100

    def buscar(self, consulta: str, n: int = 10, *, desde: int | None = None) -> list[Articulo]:
        if n < 1:
            raise ValueError("n debe ser al menos 1")

        articulos: list[Articulo] = []
        cursor_mark = "*"
        if desde is not None:
            consulta = f"({consulta}) AND (PUB_YEAR:[{desde} TO 9999])"

        while len(articulos) < n:
            page_size = min(max(25, n - len(articulos)), self.DEFAULT_PAGE_SIZE)
            params: dict[str, Any] = {
                "query": consulta,
                "format": "json",
                "resultType": "core",
                "pageSize": min(page_size, self.MAX_PAGE_SIZE),
                "cursorMark": cursor_mark,
            }
            datos = self._get_json(self.BASE_URL, params=params)
            resultado_lista = (datos.get("resultList") or {}).get("result") or []
            if not resultado_lista:
                break

            for obra in resultado_lista:
                articulo = a_articulo(obra)
                if self._admite(articulo, desde):
                    articulos.append(articulo)
                    if len(articulos) == n:
                        break

            next_cursor = datos.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor_mark:
                break
            cursor_mark = next_cursor

        return articulos


def a_articulo(obra: dict[str, Any]) -> Articulo | None:
    """Convierte un resultado de Europe PMC en Articulo; None si faltan datos obligatorios."""
    autores: list[str] = []
    author_list = (obra.get("authorList") or {}).get("author") or []
    if isinstance(author_list, dict):
        author_list = [author_list]

    for a in author_list:
        last = a.get("lastName")
        first = a.get("firstName") or a.get("initials")
        if last and first:
            autores.append(f"{last}, {first}")
        elif last:
            autores.append(str(last))
        elif full := a.get("fullName"):
            autores.append(str(full))

    if not autores and (author_string := obra.get("authorString")):
        autores = [autor.strip() for autor in author_string.rstrip(".").split(",") if autor.strip()]

    doi = obra.get("doi")
    titulo = obra.get("title")
    anio_str = obra.get("pubYear")

    if not (doi and titulo and anio_str and autores):
        return None

    try:
        anio = int(anio_str)
    except (ValueError, TypeError):
        return None

    revista = (
        (obra.get("journalInfo") or {}).get("journal", {}).get("title")
        or obra.get("journalTitle")
        or ""
    )
    resumen = obra.get("abstractText") or ""
    citas = obra.get("citedByCount")
    if citas is not None:
        try:
            citas = int(citas)
        except (ValueError, TypeError):
            citas = None

    try:
        return Articulo(
            title=titulo.strip(),
            authors=autores,
            year=anio,
            doi=doi,
            journal=revista.strip(),
            abstract=resumen.strip(),
            citations=max(0, citas) if citas is not None else None,
        )
    except ValueError:
        return None
