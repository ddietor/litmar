"""Modelo de un artículo científico."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PREFIJO_DOI = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


def normalizar_doi(doi: str) -> str:
    """Devuelve el DOI sin prefijo de URL y en minúsculas.

    Los DOI no distinguen mayúsculas, así que «10.1000/ABC» y
    «https://doi.org/10.1000/abc» identifican el mismo artículo.
    """
    normalizado = _PREFIJO_DOI.sub("", doi.strip()).lower()
    if not normalizado.startswith("10.") or "/" not in normalizado:
        raise ValueError(f"DOI no válido: {doi!r}")
    return normalizado


def apellido(autor: str) -> str:
    """Extrae el apellido de un autor.

    Con formato «Apellido, Nombre» devuelve todo lo anterior a la coma
    (admite apellidos compuestos); si no hay coma, la última palabra.
    """
    autor = autor.strip()
    if "," in autor:
        return autor.split(",", 1)[0].strip()
    return autor.split()[-1]


@dataclass(frozen=True, slots=True)
class Articulo:
    """Un artículo científico. Inmutable: el DOI actúa como identidad."""

    title: str
    authors: tuple[str, ...]
    year: int
    doi: str
    journal: str
    abstract: str = ""
    citations: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.authors, str):
            raise TypeError("authors debe ser una secuencia de nombres, no un str")
        authors = tuple(a.strip() for a in self.authors if a.strip())
        if not authors:
            raise ValueError("un artículo necesita al menos un autor")
        if self.citations is not None and type(self.citations) is not int:
            raise TypeError("citations debe ser un entero o None")
        if self.citations is not None and self.citations < 0:
            raise ValueError("el número de citas no puede ser negativo")
        # frozen=True impide la asignación normal; object.__setattr__ es la vía estándar.
        object.__setattr__(self, "authors", authors)
        object.__setattr__(self, "doi", normalizar_doi(self.doi))

    @property
    def short_authors(self) -> str:
        """Autores abreviados: «García», «García y López» o «García et al.»."""
        apellidos = [apellido(a) for a in self.authors]
        if len(apellidos) == 1:
            return apellidos[0]
        if len(apellidos) == 2:
            return f"{apellidos[0]} y {apellidos[1]}"
        return f"{apellidos[0]} et al."

    @property
    def short_citation(self) -> str:
        """Cita en texto: «García (2021)», «García y López (2021)» o «García et al. (2021)»."""
        return f"{self.short_authors} ({self.year})"
