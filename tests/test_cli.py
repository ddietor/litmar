import json
from pathlib import Path

import httpx
import pytest
from langchain_core.messages import AIMessage

from litmar import Biblioteca
from litmar.agente import LIMITE_PASOS
from litmar.cli import main, tabla
from litmar.flujo import LIMITE_RECURSION
from litmar.fuentes import Fuente, OpenAlex
from litmar.herramientas import RegistroBusquedas


@pytest.fixture
def openalex_simulado(monkeypatch):
    peticiones = []
    respuesta = json.loads(
        (Path(__file__).parent / "datos" / "openalex_works.json").read_text(encoding="utf-8")
    )

    def manejar(peticion):
        peticiones.append(peticion)
        return httpx.Response(200, json=respuesta)

    clientes = []

    def crear(**kwargs):
        fuente = OpenAlex(**kwargs)
        fuente.client.close()
        fuente.client = httpx.Client(transport=httpx.MockTransport(manejar))
        clientes.append(fuente.client)
        return fuente

    monkeypatch.setattr("litmar.configuracion.OpenAlex", crear)
    return peticiones, clientes


def test_buscar_guardar_combinar_y_exportar(tmp_path, hacer_articulo, openalex_simulado, capsys):
    ruta = tmp_path / "biblioteca.json"
    salida = tmp_path / "referencias.bib"
    original = hacer_articulo()
    Biblioteca([original]).guardar(ruta)

    for _ in range(2):
        assert main(["buscar", "bibliometrics", "-n", "2", "--guardar", str(ruta)]) == 0
    biblioteca = Biblioteca.cargar(ruta)
    assert len(biblioteca) == 3
    assert biblioteca.obtener(original.doi) == original
    assert main(["exportar", str(ruta), "--bibtex", str(salida)]) == 0
    assert salida.read_text(encoding="utf-8") == biblioteca.a_bibtex()
    assert "0 nuevos; 3 artículos" in capsys.readouterr().out
    peticiones, clientes = openalex_simulado
    assert len(peticiones) == 2
    assert all(cliente.is_closed for cliente in clientes)


def test_buscar_crea_biblioteca_y_lee_clave_del_entorno(tmp_path, openalex_simulado, monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "clave-de-prueba")
    ruta = tmp_path / "nueva.json"
    assert main(["buscar", "bibliometrics", "-n", "2", "--guardar", str(ruta)]) == 0
    assert len(Biblioteca.cargar(ruta)) == 2
    assert openalex_simulado[0][0].headers["authorization"] == "Bearer clave-de-prueba"


def test_buscar_sin_guardar_muestra_resultados(openalex_simulado, capsys):
    assert main(["buscar", "bibliometrics", "-n", "2"]) == 0
    salida = capsys.readouterr().out
    assert "2 resultados" in salida
    cabecera, primera = salida.splitlines()[:2]
    assert cabecera.split() == ["AÑO", "CITAS", "AUTORES", "TÍTULO"]
    assert primera.split()[:3] == ["1996", "702", "Osareh"]


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["buscar", "x", "-n", "0"],
        ["buscar", "  "],
        ["exportar", "x.json"],
        ["buscar", "x", "--fuente", "scopus"],
        ["buscar", "x", "--fuente", ","],
        ["buscar", "x", "--desde", "dosmil"],
    ],
)
def test_argumentos_invalidos(args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_json_invalido_no_se_sobrescribe_ni_consulta_la_red(tmp_path, openalex_simulado, capsys):
    ruta = tmp_path / "biblioteca.json"
    ruta.write_text("contenido inválido", encoding="utf-8")
    assert main(["buscar", "x", "--guardar", str(ruta)]) == 1
    assert ruta.read_text(encoding="utf-8") == "contenido inválido"
    assert openalex_simulado[0] == []
    assert "Error:" in capsys.readouterr().err


@pytest.mark.parametrize("estado", [401, 429, 503])
def test_error_http_conserva_biblioteca(tmp_path, hacer_articulo, monkeypatch, capsys, estado):
    ruta = tmp_path / "biblioteca.json"
    Biblioteca([hacer_articulo()]).guardar(ruta)
    original = ruta.read_bytes()
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(estado))) as client:
        monkeypatch.setattr(
            "litmar.configuracion.OpenAlex", lambda **kwargs: OpenAlex(client=client, max_retries=0)
        )
        assert main(["buscar", "x", "--guardar", str(ruta)]) == 1
    assert ruta.read_bytes() == original
    assert f"HTTP {estado}" in capsys.readouterr().err


def test_error_de_red_se_explica(monkeypatch, capsys):
    def fallar(peticion):
        raise httpx.ConnectError("sin conexión", request=peticion)

    with httpx.Client(transport=httpx.MockTransport(fallar)) as client:
        monkeypatch.setattr(
            "litmar.configuracion.OpenAlex", lambda **kwargs: OpenAlex(client=client, max_retries=0)
        )
        assert main(["buscar", "x"]) == 1
    assert "no se pudo conectar" in capsys.readouterr().err


def test_exportar_archivo_inexistente(tmp_path, capsys):
    assert main(["exportar", str(tmp_path / "no.json"), "--bibtex", str(tmp_path / "x.bib")]) == 1
    assert "Error:" in capsys.readouterr().err


def test_exportar_no_sobrescribe_la_biblioteca(tmp_path):
    ruta = tmp_path / "biblioteca.json"
    Biblioteca().guardar(ruta)
    original = ruta.read_bytes()
    assert main(["exportar", str(ruta), "--bibtex", str(ruta)]) == 1
    assert ruta.read_bytes() == original


def test_ui_lanza_streamlit_con_el_mismo_interprete(monkeypatch):
    import sys

    llamadas = []
    monkeypatch.setattr("litmar.cli.subprocess.call", lambda args: llamadas.append(args) or 0)
    assert main(["ui"]) == 0
    [args] = llamadas
    assert args[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert Path(args[4]) == Path(__file__).parent.parent / "src" / "litmar" / "ui.py"
    assert args[5:] == ["--browser.gatherUsageStats", "false"]


def test_ui_pasa_opciones_a_streamlit(monkeypatch):
    llamadas = []
    monkeypatch.setattr("litmar.cli.subprocess.call", lambda args: llamadas.append(args) or 0)
    assert main(["ui", "--server.port", "8600"]) == 0
    assert llamadas[0][-2:] == ["--server.port", "8600"]


def test_ui_sin_streamlit_explica_como_instalarlo(monkeypatch, capsys):
    monkeypatch.setattr("litmar.cli.importlib.util.find_spec", lambda nombre: None)
    monkeypatch.setattr("litmar.cli.subprocess.call", lambda args: pytest.fail("no debe lanzarse"))
    assert main(["ui"]) == 1
    assert "uv sync --extra ui" in capsys.readouterr().err


class FuenteFija(Fuente):
    """Fuente sin red que devuelve siempre los mismos artículos (o falla)."""

    def __init__(self, articulos=(), error=None):
        super().__init__()
        self.articulos = list(articulos)
        self.error = error
        self.llamadas = []

    def buscar(self, consulta, n=10, *, desde=None):
        self.llamadas.append((consulta, n, desde))
        if self.error:
            raise self.error
        return [a for a in self.articulos if desde is None or a.year >= desde][:n]


@pytest.fixture
def varias_fuentes(monkeypatch, hacer_articulo):
    """OpenAlex y Europe PMC comparten un artículo; arXiv falla con HTTP 503."""
    comun = hacer_articulo(year=2021)
    fuentes = {
        "OpenAlex": FuenteFija([comun, hacer_articulo(doi="10.1/viejo", year=2015)]),
        "Europe PMC": FuenteFija([comun, hacer_articulo(doi="10.1/nuevo", year=2023)]),
        "arXiv": FuenteFija(
            error=httpx.HTTPStatusError(
                "fallo", request=httpx.Request("GET", "https://x"), response=httpx.Response(503)
            )
        ),
    }
    monkeypatch.setattr("litmar.configuracion.crear_fuente", lambda nombre: fuentes[nombre])
    return fuentes


def test_demo_de_la_clase_1(tmp_path, varias_fuentes, capsys):
    """El comando de la diapositiva 8 de docs/Clase1.pdf."""
    bib = tmp_path / "refs.bib"
    codigo = main(
        [
            "buscar",
            "posidonia carbon",
            "--fuente",
            "openalex,europepmc",
            "--desde",
            "2020",
            "--bibtex",
            str(bib),
            "--n",
            "5",
        ]
    )
    assert codigo == 0
    biblioteca_bib = bib.read_text(encoding="utf-8")
    assert "10.1000/xyz123" in biblioteca_bib and "10.1/nuevo" in biblioteca_bib
    assert "10.1/viejo" not in biblioteca_bib
    assert varias_fuentes["OpenAlex"].llamadas == [("posidonia carbon", 5, 2020)]
    salida = capsys.readouterr().out
    assert "2 resultados." in salida
    assert "2 artículos exportados" in salida


def test_fuentes_sin_distinguir_mayusculas_ni_repetir(varias_fuentes):
    assert main(["buscar", "x", "--fuente", "OpenAlex, openalex ,EUROPEPMC"]) == 0
    assert len(varias_fuentes["OpenAlex"].llamadas) == 1
    assert len(varias_fuentes["Europe PMC"].llamadas) == 1


def test_si_falla_una_fuente_se_avisa_y_se_sigue(varias_fuentes, capsys):
    assert main(["buscar", "x", "--fuente", "arxiv,openalex"]) == 0
    salida = capsys.readouterr()
    assert "Aviso: arXiv respondió con HTTP 503." in salida.err
    assert "2 resultados." in salida.out


def test_si_fallan_todas_es_un_error_y_no_se_guarda(tmp_path, varias_fuentes, capsys):
    ruta = tmp_path / "biblioteca.json"
    assert main(["buscar", "x", "--fuente", "arxiv", "--guardar", str(ruta)]) == 1
    assert not ruta.exists()
    assert "Error: arXiv respondió con HTTP 503." in capsys.readouterr().err


def test_zotero_sin_configurar_se_explica(monkeypatch, capsys):
    monkeypatch.delenv("ZOTERO_USER_ID", raising=False)
    monkeypatch.delenv("ZOTERO_GROUP_ID", raising=False)
    assert main(["buscar", "x", "--fuente", "zotero"]) == 1
    assert "ZOTERO_USER_ID" in capsys.readouterr().err


def test_bibtex_y_guardar_no_pueden_ser_el_mismo_archivo(tmp_path, varias_fuentes):
    ruta = tmp_path / "a.json"
    assert main(["buscar", "x", "--guardar", str(ruta), "--bibtex", str(ruta)]) == 1
    assert varias_fuentes["OpenAlex"].llamadas == []


def test_sin_resultados_no_imprime_tabla(monkeypatch, capsys):
    monkeypatch.setattr("litmar.configuracion.crear_fuente", lambda nombre: FuenteFija())
    assert main(["buscar", "x"]) == 0
    assert capsys.readouterr().out == "0 resultados.\n"


def test_tabla_recorta_al_ancho(hacer_articulo):
    articulo = hacer_articulo(title="Un título muy largo " * 10, citations=12345)
    lineas = tabla([articulo], ancho=80).splitlines()
    assert all(len(linea) <= 80 for linea in lineas)
    assert lineas[1].endswith("…")
    assert lineas[1].startswith("2021  12345  García et al.")


class GrafoFalso:
    """Grafo de prueba: emite los seis pasos sin modelo, fuentes ni red."""

    def __init__(self, articulo, informe):
        self.articulo = articulo
        self.informe = informe
        self.config_visto = None

    def stream(self, estado, *, config, stream_mode):
        self.config_visto = config
        assert stream_mode == "updates"
        yield {"planificar": {"traza": "2 consultas"}}
        yield {"buscar": {"traza": "4 artículos"}}
        yield {"filtrar": {"traza": "1 seleccionados", "seleccionados": [self.articulo]}}
        yield {"resumir_articulos": {"traza": "1 resúmenes"}}
        yield {
            "sintetizar": {
                "traza": "informe (1 citas)",
                "informe": self.informe,
                "intentos_sintesis": 1,
            }
        }
        yield {
            "verificar_citas": {
                "traza": "ok (1 citas)",
                "citas": [self.articulo.doi],
                "citaciones_invalidas": [],
                "avisos": [],
            }
        }


def test_revisar_muestra_pasos_y_guarda_informe_y_bibtex(
    tmp_path, monkeypatch, capsys, hacer_articulo
):
    articulo = hacer_articulo(doi="10.1000/revisado", abstract="Resumen.")
    informe = f"La pradera fija carbono [{articulo.doi}]."
    grafo = GrafoFalso(articulo, informe)
    monkeypatch.setattr("litmar.cli.crear_modelo", lambda: object())
    monkeypatch.setattr("litmar.cli.crear_grafo", lambda modelo: grafo)
    ruta_informe = tmp_path / "informe.md"
    ruta_bib = tmp_path / "citas.bib"

    codigo = main(
        [
            "revisar",
            "¿Cuánto carbono fija la posidonia?",
            "--informe",
            str(ruta_informe),
            "--bibtex",
            str(ruta_bib),
        ]
    )

    assert codigo == 0
    salida = capsys.readouterr()
    for paso in (
        "planificar",
        "buscar",
        "filtrar",
        "resumir_articulos",
        "sintetizar",
        "verificar_citas",
    ):
        assert f"> {paso}" in salida.out
    assert ruta_informe.read_text(encoding="utf-8") == informe
    assert articulo.doi in ruta_bib.read_text(encoding="utf-8")
    assert f"BibTeX:  {ruta_bib} (1 artículo)" in salida.out
    assert grafo.config_visto == {"recursion_limit": LIMITE_RECURSION}


class AgenteFalso:
    """Grafo de prueba: emite tareas, una pausa opcional y el informe final."""

    def __init__(self, fragmentos, registro, *, interrumpir=False):
        self.fragmentos = fragmentos
        self.registro = registro
        self.interrumpir = interrumpir
        self.entradas = []
        self.config_visto = None

    def stream(self, entrada, *, config, stream_mode):
        self.entradas.append(entrada)
        self.config_visto = config
        assert stream_mode == "updates"
        if self.interrumpir and len(self.entradas) == 1:
            yield {"__interrupt__": [IntervaloFalso()]}
        yield from self.fragmentos


class IntervaloFalso:
    """Sustituto de `Interrupt`: expone solo el valor que lee la CLI."""

    value = {
        "action_requests": [
            {
                "name": "buscar_articulos",
                "args": {"consulta": "posidonia", "fuente": "openalex", "n": 3},
            }
        ]
    }


@pytest.fixture
def agente_falso(monkeypatch, hacer_articulo):
    articulo = hacer_articulo(doi="10.1000/revisado", abstract="Resumen.")
    registro = RegistroBusquedas()
    registro.registrar({"consulta": "posidonia", "fuente": "OpenAlex"}, [articulo])
    fragmentos = [
        {"tools": {"todos": [{"content": "Buscar", "status": "completed"}]}},
        {
            "tools": {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "buscar_articulos",
                                "args": {"consulta": "posidonia", "fuente": "openalex"},
                                "id": "b1",
                            }
                        ],
                    )
                ]
            }
        },
        {"model": {"messages": [AIMessage(content=f"Hallazgo [{articulo.doi}].")]}},
    ]
    agente = AgenteFalso(fragmentos, registro)
    monkeypatch.setattr("litmar.cli.crear_modelo", lambda: object())
    monkeypatch.setattr("litmar.cli.crear_agente", lambda modelo, **kwargs: (agente, registro))
    return agente, articulo


def test_revisar_agente_guarda_informe_y_solo_el_doi_con_respaldo(tmp_path, agente_falso, capsys):
    agente, articulo = agente_falso
    informe = tmp_path / "informe.md"
    bib = tmp_path / "citas.bib"

    codigo = main(
        [
            "revisar",
            "¿Carbono azul?",
            "--modo",
            "agente",
            "--informe",
            str(informe),
            "--bibtex",
            str(bib),
        ]
    )

    assert codigo == 0
    salida = capsys.readouterr()
    assert "> tarea           [completed] Buscar" in salida.out
    assert "→ buscar_articulos(" in salida.out
    assert informe.read_text(encoding="utf-8") == f"Hallazgo [{articulo.doi}]."
    texto_bib = bib.read_text(encoding="utf-8")
    assert articulo.doi in texto_bib
    assert "1 citas válidas" in salida.out
    assert agente.config_visto["recursion_limit"] == LIMITE_PASOS
    assert agente.config_visto["configurable"]["thread_id"]


def test_revisar_agente_avisa_de_citas_sin_respaldo(tmp_path, agente_falso, capsys, hacer_articulo):
    agente, articulo = agente_falso
    inventado = "10.9999/falso"
    agente.fragmentos[-1]["model"]["messages"][0] = AIMessage(
        content=f"Real [{articulo.doi}] e inventado [{inventado}]."
    )

    assert (
        main(
            [
                "revisar",
                "p",
                "--modo",
                "agente",
                "--informe",
                str(tmp_path / "i.md"),
                "--bibtex",
                str(tmp_path / "c.bib"),
            ]
        )
        == 0
    )
    salida = capsys.readouterr()
    assert "Citas sin respaldo" in salida.err
    assert inventado in salida.err
    assert inventado not in (tmp_path / "c.bib").read_text(encoding="utf-8")
    assert articulo.doi in (tmp_path / "c.bib").read_text(encoding="utf-8")


def test_revisar_agente_aprueba_la_busqueda_editando_los_argumentos(
    tmp_path, agente_falso, monkeypatch
):
    agente, articulo = agente_falso
    agente.interrumpir = True
    respuestas = iter(["e", '{"consulta": "posidonia warming", "fuente": "Europe PMC"}'])
    monkeypatch.setattr("builtins.input", lambda aviso="": next(respuestas))

    assert (
        main(
            [
                "revisar",
                "p",
                "--modo",
                "agente",
                "--aprobar",
                "--informe",
                str(tmp_path / "i.md"),
                "--bibtex",
                str(tmp_path / "c.bib"),
            ]
        )
        == 0
    )
    assert len(agente.entradas) == 2
    reanudacion = agente.entradas[1]
    decisiones = reanudacion.resume["decisions"]
    assert decisiones == [
        {
            "type": "edit",
            "args": {"consulta": "posidonia warming", "fuente": "Europe PMC"},
        }
    ]
    assert agente.entradas[0]["messages"][0]["content"] == "p"
    assert agente.entradas[0] != agente.entradas[1]
    assert (tmp_path / "c.bib").read_text(encoding="utf-8").count(articulo.doi) == 1


def test_aprobar_solo_se_usa_con_el_modo_agente(monkeypatch, capsys):
    monkeypatch.setattr("litmar.cli.crear_modelo", lambda: pytest.fail("no debe crear el modelo"))
    assert main(["revisar", "pregunta", "--aprobar"]) == 1
    assert "--aprobar solo se usa con --modo agente" in capsys.readouterr().err


def test_revisar_no_permite_el_mismo_archivo_para_informe_y_bibtex(tmp_path, capsys):
    ruta = tmp_path / "igual.txt"
    assert main(["revisar", "pregunta", "--informe", str(ruta), "--bibtex", str(ruta)]) == 1
    assert "deben ser distintos" in capsys.readouterr().err


def test_revisar_explica_el_error_si_falta_el_modelo(monkeypatch, capsys):
    def sin_modelo():
        raise ValueError("falta LITMAR_MODELO: añade una línea al .env")

    monkeypatch.setattr("litmar.cli.crear_modelo", sin_modelo)
    assert main(["revisar", "pregunta"]) == 1
    assert "falta LITMAR_MODELO" in capsys.readouterr().err
