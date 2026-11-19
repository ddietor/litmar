"""Tests de Pangaea. Ninguno usa la red: httpx.MockTransport responde en su lugar."""

import copy
import json
from pathlib import Path

import httpx
import pytest
from test_fuentes import cliente

from litmar.fuentes import Pangaea
from litmar.fuentes.pangaea import a_articulo

# Respuesta real de
# GET /es/pangaea/panmd/_search
#     ?source={simple_query_string "ocean acidification", size 3, _source xml}
# guardada el 2026-11-17.
RESPUESTA_PANGAEA = json.loads(
    (Path(__file__).parent / "datos" / "pangaea_search.json").read_text(encoding="utf-8")
)
VACIA = {"hits": {"total": 0, "hits": []}}


def con_xml(xml):
    """Un resultado de Elasticsearch con el XML dado."""
    return {"_source": {"xml": xml}}


def metadatos(
    autores=(
        "<md:author><md:lastName>Barner</md:lastName><md:firstName>A K</md:firstName></md:author>"
    ),
    uri="<md:URI>https://doi.org/10.1594/PANGAEA.1</md:URI>",
    anio="<md:year>2018</md:year>",
):
    return (
        '<md:MetaData xmlns:md="http://www.pangaea.de/MetaData"><md:citation>'
        f"{autores}{anio}<md:title>Un dataset</md:title>{uri}"
        "</md:citation></md:MetaData>"
    )


def test_pangaea_convierte_respuesta_guardada():
    articulos = Pangaea(client=cliente(RESPUESTA_PANGAEA)).buscar("ocean acidification", n=3)

    assert [a.doi for a in articulos] == [
        "10.1594/pangaea.892595",
        "10.1594/pangaea.842399",
        "10.1594/pangaea.778466",
    ]
    primero = articulos[0]
    assert primero.title.startswith("Data from: Generality in multispecies responses")
    assert primero.authors[:2] == ("Barner, A K", "Chan, F")
    assert len(primero.authors) == 6  # no se cuelan los autores repetidos en <supplementTo>
    assert primero.year == 2018
    assert primero.journal == "PANGAEA"
    assert primero.abstract.startswith("Decades of research have demonstrated")
    assert primero.citations is None
    assert primero.short_citation == "Barner et al. (2018)"


def test_pangaea_parametros_de_la_peticion():
    peticiones = []
    Pangaea(client=cliente(RESPUESTA_PANGAEA, peticiones=peticiones)).buscar("sea ice/arctic", n=3)

    (peticion,) = peticiones
    assert peticion.url.host == "ws.pangaea.de"
    assert peticion.url.path == "/es/pangaea/panmd/_search"
    assert peticion.url.params["source_content_type"] == "application/json"
    cuerpo = json.loads(peticion.url.params["source"])
    assert cuerpo["query"] == {
        "simple_query_string": {"query": "sea ice/arctic", "default_operator": "and"}
    }
    assert cuerpo["from"] == 0
    assert cuerpo["size"] == 3
    assert cuerpo["_source"] == ["xml"]


def test_pangaea_pide_otra_pagina_si_descarta_resultados():
    # Con n=3 la página trae 3 resultados, pero uno no tiene XML: hay que pedir la siguiente.
    pagina = copy.deepcopy(RESPUESTA_PANGAEA)
    pagina["hits"]["hits"][1] = {"_source": {}}
    peticiones = []
    articulos = Pangaea(client=cliente(pagina, VACIA, peticiones=peticiones)).buscar("x", n=3)
    assert len(articulos) == 2
    assert [json.loads(p.url.params["source"])["from"] for p in peticiones] == [0, 3]


def test_pangaea_no_pasa_del_limite_de_paginacion():
    fuente = Pangaea(client=cliente(RESPUESTA_PANGAEA, RESPUESTA_PANGAEA))
    fuente.MAX_PER_PAGE, fuente.PAGING_LIMIT = 3, 6
    # Pide 10 pero solo puede leer los 6 primeros resultados (2 páginas);
    # una tercera petición fallaría.
    assert len(fuente.buscar("x", n=10)) == 6


def test_pangaea_no_devuelve_mas_de_n():
    assert len(Pangaea(client=cliente(RESPUESTA_PANGAEA)).buscar("x", n=1)) == 1


def test_pangaea_n_invalido():
    with pytest.raises(ValueError):
        Pangaea(client=cliente()).buscar("x", n=0)


def test_pangaea_hereda_los_reintentos():
    esperas = []
    fuente = Pangaea(client=cliente(httpx.Response(503), RESPUESTA_PANGAEA), sleep=esperas.append)
    assert len(fuente.buscar("x", n=3)) == 3
    assert esperas == [1.0]


def test_autor_institucional_sin_nombre():
    autores = (
        "<md:author><md:lastName>"
        "Ocean Acidification International Coordination Centre (OA-ICC)"
        "</md:lastName></md:author>"
    )
    articulo = a_articulo(con_xml(metadatos(autores=autores)))
    assert articulo.authors == ("Ocean Acidification International Coordination Centre (OA-ICC)",)
    assert articulo.abstract == ""


@pytest.mark.parametrize(
    "resultado",
    [
        {},
        con_xml("<esto no es xml"),
        con_xml('<md:MetaData xmlns:md="http://www.pangaea.de/MetaData"/>'),
        con_xml(metadatos(uri="")),
        con_xml(metadatos(autores="")),
        con_xml(metadatos(anio="<md:year>s.f.</md:year>")),
    ],
    ids=["sin-xml", "xml-roto", "sin-citation", "sin-doi", "sin-autores", "anio-no-numerico"],
)
def test_descarta_resultados_incompletos(resultado):
    assert a_articulo(resultado) is None
