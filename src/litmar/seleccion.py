"""Criterio compartido para seleccionar artículos de una revisión."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from litmar.articulo import Articulo

PESO_RELEVANCIA = 0.7
PESO_CITAS = 0.3


def tasa_anualizada(articulo: Articulo, anio_actual: int | None = None) -> float | None:
    """Citas por año desde la publicación; None si la fuente no da el recuento."""
    if articulo.citations is None:
        return None
    anio_actual = date.today().year if anio_actual is None else anio_actual
    edad = max(1, anio_actual - articulo.year + 1)
    return articulo.citations / edad


def puntuacion_citas(articulo: Articulo, anio_actual: int | None = None) -> float | None:
    """Normaliza la tasa anualizada a una escala de 1 a 5, con saturación."""
    tasa = tasa_anualizada(articulo, anio_actual)
    if tasa is None:
        return None
    return 1 + 4 * tasa / (1 + tasa)


def puntuacion_combinada(
    articulo: Articulo, relevancia: int, anio_actual: int | None = None
) -> float:
    """Combina relevancia (70 %) y puntuación de citas ajustada (30 %)."""
    if not 1 <= relevancia <= 5:
        raise ValueError("la relevancia debe estar entre 1 y 5")
    citas = puntuacion_citas(articulo, anio_actual)
    if citas is None:
        return float(relevancia)
    return PESO_RELEVANCIA * relevancia + PESO_CITAS * citas


def ordenar_articulos(
    articulos: Iterable[Articulo],
    relevancias: Mapping[str, int],
    anio_actual: int | None = None,
) -> list[Articulo]:
    """Ordena artículos con resumen por puntuación combinada, de mayor a menor."""
    candidatos = [
        articulo
        for articulo in articulos
        if articulo.abstract.strip() and articulo.doi in relevancias
    ]
    return sorted(
        candidatos,
        key=lambda articulo: puntuacion_combinada(articulo, relevancias[articulo.doi], anio_actual),
        reverse=True,
    )


def describir_citas(articulo: Articulo, anio_actual: int | None = None) -> str:
    """Texto de citas para modelos e interfaces, indicando explícitamente si falta el dato."""
    tasa = tasa_anualizada(articulo, anio_actual)
    if tasa is None:
        return "Citas: no disponible; selección basada solo en relevancia."
    puntuacion = puntuacion_citas(articulo, anio_actual)
    return (
        f"Citas: {articulo.citations} | Citas/año: {tasa:.2f} | "
        f"Ajuste por citas: {puntuacion:.2f}/5"
    )


def aviso_citas_no_disponibles(articulos: Iterable[Articulo]) -> str | None:
    """Resume qué artículos seleccionados no tienen recuento de citas."""
    dois = [articulo.doi for articulo in articulos if articulo.citations is None]
    if not dois:
        return None
    return (
        f"No está disponible el recuento de citas para {len(dois)} artículo(s) "
        f"({', '.join(dois)}); se usó solo la relevancia."
    )
