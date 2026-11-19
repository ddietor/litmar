import dataclasses

import pytest


@pytest.mark.parametrize(
    ("autores", "esperado"),
    [
        (["García, Ana"], "García (2021)"),
        (["García, Ana", "López, Juan"], "García y López (2021)"),
        (["García, Ana", "López, Juan", "Pérez, Marta"], "García et al. (2021)"),
    ],
)
def test_cita_corta_segun_numero_de_autores(hacer_articulo, autores, esperado):
    assert hacer_articulo(authors=autores).short_citation == esperado


def test_cita_corta_con_apellido_compuesto(hacer_articulo):
    assert hacer_articulo(authors=["García López, Ana"]).short_citation == "García López (2021)"


def test_cita_corta_sin_coma_usa_ultima_palabra(hacer_articulo):
    assert hacer_articulo(authors=["Ana García"]).short_citation == "García (2021)"


@pytest.mark.parametrize(
    "doi",
    [
        "10.1000/XYZ123",
        "https://doi.org/10.1000/xyz123",
        "doi: 10.1000/xyz123",
        "  10.1000/xyz123 ",
    ],
)
def test_doi_se_normaliza(hacer_articulo, doi):
    assert hacer_articulo(doi=doi).doi == "10.1000/xyz123"


@pytest.mark.parametrize("doi", ["", "xyz123", "10.1000"])
def test_doi_invalido(hacer_articulo, doi):
    with pytest.raises(ValueError, match="DOI"):
        hacer_articulo(doi=doi)


def test_autores_se_convierten_en_tupla(hacer_articulo):
    assert hacer_articulo(authors=["García, Ana"]).authors == ("García, Ana",)


def test_autores_como_str_da_error(hacer_articulo):
    with pytest.raises(TypeError):
        hacer_articulo(authors="García, Ana")


@pytest.mark.parametrize("autores", [[], ["  "]])
def test_sin_autores_da_error(hacer_articulo, autores):
    with pytest.raises(ValueError, match="autor"):
        hacer_articulo(authors=autores)


def test_citas_negativas_da_error(hacer_articulo):
    with pytest.raises(ValueError, match="citas"):
        hacer_articulo(citations=-1)


def test_citas_no_disponibles_y_tipo_invalido(hacer_articulo):
    assert hacer_articulo(citations=None).citations is None
    with pytest.raises(TypeError, match="citations"):
        hacer_articulo(citations="muchas")


def test_es_inmutable(hacer_articulo):
    articulo = hacer_articulo()
    with pytest.raises(dataclasses.FrozenInstanceError):
        articulo.citations = 100
    assert dataclasses.replace(articulo, citations=100).citations == 100
