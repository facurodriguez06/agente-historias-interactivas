"""Cliente mínimo de la API de Unsplash para ilustrar los capítulos.

Las fotos se muestran por hotlinking, como piden las pautas de la API: la partida guarda
la URL original que devuelve Unsplash (images.unsplash.com) y la interfaz la carga directo
desde ahí. No se guardan copias de las fotos en disco. Cuando se usa una foto se avisa
al endpoint de descarga, y el crédito al fotógrafo lleva los parámetros utm que exigen
las pautas.

La única descarga ocurre al exportar el PDF (un PDF no puede hotlinkear): ahí cada foto se
pide a su URL, se incrusta desde memoria y no se guarda nada.

La key se lee de UNSPLASH_ACCESS_KEY (archivo .env). Todos los problemas esperables
(sin key, sin red, límite de consultas, sin resultados, URL o archivo inválido) se informan
como ErrorImagen, que es un ValueError: las tools lo devuelven como error y la historia
sigue sin imagen.

Prueba rápida contra la API real:  python imagenes.py "foggy old mansion"
"""

import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

URL_API = "https://api.unsplash.com"
URL_UNSPLASH = "https://unsplash.com"
HOST_IMAGENES = "images.unsplash.com"
UTM = {"utm_source": "agente_historias_interactivas", "utm_medium": "referral"}

TIMEOUT_SEGUNDOS = 10
RESULTADOS_POR_BUSQUEDA = 5
MAX_BYTES_IMAGEN = 10 * 1024 * 1024
MAX_LARGO_CONSULTA = 100


class ErrorImagen(ValueError):
    """No se pudo obtener la imagen; el mensaje se muestra tal cual al agente."""


def con_utm(url):
    """Agrega los parámetros utm que Unsplash exige en los enlaces de atribución."""
    partes = urlparse(url)
    parametros = dict(parse_qsl(partes.query))
    parametros.update(UTM)
    return urlunparse(partes._replace(query=urlencode(parametros)))


def es_url_de_imagen(url):
    """Solo se aceptan URLs https del servidor de imágenes de Unsplash."""
    try:
        partes = urlparse(url)
    except (ValueError, AttributeError):
        return False
    return partes.scheme == "https" and partes.hostname == HOST_IMAGENES


def _clave():
    clave = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
    if not clave:
        raise ErrorImagen("Falta UNSPLASH_ACCESS_KEY en el archivo .env")
    return clave


def _pedir(url, **kwargs):
    """GET con timeout; convierte los errores de red en ErrorImagen."""
    try:
        return requests.get(url, timeout=TIMEOUT_SEGUNDOS, **kwargs)
    except requests.Timeout:
        raise ErrorImagen("Unsplash no respondió a tiempo") from None
    except requests.RequestException as exc:
        raise ErrorImagen(
            f"No se pudo conectar con Unsplash ({type(exc).__name__})"
        ) from None


def _pedir_api(url, **kwargs):
    """GET a la API de Unsplash (lleva la key). Las fotos en sí se piden sin la key."""
    encabezados = {
        "Authorization": f"Client-ID {_clave()}",
        "Accept-Version": "v1",
    }
    return _pedir(url, headers=encabezados, **kwargs)


def buscar_fotos(consulta):
    """Devuelve hasta RESULTADOS_POR_BUSQUEDA fotos horizontales para la consulta."""
    consulta = (consulta or "").strip()
    if not consulta:
        raise ErrorImagen("La consulta no puede estar vacía")
    if len(consulta) > MAX_LARGO_CONSULTA:
        raise ErrorImagen(f"La consulta es muy larga (máximo {MAX_LARGO_CONSULTA} caracteres)")

    respuesta = _pedir_api(
        f"{URL_API}/search/photos",
        params={
            "query": consulta,
            "per_page": RESULTADOS_POR_BUSQUEDA,
            "orientation": "landscape",
            "content_filter": "high",
        },
    )
    if respuesta.status_code == 401:
        raise ErrorImagen("La Access Key de Unsplash es inválida")
    if respuesta.status_code in (403, 429):
        raise ErrorImagen("Se alcanzó el límite de consultas de Unsplash; probá más tarde")
    if respuesta.status_code != 200:
        raise ErrorImagen(f"Unsplash devolvió un error (código {respuesta.status_code})")

    try:
        resultados = respuesta.json()["results"]
    except (ValueError, KeyError, TypeError):
        raise ErrorImagen("Respuesta inesperada de Unsplash") from None

    fotos = []
    for item in resultados:
        try:
            foto = {
                "id": str(item["id"]),
                # Se usa tal cual la devuelve Unsplash (hotlinking): no se modifica
                "url_imagen": item["urls"]["regular"],
                "url_descarga": item["links"]["download_location"],
                "url_foto": item["links"]["html"],
                "autor": item["user"]["name"],
                "url_autor": item["user"]["links"]["html"],
                "descripcion": item.get("alt_description") or item.get("description") or "",
            }
        except (KeyError, TypeError):
            continue  # resultado incompleto: se descarta
        if es_url_de_imagen(foto["url_imagen"]):
            fotos.append(foto)
    return fotos


def _avisar_descarga(url_descarga):
    """Las pautas de Unsplash piden avisar cuando se usa una foto. Si falla, no importa."""
    try:
        _pedir_api(url_descarga)
    except ErrorImagen:
        pass


def obtener_imagen(consulta, excluir_ids=()):
    """Busca una foto y devuelve su URL (hotlink) y sus datos de atribución.

    No descarga la foto. Elige la primera cuyo id no esté en `excluir_ids`
    (para no repetir en una historia).
    """
    fotos = buscar_fotos(consulta)
    if not fotos:
        raise ErrorImagen(
            f"Unsplash no encontró fotos para '{consulta}'. Probá una consulta más genérica."
        )
    nuevas = [f for f in fotos if f["id"] not in excluir_ids]
    if not nuevas:
        raise ErrorImagen(
            "Las fotos encontradas ya se usaron en esta historia. Probá otra consulta."
        )

    foto = nuevas[0]
    _avisar_descarga(foto["url_descarga"])
    return {
        "id_foto": foto["id"],
        "url_imagen": foto["url_imagen"],
        "autor": foto["autor"],
        "url_autor": foto["url_autor"],
        "url_foto": foto["url_foto"],
        "descripcion": foto["descripcion"],
    }


def descargar_para_pdf(url):
    """Descarga una foto a memoria para incrustarla en el PDF (no se guarda en disco)."""
    if not es_url_de_imagen(url):
        raise ErrorImagen("La URL de la imagen no es de Unsplash")
    respuesta = _pedir(url, stream=True)
    if respuesta.status_code != 200:
        raise ErrorImagen(f"No se pudo descargar la imagen (código {respuesta.status_code})")

    contenido = bytearray()
    for bloque in respuesta.iter_content(chunk_size=64 * 1024):
        contenido.extend(bloque)
        if len(contenido) > MAX_BYTES_IMAGEN:
            raise ErrorImagen("La imagen es demasiado grande")
    if not contenido.startswith(b"\xff\xd8\xff"):
        raise ErrorImagen("El archivo descargado no es una imagen JPEG")
    return bytes(contenido)


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    consulta = " ".join(sys.argv[1:]) or "foggy old mansion"
    try:
        datos = obtener_imagen(consulta)
        peso = len(descargar_para_pdf(datos["url_imagen"]))
    except ErrorImagen as exc:
        sys.exit(f"ERROR: {exc}")
    print(f"URL de la foto (hotlink): {datos['url_imagen']}")
    print(f"La URL responde con una imagen JPEG de {peso // 1024} KB")
    print(f"Autor: {datos['autor']} ({con_utm(datos['url_autor'])})")
    print(f"Descripción: {datos['descripcion']}")
