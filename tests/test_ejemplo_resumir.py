"""Tests del ejemplo `ejemplos/resumir.py`, sin red ni modelo real."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from litmar import Articulo, Biblioteca, ResumenArticulo
from litmar.busqueda import Resultado
from litmar.configuracion import FUENTES as FUENTES_VALIDAS

RUTA_EJEMPLO = Path(__file__).resolve().parents[1] / "ejemplos" / "resumir.py"


def cargar_ejemplo() -> ModuleType:
    """Carga el script como módulo para poder sustituir sus dependencias."""
    especificacion = importlib.util.spec_from_file_location("ejemplo_resumir", RUTA_EJEMPLO)
    assert especificacion is not None and especificacion.loader is not None
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def resumen_falso(titulo: str) -> ResumenArticulo:
    return ResumenArticulo(
        objetivo=f"Objetivo de {titulo}",
        metodo=f"Método de {titulo}",
        hallazgos=f"Hallazgos de {titulo}",
        relevancia=4,
        limitaciones=f"Limitaciones de {titulo}",
    )


@pytest.fixture
def ejemplo(monkeypatch) -> ModuleType:
    modulo = cargar_ejemplo()
    # El ejemplo se ejecuta fuera de la CLI: comprobamos que carga el .env, pero
    # no dejamos que lea el del usuario ni que consulte red o modelo reales.
    monkeypatch.setattr(modulo, "find_dotenv", lambda **_: ".env-de-prueba")
    monkeypatch.setattr(modulo, "load_dotenv", lambda ruta: None)
    return modulo


def test_las_fuentes_del_ejemplo_son_nombres_validos(ejemplo: ModuleType) -> None:
    assert ejemplo.FUENTES == ("OpenAlex", "Europe PMC")
    assert set(ejemplo.FUENTES) <= set(FUENTES_VALIDAS)


def test_resume_tres_articulos(ejemplo: ModuleType, monkeypatch, capsys, hacer_articulo) -> None:
    articulos = [hacer_articulo(title=f"Artículo {i}", doi=f"10.1000/ejemplo{i}") for i in range(3)]
    monkeypatch.setattr(ejemplo, "crear_modelo", lambda: "modelo-falso")
    monkeypatch.setattr(
        ejemplo,
        "buscar_en_fuentes",
        lambda consulta, fuentes, n: Resultado(library=Biblioteca(articulos)),
    )
    llamadas: list[tuple[Articulo, str, str]] = []

    def falsificar_resumir(articulo, pregunta, modelo) -> ResumenArticulo:
        llamadas.append((articulo, pregunta, modelo))
        return resumen_falso(articulo.title)

    monkeypatch.setattr(ejemplo, "resumir", falsificar_resumir)

    ejemplo.main()

    salida = capsys.readouterr().out
    assert len(llamadas) == 3
    assert [articulo.title for articulo, _, _ in llamadas] == [
        "Artículo 0",
        "Artículo 1",
        "Artículo 2",
    ]
    assert all(
        pregunta == ejemplo.PREGUNTA and modelo == "modelo-falso"
        for _, pregunta, modelo in llamadas
    )
    assert "Hallazgos de Artículo 0" in salida
    assert "Relevancia:   4/5" in salida
    assert "DOI: https://doi.org/10.1000/ejemplo2" in salida


def test_busca_con_las_fuentes_y_el_numero_configurados(
    ejemplo: ModuleType, monkeypatch, hacer_articulo
) -> None:
    consultas: list[tuple[str, tuple[str, ...], int]] = []
    monkeypatch.setattr(ejemplo, "crear_modelo", lambda: "modelo-falso")

    def falsificar_busqueda(consulta, fuentes, n) -> Resultado:
        consultas.append((consulta, fuentes, n))
        return Resultado(library=Biblioteca([hacer_articulo()]))

    monkeypatch.setattr(ejemplo, "buscar_en_fuentes", falsificar_busqueda)
    monkeypatch.setattr(ejemplo, "resumir", lambda a, p, m: resumen_falso(a.title))

    ejemplo.main()

    assert consultas == [(ejemplo.CONSULTA, ejemplo.FUENTES, 3)]


def test_avisa_de_fuentes_que_fallan_y_de_articulos_sin_resumen(
    ejemplo: ModuleType, monkeypatch, capsys, hacer_articulo
) -> None:
    monkeypatch.setattr(ejemplo, "crear_modelo", lambda: "modelo-falso")
    monkeypatch.setattr(
        ejemplo,
        "buscar_en_fuentes",
        lambda consulta, fuentes, n: Resultado(
            library=Biblioteca([hacer_articulo(abstract="")]),
            errors=["OpenAlex respondió con HTTP 503."],
        ),
    )
    monkeypatch.setattr(ejemplo, "resumir", lambda a, p, m: None)

    ejemplo.main()

    salida = capsys.readouterr().out
    assert "Resumen de 1 artículo para" in salida
    assert "Aviso: OpenAlex respondió con HTTP 503." in salida
    assert "Sin resumen: el artículo no tiene abstract" in salida


def test_sin_resultados_no_llama_al_modelo(ejemplo: ModuleType, monkeypatch, capsys) -> None:
    monkeypatch.setattr(ejemplo, "crear_modelo", lambda: "modelo-falso")
    monkeypatch.setattr(ejemplo, "buscar_en_fuentes", lambda consulta, fuentes, n: Resultado())
    monkeypatch.setattr(ejemplo, "resumir", lambda a, p, m: pytest.fail("no debe resumir"))

    ejemplo.main()

    assert "No se encontraron artículos" in capsys.readouterr().out


def test_sin_modelo_explica_que_poner_en_el_env(ejemplo: ModuleType, monkeypatch) -> None:
    def fallar() -> None:
        raise ValueError("falta LITMAR_MODELO: añade al .env una línea ...")

    monkeypatch.setattr(ejemplo, "crear_modelo", fallar)

    with pytest.raises(SystemExit, match="falta LITMAR_MODELO") as salida:
        ejemplo.main()

    assert "No se pudo crear el modelo" in str(salida.value)
