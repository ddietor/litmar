"""Fuente Zotero: https://www.zotero.org/support/dev/web_api/v3/basics"""

from __future__ import annotations

import re
from typing import Any

from litmar.articulo import Articulo
from litmar.fuentes.base import Fuente

_ANIO = re.compile(r"\b(\d{4})\b")


class Zotero(Fuente):
    """Búsqueda en una biblioteca de Zotero (personal o de grupo) por la API web v3.

    Hay que indicar exactamente una de `user_id` o `group_id`. Son números, no
    nombres de usuario: el de usuario aparece en https://www.zotero.org/settings/keys
    y el de grupo en la URL del grupo. La clave solo es necesaria si la biblioteca
    no es pública; se envía en la cabecera Zotero-API-Key, no en la URL.
    Zotero no guarda recuentos de citas, así que `citations` es None.
    """

    BASE_URL = "https://api.zotero.org"
    MAX_LIMIT = 100

    def __init__(
        self,
        *,
        user_id: int | str | None = None,
        group_id: int | str | None = None,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        if (user_id is None) == (group_id is None):
            raise ValueError("indica exactamente uno de user_id o group_id")
        super().__init__(**kwargs)
        prefijo = f"users/{user_id}" if user_id is not None else f"groups/{group_id}"
        self.url = f"{self.BASE_URL}/{prefijo}/items"
        self.api_key = api_key

    def buscar(self, consulta: str, n: int = 10, *, desde: int | None = None) -> list[Articulo]:
        if n < 1:
            raise ValueError("n debe ser al menos 1")
        headers = {"Zotero-API-Version": "3"}
        if self.api_key:
            headers["Zotero-API-Key"] = self.api_key
        limit = min(n, self.MAX_LIMIT)
        articulos: list[Articulo] = []
        start = 0
        # Se descartan adjuntos, notas y obras sin DOI, así que puede hacer falta más de una página.
        # La API no filtra por fecha: `desde` solo se aplica con `_admite`.
        while len(articulos) < n:
            items = self._get_json(
                self.url,
                params={
                    "q": consulta,
                    "itemType": "-attachment",
                    "limit": limit,
                    "start": start,
                    "format": "json",
                },
                headers=headers,
            )
            for item in items:
                articulo = a_articulo(item)
                if self._admite(articulo, desde):
                    articulos.append(articulo)
                    if len(articulos) == n:
                        break
            if len(items) < limit:  # no hay más páginas
                break
            start += limit
        return articulos


def a_articulo(item: dict[str, Any]) -> Articulo | None:
    """Convierte un item de Zotero en Articulo; None si le faltan datos obligatorios."""
    datos = item.get("data") or {}
    autores = [nombre for c in datos.get("creators") or [] if (nombre := _nombre(c, "author"))]
    if not autores:  # sin autores explícitos, se aceptan otros creadores (editores...)
        autores = [nombre for c in datos.get("creators") or [] if (nombre := _nombre(c))]
    doi, titulo = datos.get("DOI"), datos.get("title")
    anio = _anio(item)
    if not (doi and titulo and anio and autores):
        return None
    try:
        return Articulo(
            title=titulo,
            authors=autores,
            year=anio,
            doi=doi,
            journal=datos.get("publicationTitle") or "",
            abstract=datos.get("abstractNote") or "",
            citations=None,
        )
    except ValueError:  # p. ej. DOI con formato inesperado
        return None


def _nombre(creador: dict[str, Any], tipo: str | None = None) -> str:
    """«Apellido, Nombre»; los creadores de un solo campo (`name`) se devuelven tal cual."""
    if tipo and creador.get("creatorType") != tipo:
        return ""
    if creador.get("name"):
        return creador["name"].strip()
    apellido = (creador.get("lastName") or "").strip()
    nombre = (creador.get("firstName") or "").strip()
    return f"{apellido}, {nombre}" if apellido and nombre else apellido or nombre


def _anio(item: dict[str, Any]) -> int | None:
    """Año a partir de la fecha ya interpretada por Zotero o, si no, del texto libre."""
    for texto in ((item.get("meta") or {}).get("parsedDate"), (item.get("data") or {}).get("date")):
        if texto and (m := _ANIO.search(texto)):
            return int(m.group(1))
    return None
