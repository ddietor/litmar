<<<<<<< HEAD
"""Tests del agente con Deep Agents: modelo y fuentes falsos, sin clave ni red."""

from __future__ import annotations

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.types import Command
from pydantic import Field

from litmar.agente import crear_agente
from litmar.flujo import extraer_citas
from litmar.fuentes import Fuente


class ModeloFalso(BaseChatModel):
    """Devuelve las respuestas en orden y recuerda las herramientas que recibe."""

    respuestas: list
    herramientas: set[str] = Field(default_factory=set)

    @property
    def _llm_type(self) -> str:
        return "falso"

    def bind_tools(self, tools, **kwargs):
        self.herramientas = {herramienta.name for herramienta in tools}
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        respuesta = self.respuestas.pop(0) if len(self.respuestas) > 1 else self.respuestas[0]
        return ChatResult(generations=[ChatGeneration(message=respuesta)])


class FuenteFija(Fuente):
    """Fuente sin red con artículos y registro de consultas."""

    def __init__(self, articulos=()):
        super().__init__()
        self.articulos = list(articulos)
        self.llamadas = []

    def buscar(self, consulta, n=10, *, desde=None):
        self.llamadas.append((consulta, n, desde))
        return self.articulos[:n]


def llamada(nombre: str, args: dict, ident: str) -> AIMessage:
    """Mensaje del modelo con una sola llamada a herramienta."""
    return AIMessage(content="", tool_calls=[{"name": nombre, "args": args, "id": ident}])


@pytest.fixture
def fuentes(hacer_articulo):
    comun = hacer_articulo(doi="10.1000/comun", abstract="Resumen del común.")
    otro = hacer_articulo(doi="10.1000/otro", abstract="Resumen del otro.")
    return {
        "OpenAlex": FuenteFija([comun]),
        "Europe PMC": FuenteFija([otro]),
    }


@pytest.fixture
def crear(fuentes):
    return lambda nombre: fuentes[nombre]


def test_el_agente_tiene_tareas_busqueda_y_subagente_pero_no_codigo(crear):
    modelo = ModeloFalso(respuestas=[AIMessage(content="Listo.")])
    agente, _ = crear_agente(modelo, crear=crear, fuentes=["OpenAlex", "Europe PMC"])
    agente.invoke(
        {"messages": [{"role": "user", "content": "hola"}]}, config={"recursion_limit": 40}
    )

    assert agente.get_graph().nodes
    herramientas = modelo.herramientas
    assert {"write_todos", "task", "buscar_articulos", "listar_fuentes"} <= herramientas
    assert "execute" not in herramientas


def test_el_agente_busca_y_registra_los_dois_que_ve(crear, hacer_articulo):
    informe = "La pradera fija carbono [10.1000/comun] y [10.1000/otro]."
    modelo = ModeloFalso(
        respuestas=[
            llamada("write_todos", {"todos": []}, "t1"),
            llamada(
                "buscar_articulos", {"consulta": "posidonia", "fuente": "OpenAlex", "n": 3}, "b1"
            ),
            llamada(
                "buscar_articulos", {"consulta": "seagrass", "fuente": "Europe PMC", "n": 3}, "b2"
            ),
            AIMessage(content=informe),
        ]
    )
    agente, registro = crear_agente(modelo, crear=crear, fuentes=["OpenAlex", "Europe PMC"])

    resultado = agente.invoke(
        {"messages": [{"role": "user", "content": "¿Qué papel tiene la posidonia?"}]},
        config={"recursion_limit": 40},
    )

    assert set(registro.articulos) == {"10.1000/comun", "10.1000/otro"}
    assert len(registro.llamadas) == 2
    assert resultado["messages"][-1].content == informe
    assert set(extraer_citas(informe)) <= set(registro.articulos)


def test_aprobar_pausa_antes_de_buscar_y_luego_reanuda(crear):
    informe = "Hallazgo [10.1000/comun]."
    modelo = ModeloFalso(
        respuestas=[
            llamada(
                "buscar_articulos", {"consulta": "posidonia", "fuente": "OpenAlex", "n": 3}, "b1"
            ),
            AIMessage(content=informe),
        ]
    )
    agente, registro = crear_agente(modelo, crear=crear, fuentes=["OpenAlex"], aprobar=True)
    config = {"configurable": {"thread_id": "aprobacion"}, "recursion_limit": 40}
    entrada = {"messages": [{"role": "user", "content": "¿Y la posidonia?"}]}

    for fragmento in agente.stream(entrada, config=config, stream_mode="updates"):
        if "__interrupt__" in fragmento:
            peticiones = fragmento["__interrupt__"][0].value["action_requests"]
            assert [peticion["name"] for peticion in peticiones] == ["buscar_articulos"]
            assert registro.llamadas == []  # todavía no se ha buscado
            break
    else:
        pytest.fail("el grafo no se pausó antes de buscar")

    for fragmento in agente.stream(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=config,
        stream_mode="updates",
    ):
        if "tools" in fragmento:
            assert "tools" in fragmento

    assert len(registro.llamadas) == 1
    assert agente.get_state(config).values["messages"][-1].content == informe


def test_el_subagente_busca_y_tambien_pide_aprobacion(crear):
    modelo = ModeloFalso(
        respuestas=[
            llamada(
                "task",
                {
                    "description": "estudios de campo",
                    "subagent_type": "buscador",
                    "prompt": "busca en OpenAlex",
                },
                "t1",
            ),
            llamada("buscar_articulos", {"consulta": "campo", "fuente": "OpenAlex", "n": 3}, "b1"),
            AIMessage(content="El buscador encontró [10.1000/comun]."),
            AIMessage(content="Informe final [10.1000/comun]."),
        ]
    )
    agente, registro = crear_agente(modelo, crear=crear, fuentes=["OpenAlex"], aprobar=True)
    config = {"configurable": {"thread_id": "subagente"}, "recursion_limit": 40}

    interrumpido = False
    for fragmento in agente.stream(
        {"messages": [{"role": "user", "content": "Busca estudios"}]},
        config=config,
        stream_mode="updates",
    ):
        if "__interrupt__" in fragmento:
            peticiones = fragmento["__interrupt__"][0].value["action_requests"]
            assert peticiones[0]["name"] == "buscar_articulos"
            interrumpido = True
            break

    assert interrumpido, "el subagente no pidió aprobación"
    assert registro.llamadas == []
=======
"""Tests del agente revisor con un modelo falso que sigue un guion: sin clave, sin red."""

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from litmar import agente, cli, herramientas, llm
from litmar.flujo import NO_VERIFICADA, citados, informe_markdown

PREGUNTA = "¿Cómo afecta el calentamiento a Posidonia oceanica?"


class ModeloGuion(BaseChatModel):
    """Responde con los mensajes de `guion`, en orden, y apunta qué herramientas ve.

    El agente principal y el buscador comparten el modelo; como se ejecutan uno
    tras otro, un único guion basta para los dos.
    """

    guion: list = []
    herramientas_vistas: list = []

    @property
    def _llm_type(self) -> str:
        return "guion"

    def bind_tools(self, tools, **kwargs):
        nombres = {getattr(t, "name", None) or t.get("name") for t in tools}
        return _ConHerramientas(self, nombres)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if not self.guion:
            raise AssertionError("el agente ha llamado al modelo más veces de las previstas")
        return ChatResult(generations=[ChatGeneration(message=self.guion.pop(0))])


class _ConHerramientas:
    def __init__(self, modelo, nombres):
        self.modelo = modelo
        self.nombres = nombres

    def invoke(self, mensajes, *args, **kwargs):
        self.modelo.herramientas_vistas.append(self.nombres)
        return self.modelo.invoke(mensajes)

    def __getattr__(self, nombre):
        return getattr(self.modelo, nombre)


def llamada(nombre, argumentos, id_):
    return AIMessage(
        content="",
        tool_calls=[{"name": nombre, "args": argumentos, "id": id_, "type": "tool_call"}],
    )


TAREAS = [
    {"content": "Buscar estudios de campo", "status": "in_progress"},
    {"content": "Escribir informe.md", "status": "pending"},
]
TAREAS_HECHAS = [{**t, "status": "completed"} for t in TAREAS]


def guion_completo(informe):
    """Planifica, encarga una búsqueda, el buscador busca y resume, escribe el informe."""
    return [
        llamada("write_todos", {"todos": TAREAS}, "1"),
        llamada(
            "task",
            {"subagent_type": "buscador", "description": "Estudios de campo en Europe PMC"},
            "2",
        ),
        # buscador
        llamada(
            "buscar_articulos",
            {"consulta": "posidonia warming", "fuente": "Europe PMC", "n": 3},
            "3",
        ),
        AIMessage(content="Encontrado: [doi:10.1/b], sobre mortalidad por calor."),
        # principal
        llamada("write_file", {"file_path": "/informe.md", "content": informe}, "4"),
        llamada("write_todos", {"todos": TAREAS_HECHAS}, "5"),
        AIMessage(content="Informe escrito."),
    ]


class FuenteFalsa:
    def __init__(self, articulos):
        self.articulos = articulos

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def buscar(self, consulta, n, *, desde=None):
        return self.articulos[:n]


@pytest.fixture
def articulos(hacer_articulo):
    return [
        hacer_articulo(doi="10.1/b", title="B", citations=50),
        hacer_articulo(doi="10.1/c", title="C", citations=30),
    ]


@pytest.fixture(autouse=True)
def fuentes_falsas(monkeypatch, articulos):
    monkeypatch.setattr(herramientas, "crear_fuente", lambda nombre: FuenteFalsa(articulos))


def ejecutar(modelo, *, aprobar=False, decisiones=(), fuentes=("OpenAlex", "Europe PMC")):
    """Ejecuta el agente; `decisiones` responde, en orden, a cada petición de aprobación."""
    registro = agente.Registro()
    revisor = agente.crear_agente(modelo, registro, fuentes=fuentes, aprobar=aprobar)
    config = agente.configuracion()
    lineas, peticiones = [], []
    decisiones = list(decisiones)

    def decidir(accion):
        peticiones.append(accion)
        return decisiones.pop(0)

    agente.ejecutar(revisor, config, PREGUNTA, mostrar=lineas.append, decidir=decidir)
    return lineas, agente.estado_final(revisor, config, PREGUNTA, registro), registro, peticiones


# --- Qué puede hacer cada agente


def test_herramientas_del_agente_y_del_buscador():
    modelo = ModeloGuion(guion=guion_completo("Según [doi:10.1/b]."))

    ejecutar(modelo)

    principal, *_ = modelo.herramientas_vistas
    buscador = modelo.herramientas_vistas[2]
    assert principal == {"write_todos", "task", "listar_fuentes", "ls", "read_file", "write_file"}
    assert buscador == {"buscar_articulos", "listar_fuentes", "read_file"}
    for prohibida in ("execute", "edit_file", "delete", "glob", "grep"):
        assert all(prohibida not in vistas for vistas in modelo.herramientas_vistas)


def test_las_instrucciones_dicen_lo_que_queremos():
    texto = agente.INSTRUCCIONES.format(
        fuentes="OpenAlex",
        n=6,
        ruta=agente.RUTA_INFORME,
        peso_relevancia=agente.PESO_RELEVANCIA,
        peso_citas=agente.PESO_CITAS,
    )
    assert "write_todos" in texto
    assert "buscador" in texto and "varias fuentes" in texto
    assert "Cita solo DOI que te haya devuelto el buscador" in texto
    assert "70% de relevancia" in texto
    assert "Citas: no disponible" in texto
    assert "## Lo que no se encontró" in texto
    assert "relevancia para el encargo (1–5)" in agente.INSTRUCCIONES_BUSCADOR


def test_estado_final_avisa_si_un_doi_citado_no_tiene_recuento(hacer_articulo):
    from types import SimpleNamespace

    articulo = hacer_articulo(citations=None)
    registro = agente.Registro(articles={articulo.doi: articulo})
    agente_falso = SimpleNamespace(
        get_state=lambda config: SimpleNamespace(
            values={"files": {agente.RUTA_INFORME: {"content": f"[doi:{articulo.doi}]."}}}
        )
    )

    estado = agente.estado_final(agente_falso, {}, PREGUNTA, registro)

    assert len(estado["warnings"]) == 1
    assert articulo.doi in estado["warnings"][0]
    assert "solo la relevancia" in estado["warnings"][0]


# --- Recorrido completo


def test_revision_completa(articulos):
    modelo = ModeloGuion(
        guion=guion_completo(
            "B lo muestra [doi:10.1/b].\n\n## Lo que no se encontró\n\nNada de laboratorio."
        )
    )

    lineas, estado, registro, _ = ejecutar(modelo)

    assert lineas == [
        "[~] Buscar estudios de campo",
        "[ ] Escribir informe.md",
        "→ task(buscador): Estudios de campo en Europe PMC",
        "    · buscar_articulos(«posidonia warming», Europe PMC, n=3)",
        "→ write_file(informe.md)",
        "[x] 2/2 tareas",
    ]
    assert registro.searches == ["posidonia warming (Europe PMC)"]
    assert estado["cited"] == ["10.1/b"]
    assert estado["warnings"] == []
    assert modelo.guion == []
    # Mismo formato que el flujo: referencias y BibTeX solo de lo citado.
    texto = informe_markdown(estado)
    assert "## Lo que no se encontró" in texto
    assert "_Búsquedas: «posidonia warming (Europe PMC)»._" in texto
    assert "## Referencias" in texto and "https://doi.org/10.1/b" in texto
    assert [a.doi for a in citados(estado)] == ["10.1/b"]


def test_un_doi_que_no_salio_de_las_busquedas_se_marca():
    modelo = ModeloGuion(guion=guion_completo("Según [doi:10.1/b] y [doi:10.9999/inventado]."))

    _, estado, _, _ = ejecutar(modelo)

    assert estado["cited"] == ["10.1/b"]
    assert estado["unverified"] == ["10.9999/inventado"]
    assert f"[{NO_VERIFICADA}]" in estado["report"]
    assert "10.9999" not in estado["report"]
    assert any("10.9999/inventado" in aviso for aviso in estado["warnings"])


def test_sin_fichero_usa_la_ultima_respuesta():
    guion = guion_completo("no se usa")
    guion[4] = AIMessage(content="Síntesis directa [doi:10.1/b].")
    modelo = ModeloGuion(guion=guion[:5])

    _, estado, _, _ = ejecutar(modelo)

    assert estado["report"] == "Síntesis directa [doi:10.1/b]."


# --- Límites en el código


def test_limite_de_pasos(monkeypatch):
    monkeypatch.setattr(agente, "MAX_PASOS", 2)
    # Solo le da tiempo a planificar dos veces: la tercera llamada ya no se hace.
    modelo = ModeloGuion(
        guion=[llamada("write_todos", {"todos": TAREAS}, "1"), llamada("ls", {}, "2")]
    )

    lineas, estado, _, _ = ejecutar(modelo)

    assert "! Límite de pasos alcanzado: el agente se detiene." in lineas
    assert "## Hasta dónde llegó" in estado["report"]
    assert "Buscar estudios de campo" in estado["report"]
    assert any("límite de 2 pasos" in aviso for aviso in estado["warnings"])


def test_limite_de_busquedas(monkeypatch):
    monkeypatch.setattr(agente, "MAX_BUSQUEDAS", 0)
    registro = agente.Registro()
    buscar, _ = agente._herramientas(registro, ["OpenAlex"])

    texto = buscar.invoke({"consulta": "x", "fuente": "OpenAlex"})

    assert texto.startswith("Error: ya se han hecho 0 búsquedas")
    assert registro.searches == []


def test_solo_las_fuentes_elegidas():
    registro = agente.Registro()
    buscar, listar = agente._herramientas(registro, ["Europe PMC"])

    assert buscar.invoke({"consulta": "x", "fuente": "OpenAlex"}).startswith(
        "Error: la fuente 'OpenAlex' no está disponible. Usa una de: Europe PMC."
    )
    assert "OpenAlex" not in listar.invoke({})
    assert registro.articles == {}


def test_las_herramientas_del_agente_se_describen_igual():
    buscar, listar = agente._herramientas(agente.Registro(), ["OpenAlex"])

    assert buscar.description == herramientas.buscar_articulos.description
    assert buscar.args == herramientas.buscar_articulos.args
    assert listar.description == herramientas.listar_fuentes.description


# --- Aprobación humana


def test_aprobar_pide_permiso_antes_de_buscar():
    modelo = ModeloGuion(guion=guion_completo("Según [doi:10.1/b]."))

    _, estado, registro, peticiones = ejecutar(
        modelo, aprobar=True, decisiones=[{"type": "approve"}]
    )

    assert [p["name"] for p in peticiones] == ["buscar_articulos"]
    assert peticiones[0]["args"]["consulta"] == "posidonia warming"
    assert registro.searches == ["posidonia warming (Europe PMC)"]
    assert estado["cited"] == ["10.1/b"]


def test_rechazar_no_busca():
    modelo = ModeloGuion(guion=guion_completo("Según [doi:10.1/b]."))

    _, estado, registro, _ = ejecutar(
        modelo, aprobar=True, decisiones=[{"type": "reject", "message": "no"}]
    )

    assert registro.searches == []
    assert estado["unverified"] == ["10.1/b"]  # sin búsqueda, la cita no se puede verificar


def test_editar_cambia_la_busqueda():
    modelo = ModeloGuion(guion=guion_completo("Según [doi:10.1/b]."))
    editada = {
        "type": "edit",
        "edited_action": {
            "name": "buscar_articulos",
            "args": {"consulta": "seagrass heat", "fuente": "OpenAlex", "n": 3},
        },
    }

    _, _, registro, _ = ejecutar(modelo, aprobar=True, decisiones=[editada])

    assert registro.searches == ["seagrass heat (OpenAlex)"]


# --- Comando `litmar revisar --modo agente`


@pytest.fixture
def modelo_cli(monkeypatch):
    modelo = ModeloGuion(guion=guion_completo("Según [doi:10.1/b]."))
    monkeypatch.setattr(llm, "crear_modelo", lambda: modelo)
    return modelo


def test_cli_modo_agente(modelo_cli, tmp_path, capsys):
    informe, bibtex = tmp_path / "i.md", tmp_path / "c.bib"

    codigo = cli.main(
        [
            "revisar",
            PREGUNTA,
            "--modo",
            "agente",
            "--informe",
            str(informe),
            "--bibtex",
            str(bibtex),
        ]
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "→ task(buscador): Estudios de campo en Europe PMC" in salida
    assert "Según [doi:10.1/b]." in informe.read_text(encoding="utf-8")
    assert bibtex.read_text(encoding="utf-8").count("@article") == 1


@pytest.mark.parametrize(("respuestas", "busquedas"), [(["s"], 1), ([""], 1), (["n"], 0)])
def test_cli_aprobar(modelo_cli, monkeypatch, tmp_path, capsys, respuestas, busquedas):
    respuestas = list(respuestas)
    monkeypatch.setattr("builtins.input", lambda _: respuestas.pop(0))
    informe = tmp_path / "i.md"

    codigo = cli.main(
        [
            "revisar",
            PREGUNTA,
            "--modo",
            "agente",
            "--aprobar",
            "--informe",
            str(informe),
            "--bibtex",
            str(tmp_path / "c.bib"),
        ]
    )

    assert codigo == 0
    texto = informe.read_text(encoding="utf-8")
    assert ("posidonia warming (Europe PMC)" in texto) == bool(busquedas)


def test_cli_aprobar_editar(modelo_cli, monkeypatch, tmp_path):
    respuestas = ["e", "seagrass heat", ""]
    monkeypatch.setattr("builtins.input", lambda _: respuestas.pop(0))
    informe = tmp_path / "i.md"

    cli.main(
        [
            "revisar",
            PREGUNTA,
            "--modo",
            "agente",
            "--aprobar",
            "--informe",
            str(informe),
            "--bibtex",
            str(tmp_path / "c.bib"),
        ]
    )

    assert "seagrass heat (Europe PMC)" in informe.read_text(encoding="utf-8")


def test_cli_aprobar_solo_con_agente(capsys):
    assert cli.main(["revisar", PREGUNTA, "--aprobar"]) == 1
    assert "--aprobar solo se usa con --modo agente" in capsys.readouterr().err


def dos_encargos_en_paralelo(informe):
    """El principal lanza dos buscadores a la vez: dos pausas de aprobación pendientes."""
    encargos = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "task",
                "args": {"subagent_type": "buscador", "description": f"Encargo {i}"},
                "id": f"t{i}",
                "type": "tool_call",
            }
            for i in (1, 2)
        ],
    )
    return [
        encargos,
        # los dos buscadores (en paralelo; cada uno toma el siguiente mensaje)
        llamada("buscar_articulos", {"consulta": "uno", "fuente": "OpenAlex", "n": 2}, "b1"),
        llamada("buscar_articulos", {"consulta": "dos", "fuente": "Europe PMC", "n": 2}, "b2"),
        AIMessage(content="Hecho: [doi:10.1/b]."),
        AIMessage(content="Hecho: [doi:10.1/c]."),
        # principal
        llamada("write_file", {"file_path": "/informe.md", "content": informe}, "w"),
        AIMessage(content="Informe escrito."),
    ]


def test_aprobar_dos_busquedas_pendientes_a_la_vez():
    # Fallo real (18/11): con dos buscadores en paralelo, reanudar sin el id de
    # cada interrupción daba «multiple pending interrupts».
    modelo = ModeloGuion(guion=dos_encargos_en_paralelo("[doi:10.1/b] y [doi:10.1/c]."))

    _, estado, registro, peticiones = ejecutar(
        modelo, aprobar=True, decisiones=[{"type": "approve"}, {"type": "reject"}]
    )

    assert len(peticiones) == 2
    assert len(registro.searches) == 1  # una aprobada, otra rechazada
    assert modelo.guion == []
    # la búsqueda aprobada devolvió los dos artículos de la fuente falsa
    assert set(estado["cited"]) == {"10.1/b", "10.1/c"}


def test_cli_aprobar_dos_busquedas_a_la_vez(monkeypatch, tmp_path):
    modelo = ModeloGuion(guion=dos_encargos_en_paralelo("[doi:10.1/b] y [doi:10.1/c]."))
    monkeypatch.setattr(llm, "crear_modelo", lambda: modelo)
    monkeypatch.setattr("builtins.input", lambda _: "s")
    informe = tmp_path / "i.md"

    codigo = cli.main(
        [
            "revisar",
            PREGUNTA,
            "--modo",
            "agente",
            "--aprobar",
            "--informe",
            str(informe),
            "--bibtex",
            str(tmp_path / "c.bib"),
        ]
    )

    assert codigo == 0
    texto = informe.read_text(encoding="utf-8")
    assert "uno (OpenAlex)" in texto
    assert "dos (Europe PMC)" in texto
    assert NO_VERIFICADA not in texto
>>>>>>> upstream/main
