"""Tests de las herramientas para el modelo: fuentes falsas, sin red."""

import httpx
import pytest

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
            raise self.error
        return self.articulos[:n]


@pytest.fixture
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
