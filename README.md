# Agente de historias interactivas — prototipo inicial

## Objetivo
Agente de misterio donde **el usuario es el protagonista**, el LLM narra en segunda persona y consulta un universo propio a través de RAG. Implementado con `create_agent` (sin Deep Agents) y memoria mediante checkpointer.

## Requisitos
- Python 3.11 o 3.12 (recomendados para simplificar compatibilidades)
- Acceso a internet en la primera ejecución para descargar el modelo de embeddings
- API Key de DeepSeek con crédito disponible

## Instalar

```bash
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copiar `.env.example` a `.env` y completar `DEEPSEEK_API_KEY=...`.
Nunca subir `.env` a GitHub.

## Correr

```bash
python ingestar.py
streamlit run app.py
```

1. Escribir: `Empezá una historia de misterio en la mansión`.
2. Ver el log de `buscar_contexto_narrativo` y la escena generada.
3. Elegir una de las tres opciones en el chat, por ejemplo `Elijo la opción 2`.
4. Preguntar qué pasó antes para probar memoria. La partida usa un `thread_id` único.

## Cómo funciona una partida
- Al abrir la app se crea una partida (`partidas/<id>.json`). Ese id es también el `thread_id` del checkpointer.
- El id **no** lo elige el LLM: la app lo pasa como contexto del agente (`ContextoPartida`) y las tools lo leen de ahí.
- La historia tiene 5 capítulos. Del 1 al 4 terminan con 3 opciones; el 5 es el desenlace, sin opciones, y deja la partida como `finalizada`.
- Inventario y pistas se actualizan con `registrar_decision`. Los objetos solo pueden ser los del catálogo (`CATALOGO_OBJETOS` en `estado_partida.py`, alineado con `corpus/pistas_y_objetos.md`) y solo se pueden usar si están en el inventario.
- El PDF solo se genera cuando la partida está finalizada.
- Las reglas viven en código (`estado_partida.py`), no solo en el prompt: el LLM recibe un error si las rompe y un campo `siguiente_paso` que le indica qué hacer.

## Tests
No usan LLM ni red (incluido un flujo de punta a punta con un modelo falso):

```bash
pip install -r requirements-dev.txt
pytest
```

## Qué está implementado
- Tres documentos Markdown de corpus propio
- Ingesta, separación en fragmentos y embeddings multilingües locales
- Chroma como vector store persistente en disco (carpeta ignorada por Git)
- Tool RAG con nombres de documentos fuente
- Estado de partida en JSON con validación de capítulos, decisiones, inventario y pistas
- Cierre garantizado en el capítulo 5 y exportación a PDF al finalizar
- `create_agent` con DeepSeek y `InMemorySaver`
- Streamlit con chat, tools en streaming y panel de estado (capítulos, inventario, pistas)

## Qué falta para la entrega final
- Probar el flujo completo con un LLM real y confirmar el nombre del modelo (`deepseek-flash` no está verificado)
- Opciones como botones, descarga del PDF y razonamiento en la UI
- Una tool con servicio externo (web/API; por ejemplo imágenes)
- Manejo de errores 429 / reintentos con espera
- `.env.example`, fuente del PDF independiente del sistema operativo y prueba de instalación desde cero
- Persistencia de la conversación entre reinicios (hoy el JSON sobrevive pero `InMemorySaver` no)
- Ampliar el corpus y evitar que el RAG devuelva pistas todavía inaccesibles
- Presentación, diagrama y justificación de componentes

## Notas
- DeepSeek genera texto; los embeddings del RAG se hacen **localmente** y no consumen tokens de DeepSeek.
- La primera descarga del modelo de embeddings puede llevar varios minutos.
- La app imprime un resumen de resultados de tools. No muestra razonamiento privado no suministrado por el proveedor.
- `InMemorySaver` mantiene el historial mientras el proceso de la app continúa funcionando; el estado de la partida (JSON) es independiente.
