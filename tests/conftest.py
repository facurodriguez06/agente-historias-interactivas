import io

import pytest
from PIL import Image

import estado_partida


@pytest.fixture(autouse=True)
def carpeta_partidas_temporal(tmp_path, monkeypatch):
    """Cada test escribe sus partidas en una carpeta temporal, nunca en partidas/."""
    monkeypatch.setattr(estado_partida, "CARPETA_PARTIDAS", tmp_path / "partidas")


def escribir_capitulo(id_partida, numero=None):
    """Guarda el capítulo siguiente con datos de prueba (3 opciones; el 5 sin opciones)."""
    estado = estado_partida.consultar_estado(id_partida)
    numero = numero or len(estado["capitulos"]) + 1
    opciones = [] if numero == estado_partida.TOTAL_CAPITULOS else ["A", "B", "C"]
    return estado_partida.guardar_capitulo(id_partida, f"Título {numero}", "Texto.", opciones)


def historia_completa(id_partida):
    """Juega los 5 capítulos eligiendo siempre la opción 1."""
    for _ in range(estado_partida.TOTAL_CAPITULOS - 1):
        escribir_capitulo(id_partida)
        estado_partida.registrar_decision(id_partida, 1)
    escribir_capitulo(id_partida)


# --- Unsplash simulado (los tests nunca usan la red ni una key real) ----------


def jpeg_bytes(ancho=60, alto=40, semilla=""):
    """Un JPEG válido y chico, generado en memoria. Otra `semilla` da otro color."""
    azar = sum(ord(c) for c in semilla) * 37
    color = (azar % 200 + 30, (azar // 7) % 200 + 30, (azar // 13) % 200 + 30)
    salida = io.BytesIO()
    Image.new("RGB", (ancho, alto), color).save(salida, format="JPEG")
    return salida.getvalue()


class RespuestaFalsa:
    def __init__(self, estado=200, datos=None, contenido=b""):
        self.status_code = estado
        self._datos = datos
        self._contenido = contenido

    def json(self):
        if self._datos is None:
            raise ValueError("sin JSON")
        return self._datos

    def iter_content(self, chunk_size=1024):
        for i in range(0, len(self._contenido), chunk_size):
            yield self._contenido[i : i + chunk_size]


def foto_falsa(id_foto, autor="Ana Fotógrafa"):
    return {
        "id": id_foto,
        "alt_description": f"foto {id_foto}",
        "urls": {"regular": f"https://images.unsplash.com/{id_foto}.jpg"},
        "links": {
            "html": f"https://unsplash.com/photos/{id_foto}",
            "download_location": f"https://api.unsplash.com/photos/{id_foto}/download",
        },
        "user": {"name": autor, "links": {"html": "https://unsplash.com/@ana"}},
    }


class UnsplashFalso:
    """Reemplaza requests.get: responde la búsqueda, la descarga y el aviso de descarga."""

    def __init__(self, fotos=None, estado_busqueda=200, estado_imagen=200,
                 contenido=None, error_red=None, estado_aviso=200):
        self.fotos = [foto_falsa("foto1"), foto_falsa("foto2")] if fotos is None else fotos
        self.estado_busqueda = estado_busqueda
        self.estado_imagen = estado_imagen
        self.contenido = contenido  # None: una imagen distinta por URL, como las fotos reales
        self.error_red = error_red
        self.estado_aviso = estado_aviso
        self.llamadas = []

    def get(self, url, headers=None, params=None, timeout=None, stream=False):
        self.llamadas.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        if self.error_red is not None:
            raise self.error_red
        if url.endswith("/search/photos"):
            return RespuestaFalsa(self.estado_busqueda, {"results": self.fotos})
        if url.startswith("https://images.unsplash.com/"):
            contenido = jpeg_bytes(semilla=url) if self.contenido is None else self.contenido
            return RespuestaFalsa(self.estado_imagen, contenido=contenido)
        if url.endswith("/download"):
            return RespuestaFalsa(self.estado_aviso, {"url": "x"})
        raise AssertionError(f"URL inesperada: {url}")

    def urls(self):
        return [c["url"] for c in self.llamadas]


@pytest.fixture
def unsplash(monkeypatch):
    """Instala un Unsplash falso con key de prueba. Se puede reconfigurar desde el test."""
    import imagenes

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "clave-de-prueba")
    falso = UnsplashFalso()
    monkeypatch.setattr(imagenes.requests, "get", falso.get)
    return falso


def instalar_unsplash(monkeypatch, falso):
    import imagenes

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "clave-de-prueba")
    monkeypatch.setattr(imagenes.requests, "get", falso.get)
    return falso
