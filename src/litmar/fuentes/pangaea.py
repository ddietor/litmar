"""Fuente PANGAEA: https://www.pangaea.de/"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any

from litmar.articulo import Articulo
from litmar.fuentes.base import Fuente

_NS = {"md": "http://www.pangaea.de/MetaData"}


class Pangaea(Fuente):
    """Búsqueda de datasets en PANGAEA (ciencias de la Tierra y del medio ambiente).

    Usa su índice Elasticsearch público, sin clave. La consulta se envía como
    simple_query_string con AND: admite cualquier texto (con `q=` una «/» o un
    paréntesis sin cerrar dan 400) y exige todos los términos. Cada resultado
    trae sus metadatos completos en XML, así que basta una petición por página.
    Al ser datasets y no artículos, como revista se usa el nombre del repositorio.
    """

    BASE_URL = "https://ws.pangaea.de/es/pangaea/panmd/_search"
    REPOSITORIO = "PANGAEA"
    MAX_PER_PAGE = 100
    PAGING_LIMIT = 10_000  # from + size no puede superarlo (max_result_window)

    def buscar(self, consulta: str, n: int = 10, *, desde: int | None = None) -> list[Articulo]:
        if n < 1:
            raise ValueError("n debe ser al menos 1")
        size = min(n, self.MAX_PER_PAGE)
        articulos: list[Articulo] = []
        consulta_es: dict[str, Any] = {
            "simple_query_string": {"query": consulta, "default_operator": "and"}
        }
        if desde is not None:
            consulta_es = {
                "bool": {
                    "must": [consulta_es],
                    "filter": [{"range": {"agg-pubYear": {"gte": desde}}}],
                }
            }
        inicio = 0
        # Se descartan datasets con metadatos incompletos, así que puede hacer falta
        # más de una página.
        while len(articulos) < n and inicio + size <= self.PAGING_LIMIT:
            cuerpo = {
                "query": consulta_es,
                "from": inicio,
                "size": size,
                "_source": ["xml"],
            }
            # Elasticsearch acepta el cuerpo de la consulta por GET en el parámetro `source`.
            datos = self._get_json(
                self.BASE_URL,
                params={"source": json.dumps(cuerpo), "source_content_type": "application/json"},
            )
            resultados = (datos.get("hits") or {}).get("hits") or []
            for resultado in resultados:
                articulo = a_articulo(resultado)
                if self._admite(articulo, desde):
                    articulos.append(articulo)
                    if len(articulos) == n:
                        break
            if len(resultados) < size:  # no hay más páginas
                break
            inicio += size
        return articulos


def a_articulo(resultado: dict[str, Any]) -> Articulo | None:
    """Convierte un resultado de PANGAEA en Articulo; None si le faltan datos obligatorios."""
    xml = (resultado.get("_source") or {}).get("xml")
    if not xml:
        return None
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError:
        return None
    # Solo los hijos directos de <citation>: <supplementTo> repite autores y título
    # del artículo asociado.
    cita = raiz.find("md:citation", _NS)
    if cita is None:
        return None
    autores = [
        nombre for autor in cita.findall("md:author", _NS) if (nombre := _nombre_autor(autor))
    ]
    doi = cita.findtext("md:URI", namespaces=_NS)
    titulo = cita.findtext("md:title", namespaces=_NS)
    anio = cita.findtext("md:year", namespaces=_NS)
    if not (doi and titulo and anio and autores):
        return None
    try:
        return Articulo(
            title=titulo.strip(),
            authors=autores,
            year=int(anio),
            doi=doi,
            journal=Pangaea.REPOSITORIO,
            abstract=(raiz.findtext("md:abstract", default="", namespaces=_NS)).strip(),
            citations=None,
        )
    except ValueError:  # p. ej. año o DOI con formato inesperado
        return None


def _nombre_autor(autor: ET.Element) -> str:
    """«Apellido, Nombre»; las instituciones solo tienen lastName y se devuelven tal cual."""
    apellido = (autor.findtext("md:lastName", default="", namespaces=_NS)).strip()
    nombre = (autor.findtext("md:firstName", default="", namespaces=_NS)).strip()
    if apellido and nombre:
        return f"{apellido}, {nombre}"
    return apellido
