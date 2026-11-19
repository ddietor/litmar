# DECISIONS — decisiones de diseño y de proceso

Por qué litmar es como es, para no volver a discutir lo ya decidido. Cada entrada:
fecha, decisión, motivo y alternativas descartadas. No se borran: si una decisión
cambia, se marca **Sustituida por D-N** y se añade la nueva al final.

---

### D-1 · uv, layout `src/` y `uv_build` — 2026-11-17
uv gestiona entorno, dependencias y lockfile con un solo comando y es mucho más
rápido que venv + pip. El layout `src/` evita importar por accidente el código
sin instalar. El proyecto sigue siendo instalable con `pip install .`.

### D-2 · Idioma: español, salvo atributos de clase en inglés — 2026-11-17
Petición del usuario. Clases, métodos, funciones, variables, docstrings y
mensajes en español; atributos (`title`, `authors`, `max_retries`…) en inglés.
Commits en inglés.

### D-3 · El DOI es la identidad de un artículo — 2026-11-17
`Articulo` exige DOI (normalizado) y al menos un autor; `Biblioteca` deduplica
por DOI y conserva el primero. Las fuentes descartan lo que no cumpla. Así la
deduplicación entre fuentes es trivial y fiable. Descartado: deduplicar por
título (frágil) o permitir artículos sin DOI.

### D-4 · Reintentos en la clase base `Fuente` — 2026-11-17
Todas las fuentes comparten la misma política: reintento ante errores de red,
429 y 5xx, espera exponencial, `Retry-After` y `max_wait` para no esperar horas
cuando se agota un cupo diario. `sleep` y `client` son inyectables para tests.

### D-5 · Tests sin red con respuestas reales guardadas — 2026-11-17
`httpx.MockTransport` + JSON/XML reales en `tests/datos/`. Los tests son
deterministas, rápidos y no gastan cupo de las APIs.

### D-6 · Una fuente por servicio; ante PRs duplicadas se elige una — 2026-11-17
Con varias PRs para el mismo servicio se acepta la más completa y correcta, y se
cierran las demás con un comentario que explica el motivo e invita a aportar sus
mejoras sobre la elegida. Las PRs se integran desde local con un commit «Merge
pull request #N from usuario/rama» y push a `main`; GitHub las marca MERGED.

### D-7 · `.env` bloqueado para el agente — 2026-11-17
Reglas `deny` de `Read` en `.claude/settings.json` para `.env` y `.env.*`, con
excepción de `.env.example` construida con rangos de caracteres (los globs no
admiten negación). Las reglas no cubren Bash: el agente tampoco usa `cat` con él.

### D-8 · Configuración por variables de entorno y `.env` — 2026-11-17
Claves y datos de fuentes en variables (`OPENALEX_API_KEY`, `CROSSREF_MAILTO`,
`ZOTERO_*`), cargadas desde `.env` con python-dotenv **solo en la entrada del
comando `litmar`** (para que los tests no lean el `.env` real). Las variables ya
definidas tienen prioridad. `configuracion.py` es el único sitio que traduce
variables en fuentes. Descartado: `uv run --env-file` (no sirve con pip).

### D-9 · Streamlit como dependencia opcional (`ui`) — 2026-11-17
Streamlit arrastra pandas, pyarrow y más; quien use la librería o la CLI no lo
necesita. Se instala con `uv sync --extra ui` o `pip install 'litmar[ui]'`, y
está también en el grupo dev. `litmar ui` lanza `streamlit run` con el mismo
intérprete, reenvía las opciones extra y desactiva las estadísticas de uso.

### D-10 · Memoria del proyecto en el repositorio — 2026-11-17
`AGENTS.md` (estable), `PROGRESS.md` (vivo) y `DECISIONS.md` (este), versionados
en git y compartidos con los colaboradores. El agente actualiza `PROGRESS.md` por
su cuenta al terminar cada tarea, y los hooks de Claude Code inyectan el estado
al empezar y recuerdan anotar al terminar. Descartado: memoria privada del
agente (no la ven otros agentes ni personas, y se pierde al cambiar de máquina).

### D-11 · `desde` como parámetro de `Fuente.buscar`, filtrado en la API y en local — 2026-11-17
Para `litmar buscar --desde AÑO` (demo de la Clase 1). Cada fuente pasa el año a
su API (comprobado contra las APIs reales) y además descarta con `_admite` lo
anterior, porque cada API fecha distinto (arXiv usa la primera versión; Zotero
no filtra). Descartado: filtrar solo los resultados ya descargados, porque con
`-n 5` podrían quedar menos de 5.

### D-12 · Búsqueda multifuente compartida en `busqueda.py` — 2026-11-17
CLI y UI usan `buscar_en_fuentes`: si una fuente falla se sigue con las demás y
se devuelven los errores (sin cabeceras ni peticiones). En la CLI, si fallan
todas es un error (código 1, no se guarda nada); si falla alguna, solo un aviso.

### D-13 · ruff con línea de 100 y reglas E, W, F, I, UP, B — 2026-11-17
Lo enseña la Clase 1. 100 en lugar de 88 porque el código ya estaba escrito así y
evita partir líneas sin ganar legibilidad. Al adoptarlo se formateó todo el
proyecto de una vez, en el mismo commit que `--fuente`/`--desde`.

### D-14 · Variables del LLM: `LITMAR_MODELO` + clave del proveedor; se mantiene `CROSSREF_MAILTO` — 2026-11-17
Lo fijan las diapositivas de la Clase 2: `LITMAR_MODELO=proveedor:modelo` (p. ej.
`google_genai:gemini-3.8-flash` o `anthropic:claude-sonnet-5-5`) y la clave con
el nombre estándar de cada proveedor (`GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`),
que es el que leen las librerías de LangChain. Sustituye a la idea de
`GEMINI_API_KEY` de la Clase 1. Las diapositivas también nombran
`CROSSREF_MAILTO`, así que no se renombra a `LITMAR_EMAIL`.

<<<<<<< HEAD
### D-15 · `resumir`: devolución de `None`, campos en español y modelo inyectado — 2026-11-18
`resumir(articulo, pregunta, modelo)` recibe el chat model como argumento: la
lógica no elige proveedor, no lee claves y se prueba con un modelo falso. Sin
resumen (`abstract` vacío o solo espacios) devuelve `None` **antes** de enlazar
el esquema o invocar el modelo. Descartado: devolver un `ResumenArticulo` con
campos vacíos (la relevancia tiene que estar entre 1 y 5, y un objeto así
parecería un resumen real) o lanzar una excepción (la ausencia de resumen es
normal en varias fuentes). Los campos del esquema Pydantic se llaman `objetivo`,
`metodo`, `hallazgos`, `relevancia` y `limitaciones`: son los que piden el
encargo y la diapositiva 11, y forman parte del prompt que lee el modelo. Es una
excepción puntual a D-2 (atributos en inglés) limitada a este esquema.

### D-16 · `crear_modelo`: limitador de LangChain y claves por proveedor — 2026-11-18
`crear_modelo()` usa `init_chat_model` con un `InMemoryRateLimiter` de
`LLAMADAS_POR_MINUTO = 10` y cubo de tamaño 1: como mucho una petición cada 6
segundos, por debajo del cupo por minuto del plan gratuito de Gemini. El
limitador se pasa al modelo, así que LangChain lo aplica también a
`with_structured_output` y a los reintentos. Descartado: envolver el modelo en
una clase propia con `sleep` (más código y no cubre todas las vías de llamada) y
poner el límite solo en `resumir` (el flujo y el agente también llaman al
modelo).

Dependencias nuevas: `langchain` (la fábrica `init_chat_model`),
`langchain-google-genai` y `langchain-anthropic` (los dos proveedores de la
diapositiva 12). Van en las dependencias normales para que cambiar de proveedor
en el `.env` no exija instalar nada más; se descartaron extras opcionales.

La fábrica lee `os.environ` (o un diccionario `entorno` inyectado), sin
`load_dotenv()` dentro: la CLI ya carga el `.env` en `litmar.main()` (D-8) y así
los tests no leen el `.env` real. La clave se elige según el proveedor con un
mapa fijo y el error indica qué línea añadir al `.env`. No hay nombres de modelo
ni claves escritos en el código. Se comprueba por introspección que
`BaseChatModel` aplica el limitador también a `with_structured_output`.

La clave se pasa a `init_chat_model(..., api_key=clave)`: los tests con fábrica
falsa no detectaron que `ChatGoogleGenerativeAI` lee `GOOGLE_API_KEY` de
`os.environ` y fallaba al construirse con `entorno`. Pasarla de forma explícita
mantiene el parámetro `entorno` útil y evita depender del entorno del proceso.
La comprobación manual construyó `ChatGoogleGenerativeAI` y `ChatAnthropic` con
el diccionario, sin red.

### D-17 · Ejemplo: ids de CLI → nombres canónicos con `nombre_fuente` — 2026-11-18
`ejemplos/resumir.py` pasaba `("openalex", "europepmc")` a
`buscar_en_fuentes`, que espera nombres de `configuracion.FUENTES`
(`"OpenAlex"`, `"Europe PMC"`): `crear_fuente` indexa
`_CONSTRUCTORES[nombre]` y respondía «fuente desconocida». La CLI ya resuelve
esto en `_fuentes()` con `nombre_fuente()`, así que el ejemplo reutiliza esa
misma función: `FUENTES = tuple(map(nombre_fuente, ("openalex", "europepmc")))`.
Descartado escribir los nombres a mano (`("OpenAlex", "Europe PMC")`): es más
corto, pero no reutiliza la conversión del repo del curso y no se adapta si
cambian los nombres. Tampoco hizo falta sincronizar el fork ni cambiar la base:
la rama ya partía de `upstream/main` (`2b5422e`); el fallo era del ejemplo, no
del historial. Añadido un test que comprueba que `FUENTES` son nombres válidos;
los tests anteriores falsificaban `buscar_en_fuentes` y no lo veían.

### D-18 · Flujo LangGraph: estado de datos, dependencias por closure y citas en corchetes — 2026-11-18
Seis nodos exactos (`planificar`, `buscar`, `filtrar`, `resumir_articulos`,
`sintetizar`, `verificar_citas`). Usan LLM `planificar`, `resumir_articulos` y
`sintetizar`; `buscar` y `filtrar` reutilizan `buscar_en_fuentes` y `Biblioteca`, y
`verificar_citas` comprueba los DOI con `normalizar_doi` y un conjunto de
seleccionados. El estado `EstadoRevision` (`TypedDict`) lleva solo datos: el
modelo y la fábrica de fuentes se pasan a `crear_grafo(modelo, crear=...)` y los
nodos los capturan por `functools.partial`. Así el mismo grafo sirve a CLI, UI o
API y se prueba con dobles. Descartado guardar el modelo en el estado: no es
serializable, ensucia los `stream()` y mezcla configuración con datos.

Formato de cita elegido: `[10.xxxx/yyy]`, extraído con una expresión regular y
normalizado antes de comparar. Descartado Markdown `[texto](url)`: obligaría a
distinguir texto de DOI y daría más falsos positivos. Si una cita no está entre
los seleccionados, `verificar_citas` devuelve `reescribir` y `sintetizar` recibe
la lista de DOI inválidos como feedback; tope de 3 escrituras (1 + 2
reescrituras) comprobado en `decidir()`, con `recursion_limit=20` como red de
seguridad. Al agotar los reintentos se guarda el informe y el BibTeX de los DOI
válidos con aviso, en lugar de abortar: el usuario conserva lo verificable.

`--n` por defecto 6 y `filtrar` recorta a 6: con 6 resúmenes el presupuesto es
1 planificación + 6 resúmenes + 1 síntesis + 2 reescrituras = 10 llamadas, el
límite del `InMemoryRateLimiter` (D-16). `langgraph` pasa de dependencia
transitiva de `langchain` a dependencia directa en `pyproject.toml`.

### D-19 · Modo agente: herramientas acotadas, registro de DOI y aprobación — 2026-11-18
Segundo modo de `revisar` con Deep Agents 0.7.39, además del flujo de D-18.
`herramientas.py` expone una sola `buscar_articulos` para todas las fuentes (más
`listar_fuentes`) construida por `crear_herramientas(...)`: reutiliza
`crear_fuente`, acepta id o nombre canónico y lleva el límite de 10 resultados,
el filtro de fuentes y el de año en el código, no en el prompt. Los fallos se
devuelven como texto (HTTP → código de estado; `ValueError` propio → mensaje)
sin URL ni cabeceras, para que el modelo pueda probar otra fuente. El resultado
se deduplica por DOI antes de entregarlo. Descartado crear una herramienta por
fuente: no se adapta a las fuentes nuevas que lleguen por PR.

`agente.py` inyecta modelo, fábrica de fuentes y límites en `crear_agente()`,
igual que D-18, y devuelve `(agente, registro)`. El subagente `buscador` usa las
mismas herramientas en su propio contexto y se invoca con `task`. La lista de
tareas es `TodoListMiddleware` de `langchain.agents.middleware` (en deepagents
0.7 no se exporta desde `deepagents`); es opt-in desde v0.7. El agente no tiene
herramientas de escritura real ni `execute`: la CLI guarda la respuesta final en
`informe.md`. Descartado que el agente escriba el fichero con `write_file`: el
backend por defecto es en memoria y el formato debe ser idéntico al del flujo
para poder compararlos.

Con `--aprobar` se instala `InMemorySaver` e `interrupt_on` para
`buscar_articulos`, que el subagente hereda. La CLI muestra la llamada y ofrece
aprobar / editar (JSON) / rechazar con `Command(resume=...)` y el mismo
`thread_id`; sin terminal, rechaza. Al terminar, la CLI reutiliza
`flujo.extraer_citas` y genera el `.bib` solo con los DOI que el registro dice
que entregaron las herramientas; los inventados se avisan y se excluyen. Así se
mantiene el principio de D-18: comprobar con código lo que es comprobable, sin
pedirle al modelo que vigile sus propias citas.
=======
### D-15 · LangChain y los dos proveedores como dependencias normales — 2026-11-18
`langchain` (por `init_chat_model`), `langchain-core`, `langchain-google-genai`
y `langchain-anthropic` van en `dependencies`, no en un extra opcional como
Streamlit (D-9): resumir y revisar son el centro de la Clase 2 y los alumnos
deben poder usar Gemini o Claude tras `uv sync`, sin pasos extra. Otro proveedor
se añade con `uv add langchain-<proveedor>` y su variable de clave en
`llm._CLAVES` (si no está, `crear_modelo` deja que LangChain lo compruebe).

### D-16 · Límite de llamadas por minuto en el modelo, configurable — 2026-11-18
`crear_modelo()` pasa un `InMemoryRateLimiter` de LangChain a `init_chat_model`:
10 llamadas por minuto por defecto (plan gratuito de Gemini), cambiable con
`LITMAR_LLAMADAS_POR_MINUTO` (0 = sin límite, p. ej. con una clave de pago).
`max_bucket_size=1` espacia las llamadas en vez de permitir ráfagas. La clave se
comprueba antes de crear el modelo para dar un error que diga qué línea añadir
al `.env`. Como D-8, `llm.py` lee el entorno y no carga `.env`: lo hace el
comando `litmar`; los scripts propios llaman a `load_dotenv()`.

### D-17 · Flujo de revisión: «los N mejores» son los más citados — 2026-11-18 (sustituida por D-23)
`filtrar` se queda con los artículos con resumen y los ordena por citas. Es
fácil de explicar y de comprobar, aunque favorece lo antiguo (en la prueba real
entraron revisiones generales sobre olas de calor). Cambiar el criterio es el
ejercicio natural de la Práctica 2. Descartado de momento: por año, o el orden de
relevancia de cada API. Lo eligió el usuario.

### D-18 · Citas inventadas tras agotar las reescrituras: se marcan — 2026-11-18
Tras `MAX_REESCRITURAS` (2), `verificar_citas` sustituye cada DOI que no está
entre los resumidos por «[cita no verificada]» y añade un aviso. Así ningún DOI
sin comprobar llega al informe ni al BibTeX. Descartado: guardar el informe tal
cual con un aviso, o fallar sin guardar nada. «Seleccionados» son los artículos
que el modelo vio en la síntesis, no todos los candidatos puntuados. Las
referencias del informe las genera el código a partir de los DOI verificados.
Lo eligió el usuario. Los campos del estado (`EstadoRevision`) van en inglés por
D-2, aunque la diapositiva diga «pregunta, artículos…».

### D-19 · Cada revisión, en su carpeta de `ejemplos/revisiones/`, fuera de git — 2026-11-18
Petición del usuario: las salidas de `litmar revisar` no se mezclan en el
directorio de trabajo. Cada ejecución crea
`ejemplos/revisiones/AAAA-MM-DD_HHMM_<pregunta-sin-acentos>/` con `revision.md`
y `revision.bib` (nombre recortado a 50 caracteres sin partir palabras; si ya
existe, `-2`, `-3`…). La carpeta se crea al final, para que una revisión que
falla no deje carpetas vacías. `ejemplos/revisiones/` va en `.gitignore`: cada
alumno tiene las suyas y no aparecen en sus PRs (una de muestra se puede añadir
con `git add -f`). `--informe` y `--bibtex` siguen permitiendo otra ruta. La
ruta es relativa al directorio desde el que se ejecuta `litmar`. Descartado:
nombrar solo por pregunta (se pisan) o solo por fecha (no dice de qué trata).

### D-20 · Una herramienta de búsqueda para todas las fuentes, errores como texto — 2026-11-18
Diapositiva 28. `buscar_articulos(consulta, fuente, n)` en vez de una
herramienta por fuente: el modelo elige la fuente con un parámetro y una fuente
nueva que llegue por PR queda disponible sin tocar las herramientas
(`listar_fuentes` usa `fuentes_disponibles`; la descripción para el modelo sale
de `herramientas.DESCRIPCIONES`, y si falta dice «sin descripción»). `fuente`
es `str` y se valida en el código (no un `Literal`), para que un nombre
inválido vuelva al modelo como texto con la lista de válidas en lugar de un
error de validación. Cualquier excepción de la fuente se convierte en texto con
`busqueda.mensaje_de_error`, que nunca incluye la petición (la URL puede llevar
`CROSSREF_MAILTO` o claves). Límite de 10 y resumen recortado a 400 caracteres
en el código.

### D-21 · Agente revisor: herramientas mínimas, registro de búsquedas y límites — 2026-11-18
Diapositivas 36-39. `--modo agente` usa `create_deep_agent` con:
- **Agente principal** con `write_todos` (`TodoListMiddleware`), `task`,
  `listar_fuentes` y solo `ls`/`read_file`/`write_file` sobre un `StateBackend`
  (ficheros virtuales). No busca él: lo delega en el subagente `buscador`
  (`buscar_articulos`, `listar_fuentes`, `read_file`), para que su contexto no
  se llene de resultados (diapositiva 37).
- **Citas comprobadas con código**: las herramientas del agente envuelven las de
  `herramientas.py` (mismo nombre, descripción y argumentos, vía
  `herramientas.buscar`) y guardan en un `Registro` cada artículo devuelto. Al
  final, los DOI citados que no estén en el registro se marcan (como D-18). No
  hay bucle de reescritura: el agente no se vuelve a llamar.
- **Mismo formato que el flujo**: `estado_final` devuelve un estado con las
  claves del flujo y se reutilizan `informe_markdown` y `citados`.
- **Límites**: `ModelCallLimitMiddleware` (25 pasos el principal con
  `thread_limit`, 8 el buscador por encargo) y 12 búsquedas en total dentro de
  la herramienta. Al llegar al límite, el informe añade «Hasta dónde llegó» con
  la lista de tareas (diapositiva 42).
- **`--aprobar`**: `interrupt_on` para `buscar_articulos` (heredado por el
  buscador), decisiones aprobar/editar/rechazar desde la terminal; sin terminal
  (EOF) se rechaza. Requiere `MemorySaver`.
- Se acepta el subagente `general-purpose` que añade Deep Agents (no puede
  buscar) antes que un perfil global por modelo. `--fuente` limita las fuentes
  en el código; `-n` es el máximo de artículos que elige el agente.

### D-22 · La revisión en la UI reutiliza `flujo.revisar` y `agente.revisar` — 2026-11-18
Diapositiva 40. Los bucles que imprimían en la CLI (`_con_flujo`, `_con_agente`)
pasan a `flujo.revisar()` y `agente.revisar()`, que reciben una función
`mostrar(linea)`: la CLI pasa `print` y la UI, `st.status(...).text`, que
escribe cada paso en cuanto llega. La salida de la terminal no cambia. La UI no
ofrece `--aprobar` (una pausa a mitad de un script de Streamlit exigiría otro
diseño: guardar el grafo en la sesión y reanudar en otra ejecución); queda para
la terminal. Si falta la configuración del modelo, aviso con la línea del `.env`
y botón desactivado. `MAX_ARTICULOS_REVISION` repite `MAX_SELECCIONADOS` para
no cargar LangGraph al abrir la UI; un test comprueba que coinciden.

### D-23 · Selección combinada con relevancia y citas anualizadas — 2026-11-18
La relevancia para la pregunta (1–5) pesa 70 % y la puntuación de citas ajustada
30 %. Para esta implementación se adopta esa proporción para mantener la
relevancia como señal principal. Para el ajuste,
`tasa = citas / max(1, año_actual - año_publicación + 1)`
y `puntuación_citas = 1 + 4 × tasa / (1 + tasa)`, en escala 1–5. Un `citations`
igual a `None` significa que la fuente no proporciona el dato: en ese caso se
usa solo la relevancia y se avisa. `0` sigue significando cero citas conocidas.
El flujo calcula la puntuación con código; en modo agente, la herramienta expone
la tasa y el ajuste, y el prompt pide aplicar la misma regla. Se sustituye
D-17, que ordenaba por citas totales.
>>>>>>> upstream/main
