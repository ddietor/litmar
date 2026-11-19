"""Fuente OpenAlex: https://help.openalex.org/"""

from __future__ import annotations

from typing import Any

from litmar.articulo import Articulo
from litmar.fuentes.base import Fuente


class OpenAlex(Fuente):
    """Búsqueda de artículos en OpenAlex.

    La clave es opcional: sin ella se comparte un presupuesto diario por IP;
    con una gratuita (https://openalex.org/settings/api) el presupuesto es
    propio y 10 veces mayor. Se envía en la cabecera Authorization para que
    no aparezca en URLs ni logs.
    """

    BASE_URL = "https://api.openalex.org/works"
    MAX_PER_PAGE = 100
    PAGING_LIMIT = 10_000  # page × per_page no puede superarlo
    FIELDS = (
        "id,doi,title,authorships,publication_year,"
        "primary_location,abstract_inverted_index,cited_by_count"
    )

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key

    def buscar(self, consulta: str, n: int = 10, *, desde: int | None = None) -> list[Articulo]:
        if n < 1:
            raise ValueError("n debe ser al menos 1")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        per_page = min(n, self.MAX_PER_PAGE)
        articulos: list[Articulo] = []
        params: dict[str, Any] = {"search": consulta, "per_page": per_page, "select": self.FIELDS}
        if desde is not None:
            params["filter"] = f"publication_year:>{desde - 1}"
        pagina = 1
        # Se descartan obras sin DOI o sin autores, así que puede hacer falta más de una página.
        while len(articulos) < n and pagina * per_page <= self.PAGING_LIMIT:
            datos = self._get_json(
                self.BASE_URL,
                params={**params, "page": pagina},
                headers=headers,
            )
            resultados = datos.get("results") or []
            for obra in resultados:
                articulo = a_articulo(obra)
                if self._admite(articulo, desde):
                    articulos.append(articulo)
                    if len(articulos) == n:
                        break
            if len(resultados) < per_page:  # no hay más páginas
                break
            pagina += 1
        return articulos


def a_articulo(obra: dict[str, Any]) -> Articulo | None:
    """Convierte una obra de OpenAlex en Articulo; None si le faltan datos obligatorios."""
    autores = [
        nombre
        for autoria in obra.get("authorships") or []
        if (nombre := (autoria.get("author") or {}).get("display_name"))
    ]
    doi, titulo, anio = obra.get("doi"), obra.get("title"), obra.get("publication_year")
    if not (doi and titulo and anio and autores):
        return None
    revista = ((obra.get("primary_location") or {}).get("source") or {}).get("display_name")
    try:
        return Articulo(
            title=titulo,
            authors=autores,
            year=anio,
            doi=doi,
            journal=revista or "",
            abstract=reconstruir_resumen(obra.get("abstract_inverted_index")),
            citations=obra.get("cited_by_count"),
        )
    except ValueError:  # p. ej. DOI con formato inesperado
        return None


def reconstruir_resumen(indice: dict[str, list[int]] | None) -> str:
    """OpenAlex da el resumen como índice invertido {palabra: [posiciones]}."""
    if not indice:
        return ""
    posiciones = {pos: palabra for palabra, lista in indice.items() for pos in lista}
    return " ".join(posiciones[p] for p in sorted(posiciones))
