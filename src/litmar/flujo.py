"""Flujo de revisión bibliográfica con LangGraph: seis nodos, tres con LLM.

El modelo decide las consultas, los resúmenes y el texto del informe. La
búsqueda, el filtrado y la verificación de citas los hace el código: son cosas
que se pueden comprobar sin pedirle nada a un modelo.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import partial
from typing import Protocol, TypedDict

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from litmar import configuracion
from litmar.articulo import Articulo, normalizar_doi
from litmar.biblioteca import Biblioteca
from litmar.busqueda import buscar_en_fuentes
from litmar.fuentes import Fuente
from litmar.resumen import ResumenArticulo, resumir

# Límites fijados en código: el modelo no decide cuánto trabajo hacer.
MIN_CONSULTAS = 2
MAX_CONSULTAS = 3
POR_FUENTE = 6
MAX_ENCONTRADOS = 40
MAX_SELECCIONADOS = 6
MAX_INTENTOS_SINTESIS = 3  # una escritura + dos reescrituras
LIMITE_RECURSION = 20


class Invocable(Protocol):
    """Lo que devuelve `with_structured_output`: algo con `invoke`."""

    def invoke(self, mensajes: list[BaseMessage]) -> BaseModel: ...


class ModeloEstructurado(Protocol):
    """Chat model de LangChain (o doble de test) con salida estructurada."""

    def with_structured_output(self, esquema: type[BaseModel]) -> Invocable: ...


class PlanBusqueda(BaseModel):
    """Consultas propuestas por el modelo para responder a la pregunta."""

    consultas: list[str] = Field(
        description=(
            "Entre 2 y 3 consultas breves de búsqueda, sin repetir, con los términos "
            "más útiles para encontrar literatura científica sobre la pregunta."
        )
    )


class InformeRedaccion(BaseModel):
    """Informe escrito por el modelo; cada afirmación citada como DOI entre corchetes."""

    texto: str = Field(
        description=(
            "Informe en español que responde a la pregunta usando solo los artículos "
            "proporcionados. Cita cada afirmación con el DOI exacto entre corchetes, "
            "por ejemplo [10.1234/ejemplo]. No inventes DOI ni autores."
        )
    )


class EstadoRevision(TypedDict, total=False):
    """Datos que comparten los nodos; el modelo y las fuentes se inyectan, no viajan aquí."""

    pregunta: str
    fuentes: list[str]
    n: int
    desde: int | None
    consultas: list[str]
    encontrados: list[Articulo]
    seleccionados: list[Articulo]
    resumenes: dict[str, ResumenArticulo]
    informe: str
    intentos_sintesis: int
    citas: list[str]
    citaciones_invalidas: list[str]
    avisos: list[str]
    traza: str


_PROMPT_PLAN = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres un revisor de literatura científica. A partir de una pregunta de "
            "investigación, propón entre 2 y 3 consultas breves que combinen los "
            "términos más útiles para buscar artículos. No escribas explicaciones, "
            "solo las consultas.",
        ),
        ("user", "Pregunta de investigación: {pregunta}"),
    ]
)

_PROMPT_SINTESIS = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres un revisor de literatura científica. Redacta un informe claro en "
            "español que responda a la pregunta usando únicamente los artículos "
            "proporcionados. Cita cada afirmación escribiendo el DOI del artículo "
            "entre corchetes, por ejemplo [10.1234/ejemplo]. Usa solo los DOI de la "
            "lista: no inventes ninguno, y no cites artículos que no estén en ella. "
            "Si los artículos no permiten responder, dilo en lugar de especular.",
        ),
        (
            "user",
            "Pregunta: {pregunta}\n\n"
            "Artículos disponibles (solo puedes citar estos DOI):\n"
            "{articulos}\n"
            "{feedback}",
        ),
    ]
)

_PATRON_CITA = re.compile(r"\[([^\[\]]+)\]")


def _contar(numero: int, singular: str, plural: str) -> str:
    """«1 resumen», «3 resúmenes»: texto para las trazas de la terminal."""
    return f"{numero} {singular if numero == 1 else plural}"


def estado_inicial(
    pregunta: str,
    fuentes: list[str],
    n: int = MAX_SELECCIONADOS,
    desde: int | None = None,
) -> EstadoRevision:
    """Estado de entrada: la pregunta, las fuentes y los límites, todo lo demás vacío."""
    return {
        "pregunta": pregunta.strip(),
        "fuentes": list(fuentes),
        "n": n,
        "desde": desde,
        "consultas": [],
        "encontrados": [],
        "seleccionados": [],
        "resumenes": {},
        "informe": "",
        "intentos_sintesis": 0,
        "citas": [],
        "citaciones_invalidas": [],
        "avisos": [],
        "traza": "",
    }


def extraer_citas(texto: str) -> list[str]:
    """Devuelve el contenido de los corchetes del informe, con el DOI normalizado.

    Si el contenido no parece un DOI se conserva tal cual: así `verificar_citas`
    puede marcarlo como inválido en lugar de descartarlo en silencio.
    """
    citas: list[str] = []
    for contenido in _PATRON_CITA.findall(texto):
        valor = contenido.strip()
        try:
            citas.append(normalizar_doi(valor))
        except ValueError:
            citas.append(valor)
    return list(dict.fromkeys(citas))


def planificar(state: EstadoRevision, *, modelo: ModeloEstructurado) -> dict:
    """Pide al modelo 2-3 consultas; el código recorta vacías, repeticiones y excesos."""
    mensajes = _PROMPT_PLAN.format_messages(pregunta=state["pregunta"])
    plan = modelo.with_structured_output(PlanBusqueda).invoke(mensajes)
    consultas = [consulta.strip() for consulta in plan.consultas if consulta.strip()]
    consultas = list(dict.fromkeys(consultas))[:MAX_CONSULTAS]
    if len(consultas) < MIN_CONSULTAS and state["pregunta"] not in consultas:
        consultas.append(state["pregunta"])
    return {"consultas": consultas, "traza": _contar(len(consultas), "consulta", "consultas")}


def buscar(state: EstadoRevision, *, crear: Callable[[str], Fuente] | None = None) -> dict:
    """Busca en todas las fuentes sin LLM y junta los resultados en una Biblioteca."""
    crear = crear or configuracion.crear_fuente
    biblioteca = Biblioteca()
    avisos = list(state["avisos"])
    for consulta in state["consultas"]:
        resultado = buscar_en_fuentes(
            consulta,
            state["fuentes"],
            POR_FUENTE,
            desde=state.get("desde"),
            crear=crear,
        )
        for articulo in resultado.library:
            biblioteca.agregar(articulo)
        avisos.extend(resultado.errors)
    encontrados = list(biblioteca)[:MAX_ENCONTRADOS]
    return {
        "encontrados": encontrados,
        "avisos": avisos,
        "traza": _contar(len(encontrados), "artículo", "artículos"),
    }


def filtrar(state: EstadoRevision) -> dict:
    """Descarta artículos sin resumen, ordena por citas y año y se queda con los N."""
    con_resumen = [articulo for articulo in state["encontrados"] if articulo.abstract.strip()]
    ordenados = sorted(con_resumen, key=lambda a: (a.citations, a.year), reverse=True)
    tope = min(state["n"], MAX_SELECCIONADOS)
    seleccionados = list(Biblioteca(ordenados))[:tope]
    avisos = list(state["avisos"])
    descartados = len(state["encontrados"]) - len(con_resumen)
    if descartados:
        avisos.append(f"{descartados} artículo(s) sin resumen descartados.")
    return {
        "seleccionados": seleccionados,
        "avisos": avisos,
        "traza": _contar(len(seleccionados), "seleccionado", "seleccionados"),
    }


def resumir_articulos(state: EstadoRevision, *, modelo: ModeloEstructurado) -> dict:
    """Resume cada artículo seleccionado con `resumir()`; clave = DOI."""
    resumenes: dict[str, ResumenArticulo] = {}
    avisos = list(state["avisos"])
    sin_resumen = 0
    for articulo in state["seleccionados"]:
        resumen = resumir(articulo, state["pregunta"], modelo)
        if resumen is None:
            sin_resumen += 1
            continue
        resumenes[articulo.doi] = resumen
    if sin_resumen:
        avisos.append(f"{sin_resumen} artículo(s) sin resumen; no se llamó al modelo para ellos.")
    return {
        "resumenes": resumenes,
        "avisos": avisos,
        "traza": _contar(len(resumenes), "resumen", "resúmenes"),
    }


def sintetizar(state: EstadoRevision, *, modelo: ModeloEstructurado) -> dict:
    """Escribe (o reescribe) el informe citando solo los DOI seleccionados."""
    bloques = []
    for articulo in state["seleccionados"]:
        resumen = state["resumenes"].get(articulo.doi)
        if resumen is None:
            continue
        bloques.append(
            f"- DOI [{articulo.doi}] — {articulo.title} ({articulo.year})\n"
            f"  Objetivo: {resumen.objetivo}\n"
            f"  Método: {resumen.metodo}\n"
            f"  Hallazgos: {resumen.hallazgos}\n"
            f"  Relevancia: {resumen.relevancia}/5\n"
            f"  Limitaciones: {resumen.limitaciones}"
        )
    invalidas = state.get("citaciones_invalidas", [])
    feedback = ""
    if invalidas:
        feedback = (
            "El informe anterior citó DOI que no están en la lista: "
            + ", ".join(invalidas)
            + ". Escríbelo de nuevo citando solo los DOI permitidos."
        )
    mensajes = _PROMPT_SINTESIS.format_messages(
        pregunta=state["pregunta"],
        articulos="\n".join(bloques),
        feedback=feedback,
    )
    informe = modelo.with_structured_output(InformeRedaccion).invoke(mensajes).texto
    intentos = state.get("intentos_sintesis", 0) + 1
    return {
        "informe": informe,
        "intentos_sintesis": intentos,
        "traza": f"informe ({_contar(len(extraer_citas(informe)), 'cita', 'citas')})",
    }


def verificar_citas(state: EstadoRevision) -> dict:
    """Comprueba con código que cada DOI citado está entre los seleccionados."""
    permitidos = {articulo.doi for articulo in state["seleccionados"]}
    citas = extraer_citas(state["informe"])
    invalidas = [cita for cita in citas if cita not in permitidos]
    agotados = state.get("intentos_sintesis", 0) >= MAX_INTENTOS_SINTESIS
    avisos = list(state["avisos"])
    if invalidas and agotados:
        avisos.append("Quedan citas no verificadas tras 2 reescrituras: " + ", ".join(invalidas))
    if invalidas:
        final = "" if agotados else " → reescribir"
        sufijo = "" if len(invalidas) == 1 else "s"
        traza = f"{len(invalidas)} cita{sufijo} inválida{sufijo}{final}"
    else:
        traza = f"ok ({_contar(len(citas), 'cita', 'citas')})"
    return {
        "citas": citas,
        "citaciones_invalidas": invalidas,
        "avisos": avisos,
        "traza": traza,
    }


def biblioteca_de_citas(state: EstadoRevision) -> Biblioteca:
    """Biblioteca con los artículos citados válidamente (uno por DOI)."""
    por_doi = {articulo.doi: articulo for articulo in state["seleccionados"]}
    biblioteca = Biblioteca()
    for doi in state["citas"]:
        articulo = por_doi.get(doi)
        if articulo is not None:
            biblioteca.agregar(articulo)
    return biblioteca


def decidir(state: EstadoRevision) -> str:
    """Vuelve a `sintetizar` solo si hay citas malas y aún quedan reescrituras."""
    if state["citaciones_invalidas"] and state["intentos_sintesis"] < MAX_INTENTOS_SINTESIS:
        return "reescribir"
    return "fin"


def crear_grafo(
    modelo: ModeloEstructurado,
    crear: Callable[[str], Fuente] | None = None,
) -> CompiledStateGraph[EstadoRevision, None, EstadoRevision, EstadoRevision]:
    """Compila el grafo: seis nodos, con un bucle de verificación de citas.

    El modelo y la fábrica de fuentes se inyectan al construir el grafo: el
    estado solo lleva datos, así el mismo grafo sirve para CLI, UI o API y se
    puede probar con dobles, sin clave ni red.
    """
    grafo = StateGraph(EstadoRevision)
    grafo.add_node("planificar", partial(planificar, modelo=modelo))
    grafo.add_node("buscar", partial(buscar, crear=crear))
    grafo.add_node("filtrar", filtrar)
    grafo.add_node("resumir_articulos", partial(resumir_articulos, modelo=modelo))
    grafo.add_node("sintetizar", partial(sintetizar, modelo=modelo))
    grafo.add_node("verificar_citas", verificar_citas)

    grafo.add_edge(START, "planificar")
    grafo.add_edge("planificar", "buscar")
    grafo.add_edge("buscar", "filtrar")
    grafo.add_edge("filtrar", "resumir_articulos")
    grafo.add_edge("resumir_articulos", "sintetizar")
    grafo.add_edge("sintetizar", "verificar_citas")
    grafo.add_conditional_edges(
        "verificar_citas",
        decidir,
        {"reescribir": "sintetizar", "fin": END},
    )
    return grafo.compile()
