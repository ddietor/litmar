from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from litmar.fuentes import Fuente

UI = str(Path(__file__).parent.parent / "src" / "litmar" / "ui.py")


class FuenteFalsa(Fuente):
    def __init__(self, articulos=(), error=None):
        super().__init__()
        self.articulos = list(articulos)
        self.error = error

    def buscar(self, consulta, n=10, *, desde=None):
        if self.error:
            raise self.error
        return self.articulos[:n]


@pytest.fixture
def fuentes(monkeypatch, hacer_articulo):
    """Sustituye las fuentes reales: OpenAlex y Crossref comparten un DOI."""
    comun = hacer_articulo()
    fuentes = {
        "OpenAlex": FuenteFalsa([comun, hacer_articulo(doi="10.1/a", year=2019, citations=None)]),
        "Crossref": FuenteFalsa([comun, hacer_articulo(doi="10.1/b", citations=7)]),
        "arXiv": FuenteFalsa(
            error=httpx.HTTPStatusError(
                "fallo", request=httpx.Request("GET", "https://x"), response=httpx.Response(503)
            )
        ),
    }
    monkeypatch.setattr("litmar.configuracion.crear_fuente", lambda nombre: fuentes[nombre])
    monkeypatch.delenv("ZOTERO_USER_ID", raising=False)
    monkeypatch.delenv("ZOTERO_GROUP_ID", raising=False)
    return fuentes


def buscar(consulta, nombres, n=10):
    app = AppTest.from_file(UI, default_timeout=30).run()
    app.text_input[0].input(consulta)
    app.multiselect[0].set_value(nombres)
    app.number_input[0].set_value(n)
    return app.button[0].click().run()


def test_busca_en_varias_fuentes_sin_duplicar(fuentes):
    app = buscar("redes", ["OpenAlex", "Crossref"])
    assert not app.exception
    tabla = app.dataframe[0].value
    assert list(tabla.columns) == ["Año", "Citas", "Autores", "Título", "DOI"]
    assert len(tabla) == 3
    assert tabla["Citas"].iloc[1] == "No disponible"
    assert tabla["DOI"].tolist() == [
        "https://doi.org/10.1000/xyz123",
        "https://doi.org/10.1/a",
        "https://doi.org/10.1/b",
    ]
    assert app.subheader[0].value == "3 artículos"


def test_numero_de_resultados_por_fuente(fuentes):
    app = buscar("redes", ["OpenAlex"], n=1)
    assert len(app.dataframe[0].value) == 1


def test_una_fuente_que_falla_no_impide_ver_las_demas(fuentes):
    app = buscar("redes", ["OpenAlex", "arXiv"])
    assert [e.value for e in app.error] == ["arXiv respondió con HTTP 503."]
    assert len(app.dataframe[0].value) == 2


def test_consulta_vacia_no_busca(fuentes):
    app = buscar("   ", ["OpenAlex"])
    assert app.warning[0].value == "Escribe algo que buscar."
    assert not app.dataframe


def test_zotero_solo_aparece_si_esta_configurado(fuentes, monkeypatch):
    assert "Zotero" not in AppTest.from_file(UI, default_timeout=30).run().multiselect[0].options
    monkeypatch.setenv("ZOTERO_USER_ID", "123")
    assert "Zotero" in AppTest.from_file(UI, default_timeout=30).run().multiselect[0].options


# --- Pestaña «Revisión»


class ModeloFalso:
    """Para el flujo: plan y resúmenes estructurados, y un informe de texto."""

    def __init__(self, informe):
        self.informe = informe

    def with_structured_output(self, esquema, **opciones):
        return self

    def invoke(self, mensajes):
        from langchain_core.messages import AIMessage

        from litmar.flujo import Plan
        from litmar.resumen import ResumenArticulo

        texto = str(mensajes[0][1])
        if "documentalista" in texto:  # planificar
            return Plan(queries=["redes neuronales"])
        if "resume artículos" in texto:  # resumir
            return ResumenArticulo(
                objective="O", method="M", findings=["H"], relevance=4, limitations="L"
            )
        return AIMessage(content=self.informe)  # sintetizar


@pytest.fixture
def sin_llm(monkeypatch):
    for variable in ("LITMAR_MODELO", "GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def con_modelo(monkeypatch, fuentes):
    modelo = ModeloFalso("Según [doi:10.1/a] y [doi:10.9999/inventado].")
    monkeypatch.setattr("litmar.llm.crear_modelo", lambda: modelo)
    return modelo


def revisar(pregunta, modo="flujo", nombres=("OpenAlex",), n=3):
    app = AppTest.from_file(UI, default_timeout=30).run()
    app.text_area[0].input(pregunta)
    app.radio[0].set_value(modo)
    app.multiselect[1].set_value(list(nombres))
    app.number_input[1].set_value(n)
    return app.button[1].click().run()


def test_sin_modelo_dice_que_poner_en_el_env(sin_llm, fuentes):
    app = AppTest.from_file(UI, default_timeout=30).run()

    avisos = [w.value for w in app.warning]
    assert any("LITMAR_MODELO=proveedor:modelo" in aviso for aviso in avisos)
    assert app.button[1].disabled  # «Revisar» desactivado


def test_revision_con_el_flujo(con_modelo):
    app = revisar("¿Sirven las redes?")

    assert not app.exception
    pasos = [t.value for t in app.text]
    assert pasos[0].startswith("> planificar")
    assert any(p.startswith("> verificar_citas") for p in pasos)
    informe = app.markdown[-1].value
    # Los DOI citados, como enlaces; el inventado, marcado tras las reescrituras.
    assert "[doi:10.1/a](https://doi.org/10.1/a)" in informe
    assert "[doi:10.9999" not in informe and "[cita no verificada]" in informe
    assert any("reescrituras" in w.value for w in app.warning)


def test_pregunta_vacia_no_revisa(con_modelo):
    app = revisar("   ")

    assert "Escribe una pregunta." in [w.value for w in app.warning]
    assert not app.text


def test_el_limite_de_articulos_coincide_con_el_del_flujo():
    from litmar import flujo, ui

    assert ui.MAX_ARTICULOS_REVISION == flujo.MAX_SELECCIONADOS


def test_enlazar_dois():
    from litmar.flujo import enlazar_dois

    assert enlazar_dois("A [doi:10.1/x] y [cita no verificada].") == (
        "A [doi:10.1/x](https://doi.org/10.1/x) y [cita no verificada]."
    )


def test_revision_con_el_agente(con_modelo, monkeypatch, hacer_articulo):
    articulo = hacer_articulo(doi="10.1/a")
    llamadas = []

    def revisar_falso(modelo, pregunta, *, fuentes, n, mostrar):
        llamadas.append((pregunta, fuentes, n))
        mostrar("→ task(buscador): redes en OpenAlex")
        return {
            "question": pregunta,
            "selected": [articulo],
            "report": "Según [doi:10.1/a].",
            "cited": ["10.1/a"],
            "warnings": [],
        }

    monkeypatch.setattr("litmar.agente.revisar", revisar_falso)

    app = revisar("¿Sirven las redes?", modo="agente", nombres=["OpenAlex", "Crossref"], n=4)

    assert not app.exception
    assert llamadas == [("¿Sirven las redes?", ["OpenAlex", "Crossref"], 4)]
    assert [t.value for t in app.text] == ["→ task(buscador): redes en OpenAlex"]
    assert "[doi:10.1/a](https://doi.org/10.1/a)" in app.markdown[-1].value
