<<<<<<< HEAD
"""Resumen estructurado de un artículo, adaptado a una pregunta de investigación."""

from __future__ import annotations

from typing import Protocol

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
=======
"""Resumen estructurado de un artículo con un modelo de lenguaje.

`resumir` le pide al modelo un `ResumenArticulo` en lugar de texto libre:
`with_structured_output` le pasa el esquema Pydantic (campos, tipos y
descripciones) y valida la respuesta, así que lo que vuelve es un objeto con
los campos que esperamos o un error, nunca un párrafo que haya que trocear.

El modelo se recibe como parámetro: este módulo no sabe qué proveedor hay
detrás ni lee claves. Cualquier modelo de chat de LangChain sirve, y en los
tests, un modelo falso.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

>>>>>>> upstream/main
from pydantic import BaseModel, Field

from litmar.articulo import Articulo

<<<<<<< HEAD

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
=======
if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

NO_CONSTA = "No consta en el resumen."


class ResumenArticulo(BaseModel):
    """Resumen estructurado de un artículo científico respecto a una pregunta."""

    # Las descripciones forman parte del prompt: el modelo las lee para saber
    # qué poner en cada campo.
    objective: str = Field(
        description="Objetivo del estudio: qué pregunta o problema aborda. Una o dos frases."
    )
    method: str = Field(
        description="Método: datos, zona o muestras, técnicas y diseño del estudio."
    )
    findings: list[str] = Field(
        description="Hallazgos principales, uno por elemento, con cifras si el resumen las da."
    )
    relevance: int = Field(
        ge=1,
        le=5,
        description=(
            "Relevancia del artículo para la pregunta de investigación: "
            "1 = nada relevante, 3 = relacionado de forma parcial o indirecta, "
            "5 = responde directamente a la pregunta."
        ),
    )
    limitations: str = Field(
        description=(
            "Limitaciones que reconocen los autores o que se deducen del resumen "
            f"(muestra, zona, método). Si no se puede saber, escribe «{NO_CONSTA}»"
>>>>>>> upstream/main
        )
    )


<<<<<<< HEAD
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
=======
_INSTRUCCIONES = f"""\
Eres un asistente que resume artículos científicos para una revisión de literatura.
Usa solo la información del título y del resumen que se te dan: no añadas datos
de otros trabajos ni de tu memoria. Si algo no aparece en el resumen, escribe
«{NO_CONSTA}» en lugar de suponerlo. Responde en español."""


def resumir(articulo: Articulo, pregunta: str, modelo: BaseChatModel) -> ResumenArticulo | None:
    """Resume `articulo` con `modelo` y puntúa su relevancia para `pregunta`.

    Devuelve `None` sin llamar al modelo si el artículo no tiene resumen: sin
    texto del que partir, el modelo solo podría inventar.
    """
    if not articulo.abstract.strip():
        return None

    mensajes = [
        ("system", _INSTRUCCIONES),
        (
            "human",
            f"Pregunta de investigación: {pregunta}\n\n"
            f"Título: {articulo.title}\n"
            f"Autores y año: {articulo.short_citation}\n"
            f"Revista: {articulo.journal}\n\n"
            f"Resumen:\n{articulo.abstract}",
        ),
    ]
    # json_schema: el proveedor obliga al modelo a responder con este esquema. Es
    # la opción recomendada en Gemini y la que funciona en los Claude recientes,
    # donde la de por defecto (forzar una llamada a herramienta) puede fallar.
    estructurado = modelo.with_structured_output(ResumenArticulo, method="json_schema")
    return estructurado.invoke(mensajes)
>>>>>>> upstream/main
