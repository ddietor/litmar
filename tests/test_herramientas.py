"""Tests de las herramientas del agente: sin red, sin clave y con límites en código."""

from __future__ import annotations

import httpx
import pytest

from litmar.fuentes import Fuente
from litmar.herramientas import MAX_RESULTADOS, crear_herramientas


class FuenteFija(Fuente):
    """Fuente falsa que devuelve artículos o falla, y recuerda lo que le pidieron."""

    def __init__(self, articulos=(), error=None):
        super().__init__()
        self.articulos = list(articulos)
        self.error = error
        self.llamadas = []

    def buscar(self, consulta, n=10, *, desde=None):
        self.llamadas.append((consulta, n, desde))
        if self.error is not None:
            raise self.error
        return self.articulos[:n]


@pytest.fixture
def fabrica(hacer_articulo):
    """Dos fuentes: OpenAlex con dos artículos y Europe PMC con uno repetido."""
    comun = hacer_articulo(doi="10.1000/comun", title="Un título común")
    otro = hacer_articulo(doi="10.1000/otro", title="Otro título")
    fuentes = {
        "OpenAlex": FuenteFija([comun, otro]),
        "Europe PMC": FuenteFija([comun]),
    }
    return fuentes, lambda nombre: fuentes[nombre]


def test_listar_fuentes_devuelve_ids_y_aviso_de_pangaea(fabrica):
    _, crear = fabrica
    _, listar, _ = crear_herramientas(crear=crear, fuentes=["OpenAlex", "Europe PMC", "PANGAEA"])

    texto = listar.invoke({})

    assert "- openalex (OpenAlex)" in texto
    assert "- europepmc (Europe PMC)" in texto
    assert "PANGAEA devuelve conjuntos de datos" in texto


def test_buscar_articulos_acepta_id_y_nombre_y_pasa_desde(fabrica, hacer_articulo):
    fuentes, crear = fabrica
    buscar, _, registro = crear_herramientas(
        crear=crear, fuentes=["OpenAlex", "Europe PMC"], desde=2020
    )

    texto = buscar.invoke({"consulta": "posidonia", "fuente": "europepmc", "n": 2})

    assert "Europe PMC: 1 artículo" in texto
    assert "DOI: [10.1000/comun]" in texto
    assert fuentes["Europe PMC"].llamadas == [("posidonia", 2, 2020)]
    assert registro.articulos["10.1000/comun"].title == "Un título común"
    assert registro.llamadas[0]["doi"] == ["10.1000/comun"]

    buscar.invoke({"consulta": "otra", "fuente": "OpenAlex", "n": 1})
    assert fuentes["OpenAlex"].llamadas[-1] == ("otra", 1, 2020)


def test_el_limite_de_diez_esta_en_el_codigo(hacer_articulo):
    articulos = [hacer_articulo(doi=f"10.1000/n{i}") for i in range(25)]
    fuente = FuenteFija(articulos)
    buscar, _, registro = crear_herramientas(
        crear=lambda nombre: fuente, fuentes=["OpenAlex"], n=99
    )

    texto = buscar.invoke({"consulta": "x", "fuente": "OpenAlex", "n": 99})

    assert f"{MAX_RESULTADOS} artículos" in texto
    assert "el máximo es 10" in texto
    assert fuente.llamadas[0][1] == MAX_RESULTADOS
    assert len(registro.articulos) == MAX_RESULTADOS


@pytest.mark.parametrize(
    "fuente, mensaje",
    [
        ("scopus", "fuente desconocida"),
        ("zotero", "no está entre las fuentes permitidas"),
    ],
)
def test_fuentes_invalidas_son_texto_y_no_llaman_a_nadie(fabrica, fuente, mensaje):
    fuentes, crear = fabrica
    buscar, _, registro = crear_herramientas(crear=crear, fuentes=["OpenAlex", "Europe PMC"])

    texto = buscar.invoke({"consulta": "x", "fuente": fuente, "n": 2})

    assert mensaje in texto
    assert all(fuente.llamadas == [] for fuente in fuentes.values())
    assert "error" in registro.llamadas[0]


def test_un_fallo_de_red_es_texto_y_no_muestra_claves(hacer_articulo):
    error = httpx.HTTPStatusError(
        "fallo",
        request=httpx.Request("GET", "https://api.ejemplo/?api_key=SECRETO"),
        response=httpx.Response(503),
    )
    buscar, _, registro = crear_herramientas(
        crear=lambda nombre: FuenteFija(error=error), fuentes=["OpenAlex"]
    )

    texto = buscar.invoke({"consulta": "x", "fuente": "openalex", "n": 2})

    assert "OpenAlex no ha podido buscar (HTTP 503)" in texto
    assert "Prueba otra fuente" in texto
    assert "SECRETO" not in texto
    assert registro.avisos and registro.llamadas[0]["error"] == "HTTP 503"


def test_consulta_vacia_y_sin_resultados(fabrica):
    fuentes, crear = fabrica
    buscar, _, registro = crear_herramientas(crear=crear, fuentes=["OpenAlex"])
    fuentes["OpenAlex"].articulos = []

    assert "consulta está vacía" in buscar.invoke({"consulta": "  ", "fuente": "openalex", "n": 2})
    assert "sin resultados" in buscar.invoke({"consulta": "x", "fuente": "openalex", "n": 2})
    assert len(registro.llamadas) == 2
    assert registro.articulos == {}


def test_resumen_largo_se_recorta_y_no_se_repite_el_doi(fabrica, hacer_articulo):
    fuentes, crear = fabrica
    comun = hacer_articulo(doi="10.1000/comun", abstract="palabra " * 200)
    otro = hacer_articulo(doi="10.1000/otro")
    fuentes["OpenAlex"].articulos = [comun, comun, otro]
    buscar, _, registro = crear_herramientas(crear=crear, fuentes=["OpenAlex"])

    texto = buscar.invoke({"consulta": "x", "fuente": "openalex", "n": 3})

    assert "…" in texto
    assert texto.count("10.1000/comun") == 1
    assert len(registro.articulos) == 2
