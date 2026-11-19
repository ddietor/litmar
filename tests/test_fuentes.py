"""Tests de Fuente, OpenAlex y Crossref.

Ninguno usa la red: httpx.MockTransport responde en su lugar.
"""

import json
from pathlib import Path

import httpx
import pytest

from litmar.fuentes import Crossref, EuropePMC, Fuente, OpenAlex
from litmar.fuentes.crossref import a_articulo as crossref_a_articulo
from litmar.fuentes.crossref import limpiar_jats
from litmar.fuentes.europepmc import a_articulo as europepmc_a_articulo
from litmar.fuentes.openalex import a_articulo as openalex_a_articulo
from litmar.fuentes.openalex import reconstruir_resumen

DATOS = Path(__file__).parent / "datos"

# Respuesta real de
# GET /works?search=bibliometrics citation analysis&per_page=3&select=...
# guardada el 2026-11-17. Contiene una obra sin DOI, que debe descartarse.
RESPUESTA_OPENALEX = json.loads((DATOS / "openalex_works.json").read_text(encoding="utf-8"))
RESPUESTA_EUROPEPMC = json.loads((DATOS / "europepmc_search.json").read_text(encoding="utf-8"))
VACIA = {"meta": {}, "results": []}
VACIA_EUROPEPMC = {"resultList": {"result": []}}

# Respuestas reales de Crossref, guardadas el 2026-11-17 con
# GET /works?query=citation analysis bibliometrics&filter=type:journal-article
#     &rows=4&cursor=*&sort=relevance&order=desc&select=...
# La segunda añade has-abstract:1 al filtro y rows=2: trae un resumen en JATS
# y una obra sin autores, que debe descartarse.
RESPUESTA_CROSSREF = json.loads((DATOS / "crossref_works.json").read_text(encoding="utf-8"))
RESPUESTA_CROSSREF_CON_RESUMEN = json.loads(
    (DATOS / "crossref_works_con_resumen.json").read_text(encoding="utf-8")
)


def cliente(*respuestas, peticiones=None):
    """Cliente httpx que devuelve las respuestas en orden y anota cada petición.

    Cada respuesta es un httpx.Response, un dict (JSON con 200) o una excepción.
    """
    pendientes = list(respuestas)

    def manejar(peticion: httpx.Request) -> httpx.Response:
        if peticiones is not None:
            peticiones.append(peticion)
        r = pendientes.pop(0)
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)

    return httpx.Client(transport=httpx.MockTransport(manejar))


class FuenteDePrueba(Fuente):
    """Implementación mínima para probar los reintentos de la clase base."""

    def buscar(self, consulta, n=10, *, desde=None):
        return self._get_json("https://ejemplo.org/api", params={"q": consulta})


def fuente_de_prueba(*respuestas, peticiones=None, **kwargs):
    esperas = []
    fuente = FuenteDePrueba(
        client=cliente(*respuestas, peticiones=peticiones), sleep=esperas.append, **kwargs
    )
    return fuente, esperas


# --- Fuente: clase base -------------------------------------------------------


def test_fuente_es_abstracta():
    with pytest.raises(TypeError):
        Fuente()


def test_reintenta_429_respetando_retry_after():
    fuente, esperas = fuente_de_prueba(
        httpx.Response(429, headers={"Retry-After": "2"}), {"ok": True}
    )
    assert fuente.buscar("x") == {"ok": True}
    assert esperas == [2.0]


def test_reintenta_5xx_con_espera_exponencial():
    fuente, esperas = fuente_de_prueba(
        httpx.Response(503), httpx.Response(500), httpx.Response(502), {"ok": True}, backoff=0.5
    )
    assert fuente.buscar("x") == {"ok": True}
    assert esperas == [0.5, 1.0, 2.0]


def test_reintenta_errores_de_red():
    fuente, esperas = fuente_de_prueba(httpx.ConnectTimeout("lento"), {"ok": True})
    assert fuente.buscar("x") == {"ok": True}
    assert esperas == [1.0]


def test_agota_reintentos_y_lanza_error():
    fuente, esperas = fuente_de_prueba(*[httpx.Response(503)] * 3, max_retries=2)
    with pytest.raises(httpx.HTTPStatusError):
        fuente.buscar("x")
    assert len(esperas) == 2  # 3 intentos, 2 esperas


def test_agota_reintentos_de_red_y_lanza_error():
    fuente, _ = fuente_de_prueba(*[httpx.ConnectError("caído")] * 2, max_retries=1)
    with pytest.raises(httpx.ConnectError):
        fuente.buscar("x")


@pytest.mark.parametrize("estado", [400, 401, 403, 404])
def test_no_reintenta_errores_del_cliente(estado):
    fuente, esperas = fuente_de_prueba(httpx.Response(estado))
    with pytest.raises(httpx.HTTPStatusError):
        fuente.buscar("x")
    assert esperas == []


def test_no_espera_si_retry_after_supera_max_wait():
    # Caso típico: presupuesto diario agotado y el servidor pide esperar horas.
    fuente, esperas = fuente_de_prueba(httpx.Response(429, headers={"Retry-After": "3600"}))
    with pytest.raises(httpx.HTTPStatusError):
        fuente.buscar("x")
    assert esperas == []


def test_retry_after_como_fecha_pasada_no_espera():
    fuente, esperas = fuente_de_prueba(
        httpx.Response(503, headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}), {"ok": True}
    )
    assert fuente.buscar("x") == {"ok": True}
    assert esperas == [0.0]


def test_get_json_returns_parsed_dict_without_waiting():
    fuente, esperas = fuente_de_prueba({"ok": True})
    assert fuente.buscar("x") == {"ok": True}
    assert esperas == []


def test_get_json_propagates_invalid_json_without_retrying():
    fuente, esperas = fuente_de_prueba(httpx.Response(200, text="not-json"))
    with pytest.raises(json.JSONDecodeError):
        fuente.buscar("x")
    assert esperas == []


def test_get_json_forwards_params_and_headers():
    peticiones = []
    fuente, esperas = fuente_de_prueba({"ok": True}, peticiones=peticiones)
    fuente._get_json("https://ejemplo.org/api", params={"q": "x"}, headers={"X-Test": "1"})
    (peticion,) = peticiones
    assert peticion.url.params["q"] == "x"
    assert peticion.headers["x-test"] == "1"
    assert esperas == []


def test_get_returns_raw_response_and_forwards_params_and_headers():
    peticiones = []
    fuente, esperas = fuente_de_prueba({"ok": True}, peticiones=peticiones)
    respuesta = fuente._get("https://ejemplo.org/api", params={"q": "x"}, headers={"X-Test": "1"})
    assert isinstance(respuesta, httpx.Response)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}
    (peticion,) = peticiones
    assert peticion.url.params["q"] == "x"
    assert peticion.headers["x-test"] == "1"
    assert esperas == []


def test_get_retries_429_and_returns_raw_response():
    peticiones = []
    esperas = []
    fuente = FuenteDePrueba(
        client=cliente(httpx.Response(429), {"ok": True}, peticiones=peticiones),
        sleep=esperas.append,
    )
    respuesta = fuente._get("https://ejemplo.org/api")
    assert respuesta.json() == {"ok": True}
    assert len(peticiones) == 2
    assert esperas == [1.0]


def test_get_exhausts_retries_and_raises_status_error():
    fuente, esperas = fuente_de_prueba(*[httpx.Response(503)] * 3, max_retries=2)
    with pytest.raises(httpx.HTTPStatusError):
        fuente._get("https://ejemplo.org/api")
    assert len(esperas) == 2


def test_close_only_closes_owned_client():
    propia = FuenteDePrueba()  # no client injected: Fuente creates and owns it
    owned_client = propia.client
    propia.close()
    assert owned_client.is_closed

    borrowed_client = cliente({"ok": True})
    prestada = FuenteDePrueba(client=borrowed_client)
    prestada.close()
    assert not borrowed_client.is_closed
    borrowed_client.close()


# --- OpenAlex -----------------------------------------------------------------


def test_openalex_convierte_respuesta_guardada():
    articulos = OpenAlex(client=cliente(RESPUESTA_OPENALEX)).buscar("bibliometrics", n=2)

    assert [a.doi for a in articulos] == [
        "10.1515/libr.1996.46.3.149",
        "10.1016/j.jbusres.2016.11.009",
    ]
    primero = articulos[0]
    assert primero.title.startswith("Bibliometrics, Citation Analysis and Co-Citation Analysis")
    assert primero.authors == ("Farideh Osareh",)
    assert primero.year == 1996
    assert primero.journal == "Libri"
    assert primero.citations == 702
    assert primero.abstract == ""
    assert articulos[1].short_citation == "Gurzki y Woisetschläger (2016)"


def test_openalex_parametros_de_la_peticion():
    peticiones = []
    OpenAlex(client=cliente(RESPUESTA_OPENALEX, peticiones=peticiones)).buscar("deep learning", n=2)

    (peticion,) = peticiones
    assert peticion.url.host == "api.openalex.org"
    assert peticion.url.path == "/works"
    params = peticion.url.params
    assert params["search"] == "deep learning"
    assert params["per_page"] == "2"
    assert params["page"] == "1"
    assert "abstract_inverted_index" in params["select"]
    assert "authorization" not in peticion.headers


def test_openalex_distingue_cero_de_recuento_ausente():
    obra = {
        "authorships": [{"author": {"display_name": "A García"}}],
        "doi": "https://doi.org/10.1/obra",
        "title": "Obra",
        "publication_year": 2024,
    }

    assert openalex_a_articulo(obra).citations is None
    assert openalex_a_articulo({**obra, "cited_by_count": 0}).citations == 0


def test_europepmc_distingue_cero_de_recuento_ausente():
    obra = dict(RESPUESTA_EUROPEPMC["resultList"]["result"][0])
    obra.pop("citedByCount", None)

    assert europepmc_a_articulo(obra).citations is None


def test_openalex_envia_la_clave_en_cabecera_y_no_en_la_url():
    peticiones = []
    OpenAlex(api_key="secreta", client=cliente(RESPUESTA_OPENALEX, peticiones=peticiones)).buscar(
        "x", n=2
    )
    assert peticiones[0].headers["authorization"] == "Bearer secreta"
    assert "secreta" not in str(peticiones[0].url)


def test_openalex_pide_otra_pagina_si_descarta_obras():
    # Con n=3 la página trae 3 obras, pero una no tiene DOI: hay que pedir la página 2.
    peticiones = []
    articulos = OpenAlex(client=cliente(RESPUESTA_OPENALEX, VACIA, peticiones=peticiones)).buscar(
        "x", n=3
    )
    assert len(articulos) == 2
    assert [p.url.params["page"] for p in peticiones] == ["1", "2"]


def test_openalex_no_devuelve_mas_de_n():
    assert len(OpenAlex(client=cliente(RESPUESTA_OPENALEX)).buscar("x", n=1)) == 1


def test_openalex_n_invalido():
    with pytest.raises(ValueError):
        OpenAlex(client=cliente()).buscar("x", n=0)


def test_openalex_hereda_los_reintentos():
    esperas = []
    fuente = OpenAlex(client=cliente(httpx.Response(429), RESPUESTA_OPENALEX), sleep=esperas.append)
    assert len(fuente.buscar("x", n=2)) == 2
    assert esperas == [1.0]


def test_reconstruir_resumen():
    indice = {
        "in": [3, 5],
        "Despite": [0],
        "growing": [1],
        "interest": [2],
        "AI": [4],
        "ethics": [6],
    }
    assert reconstruir_resumen(indice) == "Despite growing interest in AI in ethics"
    assert reconstruir_resumen(None) == ""


# --- Crossref -----------------------------------------------------------------


def pagina_crossref(items, siguiente="siguiente"):
    return {"status": "ok", "message": {"items": items, "next-cursor": siguiente}}


def item_crossref(i, **cambios):
    item = {
        "DOI": f"10.9999/{i}",
        "title": [f"Obra {i}"],
        "author": [{"family": "García", "given": "Ana"}],
        "issued": {"date-parts": [[2020, 5]]},
        "container-title": ["Revista de Pruebas"],
    }
    item.update(cambios)
    return item


def test_crossref_convierte_respuesta_guardada():
    articulos = Crossref(client=cliente(RESPUESTA_CROSSREF)).buscar("bibliometrics", n=4)

    assert [a.doi for a in articulos] == [
        "10.1515/libr.1996.46.3.149",
        "10.1515/libr.1996.46.4.217",
        "10.1007/s11192-010-0159-y",
        "10.12775/tsb.2012.009",
    ]
    primero = articulos[0]
    assert (
        primero.title
        == "Bibliometrics, Citation Analysis and Co-Citation Analysis: A Review of Literature I"
    )
    assert primero.authors == ("OSAREH, FARIDEH",)  # mayúsculas tal como las envía la editorial
    assert primero.year == 1996
    assert primero.journal == "Libri"
    assert primero.citations == 269
    assert primero.abstract == ""
    assert articulos[2].authors == ("Vinkler, P.",)
    assert articulos[2].year == 2010  # issued = [[2010, 1, 23]]
    assert articulos[3].short_citation == "Żarczyńska (2012)"
    assert articulos[3].journal == "Toruńskie Studia Bibliologiczne"


def test_crossref_limpia_resumen_jats_y_descarta_obras_sin_autores():
    # La página viene llena (2 de 2) pero se descarta una obra: se pide la siguiente.
    peticiones = []
    respuestas = (RESPUESTA_CROSSREF_CON_RESUMEN, pagina_crossref([], siguiente=None))
    articulos = Crossref(client=cliente(*respuestas, peticiones=peticiones)).buscar("x", n=2)

    assert len(peticiones) == 2
    (articulo,) = articulos  # la segunda obra no tiene autores
    assert articulo.doi == "10.4000/cybergeo.15463"
    assert articulo.authors == ("Kosmopoulos, Christine", "Pumain, Denise")
    assert articulo.abstract.startswith("La numérisation des ressources documentaires")
    assert "<" not in articulo.abstract


def test_crossref_parametros_de_la_peticion():
    peticiones = []
    Crossref(client=cliente(RESPUESTA_CROSSREF, peticiones=peticiones)).buscar("deep learning", n=4)

    (peticion,) = peticiones
    assert peticion.url.host == "api.crossref.org"
    assert peticion.url.path == "/works"
    params = peticion.url.params
    assert params["query"] == "deep learning"
    assert params["filter"] == "type:journal-article"
    assert params["rows"] == "4"
    assert params["cursor"] == "*"
    # Sin orden explícito, con cursor los resultados dejan de ir por relevancia.
    assert (params["sort"], params["order"]) == ("relevance", "desc")
    assert "abstract" in params["select"].split(",")
    assert "mailto" not in params  # el correo solo se envía si se configura


def test_crossref_mailto_opcional():
    peticiones = []
    Crossref(
        mailto="yo@ejemplo.org", client=cliente(RESPUESTA_CROSSREF, peticiones=peticiones)
    ).buscar("x", n=4)
    assert peticiones[0].url.params["mailto"] == "yo@ejemplo.org"


def test_crossref_sigue_el_cursor_si_descarta_obras():
    # Página llena (rows=2) con una obra sin DOI: hay que pedir la siguiente con el cursor.
    peticiones = []
    respuestas = (
        pagina_crossref([item_crossref(1, DOI=None), item_crossref(2)], siguiente="c2"),
        pagina_crossref([item_crossref(3), item_crossref(4)], siguiente="c3"),
    )
    articulos = Crossref(client=cliente(*respuestas, peticiones=peticiones)).buscar("x", n=2)
    assert [a.doi for a in articulos] == ["10.9999/2", "10.9999/3"]
    assert [p.url.params["cursor"] for p in peticiones] == ["*", "c2"]


def test_crossref_para_con_pagina_incompleta():
    peticiones = []
    articulos = Crossref(
        client=cliente(pagina_crossref([item_crossref(1)]), peticiones=peticiones)
    ).buscar("x", n=5)
    assert len(articulos) == 1
    assert len(peticiones) == 1


def test_crossref_para_sin_siguiente_cursor():
    peticiones = []
    respuesta = pagina_crossref([item_crossref(1, DOI=None), item_crossref(2)], siguiente=None)
    articulos = Crossref(client=cliente(respuesta, peticiones=peticiones)).buscar("x", n=2)
    assert len(articulos) == 1
    assert len(peticiones) == 1


def test_crossref_no_devuelve_mas_de_n():
    assert len(Crossref(client=cliente(RESPUESTA_CROSSREF)).buscar("x", n=1)) == 1


def test_crossref_n_invalido():
    with pytest.raises(ValueError):
        Crossref(client=cliente()).buscar("x", n=0)


def test_crossref_hereda_los_reintentos():
    esperas = []
    fuente = Crossref(client=cliente(httpx.Response(429), RESPUESTA_CROSSREF), sleep=esperas.append)
    assert len(fuente.buscar("x", n=4)) == 4
    assert esperas == [1.0]


@pytest.mark.parametrize(
    "cambios",
    [
        {"DOI": None},
        {"title": None},
        {"title": []},
        {"title": ["  "]},
        {"author": []},
        {"author": [{"given": "Ana"}]},  # sin apellido ni nombre de organización
        {"issued": None},
        {"issued": {"date-parts": [[None]]}},
        {"DOI": "no-es-un-doi"},
    ],
)
def test_crossref_descarta_obras_incompletas(cambios):
    assert crossref_a_articulo(item_crossref(1, **cambios)) is None


@pytest.mark.parametrize(
    ("autor", "esperado"),
    [
        ({"family": "García Márquez", "given": "Gabriel"}, "García Márquez, Gabriel"),
        ({"family": "García"}, "García"),
        ({"name": "WHO Study Group"}, "WHO Study Group"),
    ],
)
def test_crossref_formatos_de_autor(autor, esperado):
    assert crossref_a_articulo(item_crossref(1, author=[autor])).authors == (esperado,)


def test_crossref_campos_opcionales_ausentes():
    item = item_crossref(1)
    del item["container-title"]
    articulo = crossref_a_articulo(item)
    assert articulo.journal == ""
    assert articulo.abstract == ""
    assert articulo.citations is None


def test_limpiar_jats():
    assert limpiar_jats("<jats:title>Abstract</jats:title><jats:p>Texto.</jats:p>") == "Texto."
    assert (
        limpiar_jats(
            "<jats:sec><jats:title>Methods</jats:title>"
            "<jats:p>Uso de <jats:italic>R</jats:italic> &amp; Python.</jats:p></jats:sec>"
        )
        == "Methods: Uso de R & Python."
    )
    assert limpiar_jats("<jats:p>Uno.</jats:p><jats:p>Dos.</jats:p>") == "Uno. Dos."
    assert limpiar_jats("") == ""


# --- EuropePMC ----------------------------------------------------------------


def test_europepmc_convierte_respuesta_guardada():
    articulos = EuropePMC(client=cliente(RESPUESTA_EUROPEPMC)).buscar("malaria", n=3)

    assert len(articulos) == 3
    # Comprobar que descarta la obra sin DOI y obtiene las 3 válidas
    assert [a.doi for a in articulos] == [
        "10.4269/ajtmh.26-0338",
        "10.64898/2026.09.28.26363670",
        "10.1038/s41590-026-02610-7",
    ]
    primero = articulos[0]
    assert primero.title.startswith("Status of Malaria Vaccine Introduction")
    assert primero.year == 2026
    assert primero.journal == "The American journal of tropical medicine and hygiene"
    assert primero.short_citation == "Ly et al. (2026)"

    # Preprint sin journal
    assert articulos[1].journal == ""
    assert articulos[1].short_citation == "Wood et al. (2026)"

    # Un solo autor
    assert articulos[2].authors == ("Bernard, Nicholas J",)
    assert articulos[2].short_citation == "Bernard (2026)"


def test_europepmc_parametros_de_la_peticion():
    peticiones = []
    EuropePMC(client=cliente(RESPUESTA_EUROPEPMC, peticiones=peticiones)).buscar("cancer", n=2)

    (peticion,) = peticiones
    assert peticion.url.host == "www.ebi.ac.uk"
    assert peticion.url.path == "/europepmc/webservices/rest/search"
    params = peticion.url.params
    assert params["query"] == "cancer"
    assert params["format"] == "json"
    assert params["resultType"] == "core"
    assert params["cursorMark"] == "*"


def test_europepmc_pide_otra_pagina_si_descarta_obras():
    # Página 1 tiene 2 obras pero una no tiene DOI (queda 1 válida).
    # Si pedimos n=2, pide la página 2 con cursorMark.
    pagina_1 = {
        "nextCursorMark": "cursor_2",
        "resultList": {
            "result": [
                {
                    "title": "Valid Article 1",
                    "doi": "10.1000/1",
                    "pubYear": "2023",
                    "authorList": {"author": [{"lastName": "Garcia", "firstName": "Ana"}]},
                },
                {
                    "title": "Invalid No DOI",
                    "pubYear": "2023",
                    "authorList": {"author": [{"lastName": "Perez", "firstName": "Juan"}]},
                },
            ]
        },
    }
    pagina_2 = {
        "nextCursorMark": "cursor_3",
        "resultList": {
            "result": [
                {
                    "title": "Valid Article 2",
                    "doi": "10.1000/2",
                    "pubYear": "2023",
                    "authorList": {"author": [{"lastName": "Lopez", "firstName": "Carlos"}]},
                }
            ]
        },
    }
    peticiones = []
    articulos = EuropePMC(client=cliente(pagina_1, pagina_2, peticiones=peticiones)).buscar(
        "x", n=2
    )
    assert len(articulos) == 2
    assert len(peticiones) == 2
    assert peticiones[0].url.params["cursorMark"] == "*"
    assert peticiones[1].url.params["cursorMark"] == "cursor_2"


def test_europepmc_no_devuelve_mas_de_n():
    assert len(EuropePMC(client=cliente(RESPUESTA_EUROPEPMC)).buscar("x", n=1)) == 1


def test_europepmc_n_invalido():
    with pytest.raises(ValueError):
        EuropePMC(client=cliente()).buscar("x", n=0)


def test_europepmc_hereda_los_reintentos():
    esperas = []
    fuente = EuropePMC(
        client=cliente(httpx.Response(429), RESPUESTA_EUROPEPMC), sleep=esperas.append
    )
    assert len(fuente.buscar("x", n=2)) == 2
    assert esperas == [1.0]
