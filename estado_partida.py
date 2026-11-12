"""Estado de cada partida en un JSON, con las reglas de la historia validadas en código.

El JSON es la fuente de verdad de lo que pasó en UNA partida (capítulos, decisiones,
inventario, pistas). El RAG describe lo que existe en el mundo; el checkpointer recuerda
la conversación. Ninguno de los dos reemplaza a este estado.

Reglas que se hacen cumplir acá (no dependen de que el LLM las respete):
- La historia tiene 5 capítulos. Los capítulos 1 a 4 llevan 3 opciones; el capítulo 5 es
  el desenlace, no lleva opciones y deja la partida como `finalizada`.
- No se puede decidir sin un capítulo pendiente, ni escribir un capítulo con otro pendiente.
- Una partida finalizada no admite más escrituras.
- Un objeto solo entra al inventario si figura en el catálogo, y solo puede usarse
  si está en el inventario.
- Cada capítulo admite una sola imagen, siempre la del último capítulo guardado.
  Adjuntar una imagen no es escribir la historia: se puede hacer también con la
  partida finalizada (el desenlace se finaliza al guardarse y también lleva imagen).
"""

import json
import os
import re
import tempfile
import unicodedata
import uuid
from pathlib import Path

CARPETA_PARTIDAS = Path("partidas")

TOTAL_CAPITULOS = 5
OPCIONES_POR_CAPITULO = 3

# Objetos que el jugador puede llegar a tener. Mantener alineado con
# corpus/pistas_y_objetos.md (el reloj y la caja son parte del escenario, no se recogen).
CATALOGO_OBJETOS = (
    "Llave oxidada",
    "Nota con iniciales",
    "Fragmento de documento",
)

_ID_VALIDO = re.compile(r"[0-9a-f]{32}")


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------


def _validar_id(id_partida):
    """Acepta solo ids generados por crear_partida (uuid hex); evita rutas arbitrarias."""
    if not isinstance(id_partida, str) or not _ID_VALIDO.fullmatch(id_partida):
        raise ValueError("Identificador de partida inválido")


def _normalizar(texto):
    """Minúsculas, sin tildes y con espacios simples, para comparar nombres."""
    sin_tildes = unicodedata.normalize("NFD", str(texto))
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.lower().split())


_OBJETOS_POR_NOMBRE = {_normalizar(nombre): nombre for nombre in CATALOGO_OBJETOS}


def _objeto_canonico(nombre):
    canonico = _OBJETOS_POR_NOMBRE.get(_normalizar(nombre))
    if canonico is None:
        validos = ", ".join(CATALOGO_OBJETOS)
        raise ValueError(f"Objeto desconocido: '{nombre}'. Objetos válidos: {validos}")
    return canonico


def _lista_sin_repetir(valores):
    """Devuelve una lista sin elementos repetidos, conservando el orden."""
    resultado = []
    for valor in valores or []:
        if valor not in resultado:
            resultado.append(valor)
    return resultado


def _texto_no_vacio(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{campo} no puede estar vacío")
    return valor.strip()


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------


def crear_partida():
    # Creamos un identificador unico para cada partida
    id_partida = uuid.uuid4().hex

    estado = {
        "id_partida": id_partida,
        # Cantidad de decisiones tomadas (el capítulo en curso es capitulo_actual + 1)
        "capitulo_actual": 0,
        "capitulos": [],
        "decisiones": [],
        "inventario": [],
        "pistas_descubiertas": [],
        "finalizada": False,
    }

    # Guardamos el estado inicial
    guardar_estado(estado)

    return id_partida


def guardar_estado(estado):
    _validar_id(estado["id_partida"])
    CARPETA_PARTIDAS.mkdir(exist_ok=True)

    ruta = CARPETA_PARTIDAS / f"{estado['id_partida']}.json"

    # Escritura atómica: si el proceso se corta, nunca queda un JSON a medias.
    descriptor, ruta_temporal = tempfile.mkstemp(dir=CARPETA_PARTIDAS, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(estado, archivo, indent=4, ensure_ascii=False)
        os.replace(ruta_temporal, ruta)
    except BaseException:
        if os.path.exists(ruta_temporal):
            os.unlink(ruta_temporal)
        raise


def consultar_estado(id_partida):
    _validar_id(id_partida)
    ruta = CARPETA_PARTIDAS / f"{id_partida}.json"

    if not ruta.exists():
        raise ValueError("La partida no existe")

    with open(ruta, "r", encoding="utf-8") as archivo:
        estado = json.load(archivo)

    # Partidas guardadas antes de existir este campo
    estado.setdefault("finalizada", False)
    return estado


def siguiente_paso(estado):
    """Indica qué corresponde hacer ahora; se devuelve al LLM en cada tool de escritura."""
    if estado["finalizada"]:
        return (
            "La historia terminó. No se pueden registrar más decisiones ni capítulos. "
            "Podés generar el PDF con generar_pdf_historia."
        )

    numero = len(estado["capitulos"]) + 1
    if len(estado["capitulos"]) > estado["capitulo_actual"]:
        return (
            f"El capítulo {len(estado['capitulos'])} espera la elección del usuario: "
            f"mostrale las {OPCIONES_POR_CAPITULO} opciones y, cuando elija, "
            "registrala con registrar_decision."
        )
    if numero == TOTAL_CAPITULOS:
        return (
            f"Escribí el capítulo {numero} con guardar_capitulo: es el desenlace, "
            "cerrá la historia con lo investigado y pasá opciones=[] (sin opciones)."
        )
    return (
        f"Escribí el capítulo {numero} con guardar_capitulo, "
        f"con exactamente {OPCIONES_POR_CAPITULO} opciones."
    )


# ---------------------------------------------------------------------------
# Operaciones de la historia
# ---------------------------------------------------------------------------


def registrar_decision(
    id_partida,
    opcion,
    objetos_recogidos=None,
    objetos_usados=None,
    pistas_descubiertas=None,
):
    estado = consultar_estado(id_partida)

    if estado["finalizada"]:
        raise ValueError("La partida ya terminó")

    if isinstance(opcion, bool) or opcion not in range(1, OPCIONES_POR_CAPITULO + 1):
        raise ValueError("La opcion debe ser 1, 2 o 3")

    # Comprobamos que exista un capitulo sin responder
    if len(estado["capitulos"]) != estado["capitulo_actual"] + 1:
        raise ValueError("No hay un capitulo pendiente de decision")

    # Todo se valida sobre copias y se guarda de una sola vez: si algo falla, no queda
    # la decisión a medias.
    inventario = list(estado["inventario"])
    recogidos = []
    # Primero se normalizan los nombres y recién después se descartan repetidos.
    for objeto in _lista_sin_repetir(_objeto_canonico(n) for n in objetos_recogidos or []):
        if objeto in inventario:
            raise ValueError(f"'{objeto}' ya está en el inventario")
        inventario.append(objeto)
        recogidos.append(objeto)

    usados = []
    for objeto in _lista_sin_repetir(_objeto_canonico(n) for n in objetos_usados or []):
        if objeto not in inventario:
            raise ValueError(f"No se puede usar '{objeto}': el usuario no lo tiene")
        usados.append(objeto)

    pistas = list(estado["pistas_descubiertas"])
    nuevas_pistas = []
    for pista in _lista_sin_repetir(pistas_descubiertas):
        pista = _texto_no_vacio(pista, "La pista")
        if pista not in pistas:
            pistas.append(pista)
            nuevas_pistas.append(pista)

    estado["decisiones"].append(
        {
            "capitulo": estado["capitulo_actual"] + 1,
            "opcion": opcion,
            "objetos_recogidos": recogidos,
            "objetos_usados": usados,
            "pistas_descubiertas": nuevas_pistas,
        }
    )
    estado["capitulo_actual"] += 1
    estado["inventario"] = inventario
    estado["pistas_descubiertas"] = pistas

    guardar_estado(estado)

    return {
        "capitulos_escritos": len(estado["capitulos"]),
        "decisiones_tomadas": estado["capitulo_actual"],
        "inventario": estado["inventario"],
        "pistas_descubiertas": estado["pistas_descubiertas"],
        "finalizada": estado["finalizada"],
        "siguiente_paso": siguiente_paso(estado),
    }


def guardar_capitulo(id_partida, titulo, texto, opciones):
    estado = consultar_estado(id_partida)

    if estado["finalizada"]:
        raise ValueError("La partida ya terminó")

    numero = len(estado["capitulos"]) + 1

    if numero > TOTAL_CAPITULOS:
        raise ValueError(f"La historia ya tiene {TOTAL_CAPITULOS} capitulos")

    if numero != estado["capitulo_actual"] + 1:
        raise ValueError("Hay un capitulo pendiente de decision")

    titulo = _texto_no_vacio(titulo, "El título")
    texto = _texto_no_vacio(texto, "El texto")
    opciones = list(opciones or [])

    es_desenlace = numero == TOTAL_CAPITULOS
    if es_desenlace:
        if opciones:
            raise ValueError(
                f"El capitulo {TOTAL_CAPITULOS} es el desenlace y no lleva opciones"
            )
    else:
        if len(opciones) != OPCIONES_POR_CAPITULO:
            raise ValueError(
                f"Cada capitulo debe tener {OPCIONES_POR_CAPITULO} opciones"
            )
        opciones = [_texto_no_vacio(opcion, "Cada opción") for opcion in opciones]

    capitulo = {
        "numero": numero,
        "titulo": titulo,
        "texto": texto,
        "opciones": opciones,
        "imagen": None,
    }

    estado["capitulos"].append(capitulo)
    # El desenlace cierra la partida: desde acá nada más se puede escribir.
    estado["finalizada"] = es_desenlace
    guardar_estado(estado)

    return {
        "capitulo_guardado": numero,
        "finalizada": estado["finalizada"],
        "imagen_pendiente": (
            "Antes de mostrar el capítulo, pedí su imagen con buscar_imagen_capitulo "
            "(si falla, seguí sin imagen)."
        ),
        "siguiente_paso": siguiente_paso(estado),
    }


# ---------------------------------------------------------------------------
# Imágenes de los capítulos
# ---------------------------------------------------------------------------


def ruta_imagen_capitulo(id_partida, numero):
    """Dónde se guarda la imagen del capítulo `numero` (dentro de la carpeta de partidas)."""
    _validar_id(id_partida)
    return CARPETA_PARTIDAS / "imagenes" / id_partida / f"capitulo_{numero}.jpg"


def capitulo_para_imagen(id_partida):
    """Valida que se pueda adjuntar una imagen y devuelve (numero, ids de fotos ya usadas).

    Se llama ANTES de consultar a Unsplash para no gastar cuota si no corresponde.
    """
    estado = consultar_estado(id_partida)
    if not estado["capitulos"]:
        raise ValueError("Todavía no hay ningún capítulo guardado")

    ultimo = estado["capitulos"][-1]
    if ultimo.get("imagen"):
        raise ValueError(f"El capítulo {ultimo['numero']} ya tiene imagen")

    usadas = [
        c["imagen"]["id_foto"] for c in estado["capitulos"] if c.get("imagen")
    ]
    return ultimo["numero"], usadas


def adjuntar_imagen(id_partida, foto):
    """Asocia al último capítulo la foto ya descargada con `ruta_imagen_capitulo`.

    `foto` trae id_foto, autor, url_autor, url_foto y descripcion (ver imagenes.py).
    """
    numero, _ = capitulo_para_imagen(id_partida)
    archivo = ruta_imagen_capitulo(id_partida, numero)
    if not archivo.exists():
        raise ValueError("No se encontró el archivo de la imagen descargada")

    estado = consultar_estado(id_partida)
    estado["capitulos"][-1]["imagen"] = {
        "archivo": archivo.relative_to(CARPETA_PARTIDAS).as_posix(),
        "id_foto": str(foto["id_foto"]),
        "autor": str(foto["autor"]),
        "url_autor": str(foto["url_autor"]),
        "url_foto": str(foto["url_foto"]),
        "descripcion": str(foto.get("descripcion", "")),
    }
    guardar_estado(estado)
    return numero


def archivo_de_imagen(capitulo):
    """Ruta del archivo de imagen de un capítulo, o None si no tiene o falta el archivo."""
    imagen = capitulo.get("imagen")
    if not imagen:
        return None
    ruta = CARPETA_PARTIDAS / imagen["archivo"]
    return ruta if ruta.exists() else None
