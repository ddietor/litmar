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
