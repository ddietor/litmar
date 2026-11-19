import pytest

from litmar import Biblioteca


def test_agregar_y_tamano(hacer_articulo):
    biblioteca = Biblioteca()
    assert biblioteca.agregar(hacer_articulo()) is True
    assert len(biblioteca) == 1


def test_duplicado_por_doi_se_ignora_y_conserva_el_primero(hacer_articulo):
    biblioteca = Biblioteca()
    original = hacer_articulo(title="Original")
    biblioteca.agregar(original)

    duplicado = hacer_articulo(title="Otro título", doi="https://doi.org/10.1000/XYZ123")
    assert biblioteca.agregar(duplicado) is False
    assert len(biblioteca) == 1
    assert biblioteca.obtener("10.1000/xyz123") is original


def test_constructor_elimina_duplicados(hacer_articulo):
    biblioteca = Biblioteca([hacer_articulo(), hacer_articulo(), hacer_articulo(doi="10.1/otro")])
    assert len(biblioteca) == 2


def test_iteracion_en_orden_de_insercion(hacer_articulo):
    dois = ["10.1/c", "10.1/a", "10.1/b"]
    biblioteca = Biblioteca(hacer_articulo(doi=d) for d in dois)
    assert [a.doi for a in biblioteca] == dois


def test_contains(hacer_articulo):
    articulo = hacer_articulo()
    biblioteca = Biblioteca([articulo])
    assert articulo in biblioteca
    assert "DOI:10.1000/XYZ123" in biblioteca
    assert "10.1/no-esta" not in biblioteca
    assert "esto no es un DOI" not in biblioteca
    assert 42 not in biblioteca


def test_obtener_inexistente(hacer_articulo):
    assert Biblioteca([hacer_articulo()]).obtener("10.1/no-esta") is None


def test_bibtex_vacio():
    assert Biblioteca().a_bibtex() == ""


def test_bibtex_entrada_completa(hacer_articulo):
    bibtex = Biblioteca([hacer_articulo()]).a_bibtex()
    assert bibtex == (
        "@article{garcia2021,\n"
        "  title = {{Aprendizaje profundo para la clasificación de textos}},\n"
        "  author = {García, Ana and López, Juan and Pérez, Marta},\n"
        "  journal = {Revista de Informática},\n"
        "  year = {2021},\n"
        "  doi = {10.1000/xyz123},\n"
        "  abstract = {Un estudio sobre redes neuronales.}\n"
        "}\n"
    )


def test_bibtex_omite_resumen_vacio(hacer_articulo):
    assert "abstract" not in Biblioteca([hacer_articulo(abstract="")]).a_bibtex()


def test_bibtex_claves_unicas(hacer_articulo):
    biblioteca = Biblioteca(hacer_articulo(doi=f"10.1/{i}") for i in range(3))
    bibtex = biblioteca.a_bibtex()
    for clave in ("@article{garcia2021,", "@article{garcia2021a,", "@article{garcia2021b,"):
        assert clave in bibtex


def test_bibtex_escapa_caracteres_latex(hacer_articulo):
    bibtex = Biblioteca([hacer_articulo(title="R&D al 100% {nuevo}", doi="10.1000/a_b")]).a_bibtex()
    assert r"title = {{R\&D al 100\% \{nuevo\}}}" in bibtex
    assert "doi = {10.1000/a_b}" in bibtex  # el DOI no se escapa


def test_exportar_bibtex(tmp_path, hacer_articulo):
    biblioteca = Biblioteca([hacer_articulo()])
    ruta = tmp_path / "refs.bib"
    biblioteca.exportar_bibtex(ruta)
    assert ruta.read_text(encoding="utf-8") == biblioteca.a_bibtex()


def test_obtener_con_doi_invalido_da_error():
    with pytest.raises(ValueError):
        Biblioteca().obtener("no es un doi")


def test_csv_columnas_y_autores_en_una_celda(hacer_articulo):
    import csv
    import io

    biblioteca = Biblioteca([hacer_articulo(title='Título con "comillas", y comas')])
    filas = list(csv.reader(io.StringIO(biblioteca.a_csv())))
    assert filas[0] == ["title", "authors", "year", "doi", "journal", "abstract", "citations"]
    assert filas[1][:4] == [
        'Título con "comillas", y comas',
        "García, Ana; López, Juan; Pérez, Marta",
        "2021",
        "10.1000/xyz123",
    ]
    assert filas[1][6] == "42"


def test_csv_vacio_solo_cabecera():
    assert Biblioteca().a_csv().splitlines() == [
        "title,authors,year,doi,journal,abstract,citations"
    ]


def test_csv_identifica_citas_no_disponibles(hacer_articulo):
    import csv
    import io

    filas = list(csv.reader(io.StringIO(Biblioteca([hacer_articulo(citations=None)]).a_csv())))

    assert filas[1][-1] == "No disponible"
