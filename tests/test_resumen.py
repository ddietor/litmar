<<<<<<< HEAD
"""Tests del resumen estructurado: modelo falso, sin clave y sin red."""

from __future__ import annotations
=======
"""Tests de resumir() con un modelo falso: sin clave, sin red y sin gastar tokens."""
>>>>>>> upstream/main

import pytest
from pydantic import ValidationError

from litmar.resumen import ResumenArticulo, resumir

<<<<<<< HEAD

class ModeloFalso:
    """Doble de un chat model: registra el esquema, los mensajes y las llamadas."""

    def __init__(self, respuesta: ResumenArticulo | None = None) -> None:
        self.respuesta = respuesta
        self.esquemas: list[type] = []
        self.mensajes: list | None = None
        self.llamadas = 0

    def with_structured_output(self, esquema: type) -> ModeloFalso:
        self.esquemas.append(esquema)
        return self

    def invoke(self, mensajes: list) -> ResumenArticulo | None:
        self.llamadas += 1
        self.mensajes = mensajes
        return self.respuesta


def _datos_validos() -> dict:
    return {
        "objetivo": "Medir el carbono azul de la posidonia.",
        "metodo": "Muestreo de 20 praderas.",
        "hallazgos": "La pradera almacena 30 t/ha.",
        "relevancia": 4,
        "limitaciones": "Solo una estación.",
    }


def test_resumir_devuelve_el_objeto_y_envia_el_contexto(hacer_articulo) -> None:
    respuesta = ResumenArticulo(**_datos_validos())
    modelo = ModeloFalso(respuesta)
    articulo = hacer_articulo(abstract="Analizamos 20 praderas de Posidonia oceanica.")

    resultado = resumir(articulo, "¿Cómo afecta el calentamiento a la posidonia?", modelo)

    assert resultado == respuesta
    assert modelo.esquemas == [ResumenArticulo]
    assert modelo.llamadas == 1
    contenido = "\n".join(str(mensaje.content) for mensaje in modelo.mensajes)
    for parte in (
        "¿Cómo afecta el calentamiento a la posidonia?",
        articulo.title,
        articulo.doi,
        str(articulo.year),
        articulo.abstract,
    ):
        assert parte in contenido


@pytest.mark.parametrize("abstract", ["", "   ", "\n\t  "])
def test_sin_resumen_no_se_llama_al_modelo(hacer_articulo, abstract: str) -> None:
    modelo = ModeloFalso(ResumenArticulo(**_datos_validos()))

    resultado = resumir(hacer_articulo(abstract=abstract), "¿Hay carbono azul?", modelo)

    assert resultado is None
    assert modelo.esquemas == []
    assert modelo.llamadas == 0


def test_todos_los_campos_llevan_descripcion() -> None:
    for nombre, campo in ResumenArticulo.model_fields.items():
        assert campo.description, f"El campo {nombre} no tiene descripción"


@pytest.mark.parametrize("relevancia", [1, 5])
def test_la_relevancia_acepta_los_extremos(relevancia: int) -> None:
    datos = _datos_validos() | {"relevancia": relevancia}
    assert ResumenArticulo(**datos).relevancia == relevancia


@pytest.mark.parametrize("relevancia", [0, 6])
def test_la_relevancia_rechaza_valores_fuera_de_rango(relevancia: int) -> None:
    with pytest.raises(ValidationError):
        ResumenArticulo(**(_datos_validos() | {"relevancia": relevancia}))
=======
RESUMEN_FALSO = ResumenArticulo(
    objective="Clasificar textos con redes neuronales.",
    method="Redes neuronales profundas sobre un corpus de textos.",
    findings=["Las redes profundas mejoran la clasificación."],
    relevance=4,
    limitations="No consta en el resumen.",
)


class ModeloFalso:
    """Imita la parte de un modelo de chat de LangChain que usa resumir().

    Devuelve siempre la misma respuesta y apunta con qué se le llamó.
    """

    def __init__(self, respuesta=RESUMEN_FALSO):
        self.respuesta = respuesta
        self.esquema = None
        self.opciones = None
        self.llamadas = []

    def with_structured_output(self, esquema, **opciones):
        self.esquema = esquema
        self.opciones = opciones
        return self

    def invoke(self, mensajes):
        self.llamadas.append(mensajes)
        return self.respuesta


def texto_enviado(modelo):
    """Todo el texto de la única llamada que recibió el modelo."""
    assert len(modelo.llamadas) == 1
    return "\n".join(contenido for _, contenido in modelo.llamadas[0])


def test_devuelve_el_objeto_estructurado(hacer_articulo):
    modelo = ModeloFalso()

    resumen = resumir(hacer_articulo(), "¿Sirven las redes neuronales?", modelo)

    assert resumen == RESUMEN_FALSO
    assert modelo.esquema is ResumenArticulo
    assert modelo.opciones == {"method": "json_schema"}


def test_envia_pregunta_titulo_y_resumen(hacer_articulo):
    modelo = ModeloFalso()
    articulo = hacer_articulo(abstract="Estudiamos 300 praderas de Posidonia.")

    resumir(articulo, "¿Cuánto carbono almacena Posidonia?", modelo)

    texto = texto_enviado(modelo)
    assert "¿Cuánto carbono almacena Posidonia?" in texto
    assert articulo.title in texto
    assert "Estudiamos 300 praderas de Posidonia." in texto


@pytest.mark.parametrize("abstract", ["", "   \n"])
def test_sin_resumen_no_llama_al_modelo(hacer_articulo, abstract):
    modelo = ModeloFalso()

    assert resumir(hacer_articulo(abstract=abstract), "pregunta", modelo) is None
    assert modelo.llamadas == []


def test_todos_los_campos_tienen_descripcion():
    # El modelo lee las descripciones: un campo sin ella es un campo sin instrucciones.
    for nombre, campo in ResumenArticulo.model_fields.items():
        assert campo.description, f"el campo {nombre} no tiene descripción"


@pytest.mark.parametrize("relevancia", [0, 6])
def test_relevancia_fuera_de_rango_no_es_valida(relevancia):
    datos = RESUMEN_FALSO.model_dump() | {"relevance": relevancia}

    with pytest.raises(ValidationError):
        ResumenArticulo(**datos)
>>>>>>> upstream/main
