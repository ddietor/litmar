import json

import pytest

from litmar import Biblioteca


def test_guardar_y_cargar_conserva_metadatos_y_orden(tmp_path, hacer_articulo):
    articulos = [hacer_articulo(), hacer_articulo(doi="10.1/segundo", abstract="", citations=0)]
    ruta = tmp_path / "biblioteca.json"
    Biblioteca(articulos).guardar(ruta)

    assert list(Biblioteca.cargar(ruta)) == articulos
    assert "García" in ruta.read_text(encoding="utf-8")


def test_biblioteca_vacia_se_puede_recuperar(tmp_path):
    ruta = tmp_path / "vacia.json"
    Biblioteca().guardar(ruta)
    assert len(Biblioteca.cargar(ruta)) == 0


def test_carga_normaliza_y_elimina_duplicados(tmp_path, hacer_articulo):
    ruta = tmp_path / "biblioteca.json"
    original = hacer_articulo()
    Biblioteca([original]).guardar(ruta)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos.append(dict(datos[0], doi="https://doi.org/10.1000/XYZ123", title="Duplicado"))
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    assert list(Biblioteca.cargar(ruta)) == [original]


def test_json_conserva_citas_no_disponibles(tmp_path, hacer_articulo):
    original = hacer_articulo(citations=None)
    ruta = tmp_path / "biblioteca.json"

    Biblioteca([original]).guardar(ruta)

    assert json.loads(ruta.read_text(encoding="utf-8"))[0]["citations"] is None
    assert list(Biblioteca.cargar(ruta)) == [original]


@pytest.mark.parametrize("contenido", ["{", "null", "{}", "[null]", '[{"title": "Incompleto"}]'])
def test_rechaza_documentos_invalidos(tmp_path, contenido):
    ruta = tmp_path / "invalida.json"
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(ValueError):
        Biblioteca.cargar(ruta)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("authors", "Ana García"),
        ("authors", [None]),
        ("year", True),
        ("citations", -1),
        ("citations", "muchas"),
        ("abstract", None),
        ("doi", "inválido"),
    ],
)
def test_rechaza_metadatos_invalidos(tmp_path, hacer_articulo, campo, valor):
    ruta = tmp_path / "biblioteca.json"
    Biblioteca([hacer_articulo()]).guardar(ruta)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos[0][campo] = valor
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ValueError, match="artículo 1 inválido"):
        Biblioteca.cargar(ruta)


def test_fallo_al_reemplazar_conserva_archivo_y_limpia_temporal(
    tmp_path, hacer_articulo, monkeypatch
):
    ruta = tmp_path / "biblioteca.json"
    Biblioteca().guardar(ruta)
    original = ruta.read_bytes()

    def fallar(*args):
        raise PermissionError("archivo ocupado")

    monkeypatch.setattr("litmar.biblioteca.os.replace", fallar)
    with pytest.raises(PermissionError):
        Biblioteca([hacer_articulo()]).guardar(ruta)
    assert ruta.read_bytes() == original
    assert list(tmp_path.iterdir()) == [ruta]
