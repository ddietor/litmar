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

from pydantic import BaseModel, Field

from litmar.articulo import Articulo

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
        )
    )


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
