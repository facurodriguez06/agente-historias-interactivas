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

## Qué está implementado
- Tres documentos Markdown de corpus propio
- Ingesta, separación en fragmentos y embeddings multilingües locales
- Chroma como vector store persistente en disco (carpeta ignorada por Git)
- Tool RAG con nombres de documentos fuente
- `create_agent` con DeepSeek V4.1 Flash y `InMemorySaver`
- Streamlit básico y visibilidad de llamadas a tools y resúmenes en streaming

## Qué falta para la entrega final (¡importante!)
- Al menos dos tools adicionales necesarias para el flujo de la historia
- Estado estructurado y validación de opciones/inventario
- Guardado íntegro de capítulos y exportación a PDF
- Cierre garantizado de la historia tras cinco capítulos
- Persistencia de memoria entre reinicios, si se desea
- Pruebas de distintas decisiones, manejo de fallas y límites
- Presentación, diagrama, justificación y README de producción

## Notas
- DeepSeek genera texto; los embeddings del RAG se hacen **localmente** y no consumen tokens de DeepSeek.
- La primera descarga del modelo de embeddings puede llevar varios minutos.
- La app imprime un resumen de resultados de tools. No muestra razonamiento privado no suministrado por el proveedor.
- `InMemorySaver` mantiene el historial mientras el proceso de la app continúa funcionando; no reemplaza el estado JSON de la partida que falta implementar.
- La calidad narrativa y el cumplimiento estricto de las reglas requieren más pruebas y validaciones en código.
