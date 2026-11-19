"""Interfaz web de litmar con Streamlit. Se abre con `litmar ui`."""

from __future__ import annotations

import streamlit as st

from litmar import llm
from litmar.biblioteca import Biblioteca
from litmar.busqueda import buscar_en_fuentes
from litmar.configuracion import fuentes_disponibles

MAX_RESULTADOS = 200
MAX_ARTICULOS_REVISION = 10  # el mismo límite que flujo.MAX_SELECCIONADOS


def filas(biblioteca: Biblioteca) -> list[dict[str, object]]:
    """Filas de la tabla de resultados."""
    return [
        {
            "Año": articulo.year,
            "Citas": (articulo.citations if articulo.citations is not None else "No disponible"),
            "Autores": "; ".join(articulo.authors),
            "Título": articulo.title,
            "DOI": f"https://doi.org/{articulo.doi}",
        }
        for articulo in biblioteca
    ]


def app() -> None:
    st.set_page_config(page_title="litmar", page_icon="📚", layout="wide")
    st.title("litmar")
    st.caption("Busca literatura científica en varias fuentes y exporta las referencias.")
    pestana_busqueda, pestana_revision = st.tabs(["Búsqueda", "Revisión"])
    with pestana_busqueda:
        busqueda()
    with pestana_revision:
        revision()


def busqueda() -> None:
    """Pestaña «Búsqueda»: buscar en varias fuentes, ver la tabla y descargar."""
    disponibles = fuentes_disponibles()
    with st.form("busqueda"):
        consulta = st.text_input("Búsqueda", placeholder="ocean acidification")
        nombres = st.multiselect("Fuentes", disponibles, default=["OpenAlex"])
        n = st.number_input(
            "Resultados por fuente", min_value=1, max_value=MAX_RESULTADOS, value=10
        )
        enviado = st.form_submit_button("Buscar", type="primary")
    if "Zotero" not in disponibles:
        st.caption("Para buscar en Zotero, indica ZOTERO_USER_ID o ZOTERO_GROUP_ID en `.env`.")

    if enviado:
        if not consulta.strip():
            st.warning("Escribe algo que buscar.")
        elif not nombres:
            st.warning("Elige al menos una fuente.")
        else:
            with st.spinner("Buscando…"):
                # Se guarda en la sesión para que sobreviva a las recargas que
                # provocan los botones de descarga.
                st.session_state.resultado = buscar_en_fuentes(consulta.strip(), nombres, int(n))

    if "resultado" not in st.session_state:
        return
    resultado = st.session_state.resultado
    biblioteca = resultado.library
    for error in resultado.errors:
        st.error(error)
    if not len(biblioteca):
        st.info("No hay resultados.")
        return

    st.subheader(f"{len(biblioteca)} artículos")
    st.dataframe(
        filas(biblioteca),
        hide_index=True,
        width="stretch",
        column_config={
            "Año": st.column_config.NumberColumn(format="%d"),
            "DOI": st.column_config.LinkColumn(display_text=r"https://doi\.org/(.*)"),
        },
    )
    bibtex, csv = st.columns(2)
    bibtex.download_button(
        "Descargar BibTeX",
        biblioteca.a_bibtex(),
        file_name="litmar.bib",
        mime="application/x-bibtex",
        width="stretch",
    )
    csv.download_button(
        "Descargar CSV",
        # Con BOM para que Excel reconozca el UTF-8 (tildes, eñes...).
        biblioteca.a_csv().encode("utf-8-sig"),
        file_name="litmar.csv",
        mime="text/csv",
        width="stretch",
    )


def revision() -> None:
    """Pestaña «Revisión»: una pregunta → un informe que solo cita artículos reales.

    Reutiliza `flujo.revisar` y `agente.revisar`, las mismas funciones que
    `litmar revisar`: cada paso llega por `mostrar` y se escribe en pantalla en
    cuanto ocurre.
    """
    st.caption(
        "Haz una pregunta de investigación: litmar busca, lee y escribe un informe que solo "
        "cita artículos reales, con el BibTeX de lo citado."
    )
    try:
        modelo = llm.crear_modelo()
    except llm.ErrorDeConfiguracion as exc:
        modelo = None
        st.warning(f"La revisión necesita un modelo de lenguaje. {exc}")

    disponibles = fuentes_disponibles()
    with st.form("revision"):
        pregunta = st.text_area(
            "Pregunta de investigación",
            placeholder="¿Cómo afecta el calentamiento a las praderas de Posidonia oceanica?",
        )
        modo = st.radio(
            "Modo",
            ["flujo", "agente"],
            horizontal=True,
            captions=["Pasos fijos: más rápido y predecible.", "El modelo decide qué buscar."],
        )
        nombres = st.multiselect(
            "Fuentes",
            disponibles,
            default=[f for f in ("OpenAlex", "Europe PMC") if f in disponibles],
            key="fuentes_revision",
        )
        n = st.number_input(
            "Número de artículos", min_value=1, max_value=MAX_ARTICULOS_REVISION, value=6
        )
        enviado = st.form_submit_button("Revisar", type="primary", disabled=modelo is None)

    if enviado:
        if not pregunta.strip():
            st.warning("Escribe una pregunta.")
        elif not nombres:
            st.warning("Elige al menos una fuente.")
        else:
            _revisar(modelo, pregunta.strip(), modo, nombres, int(n))

    if "resultado_revision" not in st.session_state:
        return
    resultado = st.session_state.resultado_revision
    for aviso in resultado["avisos"]:
        st.warning(aviso)
    # Los DOI citados, como enlaces a doi.org.
    st.markdown(resultado["informe_enlazado"])
    informe, bibtex = st.columns(2)
    informe.download_button(
        "Descargar informe (Markdown)",
        resultado["informe"],
        file_name="revision.md",
        mime="text/markdown",
        width="stretch",
    )
    bibtex.download_button(
        f"Descargar BibTeX ({resultado['citados']} citados)",
        resultado["bibtex"],
        file_name="revision.bib",
        mime="application/x-bibtex",
        width="stretch",
    )


def _revisar(modelo, pregunta: str, modo: str, fuentes: list[str], n: int) -> None:
    """Ejecuta la revisión mostrando los pasos en vivo y guarda el resultado en la sesión."""
    # Se importan aquí: LangGraph y Deep Agents tardan en cargar y la pestaña de
    # búsqueda no los necesita.
    from litmar import agente, flujo

    revisar = flujo.revisar if modo == "flujo" else agente.revisar
    st.session_state.pop("resultado_revision", None)
    with st.status(f"Revisando ({modo})…", expanded=True) as progreso:
        try:
            estado = revisar(modelo, pregunta, fuentes=fuentes, n=n, mostrar=progreso.text)
        except Exception as exc:  # p. ej. un 429 del proveedor
            progreso.update(label="La revisión no ha terminado", state="error")
            st.error(f"Error del modelo: {type(exc).__name__}: {exc}")
            return
        progreso.update(label="Revisión terminada", state="complete", expanded=False)

    informe = flujo.informe_markdown(estado)
    citados = flujo.citados(estado)
    # Se guarda en la sesión para que sobreviva a las recargas de las descargas.
    st.session_state.resultado_revision = {
        "informe": informe,
        "informe_enlazado": flujo.enlazar_dois(informe),
        "bibtex": citados.a_bibtex(),
        "citados": len(citados),
        "avisos": list(estado.get("warnings", [])),
    }


if __name__ == "__main__":
    app()
