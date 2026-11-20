"""Cliente de Unsplash para las imágenes de los capítulos.

Usa la ubicación guardada para elegir fotos relevantes. Mantiene URLs originales,
créditos y aviso de descarga. Las fotos solo se descargan al generar el PDF.
"""

import os
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

URL_API = "https://api.unsplash.com"
URL_UNSPLASH = "https://unsplash.com"
HOST_IMAGENES = "images.unsplash.com"
UTM = {"utm_source": "agente_historias_interactivas", "utm_medium": "referral"}

TIMEOUT_SEGUNDOS = 10
RESULTADOS_POR_BUSQUEDA = 20
MAX_BYTES_IMAGEN = 10 * 1024 * 1024
MAX_LARGO_CONSULTA = 100

# Las claves son ambientes; nombres reconoce la ubicación guardada en inglés o español.
AMBIENTES_IMAGEN = {
    "biblioteca": {
        "nombres": ("library", "biblioteca"),
        "consultas": ("old library room bookshelves", "antique library interior"),
        "pistas": ("library", "bookshelf", "bookshelves", "bookcase", "reading room"),
    },
    "invernadero": {
        "nombres": ("greenhouse", "invernadero", "conservatory"),
        "consultas": ("greenhouse interior glass", "old conservatory plants"),
        "pistas": ("greenhouse", "conservatory", "glasshouse"),
    },
    "estudio": {
        "nombres": ("study", "estudio", "office", "despacho"),
        "consultas": ("antique study room desk", "vintage writing desk interior"),
        "pistas": ("study", "office", "writing desk", "wooden desk", "desk"),
    },
    "recibidor": {
        "nombres": (
            "entrance hall",
            "entrance",
            "foyer",
            "entryway",
            "recibidor",
            "vestibulo",
        ),
        "consultas": (
            "old mansion foyer staircase",
            "vintage house entrance hallway",
        ),
        "pistas": ("foyer", "entrance", "entryway", "hallway", "staircase", "stairs"),
    },
    "escalera": {
        "nombres": ("staircase", "stairs", "escalera", "landing"),
        "consultas": ("old wooden staircase interior", "antique house stairs"),
        "pistas": ("staircase", "stairs", "stairwell", "stairway"),
    },
    "sala": {
        "nombres": ("living room", "sala", "salon", "parlor"),
        "consultas": (
            "vintage living room interior",
            "old mansion parlor fireplace",
        ),
        "pistas": ("living room", "parlor", "lounge", "sofa", "fireplace"),
    },
    "pasillo": {
        "nombres": ("hallway", "corridor", "pasillo"),
        "consultas": ("old house hallway interior", "wooden mansion corridor"),
        "pistas": ("hallway", "corridor", "passageway"),
    },
    "exterior": {
        "nombres": (
            "exterior",
            "outside",
            "garden",
            "jardin",
            "lake",
            "lakeside",
            "boathouse",
            "dock",
            "pier",
            "muelle",
            "cobertizo",
        ),
        "consultas": (
            "old mansion exterior rainy",
            "old country house exterior",
        ),
        "pistas": ("mansion", "house", "manor", "castle", "building", "facade"),
    },
}


class ErrorImagen(ValueError):
    """Fallo controlado: la historia puede continuar sin imagen."""


def normalizar_texto(texto):
    """Convierte mayúsculas y tildes para facilitar las comparaciones."""
    return (
        unicodedata.normalize("NFKD", str(texto or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def identificar_ambiente(ubicacion):
    ubicacion = normalizar_texto(ubicacion)

    for ambiente, datos in AMBIENTES_IMAGEN.items():
        if any(nombre in ubicacion for nombre in datos["nombres"]):
            return ambiente

    return None


def puntuacion_foto(foto, ambiente):
    """Puntúa usando descripciones y etiquetas, sin descargar la imagen."""
    texto = normalizar_texto(
        " ".join(
            [
                foto.get("descripcion") or "",
                *(foto.get("etiquetas") or []),
            ]
        )
    )

    if not texto.strip():
        return 0

    # Evita retratos y fotos de productos que pueden confundir a Unsplash.
    if re.search(
        r"\b(person|people|portrait|woman|man|girl|boy|"
        r"selfie|fashion|food|coffee|cup|bottle)\b",
        texto,
    ):
        return 0

    coincidencias = sum(
        palabra in texto for palabra in AMBIENTES_IMAGEN[ambiente]["pistas"]
    )

    if ambiente == "biblioteca" and "books" in texto and "room" in texto:
        coincidencias = max(coincidencias, 1)

    if coincidencias == 0:
        return 0

    atmosfera = (
        "old",
        "vintage",
        "antique",
        "dark",
        "wooden",
        "mansion",
        "historic",
    )

    extras = sum(palabra in texto for palabra in atmosfera)

    return coincidencias * 10 + extras


def escena_es_oscura(texto):
    """Detecta si la narración describe una escena con poca luz."""
    texto = normalizar_texto(texto)

    señales = (
        "penumbra",
        "oscur",
        "sombr",
        "noche",
        "tenue",
        "apenas iluminad",
        "poco iluminad",
        "poca luz",
        "intermitente",
        "dimly lit",
        "dark",
        "shadow",
        "night",
    )

    return any(señal in texto for señal in señales)


def brillo_color(color):
    """Calcula el brillo aproximado del color informado por Unsplash."""
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        return None

    rojo, verde, azul = (int(color[i : i + 2], 16) for i in (1, 3, 5))

    return 0.2126 * rojo + 0.7152 * verde + 0.0722 * azul


def puntuacion_escena(foto, ambiente, oscura):
    """Comprueba que la foto represente el lugar y su iluminación."""
    puntos = puntuacion_foto(foto, ambiente)

    # Primero exigimos que corresponda al lugar.
    if puntos < 10:
        return -1

    # Si la escena no requiere oscuridad, usamos la puntuación normal.
    if not oscura:
        return puntos

    brillo = brillo_color(foto.get("color"))

    if brillo is not None:
        # Rechazamos fotos con un color predominante demasiado claro.
        if brillo > 150:
            return -1

        # Entre dos fotos válidas, preferimos la más oscura.
        return puntos + round((150 - brillo) / 4)

    # Si falta el color, buscamos evidencia de oscuridad en los textos.
    texto = normalizar_texto(
        " ".join(
            [
                foto.get("descripcion") or "",
                *(foto.get("etiquetas") or []),
            ]
        )
    )

    if any(palabra in texto for palabra in ("dark", "dim", "night", "shadow", "gloom")):
        return puntos + 10

    return -1


def con_utm(url):
    """Agrega parámetros de atribución conservando los existentes."""
    partes = urlparse(url)
    parametros = dict(parse_qsl(partes.query))
    parametros.update(UTM)
    return urlunparse(partes._replace(query=urlencode(parametros)))


def es_url_de_imagen(url):
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
    try:
        return requests.get(url, timeout=TIMEOUT_SEGUNDOS, **kwargs)

    except requests.Timeout:
        raise ErrorImagen("Unsplash no respondió a tiempo") from None

    except requests.RequestException as exc:
        raise ErrorImagen(
            f"No se pudo conectar con Unsplash ({type(exc).__name__})"
        ) from None


def _pedir_api(url, **kwargs):
    encabezados = {
        "Authorization": f"Client-ID {_clave()}",
        "Accept-Version": "v1",
    }

    return _pedir(url, headers=encabezados, **kwargs)


def buscar_fotos(consulta):
    """Devuelve hasta 20 candidatas horizontales con su información de Unsplash."""
    consulta = (consulta or "").strip()

    if not consulta:
        raise ErrorImagen("La consulta no puede estar vacía")

    if len(consulta) > MAX_LARGO_CONSULTA:
        raise ErrorImagen(
            f"La consulta es muy larga (máximo {MAX_LARGO_CONSULTA} caracteres)"
        )

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
        raise ErrorImagen(
            "Se alcanzó el límite de consultas de Unsplash; probá más tarde"
        )

    if respuesta.status_code != 200:
        raise ErrorImagen(
            f"Unsplash devolvió un error (código {respuesta.status_code})"
        )

    try:
        resultados = respuesta.json()["results"]

    except (ValueError, KeyError, TypeError):
        raise ErrorImagen("Respuesta inesperada de Unsplash") from None

    fotos = []

    for item in resultados:
        try:
            foto = {
                "id": str(item["id"]),
                "url_imagen": item["urls"]["regular"],
                "url_descarga": item["links"]["download_location"],
                "url_foto": item["links"]["html"],
                "color": item.get("color"),
                "autor": item["user"]["name"],
                "url_autor": item["user"]["links"]["html"],
                "descripcion": (
                    item.get("alt_description") or item.get("description") or ""
                ),
                "etiquetas": [
                    str(tag.get("title") or "")
                    for tag in (item.get("tags") or [])
                    if isinstance(tag, dict)
                ],
            }

        except (KeyError, TypeError):
            continue

        if es_url_de_imagen(foto["url_imagen"]):
            fotos.append(foto)

    return fotos


def _avisar_descarga(url_descarga):
    """Unsplash solicita registrar la elección de la fotografía."""
    try:
        _pedir_api(url_descarga)

    except ErrorImagen:
        pass


def obtener_imagen(consulta, excluir_ids=(), ubicacion=None, escena=None):
    """Busca una fotografía acorde al lugar y a la iluminación del capítulo."""

    ambiente = identificar_ambiente(ubicacion)

    if ubicacion and ambiente is None:
        raise ErrorImagen(f"No hay una búsqueda definida para '{ubicacion}'.")

    if ambiente:
        oscura = escena_es_oscura(escena)

        mejor_foto = None
        mejor_puntaje = -1

        for busqueda in AMBIENTES_IMAGEN[ambiente]["consultas"]:

            # Si el capítulo es oscuro, agregamos ese criterio a la búsqueda.
            consulta_real = f"dark moody {busqueda}" if oscura else busqueda

            try:
                fotos = buscar_fotos(consulta_real)

            except ErrorImagen:
                if mejor_foto is not None:
                    break
                raise

            for candidata in fotos:
                if candidata["id"] in excluir_ids:
                    continue

                puntaje = puntuacion_escena(
                    candidata,
                    ambiente,
                    oscura,
                )

                if puntaje > mejor_puntaje:
                    mejor_foto = candidata
                    mejor_puntaje = puntaje

        if mejor_foto is None:
            raise ErrorImagen(
                f"No se encontró una foto acorde al lugar "
                f"y la iluminación de '{ubicacion}'."
            )

        foto = mejor_foto

    else:
        # Compatibilidad con partidas que no tienen ubicación guardada.
        fotos = buscar_fotos(consulta)

        if not fotos:
            raise ErrorImagen(
                f"Unsplash no encontró fotos para '{consulta}'. "
                "Probá una consulta más genérica."
            )

        disponibles = [f for f in fotos if f["id"] not in excluir_ids]

        if not disponibles:
            raise ErrorImagen(
                "Las fotos encontradas ya se usaron en esta historia. "
                "Probá otra consulta."
            )

        foto = disponibles[0]

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
    """Descarga el JPEG a memoria para incrustarlo en el PDF."""
    if not es_url_de_imagen(url):
        raise ErrorImagen("La URL de la imagen no es de Unsplash")

    respuesta = _pedir(url, stream=True)

    if respuesta.status_code != 200:
        raise ErrorImagen(
            f"No se pudo descargar la imagen (código {respuesta.status_code})"
        )

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
