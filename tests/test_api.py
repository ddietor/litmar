"""Tests de la API HTTP: sin red, sin claves y sin escribir archivos."""

import json
import shutil
import subprocess
from importlib.resources import files

import pytest
from fastapi.testclient import TestClient

from litmar import api
from litmar.biblioteca import Biblioteca
from litmar.busqueda import Resultado
from litmar.cli import main as cli_main
from litmar.llm import ErrorDeConfiguracion

cliente = TestClient(api.app)


def _estado(hacer_articulo, pregunta: str) -> dict:
    """Estado final con una cita válida, listo para `informe_markdown` y `citados`."""
    articulo = hacer_articulo()
    return {
        "question": pregunta,
        "queries": ["posidonia carbon"],
        "selected": [articulo],
        "report": f"La evidencia coincide [doi:{articulo.doi}].",
        "cited": [articulo.doi],
        "invalid": [],
        "warnings": [],
    }


def test_index_sirve_la_web_desde_el_paquete():
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    html = respuesta.text
    assert html == files("litmar").joinpath("web", "index.html").read_text(encoding="utf-8")
    # La página llama solo a las rutas del contrato, con rutas relativas.
    for fragmento in ('id="consulta"', 'id="pregunta"', '"/fuentes"', "/buscar?", '"/revisiones"'):
        assert fragmento in html
    assert "<script src=" not in html
    assert "<link rel=" not in html
    assert "fetch('http" not in html and 'fetch("http' not in html


def test_index_ofrece_descarga_bibtex_de_la_busqueda():
    """La web genera el .bib en el navegador, sin rutas nuevas."""
    html = files("litmar").joinpath("web", "index.html").read_text(encoding="utf-8")

    # El botón nace desactivado y solo se activa si la búsqueda devuelve artículos.
    assert '<button id="descargar-bib" type="button" disabled>Descargar BibTeX</button>' in html
    assert '$("descargar-bib").disabled = articulos.length === 0;' in html

    # Mismo formato que `Biblioteca.a_bibtex`: llaves dobles, DOI literal y claves únicas.
    for fragmento in (
        "const ESCAPES_BIBTEX = {",
        "`  title = {{${escaparBibtex(articulo.title)}}}`",
        "`  doi = {${articulo.doi}}`",
        "usadas.has(clave)",
        r'return entradas.length ? entradas.join("\n\n") + "\n" : "";',
        "application/x-bibtex",
        'enlace.download = "busqueda.bib";',
    ):
        assert fragmento in html
    assert 'enlace.download = "revision.bib"' in html  # el de la revisión sigue ahí
    assert "/exportar" not in html


def test_bibtex_de_la_web_coincide_con_biblioteca(tmp_path, hacer_articulo):
    """Con Node disponible, compara la función del HTML con la de Python."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node no está instalado; el test anterior comprueba la página")

    html = files("litmar").joinpath("web", "index.html").read_text(encoding="utf-8")
    inicio = html.index("    // escaping de LaTeX")
    fin = html.index("    function descargarBib(", inicio)
    javascript = html[inicio:fin]

    articulos = [
        hacer_articulo(
            title='Posidonia & "caballas"_2026%',
            authors=("García, Ana", "López, Juan"),
        ),
        hacer_articulo(doi="10.1000/abc456", authors=("García, Ana",)),  # clave repetida
        hacer_articulo(doi="10.1000/def789", authors=("Muñoz, Olga",), abstract=""),
    ]
    datos = [api.ArticuloSalida.desde(a).model_dump() for a in articulos]
    fichero_datos = tmp_path / "articulos.json"
    fichero_datos.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    script = (
        javascript
        + '\nconst datos = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));'
        + "\nprocess.stdout.write(bibtexDeArticulos(datos));\n"
    )
    fichero_js = tmp_path / "bibtex.js"
    fichero_js.write_text(script, encoding="utf-8")
    resultado = subprocess.run(
        [node, str(fichero_js), str(fichero_datos)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout == Biblioteca(articulos).a_bibtex()


def test_salud_no_toca_nada():
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_fuentes_marca_las_no_configuradas(monkeypatch):
    monkeypatch.setattr(api, "fuentes_disponibles", lambda: ["OpenAlex"])
    respuesta = cliente.get("/fuentes")
    assert respuesta.status_code == 200
    fuentes = {f["id"]: f for f in respuesta.json()["fuentes"]}
    assert fuentes["openalex"]["nombre"] == "OpenAlex"
    assert fuentes["openalex"]["disponible"] is True
    assert "catálogo" in fuentes["openalex"]["descripcion"]
    assert fuentes["zotero"]["nombre"] == "Zotero"
    assert fuentes["zotero"]["disponible"] is False


def test_buscar_reutiliza_buscar_en_fuentes(hacer_articulo, monkeypatch):
    visto = {}

    def falso(consulta, nombres, n, *, desde=None, crear=None):
        visto.update(consulta=consulta, nombres=list(nombres), n=n, desde=desde)
        return Resultado(library=Biblioteca([hacer_articulo()]))

    monkeypatch.setattr(api, "buscar_en_fuentes", falso)
    respuesta = cliente.get(
        "/buscar",
        params=[
            ("consulta", "posidonia"),
            ("fuente", "openalex"),
            ("fuente", "Europe PMC"),
            ("n", "2"),
            ("desde", "2020"),
        ],
    )
    assert respuesta.status_code == 200
    assert visto == {
        "consulta": "posidonia",
        "nombres": ["OpenAlex", "Europe PMC"],
        "n": 2,
        "desde": 2020,
    }
    datos = respuesta.json()
    assert datos["errores"] == []
    assert datos["fuentes_fallidas"] == []
    assert datos["articulos"][0]["doi"] == "10.1000/xyz123"
    assert datos["articulos"][0]["citations"] == 42


@pytest.mark.parametrize(
    "params",
    [
        {"consulta": "posidonia", "n": 0},
        {"consulta": "posidonia", "n": 51},
        {"consulta": "   "},
        {"consulta": "posidonia", "fuente": "scopus"},
        {"consulta": "posidonia", "desde": 1800},
    ],
)
def test_buscar_valida_la_entrada(params):
    assert cliente.get("/buscar", params=params).status_code == 422


def test_buscar_502_si_fallan_todas_las_fuentes(monkeypatch):
    mensaje = "OpenAlex: no se pudo conectar tras los reintentos."

    def falso(consulta, nombres, n, *, desde=None, crear=None):
        assert list(nombres) == ["OpenAlex"]
        return Resultado(errors=[mensaje], failed=["OpenAlex"])

    monkeypatch.setattr(api, "buscar_en_fuentes", falso)
    respuesta = cliente.get("/buscar", params={"consulta": "posidonia"})
    assert respuesta.status_code == 502
    assert respuesta.json()["detail"] == {
        "mensaje": "Ninguna fuente respondió.",
        "errores": [mensaje],
    }


def test_revisiones_flujo_devuelve_texto_y_no_guarda(tmp_path, monkeypatch, hacer_articulo):
    monkeypatch.chdir(tmp_path)
    pregunta = "¿Qué papel tiene la posidonia?"
    estado = _estado(hacer_articulo, pregunta)
    visto = {}

    def falso(modelo, texto, **opciones):
        visto.update(texto=texto, **opciones)
        return estado

    monkeypatch.setattr(api, "crear_modelo", lambda: object())
    monkeypatch.setattr(api.flujo, "revisar", falso)

    respuesta = cliente.post(
        "/revisiones",
        json={
            "pregunta": f"  {pregunta}  ",
            "modo": "flujo",
            "fuente": ["openalex"],
            "n": 3,
            "desde": 2019,
        },
    )
    assert respuesta.status_code == 200
    assert visto == {
        "texto": pregunta,
        "fuentes": ["OpenAlex"],
        "n": 3,
        "desde": 2019,
    }
    datos = respuesta.json()
    assert datos["pregunta"] == pregunta
    assert datos["modo"] == "flujo"
    assert f"# {pregunta}" in datos["informe"]
    assert "10.1000/xyz123" in datos["bibtex"]
    assert datos["citados"] == ["10.1000/xyz123"]
    assert datos["avisos"] == []
    assert list(tmp_path.iterdir()) == []


def test_revisiones_agente_llama_a_agente_revisar(monkeypatch, hacer_articulo):
    pregunta = "¿Qué papel tiene la posidonia?"
    visto = {}

    def falso(consulta, texto, **opciones):
        visto.update(texto=texto, **opciones)
        return _estado(hacer_articulo, pregunta)

    monkeypatch.setattr(api, "crear_modelo", lambda: object())
    monkeypatch.setattr(api.agente, "revisar", falso)
    monkeypatch.setattr(
        api.flujo,
        "revisar",
        lambda *a, **k: pytest.fail("el modo agente no debe usar el flujo"),
    )

    respuesta = cliente.post("/revisiones", json={"pregunta": pregunta, "modo": "agente"})
    assert respuesta.status_code == 200
    assert visto == {
        "texto": pregunta,
        "fuentes": ["OpenAlex", "Europe PMC"],
        "n": 6,
        "desde": None,
    }
    assert respuesta.json()["modo"] == "agente"


def test_revisiones_503_si_falta_el_modelo(monkeypatch):
    mensaje = "Falta el modelo. Añade al .env una línea LITMAR_MODELO=proveedor:modelo."

    def falso():
        raise ErrorDeConfiguracion(mensaje)

    monkeypatch.setattr(api, "crear_modelo", falso)
    respuesta = cliente.post("/revisiones", json={"pregunta": "¿Posidonia?"})
    assert respuesta.status_code == 503
    assert respuesta.json()["detail"] == {"mensaje": mensaje}


def test_revisiones_502_sin_filtrar_el_error_del_proveedor(monkeypatch):
    monkeypatch.setattr(api, "crear_modelo", lambda: object())

    def falso(*args, **kwargs):
        raise RuntimeError("petición con clave super-secreta")

    monkeypatch.setattr(api.flujo, "revisar", falso)
    respuesta = cliente.post("/revisiones", json={"pregunta": "¿Posidonia?"})
    assert respuesta.status_code == 502
    assert "super-secreta" not in respuesta.text
    assert "RuntimeError" in respuesta.text


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"pregunta": ""},
        {"pregunta": "   "},
        {"pregunta": "x", "modo": "otro"},
        {"pregunta": "x", "n": 0},
        {"pregunta": "x", "n": 11},
        {"pregunta": "x", "fuente": []},
    ],
)
def test_revisiones_valida_la_entrada(cuerpo):
    assert cliente.post("/revisiones", json=cuerpo).status_code == 422


def test_servir_pasa_las_opciones_a_uvicorn(monkeypatch):
    visto = {}

    def falso(app, *, host, port, reload):
        visto.update(app=app, host=host, port=port, reload=reload)

    monkeypatch.setattr("uvicorn.run", falso)
    assert cli_main(["servir", "--host", "0.0.0.0", "--puerto", "8765", "--recargar"]) == 0
    assert visto == {"app": "litmar.api:app", "host": "0.0.0.0", "port": 8765, "reload": True}
