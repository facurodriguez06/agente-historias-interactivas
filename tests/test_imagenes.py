"""Cliente de Unsplash con la red simulada: no usa red ni una key real."""

import pytest
import requests

import imagenes
from conftest import UnsplashFalso, foto_falsa, instalar_unsplash


@pytest.fixture
def destino(tmp_path):
    return tmp_path / "salida" / "foto.jpg"


def test_sin_key_se_informa(monkeypatch, destino):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    with pytest.raises(imagenes.ErrorImagen, match="UNSPLASH_ACCESS_KEY"):
        imagenes.obtener_imagen("foggy mansion", destino)
    assert not destino.exists()


def test_obtener_imagen_descarga_y_devuelve_atribucion(unsplash, destino):
    datos = imagenes.obtener_imagen("foggy mansion", destino)
    assert destino.read_bytes().startswith(b"\xff\xd8\xff")
    assert datos["id_foto"] == "foto1"
    assert datos["autor"] == "Ana Fotógrafa"
    assert datos["url_autor"] == "https://unsplash.com/@ana"
    assert datos["url_foto"] == "https://unsplash.com/photos/foto1"


def test_la_busqueda_lleva_key_filtros_y_timeout(unsplash, destino):
    imagenes.obtener_imagen("foggy mansion", destino)
    busqueda = unsplash.llamadas[0]
    assert busqueda["headers"]["Authorization"] == "Client-ID clave-de-prueba"
    assert busqueda["params"]["query"] == "foggy mansion"
    assert busqueda["params"]["orientation"] == "landscape"
    assert busqueda["params"]["content_filter"] == "high"
    assert all(c["timeout"] for c in unsplash.llamadas)


def test_la_key_no_se_envia_al_servidor_de_imagenes(unsplash, destino):
    imagenes.obtener_imagen("foggy mansion", destino)
    descarga = next(c for c in unsplash.llamadas if c["url"].startswith("https://images."))
    assert not descarga["headers"]


def test_se_avisa_la_descarga_a_unsplash(unsplash, destino):
    imagenes.obtener_imagen("foggy mansion", destino)
    assert "https://api.unsplash.com/photos/foto1/download" in unsplash.urls()


def test_si_falla_el_aviso_de_descarga_no_importa(monkeypatch, destino):
    instalar_unsplash(monkeypatch, UnsplashFalso(estado_aviso=500))
    assert imagenes.obtener_imagen("foggy mansion", destino)["id_foto"] == "foto1"
    assert destino.exists()


def test_no_repite_fotos_ya_usadas(unsplash, destino):
    datos = imagenes.obtener_imagen("foggy mansion", destino, excluir_ids=["foto1"])
    assert datos["id_foto"] == "foto2"


def test_todas_las_fotos_ya_usadas(unsplash, destino):
    with pytest.raises(imagenes.ErrorImagen, match="ya se usaron"):
        imagenes.obtener_imagen("foggy mansion", destino, excluir_ids=["foto1", "foto2"])
    assert not destino.exists()


def test_sin_resultados(monkeypatch, destino):
    instalar_unsplash(monkeypatch, UnsplashFalso(fotos=[]))
    with pytest.raises(imagenes.ErrorImagen, match="no encontró"):
        imagenes.obtener_imagen("zzzz", destino)


@pytest.mark.parametrize(
    "estado, texto",
    [(401, "inválida"), (403, "límite"), (429, "límite"), (500, "500")],
)
def test_errores_http_de_la_api(monkeypatch, destino, estado, texto):
    instalar_unsplash(monkeypatch, UnsplashFalso(estado_busqueda=estado))
    with pytest.raises(imagenes.ErrorImagen, match=texto):
        imagenes.obtener_imagen("foggy mansion", destino)


def test_timeout(monkeypatch, destino):
    instalar_unsplash(monkeypatch, UnsplashFalso(error_red=requests.Timeout()))
    with pytest.raises(imagenes.ErrorImagen, match="a tiempo"):
        imagenes.obtener_imagen("foggy mansion", destino)


def test_sin_conexion(monkeypatch, destino):
    instalar_unsplash(monkeypatch, UnsplashFalso(error_red=requests.ConnectionError()))
    with pytest.raises(imagenes.ErrorImagen, match="conectar"):
        imagenes.obtener_imagen("foggy mansion", destino)


def test_el_error_de_imagen_es_un_value_error():
    # Las tools capturan ValueError: un error de imagen nunca debe cortar el flujo.
    assert issubclass(imagenes.ErrorImagen, ValueError)


def test_archivo_que_no_es_jpeg(monkeypatch, destino):
    instalar_unsplash(monkeypatch, UnsplashFalso(contenido=b"<html>no soy una foto</html>"))
    with pytest.raises(imagenes.ErrorImagen, match="no es una imagen"):
        imagenes.obtener_imagen("foggy mansion", destino)
    assert not destino.exists()


def test_imagen_demasiado_grande(unsplash, destino, monkeypatch):
    monkeypatch.setattr(imagenes, "MAX_BYTES_IMAGEN", 10)
    with pytest.raises(imagenes.ErrorImagen, match="grande"):
        imagenes.obtener_imagen("foggy mansion", destino)
    assert not destino.exists()


def test_falla_la_descarga_de_la_foto(monkeypatch, destino):
    instalar_unsplash(monkeypatch, UnsplashFalso(estado_imagen=404))
    with pytest.raises(imagenes.ErrorImagen, match="404"):
        imagenes.obtener_imagen("foggy mansion", destino)


@pytest.mark.parametrize("consulta", ["", "   ", None, "x" * 101])
def test_consulta_invalida(unsplash, destino, consulta):
    with pytest.raises(imagenes.ErrorImagen):
        imagenes.obtener_imagen(consulta, destino)
    assert unsplash.llamadas == []


def test_resultado_incompleto_se_descarta(monkeypatch, destino):
    roto = {"id": "roto", "urls": {}}
    instalar_unsplash(monkeypatch, UnsplashFalso(fotos=[roto, foto_falsa("buena")]))
    assert imagenes.obtener_imagen("foggy mansion", destino)["id_foto"] == "buena"


def test_con_utm_conserva_parametros_existentes():
    url = imagenes.con_utm("https://unsplash.com/@ana?foo=1")
    assert "foo=1" in url
    assert "utm_source=agente_historias_interactivas" in url
    assert "utm_medium=referral" in url
