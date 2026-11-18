"""Creación del modelo de lenguaje configurado en el entorno (ver .env.example)."""

from __future__ import annotations

import os
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
