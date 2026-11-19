
"""Agent tools for RAG, game state, images, and PDF export.

The game ID is provided by the application through ContextoPartida.
The LLM cannot choose or invent which game session to access.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import threading

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import estado_partida
import imagenes
from generar_pdf import generar_pdf
from ingestar import DB_DIR, MODELO_EMBEDDINGS, COLECCION


@dataclass
class ContextoPartida:
    """Game session context provided by the application.

    An empty id_partida means there is no active game session yet.
    """

    id_partida: str = ""


SIN_PARTIDA_ACTIVA = (
    "No active game session. Ask the user to start a new game or resume an open one."
)
# Evita que el PDF del capítulo 5 se genere antes de adjuntar su imagen.
_BLOQUEO_PDF = threading.Lock()


# RAG: el modelo de embeddings y Chroma se cargan una sola vez.
@lru_cache(maxsize=1)
def obtener_base():
    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)
    return Chroma(
        collection_name=COLECCION,
        embedding_function=embeddings,
        persist_directory=str(DB_DIR),
    )


@tool
def buscar_contexto_narrativo(consulta: str) -> str:
    """Retrieve setting details, locations, objects, clues, and world rules using RAG.

    The consulta argument must be a search query in English.
    The retrieved documents are written in English.
    Returns relevant excerpts and their sources.

    Retrieved information describes the world, not events
    that have necessarily happened in the current game.
    """
    if not DB_DIR.exists():
        return "ERROR: RAG database not found. Run python ingestar.py first."

    try:
        documentos = obtener_base().similarity_search(consulta, k=3)
        if not documentos:
            return "No relevant information was found in the corpus."
        return "\n\n".join(
            f"Source: {doc.metadata.get('source', 'unknown')}\n"
            f"Content: {doc.page_content}"
            for doc in documentos
        )
    except Exception as exc:
        return f"ERROR querying RAG: {type(exc).__name__}: {exc}"


# Estado: devolvemos al agente lo que necesita, no el JSON completo.
@tool
def consultar_estado_partida(runtime: ToolRuntime[ContextoPartida]) -> dict:
    """Read a compact summary of the current game state.

    Returns the latest chapter, available choices, previous decisions,
    inventory, discovered clues, persistent narrative context,
    completion status and next step.

    Call before generating a chapter or registering a decision.
    Takes no arguments.
    """
    if not runtime.context.id_partida:
        return {"error": SIN_PARTIDA_ACTIVA}
    try:
        estado = estado_partida.consultar_estado(runtime.context.id_partida)
        capitulos = estado["capitulos"]
        ultimo = capitulos[-1] if capitulos else None
        ultimo_capitulo = (
            {campo: ultimo[campo] for campo in ("numero", "titulo", "texto", "opciones")}
            if ultimo else None
        )

        decisiones = []
        for decision in estado["decisiones"]:
            numero, opcion = decision["capitulo"], decision["opcion"]
            decisiones.append({
                "capitulo": numero,
                "opcion": opcion,
                "accion_elegida": capitulos[numero - 1]["opciones"][opcion - 1],
                "objetos_recogidos": decision.get("objetos_recogidos", []),
                "objetos_usados": decision.get("objetos_usados", []),
            })

        return {
            "capitulos_escritos": len(capitulos),
            "capitulo_actual": estado["capitulo_actual"],
            "ultimo_capitulo": ultimo_capitulo,
            "decisiones": decisiones,
            "inventario": estado["inventario"],
            "pistas_descubiertas": estado["pistas_descubiertas"],
            "contexto_narrativo": estado["contexto_narrativo"],
            "finalizada": estado["finalizada"],
            "siguiente_paso": estado_partida.siguiente_paso(estado),
        }
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


# Escritura de decisiones y capítulos: el JSON se modifica en estado_partida.py.
@tool
def registrar_decision(
    opcion: int,
    runtime: ToolRuntime[ContextoPartida],
    objetos_recogidos: list[str] | None = None,
    objetos_usados: list[str] | None = None,
    pistas_descubiertas: list[str] | None = None,
) -> dict:
    """Record the user's selected option (1, 2, or 3).

    Call consultar_estado_partida and buscar_contexto_narrativo BEFORE this tool.

    Arguments:
    - opcion: the option actually chosen by the user.
    - objetos_recogidos: objects explicitly collected through the selected
      action, using their exact Spanish catalog names.
    - objetos_usados: objects used by the selected action; they must already
      be in the inventory.
    - pistas_descubiertas: genuinely discovered new clues, as short Spanish
      phrases. Use [] if no new clues were discovered.

    Never invent clues merely to fill pistas_descubiertas.
    Respect the retrieved RAG context and existing game state.
    If an error occurs, correct the arguments and retry.
    """
    if not runtime.context.id_partida:
        return {"error": SIN_PARTIDA_ACTIVA}
    try:
        return estado_partida.registrar_decision(
            runtime.context.id_partida, opcion,
            objetos_recogidos, objetos_usados, pistas_descubiertas,
        )
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


@tool
def guardar_capitulo(
    titulo: str,
    texto: str,
    opciones: list[str],
    runtime: ToolRuntime[ContextoPartida],
    ubicacion_actual: str | None = None,
    hechos_nuevos: list[str] | None = None,
    misterios_nuevos: list[str] | None = None,
    misterios_resueltos: list[str] | None = None,
    resumen_contexto: str | None = None,
) -> dict:
    """Save a chapter and its persistent narrative context.

    Chapters 1-4 require exactly three choices.
    Chapter 5 requires opciones=[].

    Write the story in Argentine Spanish.
    Keep narrative context fields concise and in English.

    Provide:
    - ubicacion_actual: canonical current location.
    - hechos_nuevos: at most 3 short new established facts.
    - misterios_nuevos: at most 2 new open mysteries.
    - misterios_resueltos: resolved pending mysteries.
    - resumen_contexto: short factual chapter summary.

    Never duplicate collected objects or established facts.
    """
    if not runtime.context.id_partida:
        return {"error": SIN_PARTIDA_ACTIVA}
    try:
        resultado = estado_partida.guardar_capitulo(
            runtime.context.id_partida, titulo, texto, opciones,
            ubicacion_actual=ubicacion_actual,
            hechos_nuevos=hechos_nuevos,
            misterios_nuevos=misterios_nuevos,
            misterios_resueltos=misterios_resueltos,
            resumen_contexto=resumen_contexto,
        )
        return {
            "capitulo_guardado": resultado["capitulo_guardado"],
            "finalizada": resultado["finalizada"],
            "imagen_pendiente": resultado["imagen_pendiente"],
            "siguiente_paso": resultado["siguiente_paso"],
        }
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


# Imágenes: se buscan después de guardar el capítulo.
@tool
def buscar_imagen_capitulo(
    consulta: str,
    runtime: ToolRuntime[ContextoPartida],
) -> dict:
    """Find a relevant image using the latest chapter location.

    Uses the location stored in the game's JSON.
    The consulta argument remains for compatibility.
    """
    if not runtime.context.id_partida:
        return {"error": SIN_PARTIDA_ACTIVA}
    try:
        id_partida = runtime.context.id_partida
        numero, ya_usadas = estado_partida.capitulo_para_imagen(id_partida)
        estado = estado_partida.consultar_estado(id_partida)
        capitulo = estado["capitulos"][-1]
        contexto = capitulo.get("contexto_narrativo") or estado["contexto_narrativo"]
        ubicacion = contexto.get("ubicacion_actual", "")
        foto = imagenes.obtener_imagen(
            consulta,
            excluir_ids=ya_usadas,
            ubicacion=ubicacion,
            escena=capitulo.get("texto", ""),
        )
        with _BLOQUEO_PDF:
            estado_partida.adjuntar_imagen(id_partida, foto)
            if estado["finalizada"] and (Path("historias_generadas") / f"{id_partida}.pdf").exists():
                generar_pdf(id_partida)
        return {
            "ok": True,
            "capitulo": numero,
            "ubicacion": ubicacion,
            "autor": foto["autor"],
            "descripcion": foto["descripcion"],
        }
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


# PDF: solo puede generarse al completar los cinco capítulos.
@tool
def generar_pdf_historia(runtime: ToolRuntime[ContextoPartida]) -> str:
    """Generate a PDF containing the completed story and decisions.

    Can only be used after chapter 5 is saved. Returns the generated path.
    """
    if not runtime.context.id_partida:
        return SIN_PARTIDA_ACTIVA
    try:
        with _BLOQUEO_PDF:
            return generar_pdf(runtime.context.id_partida)
    except (ValueError, OSError) as exc:
        return f"Error generating PDF: {exc}"


# Tools de chat: listar, consultar, crear o retomar partidas.
@tool
def listar_partidas_abiertas(
    limite: int | None = None,
    incluir_finalizadas: bool = False,
) -> dict:
    """List saved games, most recent first. By default returns UNFINISHED games.

    Pass incluir_finalizadas=True when the user asks about finished games or
    searches a past game by chat name.
    Each summary contains: id_partida, nombre_chat, capitulos_escritos,
    capitulo_actual, finalizada, titulo_ultimo_capitulo, resumen_ultimo_capitulo
    and decision_pendiente.
    - limite: maximum number of games to return; omit it to list them all.
    """
    try:
        return {
            "partidas": estado_partida.listar_partidas_abiertas(
                limite, incluir_finalizadas=incluir_finalizadas
            )
        }
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


def _estado_con_siguiente_paso(id_partida):
    """Estado completo para las tools que consultan otras partidas."""
    id_resuelto = estado_partida.resolver_id(id_partida)
    estado = estado_partida.consultar_estado(id_resuelto)
    return {**estado, "siguiente_paso": estado_partida.siguiente_paso(estado)}


@tool
def consultar_otra_partida(id_partida: str) -> dict:
    """Read-only inspection of ANOTHER game, open or finished, without touching the active one.

    Use it to answer questions about past games (their chapters, decisions,
    inventory, clues, or how they ended). It never advances or modifies any game.
    - id_partida: the full 32-character ID or the 8-character short ID shown in the UI.
    Returns the full saved state plus siguiente_paso, and does not require an
    active game session.
    """
    try:
        return _estado_con_siguiente_paso(id_partida)
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


def _instruccion_de_cambio_de_sesion(confirmacion: str) -> str:
    """Instrucción común para iniciar_nueva_partida y retomar_partida."""
    return (
        "The application switches the active game to this session AFTER this turn. "
        "Do NOT call consultar_estado_partida, registrar_decision, "
        "guardar_capitulo, buscar_imagen_capitulo or generar_pdf_historia in this "
        f"same turn. Only confirm to the user, in Argentine Spanish, {confirmacion}."
    )


INSTRUCCION_NUEVA_PARTIDA = _instruccion_de_cambio_de_sesion(
    "that a new game was created and that the story starts with their next message"
)
INSTRUCCION_RETOMAR_PARTIDA = _instruccion_de_cambio_de_sesion(
    "the game will be resumed with its saved chapters and context"
)


@tool
def iniciar_nueva_partida() -> dict:
    """Create a new game session for the user. Call ONLY when the user asks to start one.

    Takes no arguments. Returns the new id_partida plus an instruction that
    MUST be followed: do not write chapters or call game tools in the same
    turn; the application applies the switch after this turn.
    """
    try:
        id_partida = estado_partida.crear_partida()
        return {"id_partida": id_partida, "instruccion": INSTRUCCION_NUEVA_PARTIDA}
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


@tool
def retomar_partida(id_partida: str) -> dict:
    """Propose resuming an open (unfinished) game chosen from listar_partidas_abiertas.

    - id_partida: the exact ID of the game to resume.
    Returns the game state plus siguiente_paso and an instruction that MUST be
    followed: do not write chapters or call game tools in the same turn; the
    application applies the switch after this turn. Finished games are
    rejected: offer to start a new one instead.
    """
    try:
        estado = _estado_con_siguiente_paso(id_partida)
        if estado["finalizada"]:
            return {"error": "That game is already finished; start a new one instead"}
        return {**estado, "instruccion": INSTRUCCION_RETOMAR_PARTIDA}
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}
