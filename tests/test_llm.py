"""Tests de `crear_modelo`: sin clave real, sin red y sin llamadas al proveedor."""

from __future__ import annotations

import pytest

from litmar.llm import LLAMADAS_POR_MINUTO, crear_modelo

PROVEEDORES = [("google_genai", "GOOGLE_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")]


class FabricaFalsa:
    """Sustituye a `init_chat_model` y guarda con qué argumentos se le llama."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[str, dict]] = []

    def __call__(self, modelo: str, **opciones):
        self.llamadas.append((modelo, opciones))
        return "modelo-falso"


@pytest.fixture
def fabrica(monkeypatch) -> FabricaFalsa:
    falsa = FabricaFalsa()
    monkeypatch.setattr("litmar.llm.init_chat_model", falsa)
    return falsa


@pytest.mark.parametrize(("proveedor", "variable"), PROVEEDORES)
def test_crear_modelo_pasa_el_modelo_y_el_limitador(
    fabrica: FabricaFalsa, proveedor: str, variable: str
) -> None:
    entorno = {"LITMAR_MODELO": f"{proveedor}:modelo-de-prueba", variable: "clave-de-prueba"}

    assert crear_modelo(entorno) == "modelo-falso"
    assert len(fabrica.llamadas) == 1
    modelo, opciones = fabrica.llamadas[0]
    assert modelo == f"{proveedor}:modelo-de-prueba"
    # init_chat_model lee os.environ, no nosso diccionario: hay que pasar la clave.
    assert opciones["api_key"] == "clave-de-prueba"

    limitador = opciones["rate_limiter"]
    assert limitador.requests_per_second == pytest.approx(LLAMADAS_POR_MINUTO / 60)
    assert limitador.max_bucket_size == 1


def test_cambiar_de_proveedor_solo_cambia_el_entorno(fabrica: FabricaFalsa) -> None:
    con_google = {"LITMAR_MODELO": "google_genai:uno", "GOOGLE_API_KEY": "x"}
    con_anthropic = {"LITMAR_MODELO": "anthropic:dos", "ANTHROPIC_API_KEY": "x"}

    crear_modelo(con_google)
    crear_modelo(con_anthropic)

    assert [llamada[0] for llamada in fabrica.llamadas] == [
        "google_genai:uno",
        "anthropic:dos",
    ]


def test_el_modelo_se_lee_con_espacios_recortados(fabrica: FabricaFalsa) -> None:
    entorno = {"LITMAR_MODELO": "  google_genai:modelo  ", "GOOGLE_API_KEY": "x"}

    crear_modelo(entorno)

    assert fabrica.llamadas[0][0] == "google_genai:modelo"


def test_sin_litmar_modelo_el_error_dice_que_poner_en_el_env(fabrica: FabricaFalsa) -> None:
    with pytest.raises(ValueError) as como_error:
        crear_modelo({})

    mensaje = str(como_error.value)
    assert "LITMAR_MODELO" in mensaje
    assert ".env" in mensaje
    assert "proveedor:modelo" in mensaje
    assert fabrica.llamadas == []


@pytest.mark.parametrize("configurado", ["google_genai", ":modelo", "google_genai:"])
def test_modelo_mal_escrito(fabrica: FabricaFalsa, configurado: str) -> None:
    with pytest.raises(ValueError, match="no es válido"):
        crear_modelo({"LITMAR_MODELO": configurado})

    assert fabrica.llamadas == []


@pytest.mark.parametrize(("proveedor", "variable"), PROVEEDORES)
def test_sin_clave_el_error_dice_que_variable_añadir(
    fabrica: FabricaFalsa, proveedor: str, variable: str
) -> None:
    with pytest.raises(ValueError) as como_error:
        crear_modelo({"LITMAR_MODELO": f"{proveedor}:modelo-de-prueba"})

    mensaje = str(como_error.value)
    assert variable in mensaje
    assert f"{variable}=tu-clave" in mensaje
    assert ".env" in mensaje
    assert fabrica.llamadas == []


@pytest.mark.parametrize("valor", ["", "   "])
def test_una_clave_vacía_cuenta_como_faltante(fabrica: FabricaFalsa, valor: str) -> None:
    entorno = {"LITMAR_MODELO": "google_genai:modelo-de-prueba", "GOOGLE_API_KEY": valor}

    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        crear_modelo(entorno)

    assert fabrica.llamadas == []


def test_proveedor_no_integrado(fabrica: FabricaFalsa) -> None:
    with pytest.raises(ValueError) as como_error:
        crear_modelo({"LITMAR_MODELO": "otro:modelo", "GOOGLE_API_KEY": "x"})

    mensaje = str(como_error.value)
    assert "otro" in mensaje
    assert "google_genai" in mensaje
    assert "anthropic" in mensaje
    assert fabrica.llamadas == []
