import json
import uuid
from pathlib import Path

CARPETA_PARTIDAS = Path("partidas")


def crear_partida():
    # Creamos un identificador unico para cada partida
    id_partida = uuid.uuid4().hex

    estado = {
        "id_partida": id_partida,
        "capitulo_actual": 0,
        "capitulos": [],
        "decisiones": [],
        "inventario": [],
        "pistas_descubiertas": [],
    }

    # Guardamos el estado inicial
    guardar_estado(estado)

    return id_partida


def guardar_estado(estado):
    CARPETA_PARTIDAS.mkdir(exist_ok=True)

    ruta = CARPETA_PARTIDAS / f"{estado['id_partida']}.json"

    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(estado, archivo, indent=4, ensure_ascii=False)


def consultar_estado(id_partida):
    ruta = CARPETA_PARTIDAS / f"{id_partida}.json"

    if not ruta.exists():
        raise ValueError("La partida no existe")

    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def registrar_decision(id_partida, opcion):
    estado = consultar_estado(id_partida)

    if opcion not in (1, 2, 3):
        raise ValueError("La opcion debe ser 1, 2 o 3")

    if estado["capitulo_actual"] >= 5:
        raise ValueError("La partida ya termino")

    # Comprobamos que exista un capitulo sin responder
    if len(estado["capitulos"]) != estado["capitulo_actual"] + 1:
        raise ValueError("No hay un capitulo pendiente de decision")

    estado["decisiones"].append(
        {"capitulo": estado["capitulo_actual"] + 1, "opcion": opcion}
    )

    estado["capitulo_actual"] += 1

    guardar_estado(estado)

    return estado


def guardar_capitulo(id_partida, titulo, texto, opciones):
    estado = consultar_estado(id_partida)

    if len(opciones) != 3:
        raise ValueError("Cada capitulo debe tener 3 opciones")

    numero = len(estado["capitulos"]) + 1

    if numero > 5:
        raise ValueError("La historia ya tiene 5 capitulos")

    if numero != estado["capitulo_actual"] + 1:
        raise ValueError("Hay un capitulo pendiente de decision")

    capitulo = {
        "numero": numero,
        "titulo": titulo,
        "texto": texto,
        "opciones": opciones,
    }

    estado["capitulos"].append(capitulo)
    guardar_estado(estado)

    return capitulo
