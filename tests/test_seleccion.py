import pytest

from litmar.seleccion import (
    aviso_citas_no_disponibles,
    describir_citas,
    puntuacion_citas,
    puntuacion_combinada,
    tasa_anualizada,
)


def test_tasa_anualizada_y_puntuacion_combinada(hacer_articulo):
    articulo = hacer_articulo(year=2025, citations=8)

    assert tasa_anualizada(articulo, anio_actual=2026) == 4
    assert puntuacion_citas(articulo, anio_actual=2026) == 4.2
    assert puntuacion_combinada(articulo, relevancia=3, anio_actual=2026) == pytest.approx(3.36)


def test_sin_citas_usa_solo_relevancia_y_se_identifica(hacer_articulo):
    articulo = hacer_articulo(citations=None)

    assert tasa_anualizada(articulo, anio_actual=2026) is None
    assert puntuacion_citas(articulo, anio_actual=2026) is None
    assert puntuacion_combinada(articulo, relevancia=4, anio_actual=2026) == 4
    assert "Citas: no disponible" in describir_citas(articulo, anio_actual=2026)
    assert "10.1000/xyz123" in aviso_citas_no_disponibles([articulo])


def test_cero_citas_es_distinto_a_dato_no_disponible(hacer_articulo):
    articulo = hacer_articulo(citations=0)

    assert tasa_anualizada(articulo, anio_actual=2026) == 0
    assert puntuacion_citas(articulo, anio_actual=2026) == 1
    assert "Citas: 0" in describir_citas(articulo, anio_actual=2026)
    assert aviso_citas_no_disponibles([articulo]) is None
