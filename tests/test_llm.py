"""Tests de crear_modelo(): solo crean el objeto del modelo, sin llamarlo (sin red)."""

import pytest
from langchain_core.language_models import BaseChatModel

from litmar.llm import LLAMADAS_POR_MINUTO, ErrorDeConfiguracion, crear_modelo

VARIABLES = [
    "LITMAR_MODELO",
    "LITMAR_LLAMADAS_POR_MINUTO",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
]


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    """Que ninguna variable real del entorno de quien ejecuta los tests influya."""
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)


@pytest.mark.parametrize(
    ("modelo", "variable_clave"),
    [
        ("anthropic:modelo-de-prueba", "ANTHROPIC_API_KEY"),
        ("google_genai:modelo-de-prueba", "GOOGLE_API_KEY"),
        ("google_genai:modelo-de-prueba", "GEMINI_API_KEY"),
    ],
)
def test_crea_el_modelo_del_env(monkeypatch, modelo, variable_clave):
    monkeypatch.setenv("LITMAR_MODELO", modelo)
    monkeypatch.setenv(variable_clave, "clave-falsa")

    llm = crear_modelo()

    assert isinstance(llm, BaseChatModel)
    assert "modelo-de-prueba" in str(llm.model_dump())


def test_limite_por_defecto(monkeypatch):
    monkeypatch.setenv("LITMAR_MODELO", "anthropic:modelo-de-prueba")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-falsa")

    limitador = crear_modelo().rate_limiter

    assert limitador.requests_per_second == pytest.approx(LLAMADAS_POR_MINUTO / 60)


def test_limite_configurable_y_cero_es_sin_limite(monkeypatch):
    monkeypatch.setenv("LITMAR_MODELO", "anthropic:modelo-de-prueba")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-falsa")

    monkeypatch.setenv("LITMAR_LLAMADAS_POR_MINUTO", "30")
    assert crear_modelo().rate_limiter.requests_per_second == pytest.approx(0.5)

    monkeypatch.setenv("LITMAR_LLAMADAS_POR_MINUTO", "0")
    assert crear_modelo().rate_limiter is None


@pytest.mark.parametrize("valor", ["muchas", "-1", "2.5"])
def test_limite_no_valido(monkeypatch, valor):
    monkeypatch.setenv("LITMAR_MODELO", "anthropic:modelo-de-prueba")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-falsa")
    monkeypatch.setenv("LITMAR_LLAMADAS_POR_MINUTO", valor)

    with pytest.raises(ErrorDeConfiguracion, match="LITMAR_LLAMADAS_POR_MINUTO"):
        crear_modelo()


def test_sin_modelo_dice_que_poner_en_el_env():
    with pytest.raises(ErrorDeConfiguracion, match=r"LITMAR_MODELO=proveedor:modelo"):
        crear_modelo()


@pytest.mark.parametrize("valor", ["solo-un-nombre", ":modelo", "anthropic:"])
def test_modelo_sin_formato_proveedor(monkeypatch, valor):
    monkeypatch.setenv("LITMAR_MODELO", valor)

    with pytest.raises(ErrorDeConfiguracion, match="proveedor:modelo"):
        crear_modelo()


@pytest.mark.parametrize(
    ("modelo", "linea"),
    [
        ("google_genai:modelo-de-prueba", "GOOGLE_API_KEY=tu-clave"),
        ("anthropic:modelo-de-prueba", "ANTHROPIC_API_KEY=tu-clave"),
    ],
)
def test_sin_clave_dice_que_poner_en_el_env(monkeypatch, modelo, linea):
    monkeypatch.setenv("LITMAR_MODELO", modelo)

    with pytest.raises(ErrorDeConfiguracion, match=linea):
        crear_modelo()


def test_clave_vacia_cuenta_como_falta(monkeypatch):
    monkeypatch.setenv("LITMAR_MODELO", "anthropic:modelo-de-prueba")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "  ")

    with pytest.raises(ErrorDeConfiguracion, match="Falta la clave"):
        crear_modelo()


def test_proveedor_desconocido(monkeypatch):
    monkeypatch.setenv("LITMAR_MODELO", "proveedor_inventado:modelo")

    with pytest.raises(ErrorDeConfiguracion, match="no es válido"):
        crear_modelo()
