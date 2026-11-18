"""Agente revisor con Deep Agents: segundo modo de `litmar revisar`.

Frente al flujo de `flujo.py`, aquí el modelo decide qué buscar y cuándo
parar. Lo que no se le delega sigue igual: los límites están en el código,
las búsquedas pasan por `herramientas.py` y los DOI citados se comprueban
después con `flujo.extraer_citas` contra el registro de herramientas.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from deepagents import SubAgent, create_deep_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from litmar.fuentes import Fuente
from litmar.herramientas import (
    AVISO_PANGAEA,
    RegistroBusquedas,
    crear_herramientas,
)

LIMITE_PASOS = 40

_PROMPT_TAREAS = """Usa `write_todos` para planificar esta revisión y ve marcando
cada tarea como completada en cuanto termines. La respuesta final debe venir
después de la última actualización de la lista, no en el mismo turno."""

SISTEMA = (
    """Eres un revisor de literatura científica. Respondes a una pregunta
de investigación con un informe breve, en español y en Markdown.

Trabaja así:

1. Empieza con `write_todos`: decide qué vas a buscar, en qué fuentes y cómo
   redactarás el informe. Marca las tareas a medida que las termines.
2. Llama a `listar_fuentes` para saber qué fuentes hay.
3. Delega cada búsqueda al subagente `buscador` con la herramienta `task`,
   indicando la consulta y la fuente. Busca en al menos dos fuentes distintas.
   Si una falla, prueba otra y sigue: los errores de las herramientas son
   texto, no un motivo para detenerte.
4. Cita en el informe SOLO los DOI que hayan aparecido en resultados de las
   herramientas, escritos entre corchetes: [10.1234/ejemplo]. No inventes DOI,
   autores ni títulos, y no cites un artículo que no hayas visto.
5. Structura el informe con un título, unas conclusiones y una sección final
   exactamente llamada `## Lo que no encontré`. Ahí di qué huecos quedan, qué
   consultas no dieron resultados y qué fuentes fallaron. Si no encontraste
   nada sobre una parte de la pregunta, dilo: no especules.
6. Devuelve el informe como texto en tu respuesta final, sin envolverlo en
   explicaciones sobre tu trabajo. No escribas ficheros ni ejecutes comandos:
   la terminal guardará tu respuesta en `informe.md`.

"""
    + AVISO_PANGAEA
    + """

El número de resultados por búsqueda y las fuentes permitidas ya están
limitados en el propio código: no intentes bypassarlos pidiendo más."""
)

SISTEMA_BUSCADOR = """Eres el subagente buscador de litmar. Tu trabajo es
buscar literatura científica y devolver al agente principal solo lo útil.

- Usa `listar_fuentes` si no sabes qué fuentes hay.
- Usa `buscar_articulos` con la consulta y la fuente que te pidan; prueba otra
  fuente si la primera falla.
- Devuelve un resumen breve: para cada artículo, título, año y DOI exacto entre
  corchetes, y una frase con el hallazgo principal. Copia los DOI tal cual;
  no los inventes ni los corrijas.
- No escribas el informe ni tomes decisiones sobre la pregunta: eso lo hace
  el agente principal. Si no encuentras nada, dilo explícitamente.
"""


def crear_agente(
    modelo: BaseChatModel,
    *,
    crear: Callable[[str], Fuente] | None = None,
    entorno: Mapping[str, str] | None = None,
    fuentes: list[str] | None = None,
    n: int = 6,
    desde: int | None = None,
    aprobar: bool = False,
    registro: RegistroBusquedas | None = None,
) -> tuple[CompiledStateGraph, RegistroBusquedas]:
    """Compila el agente y devuelve también el registro de DOIs entregados.

    El modelo, la fábrica de fuentes y los límites se inyectan al construirlo,
    igual que en `crear_grafo`: el mismo agente sirve para CLI, UI o API y se
    puede probar con dobles, sin clave ni red.

    Con `aprobar=True` se instala el checkpointer y `interrupt_on` para que la
    llamada a `buscar_articulos` se pause antes de ejecutarse (también en el
    subagente, que hereda la configuración).
    """
    buscar_articulos, listar_fuentes, registro = crear_herramientas(
        crear=crear,
        entorno=entorno,
        registro=registro,
        fuentes=fuentes,
        n=n,
        desde=desde,
    )
    buscador = SubAgent(
        name="buscador",
        description=(
            "Busca artículos científicos en una fuente específica y devuelve un resumen "
            "breve con título, año, DOI exacto y hallazgo principal."
        ),
        system_prompt=SISTEMA_BUSCADOR,
        tools=[buscar_articulos, listar_fuentes],
    )
    agente = create_deep_agent(
        model=modelo,
        tools=[buscar_articulos, listar_fuentes],
        system_prompt=SISTEMA,
        middleware=[TodoListMiddleware(system_prompt=_PROMPT_TAREAS)],
        subagents=[buscador],
        checkpointer=InMemorySaver() if aprobar else None,
        interrupt_on={"buscar_articulos": True} if aprobar else None,
    )
    return agente, registro
