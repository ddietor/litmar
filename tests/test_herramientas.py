<<<<<<< HEAD
"""Tests de las herramientas del agente: sin red, sin clave y con límites en código."""

from __future__ import annotations
=======
"""Tests de las herramientas para el modelo: fuentes falsas, sin red."""
>>>>>>> upstream/main

import httpx
import pytest

<<<<<<< HEAD
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
=======
from litmar import herramientas
from litmar.herramientas import (
    AVISO_PANGAEA,
    LARGO_RESUMEN,
    MAX_RESULTADOS,
    buscar_articulos,
    listar_fuentes,
)


class FuenteFalsa:
    """Devuelve los artículos dados (o lanza `error`) y apunta las búsquedas."""

    def __init__(self, articulos=(), error=None):
        self.articulos = list(articulos)
        self.error = error
        self.busquedas = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def buscar(self, consulta, n, *, desde=None):
        self.busquedas.append((consulta, n))
        if self.error:
>>>>>>> upstream/main
            raise self.error
        return self.articulos[:n]


@pytest.fixture
<<<<<<< HEAD
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
=======
def usar_fuente(monkeypatch):
    """Sustituye crear_fuente por una que devuelve `fuente` y apunta qué nombre se pidió."""
    pedidas = []

    def configurar(fuente):
        def crear(nombre):
            pedidas.append(nombre)
            return fuente

        monkeypatch.setattr(herramientas, "crear_fuente", crear)
        return pedidas

    return configurar


@pytest.fixture(autouse=True)
def sin_zotero(monkeypatch):
    for variable in ("ZOTERO_USER_ID", "ZOTERO_GROUP_ID"):
        monkeypatch.delenv(variable, raising=False)


def buscar(**argumentos):
    """Invoca la herramienta como lo haría el modelo: con un diccionario de argumentos."""
    return buscar_articulos.invoke(argumentos)


# --- Resultados


def test_devuelve_titulo_anio_doi_citas_y_resumen(usar_fuente, hacer_articulo):
    articulo = hacer_articulo(title="Posidonia y carbono", year=2021, doi="10.1/p", citations=7)
    usar_fuente(FuenteFalsa([articulo]))

    texto = buscar(consulta="posidonia carbon", fuente="OpenAlex", n=3)

    assert texto.startswith("1 resultado de OpenAlex para «posidonia carbon»:")
    assert "1. Posidonia y carbono (2021)" in texto
    assert "DOI: 10.1/p | Citas: 7" in texto
    assert f"Resumen: {articulo.abstract}" in texto


def test_el_resumen_se_recorta_sin_partir_palabras(usar_fuente, hacer_articulo):
    usar_fuente(FuenteFalsa([hacer_articulo(abstract="palabra " * 200)]))

    resumen = buscar(consulta="x").split("Resumen: ", 1)[1]

    assert len(resumen) <= LARGO_RESUMEN + 1
    assert resumen.endswith("palabra…")


def test_articulo_sin_resumen(usar_fuente, hacer_articulo):
    usar_fuente(FuenteFalsa([hacer_articulo(abstract="")]))

    assert "Resumen: (sin resumen)" in buscar(consulta="x")


def test_resultado_indica_cuando_no_hay_recuento_de_citas(usar_fuente, hacer_articulo):
    usar_fuente(FuenteFalsa([hacer_articulo(citations=None)]))

    texto = buscar(consulta="redes", fuente="OpenAlex", n=1)

    assert "Citas: no disponible" in texto
    assert "solo en relevancia" in texto


def test_sin_resultados_sugiere_otra_busqueda(usar_fuente):
    usar_fuente(FuenteFalsa([]))

    texto = buscar(consulta="nada", fuente="Crossref")

    assert texto.startswith("Sin resultados en Crossref para «nada»")
    assert "otra fuente" in texto


def test_pangaea_avisa_de_que_son_datos(usar_fuente, hacer_articulo):
    usar_fuente(FuenteFalsa([hacer_articulo(journal="PANGAEA")]))

    assert buscar(consulta="ocean ph", fuente="PANGAEA").startswith(AVISO_PANGAEA)


def test_otras_fuentes_no_llevan_el_aviso(usar_fuente, hacer_articulo):
    usar_fuente(FuenteFalsa([hacer_articulo()]))

    assert AVISO_PANGAEA not in buscar(consulta="x", fuente="OpenAlex")


# --- Límites en el código


@pytest.mark.parametrize(("pedidos", "usados"), [(50, MAX_RESULTADOS), (0, 1), (-3, 1), (4, 4)])
def test_n_se_limita_en_el_codigo(usar_fuente, pedidos, usados):
    fuente = FuenteFalsa([])
    usar_fuente(fuente)

    buscar(consulta="x", n=pedidos)

    assert fuente.busquedas == [("x", usados)]


# --- Errores: texto para el modelo, nunca excepciones


@pytest.mark.parametrize(
    ("error", "esperado"),
    [
        (
            httpx.HTTPStatusError(
                "503",
                request=httpx.Request("GET", "https://api.example.org/?mailto=yo@example.org"),
                response=httpx.Response(503),
            ),
            "Error: OpenAlex respondió con HTTP 503.",
        ),
        (httpx.ConnectError("sin red"), "Error: OpenAlex: no se pudo conectar"),
        (KeyError("results"), "Error: OpenAlex: error inesperado (KeyError)."),
    ],
)
def test_si_la_fuente_falla_devuelve_un_mensaje(usar_fuente, error, esperado):
    usar_fuente(FuenteFalsa(error=error))

    texto = buscar(consulta="x")

    assert texto.startswith(esperado)
    assert "otra fuente" in texto
    assert "example.org" not in texto  # nunca la petición: puede llevar claves o correos


def test_fuente_desconocida(usar_fuente):
    pedidas = usar_fuente(FuenteFalsa([]))

    texto = buscar(consulta="x", fuente="Google Scholar")

    assert texto.startswith("Error: la fuente 'Google Scholar' no está disponible.")
    assert "OpenAlex" in texto and "Europe PMC" in texto
    assert pedidas == []


def test_zotero_sin_configurar_no_esta_disponible(usar_fuente):
    pedidas = usar_fuente(FuenteFalsa([]))

    assert buscar(consulta="x", fuente="Zotero").startswith("Error: la fuente 'Zotero'")
    assert pedidas == []


@pytest.mark.parametrize("escrita", ["europepmc", "europe pmc", "Europe PMC"])
def test_admite_el_nombre_o_el_identificador(usar_fuente, escrita):
    pedidas = usar_fuente(FuenteFalsa([]))

    buscar(consulta="x", fuente=escrita)

    assert pedidas == ["Europe PMC"]


def test_consulta_vacia(usar_fuente):
    pedidas = usar_fuente(FuenteFalsa([]))

    assert buscar(consulta="   ").startswith("Error: la consulta está vacía")
    assert pedidas == []


# --- listar_fuentes


def test_listar_fuentes_sin_zotero():
    texto = listar_fuentes.invoke({})

    assert "- OpenAlex:" in texto
    assert "- PANGAEA: conjuntos de datos" in texto
    assert "Zotero" not in texto


def test_listar_fuentes_con_zotero(monkeypatch):
    monkeypatch.setenv("ZOTERO_USER_ID", "123")

    assert "- Zotero:" in listar_fuentes.invoke({})


# --- Lo que lee el modelo


def test_las_descripciones_dicen_cuando_usarlas_y_que_devuelven():
    descripcion = buscar_articulos.description

    assert "Úsala para" in descripcion
    assert "título, año, DOI, número de citas" in descripcion
    assert "PANGAEA devuelve conjuntos de datos, no artículos" in descripcion
    assert "Úsala antes de buscar" in listar_fuentes.description


def test_cada_argumento_tiene_descripcion():
    for nombre, esquema in buscar_articulos.args.items():
        assert esquema.get("description"), f"el argumento {nombre} no tiene descripción"
>>>>>>> upstream/main
