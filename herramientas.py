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
    """Game session context provided by the application."""

    id_partida: str


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
    """Read a compact summary of the current game state.

    Returns the latest chapter, available choices, previous decisions,
    inventory, discovered clues, persistent narrative context,
    completion status and next step.

    Call before generating a chapter or registering a decision.
    Takes no arguments.
    """
    try:
        estado = estado_partida.consultar_estado(runtime.context.id_partida)

        capitulos = estado["capitulos"]
        ultimo = capitulos[-1] if capitulos else None

        ultimo_capitulo = None
        if ultimo:
            ultimo_capitulo = {
                "numero": ultimo["numero"],
                "titulo": ultimo["titulo"],
                "texto": ultimo["texto"],
                "opciones": ultimo["opciones"],
            }

        decisiones = []

        for decision in estado["decisiones"]:
            numero = decision["capitulo"]
            opcion = decision["opcion"]
            capitulo = capitulos[numero - 1]

            accion = capitulo["opciones"][opcion - 1]

            decisiones.append(
                {
                    "capitulo": numero,
                    "opcion": opcion,
                    "accion_elegida": accion,
                    "objetos_recogidos": decision.get("objetos_recogidos", []),
                    "objetos_usados": decision.get("objetos_usados", []),
                }
            )

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
    try:
        resultado = estado_partida.guardar_capitulo(
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

        return {
            "capitulo_guardado": resultado["capitulo_guardado"],
            "finalizada": resultado["finalizada"],
            "imagen_pendiente": resultado["imagen_pendiente"],
            "siguiente_paso": resultado["siguiente_paso"],
        }

    except (ValueError, OSError) as e:
        return {"error": str(e)}



@tool
def generar_pdf_historia(runtime: ToolRuntime[ContextoPartida]) -> str:
    """Generate a PDF containing the completed story and decisions.

    Can only be used after chapter 5 is saved. Returns the generated path.
    """
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
