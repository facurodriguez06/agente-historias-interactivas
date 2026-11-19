"""Estado persistente de cada historia y validación de sus reglas.

El JSON guarda lo que ocurrió en la partida. El RAG describe el mundo y SQLite
recuerda la conversación del agente; ninguno reemplaza este estado.
"""

import copy
import json
import os
import re
import tempfile
import unicodedata
import uuid
from pathlib import Path

from imagenes import es_url_de_imagen

CARPETA_PARTIDAS = Path("partidas")
TOTAL_CAPITULOS = 5
OPCIONES_POR_CAPITULO = 3
CATALOGO_OBJETOS = ("Llave oxidada", "Nota con iniciales", "Fragmento de documento")
_ID_VALIDO = re.compile(r"[0-9a-f]{32}")


# Utilidades de validación


def _validar_id(id_partida):
    if not isinstance(id_partida, str) or not _ID_VALIDO.fullmatch(id_partida):
        raise ValueError("Identificador de partida inválido")


def resolver_id(id_o_prefijo):
    """Acepta un ID completo (32 hex) o un prefijo corto (8+ hex) único."""
    texto = id_o_prefijo.strip().lower() if isinstance(id_o_prefijo, str) else ""
    if _ID_VALIDO.fullmatch(texto):
        return texto
    if not re.fullmatch(r"[0-9a-f]{8,31}", texto) or not CARPETA_PARTIDAS.exists():
        raise ValueError("Identificador de partida inválido")
    coincidencias = [
        ruta.stem
        for ruta in CARPETA_PARTIDAS.glob(f"{texto}*.json")
        if _ID_VALIDO.fullmatch(ruta.stem)
    ]
    if len(coincidencias) == 1:
        return coincidencias[0]
    raise ValueError(
        "La partida no existe"
        if not coincidencias
        else "Hay más de una partida con ese prefijo"
    )


def _normalizar(texto):
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
    resultado = []
    for valor in valores or []:
        if valor not in resultado:
            resultado.append(valor)
    return resultado


def _agregar_nuevos(destino, valores):
    """Agrega elementos que faltan y devuelve solo los incorporados."""
    nuevos = []
    for valor in valores:
        if valor not in destino:
            destino.append(valor)
            nuevos.append(valor)
    return nuevos


def _texto_no_vacio(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{campo} no puede estar vacío")
    return valor.strip()


def _lista_de_hechos(valores, campo):
    if valores is None:
        return []
    if not isinstance(valores, list):
        raise ValueError(f"{campo} debe ser una lista de frases")
    return _lista_sin_repetir(_texto_no_vacio(v, campo) for v in valores)


def _contexto_vacio():
    return {
        "ubicacion_actual": "",
        "hechos_establecidos": [],
        "misterios_pendientes": [],
        "misterios_resueltos": [],
        "resumen_ultimo_capitulo": "",
    }


# Persistencia JSON


def crear_partida():
    id_partida = uuid.uuid4().hex
    estado = {
        "id_partida": id_partida,
        "capitulo_actual": 0,  # Cantidad de decisiones tomadas
        "capitulos": [],
        "decisiones": [],
        "inventario": [],
        "pistas_descubiertas": [],
        "contexto_narrativo": _contexto_vacio(),
        "finalizada": False,
    }
    guardar_estado(estado)
    return id_partida


def guardar_estado(estado):
    """Escritura atómica: nunca deja un JSON parcialmente escrito."""
    _validar_id(estado["id_partida"])
    CARPETA_PARTIDAS.mkdir(exist_ok=True)
    ruta = CARPETA_PARTIDAS / f"{estado['id_partida']}.json"
    descriptor, temporal = tempfile.mkstemp(dir=CARPETA_PARTIDAS, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(estado, archivo, indent=4, ensure_ascii=False)
        os.replace(temporal, ruta)
    except BaseException:
        if os.path.exists(temporal):
            os.unlink(temporal)
        raise


def consultar_estado(id_partida):
    _validar_id(id_partida)
    ruta = CARPETA_PARTIDAS / f"{id_partida}.json"
    if not ruta.exists():
        raise ValueError("La partida no existe")
    with open(ruta, "r", encoding="utf-8") as archivo:
        estado = json.load(archivo)

    # Compatibilidad con los JSON de versiones anteriores.
    estado.setdefault("finalizada", False)
    contexto = estado.setdefault("contexto_narrativo", {})
    for campo, valor in _contexto_vacio().items():
        contexto.setdefault(campo, valor)
    return estado


def _resumen_de_partida(estado):
    capitulos = estado["capitulos"]
    ultimo = capitulos[-1] if capitulos else None
    return {
        "id_partida": estado["id_partida"],
        "nombre_chat": estado.get("nombre_chat", ""),
        "capitulos_escritos": len(capitulos),
        "capitulo_actual": estado["capitulo_actual"],
        "finalizada": estado["finalizada"],
        "titulo_ultimo_capitulo": ultimo["titulo"] if ultimo else "",
        "resumen_ultimo_capitulo": estado["contexto_narrativo"].get(
            "resumen_ultimo_capitulo", ""
        ),
        "decision_pendiente": bool(capitulos)
        and len(capitulos) == estado["capitulo_actual"] + 1,
    }


def listar_partidas_abiertas(limite=None, incluir_finalizadas=False):
    """Partidas ordenadas por fecha; por defecto solo abiertas."""
    if not CARPETA_PARTIDAS.exists():
        return []
    rutas = sorted(
        CARPETA_PARTIDAS.glob("*.json"),
        key=lambda ruta: ruta.stat().st_mtime,
        reverse=True,
    )
    abiertas = []
    for ruta in rutas:
        try:
            estado = consultar_estado(ruta.stem)
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        if incluir_finalizadas or not estado["finalizada"]:
            abiertas.append(_resumen_de_partida(estado))
            if limite is not None and len(abiertas) >= limite:
                break
    return abiertas


def siguiente_paso(estado):
    """Indica al LLM qué acción corresponde después de cada escritura."""
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


# Decisiones e inventario


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
    if len(estado["capitulos"]) != estado["capitulo_actual"] + 1:
        raise ValueError("No hay un capitulo pendiente de decision")

    # Validar en copias: ante un error no se modifica el JSON.
    inventario = list(estado["inventario"])
    recogidos = []
    for objeto in _lista_sin_repetir(
        _objeto_canonico(n) for n in objetos_recogidos or []
    ):
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
    nuevas_pistas = _agregar_nuevos(
        pistas,
        (
            _texto_no_vacio(p, "La pista")
            for p in _lista_sin_repetir(pistas_descubiertas)
        ),
    )
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


# Capítulos y continuidad narrativa


def _validar_opciones(numero, opciones):
    opciones = list(opciones or [])
    if numero == TOTAL_CAPITULOS:
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
    return opciones


def _actualizar_contexto(contexto, ubicacion, hechos, nuevos, resueltos, resumen):
    """Incorpora información confirmada sin repetir ni perder misterios."""
    if ubicacion is not None:
        contexto["ubicacion_actual"] = ubicacion
    _agregar_nuevos(contexto["hechos_establecidos"], hechos)
    _agregar_nuevos(contexto["misterios_pendientes"], nuevos)
    for misterio in resueltos:
        if misterio in contexto["misterios_pendientes"]:
            contexto["misterios_pendientes"].remove(misterio)
    _agregar_nuevos(contexto["misterios_resueltos"], resueltos)
    contexto["resumen_ultimo_capitulo"] = resumen


def guardar_capitulo(
    id_partida,
    titulo,
    texto,
    opciones,
    ubicacion_actual=None,
    hechos_nuevos=None,
    misterios_nuevos=None,
    misterios_resueltos=None,
    resumen_contexto=None,
):
    estado = consultar_estado(id_partida)
    if estado["finalizada"]:
        raise ValueError("La partida ya terminó")
    numero = len(estado["capitulos"]) + 1
    if numero > TOTAL_CAPITULOS:
        raise ValueError(f"La historia ya tiene {TOTAL_CAPITULOS} capitulos")
    if numero != estado["capitulo_actual"] + 1:
        raise ValueError("Hay un capitulo pendiente de decision")

    # Validar todo antes de modificar el estado.
    titulo = _texto_no_vacio(titulo, "El título")
    texto = _texto_no_vacio(texto, "El texto")
    opciones = _validar_opciones(numero, opciones)
    hechos = _lista_de_hechos(hechos_nuevos, "hechos_nuevos")
    nuevos = _lista_de_hechos(misterios_nuevos, "misterios_nuevos")
    resueltos = _lista_de_hechos(misterios_resueltos, "misterios_resueltos")
    if ubicacion_actual is not None:
        ubicacion_actual = _texto_no_vacio(ubicacion_actual, "ubicacion_actual")
    if resumen_contexto is not None:
        resumen_contexto = _texto_no_vacio(resumen_contexto, "resumen_contexto")

    contexto = estado["contexto_narrativo"]
    resumen = resumen_contexto or f"{titulo}: {texto[:350]}"
    _actualizar_contexto(contexto, ubicacion_actual, hechos, nuevos, resueltos, resumen)
    estado["capitulos"].append(
        {
            "numero": numero,
            "titulo": titulo,
            "texto": texto,
            "opciones": opciones,
            "imagen": None,
            "contexto_narrativo": copy.deepcopy(contexto),
        }
    )
    estado["finalizada"] = numero == TOTAL_CAPITULOS
    guardar_estado(estado)
    return {
        "capitulo_guardado": numero,
        "finalizada": estado["finalizada"],
        "contexto_narrativo": copy.deepcopy(contexto),
        "imagen_pendiente": (
            "Antes de mostrar el capítulo, pedí su imagen con buscar_imagen_capitulo "
            "(si falla, seguí sin imagen)."
        ),
        "siguiente_paso": siguiente_paso(estado),
    }


# Fotos de Unsplash asociadas a capítulos


def capitulo_para_imagen(id_partida):
    """Valida la imagen del último capítulo antes de gastar cuota de Unsplash."""
    estado = consultar_estado(id_partida)
    if not estado["capitulos"]:
        raise ValueError("Todavía no hay ningún capítulo guardado")
    ultimo = estado["capitulos"][-1]
    if ultimo.get("imagen"):
        raise ValueError(f"El capítulo {ultimo['numero']} ya tiene imagen")
    usadas = [c["imagen"]["id_foto"] for c in estado["capitulos"] if c.get("imagen")]
    return ultimo["numero"], usadas


def adjuntar_imagen(id_partida, foto):
    """Guarda la URL y los créditos, sin descargar una copia de la imagen."""
    numero, _ = capitulo_para_imagen(id_partida)
    if not es_url_de_imagen(foto.get("url_imagen")):
        raise ValueError("La URL de la imagen no es de Unsplash")
    estado = consultar_estado(id_partida)
    estado["capitulos"][-1]["imagen"] = {
        "url_imagen": str(foto["url_imagen"]),
        "id_foto": str(foto["id_foto"]),
        "autor": str(foto["autor"]),
        "url_autor": str(foto["url_autor"]),
        "url_foto": str(foto["url_foto"]),
        "descripcion": str(foto.get("descripcion", "")),
    }
    guardar_estado(estado)
    return numero


def url_de_imagen(capitulo):
    imagen = capitulo.get("imagen")
    return imagen["url_imagen"] if imagen else None
