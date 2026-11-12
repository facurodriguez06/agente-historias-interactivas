"""Agente mínimo con LangChain create_agent, RAG y memoria corta por partida."""
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.memory import InMemorySaver

from herramientas import buscar_contexto_narrativo

load_dotenv()

INSTRUCCIONES = """Sos un narrador de historias interactivas de misterio en español argentino.
El protagonista es el usuario: narrá en segunda persona (vos), sin asignarle nombre ni biografía.
ANTES de escribir una escena, usá la tool buscar_contexto_narrativo para conocer el mundo.
Usá el conocimiento recuperado como fuente de ambientación, lugares y pistas; no
inventes que el usuario encontró o usó objetos que no eligió recoger o usar.
No menciones el texto técnico de las fuentes durante la narración, pero respetalo.
Cuando comienza una aventura, escribí 'Capítulo 1' y una escena breve (máximo 180 palabras)
con exactamente tres alternativas numeradas 1, 2 y 3. En turnos posteriores, recordá
la decisión elegida y continuá coherentemente, con tres alternativas.
Si el usuario pregunta sobre una decisión previa, respondé sin avanzar de capítulo.
Este es un prototipo: todavía NO implementa validación dura de elecciones, estado JSON,
límite exacto de 5 capítulos, PDF ni persistencia durable entre reinicios.
"""


def crear_agente():
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("Falta DEEPSEEK_API_KEY en el archivo .env")
    modelo = ChatDeepSeek(
        model="deepseek-flash",
        temperature=0.5,
        max_tokens=1000,
        max_retries=2,
    )
    return create_agent(
        model=modelo,
        tools=[buscar_contexto_narrativo],
        system_prompt=INSTRUCCIONES,
        checkpointer=InMemorySaver(),
    )
