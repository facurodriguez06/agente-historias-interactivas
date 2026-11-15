# Agente de Historias Interactivas

Trabajo Integrador — Modelos de Lenguaje | UTN FRM | Unidad 5

## 1. Descripción del proyecto

Agente de inteligencia artificial desarrollado con **LangChain**, que genera historias interactivas de misterio donde el usuario es el protagonista.

El agente narra en segunda persona y permite tomar decisiones que modifican el desarrollo de la aventura.

Cada chat es una partida (modelo ChatGPT: un chat, una partida): se pueden hacer preguntas sobre partidas anteriores sin salir de la partida en curso, empezar una historia nueva con una instrucción explícita y retomar cualquier partida guardada, que siempre se abre en un chat nuevo.

El proyecto combina:

- **LLM:** conmutable entre proveedores desde el `.env` (NVIDIA, DeepSeek u OpenRouter), para generar las narraciones.
- **RAG:** proporciona conocimiento propio sobre el universo narrativo.
- **Tools:** permiten consultar información, registrar decisiones, guardar capítulos y generar archivos.
- **Memoria:** checkpointer de LangChain para conservar el contexto conversacional.
- **Streamlit:** interfaz web para interactuar con el agente.
- **ReportLab:** biblioteca para exportar las historias a PDF.

**Objetivo final:** generar una historia de cinco capítulos, con tres alternativas por capítulo, y permitir descargarla como PDF.

## 2. Estructura del proyecto

```text
agente-historias-interactivas/
├── corpus/
│   ├── ambientacion.md
│   ├── lugares.md
│   └── pistas_y_objetos.md
├── fonts/
│   ├── DejaVuSans.ttf
│   └── LICENSE
├── scripts/
│   └── probar_modelo.py
├── tests/
├── agente.py
├── proveedores.py
├── app.py
├── herramientas.py
├── estado_partida.py
├── middleware_reintentos.py
├── pasos_agente.py
├── comandos_chat.py
├── diagnostico.py
├── ingestar.py
├── generar_pdf.py
├── imagenes.py
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── README.md
└── .gitignore
```

Carpetas que se generan al ejecutar (están en `.gitignore` y no se versionan): `chroma_db/` (base vectorial), `partidas/` (estado JSON de cada partida), `historias_generadas/` (PDF), `logs/` (volcados de diagnóstico).

**Función de cada archivo:**

- `agente.py`: arma el agente con el modelo de `proveedores.py`, las herramientas disponibles, el prompt y el checkpointer.
- `proveedores.py`: fábrica de modelos; elige NVIDIA, DeepSeek u OpenRouter según `LLM_PROVIDER` del `.env` y resuelve `LLM_MODEL` y `LLM_TIMEOUT`.
- `scripts/probar_modelo.py`: prueba manual del modelo configurado (tool calling y razonamiento), fuera de la app; incluye medición de latencia y comparación entre modelos.
- `app.py`: implementa la interfaz web mediante Streamlit: chat, barra lateral con la lista de chats-partida estilo ChatGPT, botón único "Nuevo chat", enrutamiento de los comandos deterministas, streaming del turno, razonamiento del modelo, imágenes y panel de estado. Es la autoridad del cambio de partida activa: las tools del agente proponen, la app valida y aplica.
- `herramientas.py`: contiene las diez tools disponibles para el agente (juego, meta-consulta y control de sesión) y `ContextoPartida`, que lleva el id de la partida activa a las tools (vacío cuando no hay partida).
- `estado_partida.py`: administra los estados de partida mediante archivos JSON, hace cumplir las reglas de la historia (capítulos, decisiones, inventario, cierre) y lista las partidas abiertas (las que no llegaron a un final).
- `comandos_chat.py`: comandos deterministas del chat (`/nueva`, `/partidas`, `/ayuda`), formateo del listado de partidas abiertas, elección numérica, ayuda y saludo. Vive fuera de `app.py` para poder testearse sin Streamlit.
- `middleware_reintentos.py`: middleware propio (API base de LangChain, `wrap_model_call`) que reintenta 429, timeouts y 502/503/504 con espera exponencial, y repite la llamada cuando el modelo devuelve una respuesta vacía o con la tool call mal formada.
- `pasos_agente.py`: traduce los mensajes del agente a pasos para la interfaz (razonamiento, llamada a tool, resultado), arma el capítulo de respaldo cuando el turno termina sin texto y detecta los cambios de sesión que propone el agente (`iniciar_nueva_partida` / `retomar_partida`) para que la app los aplique; vive fuera de `app.py` para poder testearse sin Streamlit.
- `diagnostico.py`: detecta las respuestas vacías del modelo y guarda el mensaje crudo en `logs/` para inspeccionarlo.
- `ingestar.py`: procesa los documentos y construye la base vectorial RAG.
- `generar_pdf.py`: crea el PDF a partir de los capítulos, decisiones e imágenes guardados.
- `imagenes.py`: cliente de la API de Unsplash (búsqueda y atribución de la foto de cada capítulo; las fotos se muestran por hotlinking). Incluye un modo de prueba por línea de comandos.
- `corpus/`: contiene los documentos que definen el universo narrativo.
- `fonts/`: fuente DejaVu Sans y su licencia, para que el PDF salga igual en cualquier sistema operativo.
- `tests/`: pruebas automáticas que no usan LLM ni red.

## 3. Sistema RAG

El agente utiliza RAG (*Retrieval-Augmented Generation*) para consultar información sobre el mundo de la historia.

El corpus inicial contiene tres documentos:

1. `ambientacion.md`: premisa, características del universo y reglas narrativas.
2. `lugares.md`: escenarios y ubicaciones disponibles.
3. `pistas_y_objetos.md`: elementos y pistas relevantes para la aventura.

**Funcionamiento:**

1. Se leen los documentos Markdown.
2. Se dividen en fragmentos (*chunks*).
3. Se generan embeddings mediante un modelo multilingüe de Hugging Face.
4. Los vectores se almacenan en ChromaDB.
5. El agente puede invocar la herramienta `buscar_contexto_narrativo` para recuperar los fragmentos más relevantes.

**Estado:** implementado y probado.

La ingesta inicial procesó 3 documentos y generó 8 fragmentos (con `chunk_size=650` y `chunk_overlap=100`; el número exacto depende del corpus del momento). La recuperación semántica se comprobó correctamente mediante una consulta de prueba.

## 4. Herramientas implementadas

Se implementaron diez tools de LangChain.

| Tool | Función |
|---|---|
| `buscar_contexto_narrativo` | Recupera información del corpus utilizando RAG. |
| `consultar_estado_partida` | Devuelve capítulos, decisiones, inventario, pistas y el siguiente paso de la partida en curso. |
| `registrar_decision` | Valida y guarda la opción elegida (1, 2 o 3) y actualiza inventario y pistas (`objetos_recogidos`, `objetos_usados`, `pistas_descubiertas`). |
| `guardar_capitulo` | Almacena el título, texto y opciones de un capítulo: tres opciones en los capítulos 1 a 4; el capítulo 5 es el desenlace y no lleva opciones. |
| `buscar_imagen_capitulo` | **Servicio externo (API de Unsplash).** Busca una foto de ambiente para el capítulo recién guardado, y guarda su URL original en el capítulo, con el crédito del fotógrafo. La foto se muestra por hotlinking, sin guardar copias. |
| `generar_pdf_historia` | Genera el PDF ilustrado de la historia. Solo funciona cuando la historia terminó. |
| `listar_partidas_abiertas` | Lista las últimas partidas abiertas (las que no llegaron a un final), con un resumen de cada una, para retomarlas o consultarlas. |
| `consultar_otra_partida` | Lee el estado de otra partida (abierta o terminada) para responder preguntas sobre partidas anteriores. Es de solo lectura. |
| `iniciar_nueva_partida` | Crea una partida nueva y devuelve su id. La aplicación la activa al terminar el turno; en ese turno el agente solo confirma. |
| `retomar_partida` | Propone retomar una partida abierta por id. Valida que exista y no esté terminada; la aplicación la activa al terminar el turno. |

Las herramientas utilizan el decorador `@tool` de LangChain.

**El id de la partida no es un argumento de las tools.** La aplicación lo fija en el contexto de cada ejecución (`ContextoPartida`, mediante `context_schema` y `ToolRuntime`) y las tools lo leen de ahí. El LLM no lo ve ni lo elige; puede haber sesiones sin partida activa (id vacío), en las que las tools del juego responden con un error claro. Cuando el agente quiere cambiar de partida, lo propone con `iniciar_nueva_partida` o `retomar_partida`, y la aplicación valida y aplica el cambio al terminar el turno. Las tools de escritura devuelven `siguiente_paso`, que le indica al agente qué corresponde hacer, y los errores de validación vuelven como `{"error": ...}` sin cortar el flujo (las de estado); `buscar_contexto_narrativo` y `generar_pdf_historia` informan el fallo como texto (`"ERROR: ..."` y `"Error al generar PDF: ..."`), también sin cortar el flujo.

**Imágenes (`buscar_imagen_capitulo`).** El agente la llama una vez por capítulo, justo después de `guardar_capitulo`, con una consulta corta en inglés sobre el lugar de la escena (por ejemplo, "foggy old mansion library"). Cada capítulo admite una sola imagen, siempre la del último capítulo guardado, y no se repite una foto dentro de la misma historia. Si Unsplash falla (sin key, sin red, límite de consultas, sin resultados), la tool devuelve un error y la historia sigue sin imagen. **Hotlinking:** la partida guarda solo la URL original de la foto (`images.unsplash.com`, sin modificar) y la interfaz la carga directamente desde Unsplash, como piden sus pautas; la app no guarda copias de las fotos. Se avisa al endpoint de descarga de Unsplash al elegir cada foto. La imagen se muestra en el chat con su crédito y se incluye en el PDF, que es el entregable final.

**Estado:** las herramientas están probadas por separado y también en un flujo de punta a punta con un modelo falso (ver sección de tests). Falta comprobar el uso coordinado con un LLM real.

## 5. Estado y memoria

Se utilizan dos mecanismos diferentes:

**Estado estructurado (JSON)**

Cada partida tiene un identificador único (uuid) y almacena:

- Capítulo actual (cantidad de decisiones tomadas).
- Capítulos generados, cada uno con su imagen (URL original de Unsplash y datos de atribución; no se guarda ningún archivo de imagen).
- Decisiones tomadas, con los objetos y pistas que implicó cada una.
- Inventario.
- Pistas descubiertas.
- Si la partida está finalizada.

Las reglas se hacen cumplir en código (`estado_partida.py`) y no solo en el prompt:

- La historia tiene 5 capítulos. Los capítulos 1 a 4 llevan tres opciones; el capítulo 5 es el desenlace, no lleva opciones y deja la partida finalizada. Después no se puede escribir nada más.
- No se puede decidir sin un capítulo pendiente ni escribir un capítulo con otro pendiente.
- Los objetos solo pueden ser los del catálogo (`CATALOGO_OBJETOS`, alineado con `corpus/pistas_y_objetos.md`), solo se pueden usar si están en el inventario y no se pueden recoger dos veces.
- El id de la partida se valida (uuid hexadecimal) y el JSON se escribe de forma atómica.

La app no crea ninguna partida al abrir la sesión: el chat saluda y queda a la espera. El botón "Nuevo chat" crea un chat con una partida nueva en blanco que espera la instrucción del usuario: el capítulo 1 solo se escribe cuando se lo pide (`/nueva` o un pedido en lenguaje natural). Cada chat tiene su propio `thread_id` y corresponde a una partida; retomar una partida (desde el sidebar, con `/partidas` o por propuesta del agente) siempre abre un chat nuevo. El panel lateral muestra capítulos, inventario y pistas de la partida activa (o "Sin partida activa").

Todavía falta implementar consecuencias narrativas más complejas, por ejemplo puertas que exijan una llave concreta.

**Memoria conversacional**

El agente está configurado con un checkpointer de LangChain sobre SQLite (`partidas/memoria_agente.sqlite3`), con una conexión por proceso.

Cada chat tiene su propio `thread_id`, distinto del id de la partida, y una partida se juega en un chat. La memoria de la conversación sobrevive a reinicios del servidor, aunque cada sesión de navegador abre un chat nuevo. Al retomar una partida, la continuidad narrativa no depende de la conversación vieja: viene del estado JSON (capítulos, decisiones, inventario, pistas y `contexto_narrativo`), que la app reconstruye en el chat nuevo.

Su funcionamiento con el modelo real todavía está pendiente de pruebas.

## 6. Generación de PDF

Se implementó la generación de documentos mediante ReportLab.

Los archivos incluyen:

- Título de la historia.
- Capítulos guardados.
- Narración de cada capítulo.
- Decisiones tomadas por el usuario.

El PDF solo se genera cuando la historia terminó (capítulo 5 guardado). Cada capítulo lleva su imagen debajo del título, con el crédito ("Foto: autor / Unsplash", con enlaces). Un PDF no puede hotlinkear, así que **al exportar** cada foto se descarga de su URL original y se incrusta desde memoria, sin guardarla en disco. Si un capítulo no tiene imagen, o no se puede descargar al exportar (por ejemplo, sin conexión), sale sin ella.

**Estado:** generación probada con una historia completa de cinco capítulos (test automático).

Pendiente: incorporar la descarga desde Streamlit. La fuente (DejaVu Sans) viene incluida en `fonts/` junto con su licencia, así que funciona en cualquier sistema operativo.

## 7. Instalación

### Requisitos

- Python 3.11 o 3.12.
- Git.
- Acceso a internet para descargar el modelo de embeddings.
- La API Key del proveedor que elijas (NVIDIA, DeepSeek u OpenRouter) con crédito disponible para ejecutar el agente.

### Clonar el repositorio

```bash
git clone https://github.com/facurodriguez06/agente-historias-interactivas.git
cd agente-historias-interactivas
```

### Crear entorno virtual (Linux / Pop!_OS)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Instalar dependencias

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Elegir proveedor de LLM

El proveedor se elige en el `.env`, sin tocar código (ver `.env.example`):

```env
LLM_PROVIDER=nvidia            # nvidia | deepseek | openrouter (sin definir: deepseek)
LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b
NVIDIA_API_KEY=tu_clave        # o DEEPSEEK_API_KEY si usás deepseek
```

`LLM_MODEL` es opcional: si queda vacío se usa el default del proveedor (`nvidia/nemotron-3-ultra-550b-a55b`, `deepseek-flash` o `deepseek/deepseek-v4.1-flash-1017`, respectivamente). La clave de NVIDIA se obtiene en [build.nvidia.com](https://build.nvidia.com). Agregar otro proveedor es sumar una función y una entrada en `PROVEEDORES` dentro de `proveedores.py`.

`LLM_TIMEOUT` (opcional, default 120) es el tiempo máximo en segundos de cada llamada al modelo. Si se agota, o el proveedor responde 429/502/503/504, el middleware de `middleware_reintentos.py` reintenta hasta 3 veces esperando 2, 4 y 8 segundos. El mismo middleware repite la llamada hasta dos veces cuando el modelo devuelve una respuesta vacía o con la tool call mal formada (en el último intento se le recuerda el formato), y guarda el mensaje crudo en `logs/` para poder diagnosticarlo.

Ojo: varios modelos del catálogo de NVIDIA responden `410 Gone` (fueron dados de baja en el endpoint hosteado aunque sigan apareciendo en la lista). `nvidia/nemotron-3-ultra-550b-a55b` es el que pasó la prueba de tool calling + razonamiento con `scripts/probar_modelo.py`; por eso es el modelo recomendado en el `.env` (y el default del proveedor `nvidia`).

Para probar el modelo antes de abrir la app:

```bash
python scripts/probar_modelo.py --listar   # modelos de NVIDIA que soportan tools
python scripts/probar_modelo.py            # pide 21 + 21 usando una tool y muestra tool calls y razonamiento
python scripts/probar_modelo.py --latencia # repite la prueba 2 veces y mide cada llamada
python scripts/probar_modelo.py --modelos nvidia/nemotron-3-ultra-550b-a55b,meta/llama-3.3-70b-instruct
                                           # compara varios modelos en una tabla (pisa LLM_MODEL)
```

### Configurar OpenRouter con DeepSeek V4.1 Flash

Instalar las dependencias actualizadas (`pip install -r requirements.txt`) y agregar o reemplazar estas variables en el `.env` local, sin duplicarlas:

```env
LLM_PROVIDER=openrouter
LLM_MODEL=deepseek/deepseek-v4.1-flash-1017
OPENROUTER_API_KEY=tu_clave_de_openrouter
LLM_TIMEOUT=120
```

Esta opción usa `ChatOpenRouter` de la integración oficial `langchain-openrouter`. La clave es de **OpenRouter**, no `DEEPSEEK_API_KEY`; no hace falta configurar NVIDIA ni DeepSeek directo. Reiniciar Streamlit después de cambiar el proveedor.

Para comprobar la conexión y el tool calling, ejecutar `python scripts/probar_modelo.py`. Esta prueba hace llamadas reales y consume créditos; `--listar` solo lista modelos NVIDIA, no OpenRouter. Después se puede abrir `streamlit run app.py` (con el RAG previamente preparado). La configuración y el enlace de tools se prueban automáticamente sin red; eso no acredita una partida completa con este modelo ni garantiza que el proveedor devuelva razonamiento.

### Configurar DeepSeek

Crear un archivo `.env` en la raíz del proyecto:

```env
DEEPSEEK_API_KEY=tu_clave
```

Para las imágenes hace falta una Access Key de Unsplash (gratis):

1. Crear una cuenta en [unsplash.com](https://unsplash.com) y una aplicación en [unsplash.com/oauth/applications](https://unsplash.com/oauth/applications).
2. Copiar la **Access Key** (no hace falta el Secret) al `.env`:

```env
UNSPLASH_ACCESS_KEY=tu_access_key
```

Cada integrante usa su propia key: la cuota del modo demo (unas 50 consultas por hora) es por aplicación. Sin la key el resto de la app funciona; solo faltan las imágenes.

Para probar la key sin correr toda la app: `python imagenes.py "foggy old mansion"` (busca una foto, imprime su URL y el autor, y comprueba que la URL responda con una imagen).

**Importante:** nunca subir `.env` ni claves reales a GitHub.

La API de DeepSeek todavía no fue configurada ni probada en este proyecto.

## 8. Ejecución

### Paso 1. Crear la base vectorial

```bash
python ingestar.py
```

Este comando lee el corpus, genera los embeddings y almacena los vectores en ChromaDB.

No necesita la API de DeepSeek.

### Paso 2. Ejecutar Streamlit

```bash
streamlit run app.py
```

La interfaz requiere configurar previamente la API Key del proveedor elegido (`NVIDIA_API_KEY`, `DEEPSEEK_API_KEY` u `OPENROUTER_API_KEY`).

Al abrir la app no hay ninguna partida activa: el chat saluda y queda a la espera. Una historia arranca únicamente con una instrucción explícita, nunca porque se escriba cualquier cosa.

**El chat**

- **`/nueva`**: instrucción explícita de juego. Si el chat actual tiene una partida sin capítulos (la que dejó el botón "Nuevo chat"), escribe el capítulo 1 en ese mismo turno; si la partida ya estaba en marcha (o terminada), abre un chat nuevo con una partida nueva y arranca ahí.
- **`/partidas`**: lista las últimas 3 partidas abiertas ("abierta" = una partida que no llegó a su desenlace), con su id corto, capítulos y último capítulo. Respondiendo con el número (o describiéndola) se abre esa partida en un chat nuevo, reconstruyendo la historia desde su JSON; también se puede pedir en lenguaje natural.
- **`/ayuda`**: muestra los comandos y qué puede hacer el chat.
- **Lista de chats** (barra lateral, estilo ChatGPT): muestra todos los chats-partida guardados, abiertos y terminados, más recientes primero, con el título del último capítulo y "N de 5 capítulos" (más "· terminada" si corresponde). El chat activo va resaltado, y tocar una entrada abre esa partida en un chat nuevo.
- **Botón "Nuevo chat"** (único botón, arriba de la lista): crea un chat con una partida nueva en blanco que espera la instrucción; la historia no se escribe sola, arranca cuando se lo pedís (por ejemplo, "empezá").
- Preguntas sobre partidas anteriores (abiertas o terminadas): el asistente responde sin avanzar ni cerrar la partida activa y, si un capítulo estaba esperando decisión, te lo recuerda al final para seguir jugando.

**Advertencia:** el flujo completo todavía no se probó con un LLM real. La aplicación no está validada como experiencia completa de juego.

### Ayuda memoria: levantar y cerrar el servidor local

**Levantarlo:** desde la raíz del repositorio, con el `.env` configurado y las dependencias instaladas:

```bash
source .venv/bin/activate
HF_HOME="$PWD/.venv/.cache/huggingface" python -m streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.fileWatcherType none
```

Abrir **http://127.0.0.1:8501** y dejar esa terminal abierta. `python -m streamlit` usa la instalación del entorno virtual. `HF_HOME` reutiliza la caché de embeddings preparada en este entorno local; mantener ese mismo valor para no descargarlos de nuevo.

`--server.fileWatcherType none` desactiva la vigilancia de archivos para evitar mensajes como `Inotify queue overflowed`. El chat sigue funcionando; si modificás código Python, reiniciá el servidor para cargar los cambios.

**Cerrar el servidor:** presionar **Ctrl+C en la terminal donde se está ejecutando**. Cerrar solamente la pestaña del navegador **no** apaga el servidor. Cuando vuelva el prompt de la terminal, opcionalmente ejecutar `deactivate` para salir del entorno virtual; `deactivate` por sí solo no detiene Streamlit.

**Volver a levantarlo:** repetir el bloque anterior. No hace falta reinstalar dependencias ni ejecutar la ingesta cada vez.

Si falta `chroma_db/` o cambió el corpus, preparar el RAG antes de iniciar la app:

```bash
source .venv/bin/activate
HF_HOME="$PWD/.venv/.cache/huggingface" python ingestar.py
```

La ingesta **reconstruye** el índice existente. Al apagar el servidor se conservan los JSON de `partidas/`, los PDF y el RAG, y también la memoria conversacional (SQLite en `partidas/`). Al volver a abrir la app, cada sesión de navegador abre un chat nuevo, pero cualquier partida se puede retomar desde su JSON desde la lista de chats del sidebar o con `/partidas`. Conversar con el agente consume créditos del proveedor.

### Tests

Las pruebas no usan LLM ni red. Incluyen un flujo de punta a punta con un modelo falso que emite llamadas a tools.

```bash
pip install -r requirements-dev.txt
pytest
```

## 9. Estado actual del desarrollo

### Implementado y probado

- [x] Creación del repositorio GitHub.
- [x] Corpus narrativo de tres documentos.
- [x] Ingesta, chunking y embeddings.
- [x] Base vectorial ChromaDB.
- [x] Recuperación semántica mediante RAG.
- [x] Creación y consulta de partidas JSON.
- [x] Registro de decisiones.
- [x] Guardado de capítulos.
- [x] Generación de PDF.
- [x] Pruebas individuales de las diez tools.
- [x] Estado JSON integrado con la sesión de Streamlit (el chat tiene su propio `thread_id`; la partida activa viaja en `ContextoPartida` y puede no haber ninguna).
- [x] Chat conversacional: preguntas sobre partidas anteriores, arrancar por instrucción y retomar siempre en un chat nuevo (un chat por partida).
- [x] Comandos deterministas `/nueva`, `/partidas` y `/ayuda` resueltos por la app, sin gastar LLM.
- [x] Lista de chats estilo ChatGPT (abiertas y terminadas, más recientes primero, activa resaltada) y botón único "Nuevo chat" que crea una partida a la espera de la instrucción.
- [x] Listado de partidas abiertas (últimas 3, las que no llegaron a un final) y retomado determinista por número, sidebar o propuesta del agente.
- [x] Cambio de partida activa: el agente propone con tools, la app valida y aplica; el id de partida nunca lo elige el LLM.
- [x] Id de partida fijado por la aplicación, no por el LLM.
- [x] Finalización garantizada en el capítulo 5 (desenlace sin opciones).
- [x] Inventario y pistas con validación (catálogo de objetos).
- [x] PDF solo al finalizar la historia.
- [x] Tests automáticos sin LLM, incluido un flujo con modelo falso.
- [x] Tool con servicio externo: imágenes de Unsplash, una por capítulo, mostradas en la UI e incluidas en el PDF (probada con la API real y con la red simulada en los tests).
- [x] Proveedores conmutables (NVIDIA / DeepSeek) desde el `.env`, con el proveedor y el modelo activos a la vista en la barra lateral.
- [x] Middleware propio de reintentos: 429, timeouts y 502/503/504 con espera exponencial (2, 4 y 8 segundos), y reintento de respuestas vacías o mal formadas.
- [x] Streaming del turno en Streamlit: el razonamiento, cada llamada a tool y su resultado se dibujan en vivo y quedan en el historial.
- [x] Razonamiento del modelo visible en la interfaz y conservado en el historial de la sesión.
- [x] Diagnóstico de respuestas vacías: el mensaje crudo del modelo se guarda en `logs/`.
- [x] Red de seguridad en la interfaz: si el turno termina sin texto, se muestra el capítulo guardado en el JSON.
- [x] Fuente del PDF incluida en el repo (`fonts/DejaVuSans.ttf`), así el PDF sale igual en cualquier sistema operativo.
- [x] Medición de latencia y comparación de modelos en `scripts/probar_modelo.py` (`--latencia`, `--modelos`).

### Implementado, pendiente de pruebas con un LLM real

- [ ] Una partida completa de punta a punta con el modelo real (el agente está armado con `create_agent` y probado con un modelo falso).
- [ ] Uso coordinado de las diez herramientas siguiendo el prompt.
- [ ] El flujo de chat con modelo real: arrancar por instrucción, meta-consultas y retomado propuesto por el agente (los comandos y el retomado determinista ya están probados sin LLM).
- [ ] Memoria conversacional mediante checkpointer.
- [ ] Que el modelo respete el catálogo de objetos.
- [ ] Que el modelo pida la imagen de cada capítulo con consultas útiles.

### Pendiente de desarrollar

- [ ] Confirmar el nombre del modelo de DeepSeek (`deepseek-flash` no está verificado); el proveedor probado hasta ahora es NVIDIA.
- [ ] Más tools con servicio externo, si la cátedra lo requiere (por ejemplo, clima).
- [ ] Confirmar con las pautas de Unsplash el uso de las fotos dentro del PDF (se descargan solo al exportar, desde su URL original, y no se guardan).
- [ ] Opciones como botones y descarga del PDF en la interfaz.
- [ ] Reglas de consecuencias más complejas (por ejemplo, puertas que exigen una llave).
- [ ] Ampliar el corpus y evitar que el RAG devuelva pistas todavía inaccesibles.
- [ ] Retomar el mismo chat tras cerrar el navegador (hoy cada sesión de navegador abre un chat nuevo; las partidas se retoman desde su JSON).
- [ ] Probar la instalación desde cero.
- [ ] Completar documentación y presentación final.

## 10. Consideraciones técnicas

- El protagonista siempre es el usuario; no se le asigna identidad ficticia.
- El RAG almacena conocimiento del universo, no las decisiones de cada partida.
- El JSON conserva los acontecimientos específicos de cada historia.
- Los embeddings se generan localmente y no consumen tokens de DeepSeek.
- Las herramientas se implementaron de forma modular para permitir pruebas independientes.
- El modelo no puede modificar el estado de una partida sin pasar por las validaciones de `estado_partida.py`, y no elige el id de la partida.
- Las imágenes vienen de la API de Unsplash (fotos de stock de ambiente), no se generan con IA: es más rápido y confiable, y la atribución al fotógrafo queda en el PDF y en la UI.

## 11. Próximos pasos

La prioridad es validar el agente ya cableado con un modelo real: una partida completa de cinco capítulos en la que el modelo use las seis herramientas en el orden que pide el prompt.

Después se completará la interfaz (opciones como botones, descarga del PDF), se ajustará el corpus y, finalmente, las pruebas completas, la documentación y la preparación de la exposición.

---

**Estado general:** prototipo técnico en desarrollo. El flujo de la partida (estado, cierre en cinco capítulos, inventario, imágenes, PDF), la interfaz con streaming y razonamiento, y el middleware de reintentos están implementados y probados con tests automáticos y un modelo falso. Todavía no existe una demo integral validada con un LLM real.
