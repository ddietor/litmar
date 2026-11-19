"""Colección de artículos sin duplicados y exportación a BibTeX y CSV."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import string
import tempfile
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import asdict, fields
from pathlib import Path

from litmar.articulo import Articulo, apellido, normalizar_doi

_ESCAPES_LATEX = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_PATRON_LATEX = re.compile("|".join(re.escape(c) for c in _ESCAPES_LATEX))


class Biblioteca:
    """Conjunto ordenado de artículos, único por DOI."""

    def __init__(self, articulos: Iterable[Articulo] = ()) -> None:
        self._articles: dict[str, Articulo] = {}
        for articulo in articulos:
            self.agregar(articulo)

    def agregar(self, articulo: Articulo) -> bool:
        """Añade el artículo. Devuelve False (y no hace nada) si su DOI ya está."""
        if articulo.doi in self._articles:
            return False
        self._articles[articulo.doi] = articulo
        return True

    def obtener(self, doi: str) -> Articulo | None:
        """Busca por DOI en cualquier formato (URL, mayúsculas...)."""
        return self._articles.get(normalizar_doi(doi))

    def __len__(self) -> int:
        return len(self._articles)

    def __iter__(self) -> Iterator[Articulo]:
        return iter(self._articles.values())

    def __contains__(self, elemento: object) -> bool:
        if isinstance(elemento, Articulo):
            return elemento.doi in self._articles
        if isinstance(elemento, str):
            try:
                return normalizar_doi(elemento) in self._articles
            except ValueError:
                return False
        return False

    def a_bibtex(self) -> str:
        """Devuelve todos los artículos como entradas @article de BibTeX."""
        usadas: set[str] = set()
        entradas = [_entrada_bibtex(a, _clave_unica(a, usadas)) for a in self]
        return "\n\n".join(entradas) + "\n" if entradas else ""

    def exportar_bibtex(self, ruta: str | Path) -> None:
        """Escribe la biblioteca en un fichero .bib (UTF-8)."""
        Path(ruta).write_text(self.a_bibtex(), encoding="utf-8")

    def a_csv(self) -> str:
        """Devuelve los artículos como CSV, con las mismas columnas que el JSON.

        Los autores van en una sola celda separados por «; ».
        """
        salida = io.StringIO()
        escritor = csv.writer(salida)
        escritor.writerow(campo.name for campo in fields(Articulo))
        for articulo in self:
            fila = asdict(articulo)
            fila["authors"] = "; ".join(articulo.authors)
            if articulo.citations is None:
                fila["citations"] = "No disponible"
            escritor.writerow(fila.values())
        return salida.getvalue()

    def guardar(self, ruta: str | Path) -> None:
        """Guarda todos los metadatos en JSON, sustituyendo el archivo de forma atómica."""
        ruta = Path(ruta)
        contenido = json.dumps([asdict(a) for a in self], ensure_ascii=False, indent=2) + "\n"
        temporal = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=ruta.parent, delete=False
            ) as archivo:
                temporal = Path(archivo.name)
                archivo.write(contenido)
            os.replace(temporal, ruta)
        finally:
            if temporal is not None:
                temporal.unlink(missing_ok=True)

    @classmethod
    def cargar(cls, ruta: str | Path) -> Biblioteca:
        """Carga una lista JSON de artículos y elimina duplicados por DOI.

        Rechaza documentos mal formados antes de construir la biblioteca.
        """
        try:
            datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ValueError("la biblioteca no contiene JSON válido en UTF-8") from exc
        if not isinstance(datos, list):
            raise ValueError("la biblioteca debe ser una lista de artículos")
        articulos = []
        for posicion, dato in enumerate(datos, start=1):
            try:
                if not isinstance(dato, dict):
                    raise ValueError("se esperaba un objeto")
                for campo in ("title", "doi", "journal"):
                    if not isinstance(dato.get(campo), str):
                        raise ValueError(f"{campo} debe ser texto")
                if not isinstance(dato.get("authors"), list) or not all(
                    isinstance(autor, str) for autor in dato["authors"]
                ):
                    raise ValueError("authors debe ser una lista de nombres")
                if type(dato.get("year")) is not int:
                    raise ValueError("year debe ser un entero")
                if not isinstance(dato.get("abstract", ""), str):
                    raise ValueError("abstract debe ser texto")
                if dato.get("citations") is not None and type(dato["citations"]) is not int:
                    raise ValueError("citations debe ser un entero o null")
                articulos.append(Articulo(**dato))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"artículo {posicion} inválido: {exc}") from exc
        return cls(articulos)


def _escapar(texto: str) -> str:
    return _PATRON_LATEX.sub(lambda m: _ESCAPES_LATEX[m.group()], texto)


def _clave_unica(articulo: Articulo, usadas: set[str]) -> str:
    """Clave «apellido+año» en ASCII; añade a, b, c... si ya existe."""
    sin_tildes = unicodedata.normalize("NFKD", apellido(articulo.authors[0]))
    base = "".join(c for c in sin_tildes if c.isascii() and c.isalnum()).lower()
    base = f"{base or 'anonimo'}{articulo.year}"
    clave = base
    sufijos = iter(string.ascii_lowercase)
    while clave in usadas:
        clave = base + next(sufijos)
    usadas.add(clave)
    return clave


def _entrada_bibtex(articulo: Articulo, clave: str) -> str:
    campos = [
        ("title", "{" + _escapar(articulo.title) + "}"),  # doble llave: conserva mayúsculas
        ("author", " and ".join(_escapar(a) for a in articulo.authors)),
        ("journal", _escapar(articulo.journal)),
        ("year", str(articulo.year)),
        ("doi", articulo.doi),  # sin escapar: biblatex lo trata literalmente
    ]
    if articulo.abstract:
        campos.append(("abstract", _escapar(articulo.abstract)))
    cuerpo = ",\n".join(f"  {nombre} = {{{valor}}}" for nombre, valor in campos)
    return f"@article{{{clave},\n{cuerpo}\n}}"
