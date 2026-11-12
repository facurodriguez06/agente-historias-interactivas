"""Cliente de Unsplash con la red simulada: no usa red ni una key real."""

import pytest
import requests

import imagenes
from conftest import UnsplashFalso, foto_falsa, instalar_unsplash, jpeg_bytes

HOST_IMAGENES = "https://images.unsplash.com/"


def pedidos_a_imagenes(falso):
    return [u for u in falso.urls() if u.startswith(HOST_IMAGENES)]


def test_sin_key_se_informa(monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    with pytest.raises(imagenes.ErrorImagen, match="UNSPLASH_ACCESS_KEY"):
        imagenes.obtener_imagen("foggy mansion")


def test_obtener_imagen_devuelve_url_y_atribucion(unsplash):
    datos = imagenes.obtener_imagen("foggy mansion")
    assert datos["id_foto"] == "foto1"
    assert datos["url_imagen"] == "https://images.unsplash.com/foto1.jpg"
    assert datos["autor"] == "Ana Fotógrafa"
    assert datos["url_autor"] == "https://unsplash.com/@ana"
    assert datos["url_foto"] == "https://unsplash.com/photos/foto1"


def test_hotlinking_no_descarga_la_foto(unsplash):
    """La foto se muestra desde la URL de Unsplash: la app no la pide ni la guarda."""
    imagenes.obtener_imagen("foggy mansion")
    assert pedidos_a_imagenes(unsplash) == []


def test_la_url_se_devuelve_sin_modificar(monkeypatch):
    original = "https://images.unsplash.com/photo-1?ixid=abc&ixlib=rb-4.0&w=1080&q=80"
    foto = foto_falsa("conparams")
    foto["urls"]["regular"] = original
    instalar_unsplash(monkeypatch, UnsplashFalso(fotos=[foto]))
    assert imagenes.obtener_imagen("foggy mansion")["url_imagen"] == original


def test_la_busqueda_lleva_key_filtros_y_timeout(unsplash):
    imagenes.obtener_imagen("foggy mansion")
    busqueda = unsplash.llamadas[0]
    assert busqueda["headers"]["Authorization"] == "Client-ID clave-de-prueba"
    assert busqueda["params"]["query"] == "foggy mansion"
    assert busqueda["params"]["orientation"] == "landscape"
    assert busqueda["params"]["content_filter"] == "high"
    assert all(c["timeout"] for c in unsplash.llamadas)


def test_se_avisa_la_descarga_a_unsplash(unsplash):
    imagenes.obtener_imagen("foggy mansion")
    assert "https://api.unsplash.com/photos/foto1/download" in unsplash.urls()


def test_si_falla_el_aviso_de_descarga_no_importa(monkeypatch):
    instalar_unsplash(monkeypatch, UnsplashFalso(estado_aviso=500))
    assert imagenes.obtener_imagen("foggy mansion")["id_foto"] == "foto1"


def test_no_repite_fotos_ya_usadas(unsplash):
    assert imagenes.obtener_imagen("foggy mansion", excluir_ids=["foto1"])["id_foto"] == "foto2"


def test_todas_las_fotos_ya_usadas(unsplash):
    with pytest.raises(imagenes.ErrorImagen, match="ya se usaron"):
        imagenes.obtener_imagen("foggy mansion", excluir_ids=["foto1", "foto2"])


def test_sin_resultados(monkeypatch):
    instalar_unsplash(monkeypatch, UnsplashFalso(fotos=[]))
    with pytest.raises(imagenes.ErrorImagen, match="no encontró"):
        imagenes.obtener_imagen("zzzz")


@pytest.mark.parametrize(
    "estado, texto",
    [(401, "inválida"), (403, "límite"), (429, "límite"), (500, "500")],
)
def test_errores_http_de_la_api(monkeypatch, estado, texto):
    instalar_unsplash(monkeypatch, UnsplashFalso(estado_busqueda=estado))
    with pytest.raises(imagenes.ErrorImagen, match=texto):
        imagenes.obtener_imagen("foggy mansion")


def test_timeout(monkeypatch):
    instalar_unsplash(monkeypatch, UnsplashFalso(error_red=requests.Timeout()))
    with pytest.raises(imagenes.ErrorImagen, match="a tiempo"):
        imagenes.obtener_imagen("foggy mansion")


def test_sin_conexion(monkeypatch):
    instalar_unsplash(monkeypatch, UnsplashFalso(error_red=requests.ConnectionError()))
    with pytest.raises(imagenes.ErrorImagen, match="conectar"):
        imagenes.obtener_imagen("foggy mansion")


def test_el_error_de_imagen_es_un_value_error():
    # Las tools capturan ValueError: un error de imagen nunca debe cortar el flujo.
    assert issubclass(imagenes.ErrorImagen, ValueError)


@pytest.mark.parametrize("consulta", ["", "   ", None, "x" * 101])
def test_consulta_invalida(unsplash, consulta):
    with pytest.raises(imagenes.ErrorImagen):
        imagenes.obtener_imagen(consulta)
    assert unsplash.llamadas == []


def test_resultado_incompleto_se_descarta(monkeypatch):
    roto = {"id": "roto", "urls": {}}
    instalar_unsplash(monkeypatch, UnsplashFalso(fotos=[roto, foto_falsa("buena")]))
    assert imagenes.obtener_imagen("foggy mansion")["id_foto"] == "buena"


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/foto.jpg",
        "http://images.unsplash.com/foto.jpg",  # sin https
        "https://images.unsplash.com.evil.example/foto.jpg",  # host que solo empieza igual
        "file:///etc/passwd",
        "",
    ],
)
def test_fotos_con_url_de_otro_host_se_descartan(monkeypatch, url):
    ajena = foto_falsa("ajena")
    ajena["urls"]["regular"] = url
    instalar_unsplash(monkeypatch, UnsplashFalso(fotos=[ajena, foto_falsa("buena")]))
    assert imagenes.obtener_imagen("foggy mansion")["id_foto"] == "buena"


def test_con_utm_conserva_parametros_existentes():
    url = imagenes.con_utm("https://unsplash.com/@ana?foo=1")
    assert "foo=1" in url
    assert "utm_source=agente_historias_interactivas" in url
    assert "utm_medium=referral" in url


# --- descarga en memoria, solo para incrustar en el PDF ---------------------


def test_descargar_para_pdf_devuelve_bytes_jpeg(unsplash):
    datos = imagenes.descargar_para_pdf("https://images.unsplash.com/foto1.jpg")
    assert datos == jpeg_bytes(semilla="https://images.unsplash.com/foto1.jpg")


def test_la_key_no_se_envia_al_servidor_de_imagenes(unsplash):
    imagenes.descargar_para_pdf("https://images.unsplash.com/foto1.jpg")
    descarga = unsplash.llamadas[-1]
    assert descarga["url"].startswith(HOST_IMAGENES) and not descarga["headers"]


def test_descargar_para_pdf_rechaza_otros_hosts_sin_hacer_pedidos(unsplash):
    with pytest.raises(imagenes.ErrorImagen, match="no es de Unsplash"):
        imagenes.descargar_para_pdf("https://evil.example/foto.jpg")
    assert unsplash.llamadas == []


def test_descargar_para_pdf_archivo_que_no_es_jpeg(monkeypatch):
    instalar_unsplash(monkeypatch, UnsplashFalso(contenido=b"<html>no soy una foto</html>"))
    with pytest.raises(imagenes.ErrorImagen, match="no es una imagen"):
        imagenes.descargar_para_pdf("https://images.unsplash.com/foto1.jpg")


def test_descargar_para_pdf_imagen_demasiado_grande(unsplash, monkeypatch):
    monkeypatch.setattr(imagenes, "MAX_BYTES_IMAGEN", 10)
    with pytest.raises(imagenes.ErrorImagen, match="grande"):
        imagenes.descargar_para_pdf("https://images.unsplash.com/foto1.jpg")


def test_descargar_para_pdf_falla_la_descarga(monkeypatch):
    instalar_unsplash(monkeypatch, UnsplashFalso(estado_imagen=404))
    with pytest.raises(imagenes.ErrorImagen, match="404"):
        imagenes.descargar_para_pdf("https://images.unsplash.com/foto1.jpg")


def test_descargar_para_pdf_timeout(monkeypatch):
    instalar_unsplash(monkeypatch, UnsplashFalso(error_red=requests.Timeout()))
    with pytest.raises(imagenes.ErrorImagen, match="a tiempo"):
        imagenes.descargar_para_pdf("https://images.unsplash.com/foto1.jpg")
