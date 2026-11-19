"""Tests de Zotero. Ninguno usa la red: httpx.MockTransport responde en su lugar."""

import json
from pathlib import Path

import httpx
import pytest

from litmar.fuentes import Zotero

# Escrita a mano siguiendo el formato documentado de la API v3 (no es una descarga real).
# Contiene un artículo, una ponencia con un solo campo de nombre, un libro sin DOI y una nota.
ITEMS = json.loads(
    (Path(__file__).parent / "datos" / "zotero_items.json").read_text(encoding="utf-8")
)


def cliente(*respuestas, peticiones=None):
    """Cliente httpx que devuelve las respuestas en orden y anota cada petición."""
    pendientes = list(respuestas)

    def manejar(peticion: httpx.Request) -> httpx.Response:
        if peticiones is not None:
            peticiones.append(peticion)
        r = pendientes.pop(0)
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)

    return httpx.Client(transport=httpx.MockTransport(manejar))


def test_zotero_convierte_respuesta_guardada():
    articulos = Zotero(user_id=123456, client=cliente(ITEMS)).buscar("mar", n=10)

    assert [a.doi for a in articulos] == ["10.1000/xyz123", "10.2000/mar.2019.7"]
    primero, segundo = articulos
    assert primero.title == "Aprendizaje profundo para la clasificación de textos"
    assert primero.authors == ("García, Ana", "López, Juan")  # el editor no cuenta como autor
    assert primero.year == 2021
    assert primero.journal == "Revista de Informática"
    assert primero.abstract == "Un estudio sobre redes neuronales."
    assert primero.citations is None
    assert primero.short_citation == "García y López (2021)"
    assert segundo.authors == ("Consorcio Mar",)
    assert segundo.year == 2019  # sale de la fecha en texto libre
    assert segundo.journal == ""  # una ponencia no tiene publicationTitle


def test_zotero_parametros_de_la_peticion():
    peticiones = []
    Zotero(user_id=123456, client=cliente(ITEMS, peticiones=peticiones)).buscar(
        "deep learning", n=10
    )

    (peticion,) = peticiones
    assert peticion.url.host == "api.zotero.org"
    assert peticion.url.path == "/users/123456/items"
    params = peticion.url.params
    assert params["q"] == "deep learning"
    assert params["itemType"] == "-attachment"
    assert params["limit"] == "10"
    assert params["start"] == "0"
    assert peticion.headers["zotero-api-version"] == "3"
    assert "zotero-api-key" not in peticion.headers


def test_zotero_biblioteca_de_grupo():
    peticiones = []
    Zotero(group_id=987, client=cliente(ITEMS, peticiones=peticiones)).buscar("x", n=2)
    assert peticiones[0].url.path == "/groups/987/items"


def test_zotero_envia_la_clave_en_cabecera_y_no_en_la_url():
    peticiones = []
    fuente = Zotero(user_id=1, api_key="secreta", client=cliente(ITEMS, peticiones=peticiones))
    fuente.buscar("x", n=2)
    assert peticiones[0].headers["zotero-api-key"] == "secreta"
    assert "secreta" not in str(peticiones[0].url)


def test_zotero_pide_otra_pagina_si_descarta_items():
    # Con n=4 la página trae 4 items pero solo 2 valen: hay que pedir la siguiente (start=4).
    peticiones = []
    articulos = Zotero(user_id=1, client=cliente(ITEMS, [], peticiones=peticiones)).buscar("x", n=4)
    assert len(articulos) == 2
    assert [p.url.params["start"] for p in peticiones] == ["0", "4"]


def test_zotero_no_devuelve_mas_de_n():
    assert len(Zotero(user_id=1, client=cliente(ITEMS)).buscar("x", n=1)) == 1


def test_zotero_n_invalido():
    with pytest.raises(ValueError):
        Zotero(user_id=1, client=cliente()).buscar("x", n=0)


@pytest.mark.parametrize("ids", [{}, {"user_id": 1, "group_id": 2}])
def test_zotero_exige_exactamente_un_identificador(ids):
    with pytest.raises(ValueError):
        Zotero(**ids)


def test_zotero_hereda_los_reintentos():
    esperas = []
    fuente = Zotero(
        user_id=1,
        client=cliente(httpx.Response(429, headers={"Retry-After": "2"}), ITEMS),
        sleep=esperas.append,
    )
    assert len(fuente.buscar("x", n=10)) == 2
    assert esperas == [2.0]
