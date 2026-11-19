"""arXiv source: https://info.arxiv.org/help/api/user-manual.html"""

from __future__ import annotations

import re
from typing import Any
from xml.etree.ElementTree import Element, fromstring

from litmar.articulo import Articulo, normalizar_doi
from litmar.fuentes.base import Fuente

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"

_ENTRY_ID = re.compile(r"/abs/(?P<id>.+?)(?:v\d+)?$")
_WHITESPACE = re.compile(r"\s+")
_FIELD_PREFIX = re.compile(r"\b(?:all|ti|au|abs|co|jr|cat|rn|id):")
_BOOLEAN = re.compile(r"\b(?:AND|OR|ANDNOT)\b")


class Arxiv(Fuente):
    """Article search on arXiv.

    The API returns Atom XML instead of JSON and asks for a three second delay
    between consecutive requests. No API key is required.

    ``consulta`` is sent as ``all:<text>`` by default. Advanced arXiv syntax
    (field prefixes or boolean operators) is passed through unchanged.
    Entries without a usable identifier or DOI are discarded, as required by
    the Articulo model.
    """

    BASE_URL = "https://export.arxiv.org/api/query"
    MAX_RESULTS = 2000  # maximum results per request
    MAX_TOTAL = 30_000  # arXiv rejects queries beyond this offset
    REQUEST_DELAY = 3.0  # seconds between paged requests, as requested by arXiv

    def __init__(self, *, request_delay: float = REQUEST_DELAY, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.request_delay = request_delay

    def buscar(self, consulta: str, n: int = 10, *, desde: int | None = None) -> list[Articulo]:
        if n < 1:
            raise ValueError("n must be at least 1")
        page_size = min(n, self.MAX_RESULTS)
        articles: list[Articulo] = []
        start = 0
        while len(articles) < n and start < self.MAX_TOTAL:
            if start:
                self._sleep(self.request_delay)
            response = self._get(
                self.BASE_URL,
                params={
                    "search_query": _search_query(consulta, desde),
                    "start": start,
                    "max_results": page_size,
                    "sortBy": "relevance",
                    "sortOrder": "descending",
                },
            )
            entries = fromstring(response.content).findall(f"{ATOM}entry")
            _raise_for_api_error(entries)
            for entry in entries:
                article = to_article(entry)
                if self._admite(article, desde):
                    articles.append(article)
                    if len(articles) == n:
                        break
            if len(entries) < page_size:  # no more pages
                break
            start += page_size
        return articles


def _search_query(consulta: str, desde: int | None = None) -> str:
    text = consulta.strip()
    if not (_FIELD_PREFIX.search(text) or _BOOLEAN.search(text)):
        text = f"all:{text}"
    if desde is not None:
        # Fecha de la primera versión; el año del artículo se comprueba aparte.
        text = f"({text}) AND submittedDate:[{desde}01010000 TO 999912312359]"
    return text


def _raise_for_api_error(entries: list[Element]) -> None:
    """arXiv reports errors as HTTP 200 feeds with a single error entry."""
    for entry in entries:
        entry_id = _text(entry, f"{ATOM}id")
        if "/api/errors#" in entry_id:
            message = _text(entry, f"{ATOM}summary") or "arXiv API returned an error"
            raise ValueError(message)


def to_article(entry: Element) -> Articulo | None:
    """Convert an Atom entry into an Articulo; None if required data is missing."""
    title = _text(entry, f"{ATOM}title")
    year = _year(_text(entry, f"{ATOM}published"))
    authors = [
        name for author in entry.findall(f"{ATOM}author") if (name := _text(author, f"{ATOM}name"))
    ]
    doi = _doi(entry)
    if not (title and year and authors and doi):
        return None
    try:
        return Articulo(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            journal=_text(entry, f"{ARXIV}journal_ref") or "arXiv",
            abstract=_text(entry, f"{ATOM}summary"),
            citations=None,
        )
    except ValueError:  # invalid DOI or article data
        return None


def _doi(entry: Element) -> str | None:
    published_doi = _text(entry, f"{ARXIV}doi")
    if published_doi:
        try:
            normalizar_doi(published_doi)
        except ValueError:
            pass  # ignore a malformed journal DOI and use the arXiv one
        else:
            return published_doi
    arxiv_id = _arxiv_id(entry)
    return f"10.48550/arXiv.{arxiv_id}" if arxiv_id else None


def _arxiv_id(entry: Element) -> str | None:
    match = _ENTRY_ID.search(_text(entry, f"{ATOM}id"))
    return match.group("id") if match else None


def _year(published: str) -> int | None:
    return int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None


def _text(element: Element, path: str) -> str:
    value = element.findtext(path)
    return _WHITESPACE.sub(" ", value).strip() if value else ""
