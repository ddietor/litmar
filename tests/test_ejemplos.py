"""El ejemplo ejemplos/resumir.py funciona con una fuente y un modelo falsos (sin red ni clave)."""

import importlib.util
from pathlib import Path

import pytest

from litmar.llm import ErrorDeConfiguracion
from litmar.resumen import ResumenArticulo

RUTA = Path(__file__).parent.parent / "ejemplos" / "resumir.py"


@pytest.fixture
def ejemplo(monkeypatch):
    """Carga el script como módulo, sin leer el .env real."""
    spec = importlib.util.spec_from_file_location("ejemplo_resumir", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    monkeypatch.setattr(modulo, "load_dotenv", lambda: None)
    return modulo


class FuenteFalsa:
    def __init__(self, articulos):
        self.articulos = articulos

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def buscar(self, consulta, n):
        return self.articulos[:n]


class ModeloFalso:
    def with_structured_output(self, esquema, **opciones):
        return self

    def invoke(self, mensajes):
        return ResumenArticulo(
            objective="Objetivo falso",
            method="Método falso",
            findings=["Hallazgo falso"],
            relevance=3,
            limitations="No consta en el resumen.",
        )


def test_resume_tres_articulos_con_resumen(ejemplo, monkeypatch, capsys, hacer_articulo):
    articulos = [hacer_articulo(doi="10.1000/sin", abstract="")] + [
        hacer_articulo(doi=f"10.1000/{i}") for i in range(5)
    ]
    monkeypatch.setattr(ejemplo, "crear_fuente", lambda nombre: FuenteFalsa(articulos))
    monkeypatch.setattr(ejemplo, "crear_modelo", ModeloFalso)

    assert ejemplo.main() == 0

    salida = capsys.readouterr().out
    assert salida.count("Objetivo falso") == 3
    assert "10.1000/sin" not in salida
    assert "https://doi.org/10.1000/0" in salida


def test_sin_configuracion_explica_el_error(ejemplo, monkeypatch, capsys):
    def sin_modelo():
        raise ErrorDeConfiguracion("Falta el modelo.")

    monkeypatch.setattr(ejemplo, "crear_modelo", sin_modelo)

    assert ejemplo.main() == 1
    assert "Falta el modelo." in capsys.readouterr().out
