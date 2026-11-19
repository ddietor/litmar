"""Tests for the Arxiv connector. No network: httpx.MockTransport replies."""

from pathlib import Path
from xml.etree.ElementTree import Element, fromstring

import httpx
import pytest

from litmar.fuentes import Arxiv
from litmar.fuentes.arxiv import to_article

FEED = (Path(__file__).parent / "datos" / "arxiv_feed.xml").read_text(encoding="utf-8")


def atom_response(body: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        content=body.encode("utf-8"),
        headers={"Content-Type": "application/atom+xml"},
    )


def client(*responses, requests=None):
    pending = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        response = pending.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    return httpx.Client(transport=httpx.MockTransport(handler))


def make_entry(**changes) -> str:
    fields = {
        "id": "http://arxiv.org/abs/2401.11111v1",
        "published": "2024-01-01T00:00:00Z",
        "title": "A paper",
        "summary": "An abstract.",
        "authors": "<author><name>Alice, Smith</name></author>",
        "extra": "",
    }
    fields.update(changes)
    return (
        f"<entry><id>{fields['id']}</id>"
        f"<published>{fields['published']}</published>"
        f"<title>{fields['title']}</title>"
        f"<summary>{fields['summary']}</summary>"
        f"{fields['authors']}{fields['extra']}</entry>"
    )


def make_feed(entries: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:arxiv="http://arxiv.org/schemas/atom">'
        f"{entries}</feed>"
    )


def entry_element(body: str) -> Element:
    return fromstring(make_feed(body))[0]


class CappedArxiv(Arxiv):
    """Test subclass with a small page size to exercise the cap without huge feeds."""

    MAX_RESULTS = 2


def test_arxiv_converts_saved_feed():
    articles = Arxiv(client=client(atom_response(FEED))).buscar("bibliometrics", n=3)

    assert [a.doi for a in articles] == [
        "10.1000/published.one",
        "10.48550/arxiv.2302.09999",
        "10.48550/arxiv.hep-th/9901001",
    ]
    first = articles[0]
    assert first.title == "Bibliometric mapping of scientific literature"
    assert first.authors == ("Alice, Smith", "Bob Jones")
    assert first.year == 2024
    assert first.journal == "Journal of Examples 12 (2024) 1-9"
    assert first.abstract == "A study of bibliometric maps and their limits."
    assert first.citations is None
    assert articles[1].journal == "arXiv"
    assert articles[2].year == 1999


def test_arxiv_request_parameters():
    requests = []
    Arxiv(client=client(atom_response(FEED), requests=requests)).buscar("deep learning", n=3)

    (request,) = requests
    assert request.url.host == "export.arxiv.org"
    assert request.url.path == "/api/query"
    params = request.url.params
    assert params["search_query"] == "all:deep learning"
    assert params["start"] == "0"
    assert params["max_results"] == "3"
    assert params["sortBy"] == "relevance"
    assert params["sortOrder"] == "descending"


def test_arxiv_keeps_advanced_query_syntax():
    requests = []
    Arxiv(client=client(atom_response(FEED), requests=requests)).buscar(
        "ti:transformer AND cat:cs.CL", n=1
    )
    assert requests[0].url.params["search_query"] == "ti:transformer AND cat:cs.CL"


def test_arxiv_prefers_published_doi():
    entry = entry_element(make_entry(extra="<arxiv:doi>10.1000/journal.article</arxiv:doi>"))
    assert to_article(entry).doi == "10.1000/journal.article"


def test_arxiv_ignores_malformed_published_doi():
    entry = entry_element(make_entry(extra="<arxiv:doi>not-a-doi</arxiv:doi>"))
    assert to_article(entry).doi == "10.48550/arxiv.2401.11111"


def test_arxiv_strips_version_from_identifier():
    entry = entry_element(make_entry(id="http://arxiv.org/abs/math.GT/0309136v4"))
    assert to_article(entry).doi == "10.48550/arxiv.math.gt/0309136"


def test_arxiv_normalizes_whitespace():
    entry = entry_element(
        make_entry(title="  A   title\n with lines  ", summary=" An\n abstract. ")
    )
    article = to_article(entry)
    assert article.title == "A title with lines"
    assert article.abstract == "An abstract."


@pytest.mark.parametrize(
    "changes",
    [
        {"id": ""},
        {"published": ""},
        {"title": ""},
        {"authors": ""},
    ],
)
def test_arxiv_discards_incomplete_entries(changes):
    assert to_article(entry_element(make_entry(**changes))) is None


def test_arxiv_paginates_when_entries_are_discarded():
    first_page = make_feed(
        make_entry(id="http://arxiv.org/abs/2401.11111v1")
        + make_entry(id="http://arxiv.org/abs/2401.22222v1", published="")
    )
    second_page = make_feed(make_entry(id="http://arxiv.org/abs/2401.33333v1"))
    requests = []
    waits = []
    articles = Arxiv(
        client=client(atom_response(first_page), atom_response(second_page), requests=requests),
        sleep=waits.append,
    ).buscar("x", n=2)

    assert [a.doi for a in articles] == [
        "10.48550/arxiv.2401.11111",
        "10.48550/arxiv.2401.33333",
    ]
    assert [r.url.params["start"] for r in requests] == ["0", "2"]
    assert waits == [3.0]


def test_arxiv_caps_page_size():
    pages = [
        atom_response(
            make_feed(
                make_entry(id=f"http://arxiv.org/abs/2401.000{i}v1")
                + make_entry(id=f"http://arxiv.org/abs/2401.001{i}v1")
            )
        )
        for i in range(2)
    ]
    pages.append(atom_response(make_feed(make_entry(id="http://arxiv.org/abs/2401.0020v1"))))
    requests = []
    waits = []
    articles = CappedArxiv(client=client(*pages, requests=requests), sleep=waits.append).buscar(
        "x", n=5
    )

    assert len(articles) == 5
    assert [r.url.params["max_results"] for r in requests] == ["2", "2", "2"]
    assert [r.url.params["start"] for r in requests] == ["0", "2", "4"]
    assert waits == [3.0, 3.0]


def test_arxiv_does_not_return_more_than_n():
    assert len(Arxiv(client=client(atom_response(FEED))).buscar("x", n=1)) == 1


def test_arxiv_n_invalid():
    with pytest.raises(ValueError):
        Arxiv(client=client()).buscar("x", n=0)


def test_arxiv_inherits_retries():
    waits = []
    fuente = Arxiv(client=client(httpx.Response(429), atom_response(FEED)), sleep=waits.append)
    assert len(fuente.buscar("x", n=3)) == 3
    assert waits == [1.0]


def test_arxiv_raises_for_api_error_feed():
    error_feed = make_feed(
        "<entry><id>http://arxiv.org/api/errors#incorrect_id_format</id>"
        "<title>Error</title><summary>incorrect id format</summary></entry>"
    )
    with pytest.raises(ValueError, match="incorrect id format"):
        Arxiv(client=client(atom_response(error_feed))).buscar("x", n=1)
