<<<<<<< HEAD
"""Creación del modelo de lenguaje configurado en el entorno (ver .env.example)."""
=======
"""Creación del modelo de lenguaje a partir de la configuración.

Como con las fuentes, el resto de litmar trabaja con una interfaz común (un
modelo de chat de LangChain) y no sabe qué proveedor hay detrás. Qué modelo se
usa lo decide el `.env`:

    LITMAR_MODELO=proveedor:modelo     (p. ej. google_genai:… o anthropic:…)
    GOOGLE_API_KEY=…                   (o la clave del proveedor que elijas)
    LITMAR_LLAMADAS_POR_MINUTO=10      (opcional; 0 = sin límite)

Aquí no hay nombres de modelo ni claves: LangChain lee la clave de la variable
estándar de cada proveedor. Cambiar de modelo es cambiar una línea del `.env`.

Como el resto de la configuración (D-8), este módulo lee las variables de
entorno, no el fichero `.env`: lo carga el comando `litmar`, y un script propio
debe llamar antes a `dotenv.load_dotenv()`.
"""
>>>>>>> upstream/main

from __future__ import annotations

import os
<<<<<<< HEAD
from collections.abc import Mapping

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter

# Por debajo del límite por minuto del plan gratuito de Gemini. El cubo de
# tamaño 1 evita ráfagas: como mucho una petición cada 6 segundos.
LLAMADAS_POR_MINUTO = 10

# Cada proveedor integrado lee su clave de una variable distinta. No hay claves
# ni nombres de modelo escritos aquí: vienen del .env.
_CLAVES_PROVEEDOR = {
    "google_genai": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def crear_modelo(entorno: Mapping[str, str] | None = None) -> BaseChatModel:
    """Crea el chat model indicado en `LITMAR_MODELO` (formato `proveedor:modelo`).

    La clave exigida depende del proveedor: `GOOGLE_API_KEY` para `google_genai`,
    `ANTHROPIC_API_KEY` para `anthropic`. Si falta alguna de las dos variables,
    el error dice qué línea hay que añadir al `.env`. Cambiar de modelo no
    requiere tocar el código, solo esa variable.

    La CLI carga el `.env` antes de llamar a esta función; desde Python hay que
    cargarlo con `dotenv.load_dotenv()` o pasar un diccionario en `entorno`::

        modelo = crear_modelo()
        resumen = resumir(articulo, pregunta, modelo)

    El modelo lleva un limitador de `LLAMADAS_POR_MINUTO` peticiones sin ráfagas,
    para no superar el cupo del plan gratuito. Se comprueba con un
    `init_chat_model` falso que recibe el limitador: sin clave ni red.
    """
    entorno = os.environ if entorno is None else entorno
    configurado = entorno.get("LITMAR_MODELO", "").strip()
    if not configurado:
        raise ValueError(
            "falta LITMAR_MODELO: añade al .env una línea 'LITMAR_MODELO=proveedor:modelo' "
            f"(proveedores: {', '.join(_CLAVES_PROVEEDOR)})"
        )

    proveedor, separador, nombre = configurado.partition(":")
    proveedor, nombre = proveedor.strip(), nombre.strip()
    if not separador or not proveedor or not nombre:
        raise ValueError(
            f"LITMAR_MODELO={configurado!r} no es válido: escribe 'proveedor:modelo' en el .env"
        )

    try:
        variable_clave = _CLAVES_PROVEEDOR[proveedor]
    except KeyError:
        validos = ", ".join(_CLAVES_PROVEEDOR)
        raise ValueError(
            f"proveedor {proveedor!r} no está integrado en litmar (proveedores: {validos}); "
            "cámbialo en LITMAR_MODELO"
        ) from None

    clave = entorno.get(variable_clave, "").strip()
    if not clave:
        raise ValueError(
            f"falta {variable_clave} en el .env: añade '{variable_clave}=tu-clave' "
            f"para usar el proveedor {proveedor!r}"
        )

    limitador = InMemoryRateLimiter(
        requests_per_second=LLAMADAS_POR_MINUTO / 60,
        check_every_n_seconds=0.1,
        max_bucket_size=1,
    )
    # `init_chat_model` no consulta el diccionario `entorno`: pasar la clave
    # explícitamente hace que la fábrica real funcione también con él (tests y
    # scripts), sin depender de `os.environ`.
    return init_chat_model(f"{proveedor}:{nombre}", api_key=clave, rate_limiter=limitador)
=======

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter

VARIABLE_MODELO = "LITMAR_MODELO"
VARIABLE_LIMITE = "LITMAR_LLAMADAS_POR_MINUTO"

# Por defecto, por debajo del límite por minuto del plan gratuito de Gemini.
LLAMADAS_POR_MINUTO = 10

# Variables de las que LangChain lee la clave de cada proveedor (vale cualquiera
# de ellas). Con un proveedor que no esté aquí, la comprobación la hace LangChain.
_CLAVES = {
    "google_genai": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
}

_AYUDA = "Mira .env.example para ver un ejemplo."


class ErrorDeConfiguracion(Exception):
    """Falta o está mal algo del `.env` necesario para usar el modelo."""


def crear_modelo() -> BaseChatModel:
    """Crea el modelo indicado en `LITMAR_MODELO`, con límite de llamadas por minuto.

    Lanza `ErrorDeConfiguracion`, con un mensaje que dice qué poner en el
    `.env`, si falta el modelo, si falta la clave del proveedor o si el límite
    no es un número.
    """
    nombre = os.environ.get(VARIABLE_MODELO, "").strip()
    if not nombre:
        raise ErrorDeConfiguracion(
            f"Falta el modelo. Añade al .env una línea {VARIABLE_MODELO}=proveedor:modelo. "
            f"{_AYUDA} (Si usas litmar desde tu propio script, carga antes el .env con "
            "dotenv.load_dotenv().)"
        )
    proveedor, separador, modelo = nombre.partition(":")
    if not separador or not proveedor or not modelo:
        raise ErrorDeConfiguracion(
            f"{VARIABLE_MODELO}={nombre!r} no tiene el formato proveedor:modelo. {_AYUDA}"
        )

    variables = _CLAVES.get(proveedor, ())
    if variables and not any(os.environ.get(v, "").strip() for v in variables):
        raise ErrorDeConfiguracion(
            f"Falta la clave de {proveedor}. Añade al .env la línea {variables[0]}=tu-clave. "
            f"{_AYUDA}"
        )

    try:
        return init_chat_model(nombre, rate_limiter=_limitador(_llamadas_por_minuto()))
    except ImportError as error:
        raise ErrorDeConfiguracion(
            f"Falta el paquete de LangChain para {proveedor}: {error}"
        ) from error
    except ValueError as error:
        raise ErrorDeConfiguracion(f"{VARIABLE_MODELO}={nombre!r} no es válido: {error}") from error


def _llamadas_por_minuto() -> int:
    """Lee el límite del entorno; si no está, usa `LLAMADAS_POR_MINUTO`."""
    valor = os.environ.get(VARIABLE_LIMITE, "").strip()
    if not valor:
        return LLAMADAS_POR_MINUTO
    try:
        limite = int(valor)
    except ValueError:
        limite = -1
    if limite < 0:
        raise ErrorDeConfiguracion(
            f"{VARIABLE_LIMITE}={valor!r} debe ser un número entero (0 = sin límite)."
        )
    return limite


def _limitador(llamadas_por_minuto: int) -> InMemoryRateLimiter | None:
    """Limitador que espera lo necesario para no pasar de N llamadas por minuto.

    `max_bucket_size=1` evita ráfagas: las llamadas salen espaciadas de forma
    regular (con 10 por minuto, una cada 6 s), en lugar de 10 seguidas y luego
    un 429.
    """
    if llamadas_por_minuto == 0:
        return None
    return InMemoryRateLimiter(
        requests_per_second=llamadas_por_minuto / 60,
        check_every_n_seconds=0.1,
        max_bucket_size=1,
    )
>>>>>>> upstream/main
