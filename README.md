
# Agente de Historias Interactivas

Trabajo Integrador — Modelos de Lenguaje | UTN FRM | Unidad 5

## 1. Descripción del proyecto

Agente de inteligencia artificial desarrollado con **LangChain**, capaz de generar historias interactivas de misterio en las que el usuario es el protagonista.

El agente narra en español, utilizando la segunda persona, y permite tomar decisiones que modifican el desarrollo de la aventura. Cada historia tiene cinco capítulos y las decisiones del jugador se guardan para mantener la continuidad narrativa.

La aplicación incluye una interfaz conversacional desarrollada con **Streamlit**, similar a un sistema de chats. Cada partida puede abrirse desde la barra lateral, retomarse, renombrarse o eliminarse.

Además, el usuario puede consultar información sobre partidas anteriores sin modificar la partida que está jugando.

### Tecnologías utilizadas

- **LangChain y LangGraph:** construcción del agente, herramientas y memoria.
- **LLM:** integración con NVIDIA, DeepSeek y OpenRouter.
- **RAG:** recuperación de información sobre el universo narrativo.
- **Hugging Face:** generación de embeddings multilingües.
- **ChromaDB:** almacenamiento de la base vectorial.
- **Streamlit:** interfaz web conversacional.
- **Unsplash API:** búsqueda de imágenes para ilustrar los capítulos.
- **ReportLab:** generación de historias en PDF.
- **JSON:** persistencia del estado de cada partida.
- **SQLite:** almacenamiento de checkpoints del agente.
- **Pytest:** pruebas automáticas.

**Objetivo:** ofrecer una experiencia narrativa interactiva de misterio, con decisiones, memoria, recuperación de contexto, imágenes y exportación de la historia completa a PDF.

---

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

### Función de los principales archivos

- **`agente.py`:** configura el agente mediante `create_agent`, define sus instrucciones, registra las herramientas y conecta el checkpointer.
- **`proveedores.py`:** permite elegir el proveedor y modelo de lenguaje desde el archivo `.env`.
- **`app.py`:** implementa la interfaz Streamlit, el chat, la barra lateral, la navegación entre partidas, las decisiones y la visualización de herramientas.
- **`herramientas.py`:** define las diez herramientas disponibles para el agente.
- **`estado_partida.py`:** administra los JSON de las partidas y valida las reglas del juego.
- **`comandos_chat.py`:** procesa comandos como `/nueva`, `/partidas` y `/ayuda`.
- **`pasos_agente.py`:** procesa los mensajes del agente para mostrar herramientas, resultados y razonamiento en la interfaz.
- **`middleware_reintentos.py`:** implementa reintentos ante errores del proveedor o respuestas inválidas.
- **`diagnostico.py`:** guarda información para analizar respuestas problemáticas del modelo.
- **`ingestar.py`:** procesa los documentos del corpus y construye la base vectorial.
- **`imagenes.py`:** consulta Unsplash y selecciona imágenes considerando la ubicación y ambientación del capítulo.
- **`generar_pdf.py`:** genera el documento PDF con los capítulos, decisiones e imágenes.
- **`scripts/probar_modelo.py`:** permite verificar el funcionamiento de los modelos y sus llamadas a herramientas.
- **`tests/`:** contiene las pruebas automáticas.

### Archivos generados durante la ejecución

Las siguientes carpetas se crean localmente y no se versionan en Git:

| Carpeta | Contenido |
|---|---|
| `chroma_db/` | Base vectorial del sistema RAG. |
| `partidas/` | Estados JSON y memoria SQLite. |
| `historias_generadas/` | Historias exportadas en PDF. |
| `logs/` | Archivos de diagnóstico. |

El archivo `.env` también se excluye de Git para evitar publicar claves privadas.

---

## 3. Sistema RAG

El agente utiliza **Retrieval-Augmented Generation (RAG)** para consultar información relevante antes de generar los capítulos.

Esto permite que las historias respeten las características del universo narrativo definido por el proyecto.

### Corpus utilizado

El corpus está formado por tres documentos Markdown:

1. **`ambientacion.md`:** describe la atmósfera y las reglas generales del mundo.
2. **`lugares.md`:** define las ubicaciones disponibles, sus características y conexiones.
3. **`pistas_y_objetos.md`:** contiene información sobre objetos, pistas y elementos de la investigación.

### Funcionamiento

1. `ingestar.py` lee los documentos del corpus.
2. Los textos se dividen en fragmentos o *chunks*.
3. Se generan embeddings con un modelo multilingüe de Hugging Face.
4. Los embeddings se almacenan en ChromaDB.
5. El agente utiliza `buscar_contexto_narrativo` para recuperar información relevante.
6. El modelo emplea el contexto recuperado para generar la historia.

El sistema diferencia entre el conocimiento general del mundo y los acontecimientos específicos de cada partida.

Por ejemplo, el RAG puede indicar que existe una llave en determinado lugar, pero eso no significa que el jugador ya la haya encontrado.

Los objetos descubiertos, decisiones y pistas se registran por separado en el estado de la partida.

### Estado

El sistema RAG está implementado y se ha probado mediante consultas de recuperación semántica y durante la generación de capítulos.

---

## 4. Herramientas implementadas

El agente dispone de **diez herramientas (`tools`)**, desarrolladas con LangChain.

| Herramienta | Función |
|---|---|
| `buscar_contexto_narrativo` | Recupera información relevante del corpus mediante RAG. |
| `consultar_estado_partida` | Consulta el estado de la partida activa. |
| `registrar_decision` | Registra y valida la decisión del jugador. |
| `guardar_capitulo` | Guarda un nuevo capítulo y su contexto narrativo. |
| `buscar_imagen_capitulo` | Busca y asocia una imagen al capítulo. |
| `generar_pdf_historia` | Genera el PDF de una historia finalizada. |
| `listar_partidas_abiertas` | Lista las partidas que todavía pueden retomarse. |
| `consultar_otra_partida` | Consulta una partida anterior sin modificar la actual. |
| `iniciar_nueva_partida` | Propone crear una nueva partida desde el agente. |
| `retomar_partida` | Propone retomar una partida abierta. |

Las herramientas utilizan el decorador `@tool` de LangChain.

### Contexto de ejecución

El identificador de la partida activa se transmite mediante `ContextoPartida` y `ToolRuntime`.

Esto permite que las herramientas trabajen sobre la partida correcta sin que el modelo tenga que inventar o seleccionar su identificador.

La aplicación es responsable de validar y aplicar los cambios de partida.

### Validaciones

Las herramientas permiten controlar que:

- No se escriban más de cinco capítulos.
- Los capítulos 1 a 4 tengan exactamente tres opciones.
- El capítulo 5 sea un desenlace sin opciones.
- No se registren decisiones cuando no corresponda.
- No se agreguen objetos inválidos al inventario.
- No se recoja dos veces el mismo objeto.
- No se utilicen objetos que el jugador todavía no posee.
- No se modifique una partida finalizada.

Cuando una operación no es válida, la herramienta devuelve un error controlado para evitar alterar el estado.

### Imágenes de los capítulos

La herramienta `buscar_imagen_capitulo` utiliza la API de Unsplash.

La selección fue mejorada para considerar:

- La ubicación actual guardada en el JSON.
- Los ambientes definidos para la historia.
- Las descripciones y etiquetas de las fotografías.
- La iluminación aproximada de la escena.
- Las imágenes utilizadas previamente.

El sistema realiza búsquedas específicas para ambientes como bibliotecas, recibidores, estudios e invernaderos.

Cuando el capítulo describe una escena oscura, la búsqueda intenta priorizar fotografías compatibles con esa ambientación.

La iluminación se estima utilizando información de Unsplash, por lo que no constituye un análisis visual perfecto.

Si no se encuentra una imagen adecuada o falla la API, la historia puede continuar sin imagen.

Las fotografías se muestran mediante sus URLs originales y conservan la atribución correspondiente.

---

## 5. Estado, memoria y gestión de partidas

El proyecto utiliza dos mecanismos complementarios para conservar información.

### 5.1. Estado estructurado en JSON

Cada partida tiene un identificador único y un archivo JSON propio.

En él se almacenan:

- Identificador de la partida.
- Capítulos generados.
- Opciones disponibles.
- Decisiones tomadas.
- Inventario del jugador.
- Pistas descubiertas.
- Imágenes y datos de atribución.
- Contexto narrativo persistente.
- Estado de finalización.
- Nombre personalizado del chat, cuando el usuario lo define.

### Contexto narrativo persistente

El estado guarda información como:

- `ubicacion_actual`
- `hechos_establecidos`
- `misterios_pendientes`
- `misterios_resueltos`
- `resumen_ultimo_capitulo`

Estos datos ayudan a evitar contradicciones entre capítulos y permiten continuar la historia aunque se abra una nueva sesión.

### 5.2. Memoria conversacional con SQLite

El agente utiliza un checkpointer de LangGraph respaldado por SQLite.

La memoria se almacena en:

```text
partidas/memoria_agente.sqlite3
```

Cada conversación utiliza un `thread_id`.

El identificador del chat y el identificador de la partida son conceptos diferentes.

Cuando se retoma una partida desde la interfaz, su historia se reconstruye desde el JSON. Por eso no depende exclusivamente de la memoria conversacional anterior.

### 5.3. Gestión de chats

La interfaz permite:

- Crear un chat nuevo.
- Abrir partidas guardadas.
- Retomar historias inconclusas.
- Consultar partidas anteriores.
- Renombrar la partida activa.
- Eliminar chats con confirmación.
- Identificar partidas mediante un código corto.
- Continuar una partida sin modificar sus decisiones pendientes.

El nombre personalizado se guarda en el JSON, por lo que permanece después de cerrar la aplicación.

Si el usuario no asigna un nombre, la interfaz utiliza el título del último capítulo o **«Partida nueva»** cuando todavía no hay capítulos.

### Eliminación de chats

El botón **Borrar** solicita confirmación antes de eliminar una partida.

Al confirmar, se elimina el archivo JSON correspondiente y la partida desaparece de la lista.

Si se elimina la partida activa, la aplicación vuelve a una conversación sin partida seleccionada.

Los PDF previamente generados no se eliminan automáticamente. Los checkpoints históricos de SQLite tampoco se limpian con esta operación.

---

## 6. Generación de PDF

La aplicación utiliza **ReportLab** para generar un documento con la historia completa.

El PDF incluye:

- Título de la historia.
- Cinco capítulos narrativos.
- Decisiones tomadas por el jugador.
- Imágenes asociadas a los capítulos, cuando existen.
- Créditos de los fotógrafos.
- Presentación visual con estética de misterio.

### Funcionamiento

El agente puede generar el PDF una vez que se guarda el capítulo 5.

La información se recupera del JSON, sin necesidad de reconstruir la historia desde la conversación.

Las imágenes se descargan temporalmente en memoria para incrustarlas en el documento.

No se almacenan copias individuales de las fotografías.

Si una imagen no está disponible, el PDF puede generarse sin ella.

### Ubicación de los archivos

Los documentos se guardan en:

```text
historias_generadas/
```

El agente informa la ruta del PDF al finalizar la historia.

### Estado

La generación y descarga directa del PDF desde Streamlit están implementadas y probadas con historias completas de cinco capítulos.

---

## 7. Instalación

### Requisitos

- Python 3.11 o 3.12.
- Git.
- Conexión a internet.
- Clave API de un proveedor de modelos compatible.
- Clave de Unsplash si se desean imágenes.

### Clonar el repositorio

```bash
git clone https://github.com/facurodriguez06/agente-historias-interactivas.git
cd agente-historias-interactivas
```

### Crear el entorno virtual

En Linux o Pop!_OS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Instalar dependencias

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Para ejecutar las pruebas automáticas:

```bash
pip install -r requirements-dev.txt
```

### Configurar las variables de entorno

Crear un archivo `.env` en la raíz del proyecto.

El proveedor se selecciona mediante `LLM_PROVIDER`.

Se admiten:

- `nvidia`
- `deepseek`
- `openrouter`

El modelo puede especificarse con `LLM_MODEL`.

Si no se indica un proveedor, la configuración utiliza DeepSeek como valor predeterminado.

### Ejemplo: OpenRouter con DeepSeek

Configuración utilizada durante las pruebas manuales del proyecto:

```env
LLM_PROVIDER=openrouter
LLM_MODEL=deepseek/deepseek-v4.1-flash-1017
OPENROUTER_API_KEY=tu_clave
LLM_TIMEOUT=120
```

La clave se obtiene desde la plataforma de OpenRouter.

### Ejemplo: NVIDIA

```env
LLM_PROVIDER=nvidia
LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b
NVIDIA_API_KEY=tu_clave
LLM_TIMEOUT=120
```

### Ejemplo: DeepSeek directo

```env
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-flash
DEEPSEEK_API_KEY=tu_clave
LLM_TIMEOUT=120
```

El nombre `deepseek-flash` corresponde a la configuración predeterminada implementada en el código. Su disponibilidad debe verificarse con la API correspondiente.

### Configurar Unsplash

Crear una aplicación desde:

https://unsplash.com/oauth/applications

Agregar al `.env`:

```env
UNSPLASH_ACCESS_KEY=tu_access_key
```

La Access Key permite buscar imágenes para los capítulos.

Sin esta clave, la generación de historias puede funcionar, pero no se obtendrán nuevas imágenes de Unsplash.

### Seguridad

**Nunca subir archivos `.env` ni claves API reales al repositorio.**

El archivo `.env.example` sirve como referencia para configurar el proyecto.

---

## 8. Ejecución y uso de la aplicación

### Paso 1. Preparar el sistema RAG

Desde la raíz del proyecto:

```bash
python ingestar.py
```

Este comando procesa el corpus y crea la base vectorial en ChromaDB.

Debe ejecutarse en la instalación inicial y cuando se modifiquen los documentos del corpus.

### Paso 2. Iniciar Streamlit

```bash
python -m streamlit run app.py
```

Abrir en el navegador la dirección indicada por Streamlit, normalmente:

```text
http://localhost:8501
```

### Comandos del chat

**`/nueva`**

Inicia una historia nueva.

Si la partida activa está vacía, comienza el capítulo 1 dentro de ella.

Si la partida actual ya tiene capítulos, crea una nueva partida y comienza su historia.

También se reconocen expresiones de inicio como **«empezá»**, **«arrancá»** o **«juguemos»**, que permiten comenzar directamente cuando no hay una historia iniciada.

**`/partidas`**

Muestra hasta tres partidas guardadas recientes, excluyendo la partida actual.

La interfaz presenta botones para seleccionar una partida y una cuarta opción fija:

**4. Continuar con partida actual**

Esta cuarta opción cierra el menú y vuelve a mostrar las decisiones pendientes, sin registrar una elección ni generar un capítulo nuevo.

El menú también permite seleccionar opciones escribiendo su número.

Las partidas terminadas pueden abrirse para releer su historia, pero no seguir jugando.

**`/ayuda`**

Muestra información sobre los comandos disponibles y las funciones del chat.

### Barra lateral

La barra lateral contiene:

- Identificador de la partida actual.
- Opción para renombrar el chat activo.
- Botón **Nuevo chat**.
- Lista de partidas guardadas.
- Botón **Borrar** junto a cada partida.
- Información del proveedor y modelo configurados.
- Estado, inventario y pistas de la partida activa.

El nombre de cada chat puede personalizarse desde la opción **Renombrar chat actual**.

### Decisiones de la historia

Los capítulos 1 a 4 presentan tres botones de decisión.

El jugador selecciona una opción y el agente continúa la narración considerando el estado y la información recuperada mediante RAG.

El capítulo 5 es el desenlace y no presenta nuevas decisiones.

### Consultas durante la partida

El usuario también puede preguntar al agente sobre:

- Decisiones anteriores.
- Objetos encontrados.
- Pistas descubiertas.
- Misterios pendientes.
- Información de otras partidas.

Estas consultas no deberían avanzar la historia ni registrar decisiones por sí mismas.

### Iniciar Streamlit con configuración local

En Linux o Pop!_OS también puede utilizarse:

```bash
source .venv/bin/activate

HF_HOME="$PWD/.venv/.cache/huggingface" python -m streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.fileWatcherType none
```

Esta configuración permite reutilizar la caché local de Hugging Face y desactiva la vigilancia de archivos para evitar posibles problemas con `inotify`.

Cuando se utiliza `--server.fileWatcherType none`, es necesario reiniciar Streamlit después de modificar el código.

Para detener el servidor, presionar **Ctrl+C** en la terminal.

---

## 9. Estado actual del desarrollo

### Implementado

- [x] Creación del repositorio y organización del proyecto.
- [x] Corpus narrativo de tres documentos.
- [x] Ingesta y generación de embeddings.
- [x] Almacenamiento vectorial en ChromaDB.
- [x] Recuperación de contexto mediante RAG.
- [x] Agente construido con LangChain `create_agent`.
- [x] Integración de diez herramientas.
- [x] Selección de proveedor mediante variables de entorno.
- [x] Estado persistente de partidas en JSON.
- [x] Memoria conversacional con SQLite.
- [x] Generación de historias de cinco capítulos.
- [x] Tres decisiones por capítulo, excepto el desenlace.
- [x] Validación del inventario y las pistas.
- [x] Contexto narrativo persistente.
- [x] Generación de imágenes mediante Unsplash.
- [x] Selección de imágenes considerando ubicación y ambientación.
- [x] Generación de historias en PDF.
- [x] Interfaz Streamlit.
- [x] Visualización de llamadas a herramientas y resultados.
- [x] Visualización del razonamiento cuando el proveedor lo entrega.
- [x] Comandos `/nueva`, `/partidas` y `/ayuda`.
- [x] Botones para seleccionar decisiones.
- [x] Apertura de partidas anteriores.
- [x] Menú para continuar con la partida actual.
- [x] Inicio directo del capítulo 1 con instrucciones reconocidas.
- [x] Lista de chats en la barra lateral.
- [x] Renombrado de chats con persistencia en JSON.
- [x] Eliminación de chats con confirmación.
- [x] Middleware de reintentos.
- [x] Descarga directa del PDF desde Streamlit.
- [x] Pruebas automáticas con Pytest.

### Pruebas realizadas

Se realizaron pruebas automáticas de las herramientas y del flujo de la aplicación utilizando datos y modelos simulados.

La suite actual cuenta con **225 pruebas aprobadas** verificadas tras los últimos cambios.

También se realizaron pruebas manuales utilizando un modelo real de DeepSeek mediante OpenRouter.

Estas pruebas incluyeron:

- Inicio de nuevas historias.
- Generación de capítulos.
- Registro de decisiones.
- Recuperación de información mediante RAG.
- Consulta de partidas anteriores sin avanzar la actual.
- Generación de imágenes.
- Finalización de una historia de cinco capítulos.
- Generación del PDF correspondiente.

Las pruebas manuales permitieron comprobar el funcionamiento general, aunque no garantizan que todas las posibles decisiones produzcan siempre resultados narrativamente correctos.

### Pendiente de mejorar o verificar

- [ ] Mejorar la relevancia visual de algunas imágenes.
- [ ] Ampliar las reglas narrativas y consecuencias de las decisiones.
- [ ] Extender el corpus con nuevas ubicaciones y situaciones.
- [ ] Evitar que el RAG exponga información que el jugador todavía no debería conocer.
- [ ] Mejorar la identificación visual de las partidas en la barra lateral.
- [ ] Permitir recuperar exactamente el historial conversacional después de cerrar el navegador.
- [ ] Revisar la limpieza de checkpoints antiguos al eliminar partidas.
- [ ] Probar la instalación desde cero.
- [ ] Completar la documentación y la presentación final.

---

## 10. Consideraciones técnicas

### Consistencia narrativa

El agente debe respetar las decisiones y descubrimientos realizados por el jugador.

El corpus RAG define el mundo narrativo, mientras que el JSON determina qué sucedió efectivamente en cada partida.

El estado persistente permite conservar hechos establecidos y misterios pendientes entre capítulos.

### Separación de responsabilidades

La arquitectura distingue:

- **LLM:** genera respuestas y propone acciones.
- **RAG:** proporciona información del universo narrativo.
- **Tools:** realizan operaciones concretas.
- **JSON:** conserva el estado de la partida.
- **SQLite:** mantiene checkpoints de conversación.
- **Streamlit:** controla la interacción del usuario.
- **ReportLab:** genera el PDF final.

Esta separación facilita la validación, las pruebas y el mantenimiento.

### Control de errores

El proyecto incluye un middleware que permite reintentar determinadas llamadas fallidas al proveedor.

También contempla errores de herramientas, búsquedas sin resultados y fallas de servicios externos.

Cuando Unsplash no devuelve una fotografía adecuada, la narración puede continuar sin imagen.

### Seguridad y persistencia

Las claves API se leen desde variables de entorno.

Los identificadores de partida se validan antes de acceder a sus archivos.

Las operaciones de escritura del estado se realizan de forma atómica para reducir el riesgo de archivos incompletos.

El borrado de partidas desde la interfaz requiere confirmación.

### Limitaciones actuales

El sistema todavía puede generar inconsistencias narrativas, repetir ideas o seleccionar fotografías que no coincidan completamente con la escena.

La calidad de las respuestas depende del modelo utilizado, del contexto recuperado y de las instrucciones del agente.

Las pruebas automáticas verifican reglas y comportamientos concretos, pero no reemplazan la evaluación manual de la calidad narrativa.

---

## 11. Próximos pasos

Las prioridades para continuar el desarrollo son:

1. Mejorar la presentación y administración de los chats.
2. Revisar la coherencia narrativa y las consecuencias de las decisiones.
3. Completar las pruebas finales con un modelo real.
4. Preparar la documentación y presentación del trabajo integrador.

---

**Estado general:** prototipo funcional en desarrollo. El proyecto integra un agente con herramientas, RAG, memoria persistente, generación de historias, gestión de partidas, imágenes de Unsplash y exportación a PDF.

Se realizaron pruebas automáticas y pruebas manuales de historias completas con un modelo real. Quedan mejoras de interfaz, validaciones adicionales y verificaciones finales antes de considerar terminada la entrega.
