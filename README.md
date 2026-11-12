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
├── app.py
├── herramientas.py
├── estado_partida.py
├── ingestar.py
├── generar_pdf.py
├── requirements.txt
├── README.md
└── .gitignore
```

**Función de cada archivo:**

- `agente.py`: configura el modelo DeepSeek, las herramientas disponibles, el prompt y el checkpointer.
- `app.py`: implementa la interfaz web mediante Streamlit.
- `herramientas.py`: contiene las cinco tools disponibles para el agente.
- `estado_partida.py`: administra los estados de partida mediante archivos JSON.
- `ingestar.py`: procesa los documentos y construye la base vectorial RAG.
- `generar_pdf.py`: crea el PDF a partir de los capítulos y decisiones guardados.
- `corpus/`: contiene los documentos que definen el universo narrativo.

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

Actualmente se implementaron y probaron individualmente cinco tools de LangChain.

| Tool | Función |
|---|---|
| `buscar_contexto_narrativo` | Recupera información del corpus utilizando RAG. |
| `consultar_estado_partida` | Consulta decisiones, inventario y progreso de una partida. |
| `registrar_decision` | Valida y guarda la opción elegida por el usuario. |
| `guardar_capitulo` | Almacena el título, texto y tres opciones de un capítulo. |
| `generar_pdf_historia` | Genera un PDF con los capítulos y decisiones guardados. |

Las herramientas utilizan el decorador `@tool` de LangChain.

**Estado:** las cinco herramientas funcionan individualmente. Falta comprobar su funcionamiento coordinado durante una aventura completa.

## 5. Estado y memoria

Se utilizan dos mecanismos diferentes:

**Estado estructurado (JSON)**

Cada partida tiene un identificador único y almacena:

- Capítulo actual.
- Capítulos generados.
- Decisiones tomadas.
- Inventario.
- Pistas descubiertas.

Las funciones de creación, consulta y registro de decisiones fueron probadas. Todavía falta implementar la actualización automática del inventario y las consecuencias narrativas.

**Memoria conversacional**

El agente está configurado con `InMemorySaver`, un checkpointer de LangChain.

Permite conservar el historial por `thread_id` mientras la memoria del proceso siga disponible.

Su funcionamiento con el modelo real todavía está pendiente de pruebas.

También falta vincular correctamente el identificador de la partida JSON con la sesión del usuario en Streamlit.

## 6. Generación de PDF

Se implementó la generación de documentos mediante ReportLab.

Los archivos incluyen:

- Título de la historia.
- Capítulos guardados.
- Narración de cada capítulo.
- Decisiones tomadas por el usuario.

**Estado:** generación probada correctamente con una partida de ejemplo.

Pendiente: incorporar la descarga desde Streamlit y probar una historia completa de cinco capítulos.

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

### Configurar DeepSeek

Crear un archivo `.env` en la raíz del proyecto:

```env
DEEPSEEK_API_KEY=tu_clave
```

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

**Advertencia:** la integración completa entre Streamlit, el estado JSON y las herramientas está en desarrollo. La aplicación todavía no está validada como experiencia completa de juego.

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

### Implementado, pendiente de pruebas integrales

- [ ] Ejecución de `create_agent` con DeepSeek.
- [ ] Uso coordinado de las cinco herramientas.
- [ ] Memoria conversacional mediante checkpointer.
- [ ] Streaming de herramientas en Streamlit.

### Pendiente de desarrollar

- [ ] Integrar el estado JSON con la sesión de Streamlit.
- [ ] Implementar consecuencias persistentes de las decisiones.
- [ ] Gestionar inventario y pistas descubiertas.
- [ ] Garantizar la finalización de la historia en cinco capítulos.
- [ ] Implementar controles para evitar inconsistencias narrativas.
- [ ] Incorporar descarga de PDF desde la interfaz.
- [ ] Manejar errores del modelo y sus herramientas.
- [ ] Realizar pruebas completas con diferentes recorridos.
- [ ] Completar documentación y presentación final.

## 10. Consideraciones técnicas

- El protagonista siempre es el usuario; no se le asigna identidad ficticia.
- El RAG almacena conocimiento del universo, no las decisiones de cada partida.
- El JSON conserva los acontecimientos específicos de cada historia.
- Los embeddings se generan localmente y no consumen tokens de DeepSeek.
- Las herramientas se implementaron de forma modular para permitir pruebas independientes.
- El modelo no debe modificar el estado de una partida sin pasar por las validaciones correspondientes.
- La generación de imágenes queda fuera del alcance inicial.

## 11. Próximos pasos

La prioridad es conectar el modelo de lenguaje y conseguir que el agente utilice las herramientas durante una historia real.

Después se completará la integración con Streamlit, la lógica de decisiones, la memoria y la descarga del PDF.

Finalmente se realizarán las pruebas, documentación y preparación de la exposición.

---

**Estado general:** prototipo técnico en desarrollo, con RAG, persistencia de partidas, herramientas y generación de PDF probados individualmente. Todavía no existe una demo integral validada.