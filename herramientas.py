"""Agent tools for RAG, game state, images, and PDF export.

The game ID is provided by the application through ContextoPartida.
The LLM cannot choose or invent which game session to access.
"""

from dataclasses import dataclass
from functools import lru_cache

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


SIN_PARTIDA_ACTIVA = "No active game session. Ask the user to start a new game or resume an open one."


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


@tool
def consultar_estado_partida(runtime: ToolRuntime[ContextoPartida]) -> dict:
    """Read the current game state from disk BEFORE deciding or writing a chapter.

    Returns chapters, choices, decisions, inventory, discovered clues,
    contexto_narrativo (location, established facts, open/resolved mysteries,
    last chapter summary), completion status and the next step.
    Always use this state to preserve continuity, including after a restart.
    Takes no arguments.
    """
    if not runtime.context.id_partida:
        return {"error": SIN_PARTIDA_ACTIVA}
    try:
        estado = estado_partida.consultar_estado(runtime.context.id_partida)
        return {**estado, "siguiente_paso": estado_partida.siguiente_paso(estado)}
    except (ValueError, OSError) as e:
        return {"error": str(e)}


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
            runtime.context.id_partida,
            opcion,
            objetos_recogidos,
            objetos_usados,
            pistas_descubiertas,
        )

    except (ValueError, OSError) as e:
        return {"error": str(e)}


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
    """Save a chapter AND its persistent narrative context to disk.

    Chapters 1 through 4 require exactly three choices; chapter 5 requires [].
    The title, narrative text and choices must be in Argentine Spanish.
    Provide these additional context fields in English EVERY time:
    - ubicacion_actual: current canonical location (e.g., "Entrance Hall").
    - hechos_nuevos: short facts actually established by this chapter; [] if none.
    - misterios_nuevos: new unresolved story questions; [] if none.
    - misterios_resueltos: exact pending questions answered here; [] if none.
    - resumen_contexto: a factual short summary of this chapter for continuity.

    Previously established facts are retained. Never record possibilities
    or events not actually shown in the story as established facts.
    The extra fields are optional for compatibility with older callers,
    but the agent must provide them when generating new chapters.
    """
    if not runtime.context.id_partida:
        return {"error": SIN_PARTIDA_ACTIVA}
    try:
        return estado_partida.guardar_capitulo(
            runtime.context.id_partida,
            titulo,
            texto,
            opciones,
            ubicacion_actual=ubicacion_actual,
            hechos_nuevos=hechos_nuevos,
            misterios_nuevos=misterios_nuevos,
            misterios_resueltos=misterios_resueltos,
            resumen_contexto=resumen_contexto,
        )

    except (ValueError, OSError) as e:
        return {"error": str(e)}


@tool
def generar_pdf_historia(runtime: ToolRuntime[ContextoPartida]) -> str:
    """Generate a PDF containing the completed story and decisions.

    Can only be used after chapter 5 is saved. Returns the generated path.
    """
    if not runtime.context.id_partida:
        return SIN_PARTIDA_ACTIVA
    try:
        return generar_pdf(runtime.context.id_partida)
    except (ValueError, OSError) as e:
        return f"Error generating PDF: {e}"


@tool
def buscar_imagen_capitulo(
    consulta: str, runtime: ToolRuntime[ContextoPartida]
) -> dict:
    """Find an atmospheric Unsplash image for the latest chapter.

    Call once immediately after guardar_capitulo.
    - consulta: 3 to 5 English words describing the scene or atmosphere.
    - Examples: "foggy old mansion library", "rainy greenhouse glass".
    - Do not include people's names.
    Retry once with a more general query if the search fails; then continue
    without an image. The result is attached to the chapter and its PDF.
    """
    if not runtime.context.id_partida:
        return {"error": SIN_PARTIDA_ACTIVA}
    try:
        id_partida = runtime.context.id_partida
        numero, ya_usadas = estado_partida.capitulo_para_imagen(id_partida)
        foto = imagenes.obtener_imagen(consulta, excluir_ids=ya_usadas)
        estado_partida.adjuntar_imagen(id_partida, foto)
        return {
            "ok": True,
            "capitulo": numero,
            "autor": foto["autor"],
            "descripcion": foto["descripcion"],
        }
    except (ValueError, OSError) as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Chat tools: listado, consulta y control de sesiones de partida
# ---------------------------------------------------------------------------


@tool
def listar_partidas_abiertas(limite: int | None = None) -> dict:
    """List the user's open games, most recent first. These are UNFINISHED games.

    An open game is one that has not reached its ending; every one of them can
    be resumed with retomar_partida.
    Each summary contains: id_partida, capitulos_escritos, capitulo_actual,
    titulo_ultimo_capitulo, resumen_ultimo_capitulo and decision_pendiente.
    - limite: maximum number of games to return; omit it to list them all.
    Use this tool when the user wants to see, resume, or ask about their open
    games. Takes no arguments besides the optional limit.
    """
    try:
        return {"partidas": estado_partida.listar_partidas_abiertas(limite)}
    except (ValueError, OSError) as e:
        return {"error": str(e)}


@tool
def consultar_otra_partida(id_partida: str) -> dict:
    """Read-only inspection of ANOTHER game, open or finished, without touching the active one.

    Use it to answer questions about past games (their chapters, decisions,
    inventory, clues, or how they ended). It never advances or modifies any game.
    - id_partida: the exact ID of the other game, as shown by
      listar_partidas_abiertas or provided by the user.
    Returns the full saved state plus siguiente_paso, and does not require an
    active game session.
    """
    try:
        estado = estado_partida.consultar_estado(id_partida)
        return {**estado, "siguiente_paso": estado_partida.siguiente_paso(estado)}
    except (ValueError, OSError) as e:
        return {"error": str(e)}


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
    except (ValueError, OSError) as e:
        return {"error": str(e)}


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
        estado = estado_partida.consultar_estado(id_partida)
        if estado["finalizada"]:
            return {"error": "That game is already finished; start a new one instead"}
        return {
            **estado,
            "siguiente_paso": estado_partida.siguiente_paso(estado),
            "instruccion": INSTRUCCION_RETOMAR_PARTIDA,
        }
    except (ValueError, OSError) as e:
        return {"error": str(e)}
