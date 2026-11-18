"""Tests del flujo de revisión: modelo y fuentes falsos, sin clave ni red."""

from __future__ import annotations

import pytest

from litmar.flujo import (
    MAX_INTENTOS_SINTESIS,
    POR_FUENTE,
    InformeRedaccion,
    PlanBusqueda,
    biblioteca_de_citas,
    buscar,
    crear_grafo,
    decidir,
    estado_inicial,
    extraer_citas,
    filtrar,
    planificar,
    resumir_articulos,
    sintetizar,
    verificar_citas,
)
from litmar.fuentes import Fuente
from litmar.resumen import ResumenArticulo


class ModeloFalso:
    """Doble de un chat model: devuelve un objeto distinto según el esquema."""

    def __init__(self, informes=(), consultas=("posidonia carbono", "carbono azul praderas")):
        self.informes = list(informes) or ["Informe sin citas."]
        self.consultas = list(consultas)
        self.esquemas: list[type] = []
        self.llamadas = 0
        self.informes_vistos: list[str] = []

    def with_structured_output(self, esquema: type):
        self.esquemas.append(esquema)
        return self

    def invoke(self, mensajes: list):
        self.llamadas += 1
        esquema = self.esquemas[-1]
        contenido = "\n".join(str(mensaje.content) for mensaje in mensajes)
        if esquema is PlanBusqueda:
            return PlanBusqueda(consultas=self.consultas)
        if esquema is ResumenArticulo:
            return ResumenArticulo(
                objetivo="Objetivo leído en el resumen.",
                metodo="Método leído en el resumen.",
                hallazgos="Hallazgos leídos en el resumen.",
                relevancia=5,
                limitaciones="Sin limitaciones declaradas.",
            )
        if esquema is InformeRedaccion:
            self.informes_vistos.append(contenido)
            indice = min(len(self.informes_vistos) - 1, len(self.informes) - 1)
            return InformeRedaccion(texto=self.informes[indice])
        raise AssertionError(f"Esquema inesperado: {esquema}")


class FuenteFija(Fuente):
    """Fuente sin red que devuelve siempre los mismos artículos."""

    def __init__(self, articulos=()):
        super().__init__()
        self.articulos = list(articulos)
        self.llamadas = []

    def buscar(self, consulta, n=10, *, desde=None):
        self.llamadas.append((consulta, n, desde))
        return [a for a in self.articulos if desde is None or a.year >= desde][:n]


@pytest.fixture
def fuentes(hacer_articulo):
    """OpenAlex y Europe PMC comparten un artículo; uno no tiene resumen."""
    bueno = hacer_articulo(doi="10.1000/bueno", citations=20, abstract="Resumen del bueno.")
    mediano = hacer_articulo(doi="10.1000/mediano", citations=5, abstract="Resumen del mediano.")
    sin_resumen = hacer_articulo(doi="10.1000/sin", citations=100, abstract="")
    return {
        "OpenAlex": FuenteFija([bueno, sin_resumen]),
        "Europe PMC": FuenteFija([bueno, mediano]),
    }


def _crear(fuentes):
    return lambda nombre: fuentes[nombre]


def test_el_grafo_tiene_los_seis_nodos_y_el_bucle_de_citas():
    grafo = crear_grafo(ModeloFalso()).get_graph()
    assert set(grafo.nodes) - {"__start__", "__end__"} == {
        "planificar",
        "buscar",
        "filtrar",
        "resumir_articulos",
        "sintetizar",
        "verificar_citas",
    }
    aristas = {(arista.source, arista.target) for arista in grafo.edges}
    for esperada in (
        ("__start__", "planificar"),
        ("planificar", "buscar"),
        ("buscar", "filtrar"),
        ("filtrar", "resumir_articulos"),
        ("resumir_articulos", "sintetizar"),
        ("sintetizar", "verificar_citas"),
    ):
        assert esperada in aristas
    condicionales = {(arista.source, arista.target) for arista in grafo.edges if arista.conditional}
    assert condicionales == {
        ("verificar_citas", "sintetizar"),
        ("verificar_citas", "__end__"),
    }


def test_planificar_recorta_vacias_repeticiones_y_excesos():
    modelo = ModeloFalso(
        consultas=["  posidonia  ", "", "posidonia", "carbono azul", "otra", "cuarta"]
    )
    estado = estado_inicial("¿Qué papel tiene la posidonia?", ["OpenAlex"])

    resultado = planificar(estado, modelo=modelo)

    assert resultado["consultas"] == ["posidonia", "carbono azul", "otra"]
    assert resultado["traza"] == "3 consultas"
    assert modelo.llamadas == 1


def test_planificar_con_una_sola_consulta_añade_la_pregunta():
    modelo = ModeloFalso(consultas=["posidonia"])
    estado = estado_inicial("¿Carbono azul?", ["OpenAlex"])
    assert planificar(estado, modelo=modelo)["consultas"] == ["posidonia", "¿Carbono azul?"]


def test_buscar_y_filtrar_son_codigo_y_deduplican(fuentes):
    modelo = ModeloFalso()
    estado = estado_inicial("¿Carbono?", ["OpenAlex", "Europe PMC"], n=5)
    estado["consultas"] = ["q1", "q2"]

    encontrados = buscar(estado, crear=_crear(fuentes))
    filtrado = filtrar({**estado, **encontrados})

    assert modelo.llamadas == 0  # ninguno de los dos nodos usa el modelo
    assert [a.doi for a in encontrados["encontrados"]] == [
        "10.1000/bueno",
        "10.1000/sin",
        "10.1000/mediano",
    ]
    assert [a.doi for a in filtrado["seleccionados"]] == ["10.1000/bueno", "10.1000/mediano"]
    assert any("sin resumen descartados" in aviso for aviso in filtrado["avisos"])
    for fuente in fuentes.values():
        assert len(fuente.llamadas) == 2
        assert all(llamada[1] == POR_FUENTE and llamada[2] is None for llamada in fuente.llamadas)


def test_filtrar_no_supera_el_tope_de_seleccionados(hacer_articulo):
    estado = estado_inicial("p", ["OpenAlex"], n=100)
    estado["encontrados"] = [
        hacer_articulo(doi=f"10.1000/n{i}", abstract="Resumen.") for i in range(10)
    ]
    assert len(filtrar(estado)["seleccionados"]) == 6


def test_resumir_articulos_llama_una_vez_por_seleccionado(fuentes):
    modelo = ModeloFalso()
    estado = estado_inicial("¿Carbono?", ["OpenAlex", "Europe PMC"], n=3)
    estado["consultas"] = ["q"]
    estado.update(buscar(estado, crear=_crear(fuentes)))
    estado.update(filtrar(estado))

    resultado = resumir_articulos(estado, modelo=modelo)

    assert set(resultado["resumenes"]) == {"10.1000/bueno", "10.1000/mediano"}
    assert modelo.llamadas == 2
    assert resultado["traza"] == "2 resúmenes"


def test_extraer_citas_normaliza_y_no_repite():
    texto = "Uno [10.1000/ABC], dos [https://doi.org/10.1000/abc] y tres [García 2021]."
    assert extraer_citas(texto) == ["10.1000/abc", "García 2021"]


def test_verificar_citas_detecta_un_doi_inventado(hacer_articulo):
    estado = estado_inicial("p", ["OpenAlex"])
    estado["seleccionados"] = [hacer_articulo(doi="10.1000/xyz123")]
    estado["intentos_sintesis"] = 1
    estado["informe"] = (
        "Hallazgo [10.1000/xyz123], inventado [10.9999/falso] y "
        "repetido [https://doi.org/10.1000/XYZ123]."
    )

    resultado = verificar_citas(estado)

    assert resultado["citas"] == ["10.1000/xyz123", "10.9999/falso"]
    assert resultado["citaciones_invalidas"] == ["10.9999/falso"]
    assert "1 cita inválida → reescribir" in resultado["traza"]
    assert decidir({**estado, **resultado}) == "reescribir"

    estado["informe"] = "Solo una cita [10.1000/xyz123]."
    assert verificar_citas(estado)["traza"] == "ok (1 cita)"


def test_decidir_para_tras_tres_escrituras():
    estado = estado_inicial("p", ["OpenAlex"])
    estado["citaciones_invalidas"] = ["10.9999/falso"]
    estado["intentos_sintesis"] = MAX_INTENTOS_SINTESIS
    assert decidir(estado) == "fin"


def test_biblioteca_de_citas_solo_incluye_lo_citado_valido(hacer_articulo):
    estado = estado_inicial("p", ["OpenAlex"])
    estado["seleccionados"] = [
        hacer_articulo(doi="10.1000/uno"),
        hacer_articulo(doi="10.1000/dos"),
    ]
    estado["citas"] = ["10.1000/uno", "10.1000/uno", "10.9999/falso"]

    biblioteca = biblioteca_de_citas(estado)

    assert [articulo.doi for articulo in biblioteca] == ["10.1000/uno"]


def test_sintetizar_incluye_los_resumenes_y_el_feedback(fuentes):
    modelo = ModeloFalso(informes=["primer informe"])
    estado = estado_inicial("¿Carbono?", ["OpenAlex"], n=2)
    estado["consultas"] = ["q"]
    estado.update(buscar(estado, crear=_crear(fuentes)))
    estado.update(filtrar(estado))
    estado.update(resumir_articulos(estado, modelo=modelo))
    estado["citaciones_invalidas"] = ["10.9999/falso"]

    resultado = sintetizar(estado, modelo=modelo)

    contenido = modelo.informes_vistos[0]
    assert "¿Carbono?" in contenido
    assert "Hallazgos leídos en el resumen." in contenido
    assert "[10.1000/bueno]" in contenido
    assert "no están en la lista: 10.9999/falso" in contenido
    assert resultado["intentos_sintesis"] == 1


def test_el_bucle_reescribe_como_maximo_dos_veces(fuentes, hacer_articulo):
    modelo = ModeloFalso(
        informes=[
            "Primero [10.9999/falso].",
            "Segundo [10.8888/falso].",
            "Tercero [10.1000/bueno].",
        ],
        consultas=["posidonia"],
    )
    grafo = crear_grafo(modelo, crear=_crear(fuentes))
    estado = estado_inicial("¿Carbono?", ["OpenAlex", "Europe PMC"], n=3)

    resultado = grafo.invoke(estado, config={"recursion_limit": 20})

    assert resultado["intentos_sintesis"] == 3  # una escritura + dos reescrituras
    assert resultado["informe"] == "Tercero [10.1000/bueno]."
    assert resultado["citaciones_invalidas"] == []
    assert sum("no están en la lista" in texto for texto in modelo.informes_vistos) == 2
    assert [articulo.doi for articulo in biblioteca_de_citas(resultado)] == ["10.1000/bueno"]


def test_si_no_se_corrige_guarda_lo_valido_y_avisa(fuentes):
    modelo = ModeloFalso(informes=["Siempre [10.9999/falso]."], consultas=["q"])
    grafo = crear_grafo(modelo, crear=_crear(fuentes))
    estado = estado_inicial("¿Carbono?", ["OpenAlex", "Europe PMC"], n=3)

    resultado = grafo.invoke(estado, config={"recursion_limit": 20})

    assert resultado["intentos_sintesis"] == 3
    assert resultado["citaciones_invalidas"] == ["10.9999/falso"]
    assert any("Quedan citas no verificadas tras 2 reescrituras" in a for a in resultado["avisos"])
    assert len(biblioteca_de_citas(resultado)) == 0
    assert isinstance(resultado["informe"], str)


def test_el_stream_emite_un_paso_por_nodo(fuentes):
    modelo = ModeloFalso(informes=["Válido [10.1000/bueno]."], consultas=["q1", "q2"])
    grafo = crear_grafo(modelo, crear=_crear(fuentes))
    estado = estado_inicial("¿Carbono?", ["OpenAlex", "Europe PMC"], n=3)

    pasos = [
        nombre
        for fragmento in grafo.stream(estado, config={"recursion_limit": 20}, stream_mode="updates")
        for nombre in fragmento
    ]

    assert pasos == [
        "planificar",
        "buscar",
        "filtrar",
        "resumir_articulos",
        "sintetizar",
        "verificar_citas",
    ]
