"""Comandos deterministas del chat: /nueva, /retomar, /partidas y /ayuda.

Vive fuera de app.py para poder testearlo sin Streamlit y sin LLM. Todo lo que
devuelven estas funciones son strings o escalares, así se guardan tal cual en
st.session_state. Los comandos se resuelven acá, sin llamar al agente; el resto
de los mensajes va al agente con sus tools de meta-consulta.
"""

import re
import unicodedata

import estado_partida

# Cantidad de partidas abiertas que se listan por defecto (decisión del usuario).
LIMITE_PARTIDAS = 3

_COMANDOS = {
    "/nueva": "nueva",
    "/retomar": "retomar",
    "/partidas": "partidas",
    "/ayuda": "ayuda",
}

_NUMERO = re.compile(r"^(?:la\s+)?(?:(?:opcion|partida)\s+)?(\d+)$")


def parsear_comando(mensaje):
    """Token del comando que trae el mensaje, o None si no es un comando.

    Acepta la barra inicial seguida del comando, sin distinguir mayúsculas y
    tolerando espacios alrededor. Sin la barra ("nueva") no es comando: eso va
    al agente como texto común. "retomar" y "partidas" vuelven como tokens
    distintos; la app trata a ambos como "listar partidas abiertas".
    """
    texto = (mensaje or "").strip().lower()
    return _COMANDOS.get(texto)


def formatear_listado(abiertas):
    """Listado en Markdown de las partidas abiertas, con invitación a elegir.

    `abiertas` es lo que devuelve estado_partida.listar_partidas_abiertas():
    un resumen por partida con id_partida, capitulos_escritos,
    titulo_ultimo_capitulo y resumen_ultimo_capitulo, entre otros.
    """
    if not abiertas:
        return (
            "No hay partidas abiertas. Podés empezar una nueva cuando quieras "
            "con **/nueva**."
        )

    entradas = []
    for numero, partida in enumerate(abiertas, start=1):
        partes = [
            f"{numero}. `{partida['id_partida'][:8]}` — "
            f"{partida['capitulos_escritos']} de {estado_partida.TOTAL_CAPITULOS} capítulos"
        ]
        titulo = partida.get("titulo_ultimo_capitulo", "")
        if titulo:
            partes.append(f"«{titulo}»")
        resumen = partida.get("resumen_ultimo_capitulo", "").strip().splitlines()[0]
        if resumen:
            partes.append(resumen)
        entradas.append(" — ".join(partes))

    return (
        "**Partidas abiertas**\n\n"
        + "\n".join(entradas)
        + "\n\nRespondé con el número de la partida que querés retomar "
        "(o describila con tus palabras)."
    )


def eleccion_numerica(mensaje, cantidad):
    """Número de partida elegida como índice 1-based, o None si no es una elección válida.

    Acepta "1", " 2 ", "la 2", "opcion 3", "partida 2", "la partida 3", sin
    distinguir mayúsculas ni tildes. Devuelve None si el número queda fuera de
    rango, si el texto no es numérico o si la elección es ambigua ("1 y 2").
    """
    texto = unicodedata.normalize("NFD", (mensaje or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    coincidencia = _NUMERO.match(texto.strip().lower())
    if coincidencia is None:
        return None

    eleccion = int(coincidencia.group(1))
    if not 1 <= eleccion <= cantidad:
        return None
    return eleccion


def texto_ayuda():
    """Ayuda del chat: los cuatro comandos y qué más puede hacer el chat."""
    return (
        "**Comandos**\n\n"
        "- **/nueva**: arranca una partida nueva desde cero.\n"
        "- **/retomar**: te listo las partidas abiertas para retomar una acá mismo.\n"
        "- **/partidas**: igual que /retomar, muestra las partidas abiertas.\n"
        "- **/ayuda**: muestra esta ayuda.\n\n"
        "Además podés preguntarme cosas en común: cómo venían tus partidas "
        "anteriores, qué objetos o pistas juntaste, o qué misterios quedaron "
        "pendientes."
    )


def saludo_inicial():
    """Mensaje de bienvenida de un chat sin partidas activas."""
    return (
        "¡Hola! Soy tu asistente de historias. Acá podés preguntarme por tus "
        "partidas anteriores, empezar una partida nueva o retomar una que "
        "dejaste a medio jugar.\n\n"
        "Escribí **/ayuda** para ver todo lo que puedo hacer, o **/nueva** si "
        "querés arrancar una historia ya."
    )
