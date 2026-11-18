"""Resumen estructurado de un artículo, adaptado a una pregunta de investigación."""

from __future__ import annotations

from typing import Protocol

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from litmar.articulo import Articulo


class ResumenArticulo(BaseModel):
    """Lo que litmar extrae de un artículo para una pregunta concreta."""

    objetivo: str = Field(
        description="Objetivo o pregunta que el artículo se propone responder, según el resumen."
    )
    metodo: str = Field(
        description="Método, diseño y datos usados en el estudio, según el resumen."
    )
    hallazgos: str = Field(
        description="Resultados y conclusiones principales del artículo, según el resumen."
    )
    relevancia: int = Field(
        description=(
            "Relevancia para la pregunta de investigación del usuario, "
            "de 1 (nada relevante) a 5 (esencial)."
        ),
        ge=1,
        le=5,
    )
    limitaciones: str = Field(
        description=(
            "Limitaciones o advertencias mencionadas en el resumen; "
            "si no se indican, di que no se mencionan."
        )
    )


class Invocable(Protocol):
    """Lo que devuelve `with_structured_output`: algo con `invoke`."""

    def invoke(self, mensajes: list[BaseMessage]) -> ResumenArticulo: ...


class ModeloEstructurado(Protocol):
    """Un chat model de LangChain (o un doble de test) con salida estructurada."""

    def with_structured_output(self, schema: type[ResumenArticulo]) -> Invocable: ...


_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres un revisor de literatura científica. Resume el artículo usando solo "
            "el resumen proporcionado. No inventes datos: si el texto no menciona algo, "
            "indícalo en el campo correspondiente. La relevancia se refiere a la pregunta "
            "de investigación del usuario: 1 es irrelevante y 5 es esencial.",
        ),
        (
            "user",
            "Pregunta de investigación: {pregunta}\n\n"
            "Título: {titulo}\n"
            "Año: {anio}\n"
            "DOI: {doi}\n"
            "Resumen del artículo:\n{resumen}",
        ),
    ]
)


def resumir(
    articulo: Articulo, pregunta: str, modelo: ModeloEstructurado
) -> ResumenArticulo | None:
    """Resume un artículo respecto a una pregunta, como objeto Pydantic validado.

    La salida estructurada convierte las descripciones de los campos de
    `ResumenArticulo` en parte del prompt: el modelo recibe el esquema y devuelve
    un objeto con esos cinco campos, sin texto que haya que parsear a mano.

    Se llama con un artículo, la pregunta de investigación y un chat model de
    LangChain (inyectado, así que aquí no se leen claves ni se elige proveedor)::

        resumen = resumir(articulo, "¿Qué sagú es más abundante?", modelo)

    Si el artículo no tiene resumen devuelve ``None`` sin llamar al modelo: el
    código no le pide que invente lo que no está en los datos. Se comprueba con
    un modelo falso que registra si se enlazó el esquema y si se invocó.
    """
    if not articulo.abstract or not articulo.abstract.strip():
        return None

    mensajes = _PROMPT.format_messages(
        pregunta=pregunta.strip(),
        titulo=articulo.title,
        anio=articulo.year,
        doi=articulo.doi,
        resumen=articulo.abstract.strip(),
    )
    return modelo.with_structured_output(ResumenArticulo).invoke(mensajes)
