# Agente de Historias Interactivas

Trabajo Integrador — Modelos de Lenguaje | UTN FRM | Unidad 5

## 1. Descripción del proyecto

Agente de inteligencia artificial desarrollado con **LangChain**, que genera historias interactivas de misterio donde el usuario es el protagonista.

El agente narra en segunda persona y permite tomar decisiones que modifican el desarrollo de la aventura.

El proyecto combina:

- **LLM:** DeepSeek V4.1 Flash, para generar las narraciones.
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
├── agente.py
├── proveedores.py
├── app.py
├── herramientas.py
├── estado_partida.py
├── ingestar.py
├── generar_pdf.py
├── imagenes.py
├── scripts/
│   └── probar_modelo.py
├── tests/
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── README.md
└── .gitignore
```

**Función de cada archivo:**

- `agente.py`: arma el agente con el modelo de `proveedores.py`, las herramientas disponibles, el prompt y el checkpointer.
- `proveedores.py`: fábrica de modelos; elige NVIDIA o DeepSeek según `LLM_PROVIDER` del `.env`.
- `scripts/probar_modelo.py`: prueba manual del modelo configurado (tool calling y razonamiento), fuera de la app.
- `app.py`: implementa la interfaz web mediante Streamlit.
- `herramientas.py`: contiene las seis tools disponibles para el agente y `ContextoPartida`, que lleva el id de la partida a las tools.
- `estado_partida.py`: administra los estados de partida mediante archivos JSON y hace cumplir las reglas de la historia (capítulos, decisiones, inventario, cierre).
- `ingestar.py`: procesa los documentos y construye la base vectorial RAG.
- `generar_pdf.py`: crea el PDF a partir de los capítulos, decisiones e imágenes guardados.
- `imagenes.py`: cliente de la API de Unsplash (búsqueda y atribución de la foto de cada capítulo; las fotos se muestran por hotlinking).
- `corpus/`: contiene los documentos que definen el universo narrativo.
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

La ingesta inicial procesó 3 documentos y generó 8 fragmentos. La recuperación semántica se comprobó correctamente mediante una consulta de prueba.

## 4. Herramientas implementadas

Se implementaron seis tools de LangChain.

| Tool | Función |
|---|---|
| `buscar_contexto_narrativo` | Recupera información del corpus utilizando RAG. |
| `consultar_estado_partida` | Devuelve capítulos, decisiones, inventario, pistas y el siguiente paso de la partida en curso. |
| `registrar_decision` | Valida y guarda la opción elegida (1, 2 o 3) y actualiza inventario y pistas (`objetos_recogidos`, `objetos_usados`, `pistas_descubiertas`). |
| `guardar_capitulo` | Almacena el título, texto y opciones de un capítulo: tres opciones en los capítulos 1 a 4; el capítulo 5 es el desenlace y no lleva opciones. |
| `buscar_imagen_capitulo` | **Servicio externo (API de Unsplash).** Busca una foto de ambiente para el capítulo recién guardado, y guarda su URL original en el capítulo, con el crédito del fotógrafo. La foto se muestra por hotlinking, sin guardar copias. |
| `generar_pdf_historia` | Genera el PDF ilustrado de la historia. Solo funciona cuando la historia terminó. |

Las herramientas utilizan el decorador `@tool` de LangChain.

**El id de la partida no es un argumento de las tools.** La aplicación lo fija en el contexto de cada ejecución (`ContextoPartida`, mediante `context_schema` y `ToolRuntime`) y las tools lo leen de ahí. El LLM no lo ve ni lo elige. Las tools de escritura devuelven `siguiente_paso`, que le indica al agente qué corresponde hacer, y los errores de validación vuelven como `{"error": ...}` sin cortar el flujo.

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

La app crea la partida al abrir la sesión y usa su id también como `thread_id` del checkpointer. El panel lateral muestra capítulos, inventario y pistas.

Todavía falta implementar consecuencias narrativas más complejas, por ejemplo puertas que exijan una llave concreta.

**Memoria conversacional**

El agente está configurado con `InMemorySaver`, un checkpointer de LangChain.

Permite conservar el historial por `thread_id` mientras la memoria del proceso siga disponible. El estado JSON, en cambio, sobrevive a un reinicio.

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
- API Key de DeepSeek con crédito disponible para ejecutar el agente.

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
LLM_PROVIDER=nvidia            # nvidia | deepseek (sin definir: deepseek)
LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b
NVIDIA_API_KEY=tu_clave        # o DEEPSEEK_API_KEY si usás deepseek
```

`LLM_MODEL` es opcional: si queda vacío se usa el default del proveedor (`nvidia/nemotron-3-ultra-550b-a55b` o `deepseek-flash`). La clave de NVIDIA se obtiene en [build.nvidia.com](https://build.nvidia.com). Agregar otro proveedor es sumar una función y una entrada en `PROVEEDORES` dentro de `proveedores.py`.

`LLM_TIMEOUT` (opcional, default 120) es el tiempo máximo en segundos de cada llamada al modelo. Si se agota, o el proveedor responde 429/502/503/504, el middleware de `middleware_reintentos.py` reintenta hasta 3 veces esperando 2, 4 y 8 segundos.

Ojo: varios modelos del catálogo de NVIDIA responden `410 Gone` (fueron dados de baja en el endpoint hosteado aunque sigan apareciendo en la lista). `nvidia/nemotron-3-ultra-550b-a55b` es el que pasó la prueba de tool calling + razonamiento con `scripts/probar_modelo.py`; por eso es el default.

Para probar el modelo antes de abrir la app:

```bash
python scripts/probar_modelo.py --listar   # modelos de NVIDIA que soportan tools
python scripts/probar_modelo.py            # pide 21 + 21 usando una tool y muestra tool calls y razonamiento
```

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

La interfaz requiere configurar previamente la API de DeepSeek.

Al abrir la app se crea una partida nueva. Con el botón "Nueva partida" se crea otra.

**Advertencia:** el flujo completo todavía no se probó con un LLM real. La aplicación no está validada como experiencia completa de juego.

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
- [x] Pruebas individuales de las cinco tools.
- [x] Estado JSON integrado con la sesión de Streamlit (el id de partida es también el `thread_id`).
- [x] Id de partida fijado por la aplicación, no por el LLM.
- [x] Finalización garantizada en el capítulo 5 (desenlace sin opciones).
- [x] Inventario y pistas con validación (catálogo de objetos).
- [x] PDF solo al finalizar la historia.
- [x] Tests automáticos sin LLM, incluido un flujo con modelo falso.
- [x] Tool con servicio externo: imágenes de Unsplash, una por capítulo, mostradas en la UI e incluidas en el PDF (probada con la API real y con la red simulada en los tests).

### Implementado, pendiente de pruebas con un LLM real

- [ ] Ejecución de `create_agent` con DeepSeek.
- [ ] Uso coordinado de las cinco herramientas siguiendo el prompt.
- [ ] Memoria conversacional mediante checkpointer.
- [ ] Streaming de herramientas en Streamlit.
- [ ] Que el modelo respete el catálogo de objetos.
- [ ] Que el modelo pida la imagen de cada capítulo con consultas útiles.

### Pendiente de desarrollar

- [ ] Confirmar el nombre del modelo de DeepSeek (`deepseek-flash` no está verificado).
- [ ] Más tools con servicio externo, si la cátedra lo requiere (por ejemplo, clima).
- [ ] Confirmar con las pautas de Unsplash el uso de las fotos dentro del PDF (se descargan solo al exportar, desde su URL original, y no se guardan).
- [ ] Opciones como botones y descarga del PDF en la interfaz.
- [ ] Mostrar el razonamiento del modelo, si el proveedor lo expone.
- [ ] Manejar errores 429 y reintentos con espera.
- [ ] Reglas de consecuencias más complejas (por ejemplo, puertas que exigen una llave).
- [ ] Ampliar el corpus y evitar que el RAG devuelva pistas todavía inaccesibles.
- [ ] Persistir la conversación entre reinicios.
- [ ] Fuente del PDF independiente del sistema operativo.
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

La prioridad es conectar el modelo de lenguaje y conseguir que el agente utilice las herramientas durante una historia real.

Después se completará la interfaz (opciones, descarga del PDF), el manejo de errores del proveedor y, finalmente, las pruebas completas, la documentación y la preparación de la exposición.

---

**Estado general:** prototipo técnico en desarrollo. El flujo de la partida (estado, cierre en cinco capítulos, inventario, PDF) está implementado y probado con tests automáticos y un modelo falso. Todavía no existe una demo integral validada con un LLM real.
