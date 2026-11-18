# PROGRESS — estado y registro de litmar

Memoria viva del proyecto. Cómo se usa y cuándo se actualiza: `AGENTS.md`, §1.
«Estado actual» y «Próximos pasos» se reescriben para que siempre sean ciertos;
el registro solo crece (entradas nuevas arriba).

## Estado actual

_Actualizado: 2026-11-18._

- **`main`**: en `ba51237`, con todo el trabajo del día (resumen estructurado
  `caf9d01`, flujo y modelo `d2fac24`, agente `ba51237`). Hecho merge
  fast-forward desde `feature/2nd-class-development` y push a `origin/main`
  (fork `ddietor/litmar`, que estaba en `0083af3`): `main` y `origin/main`
  sincronizados; `origin/main` también incorpora los 26 commits de `upstream`.
  `gh` no está instalado en esta máquina: no se han podido listar PRs.
- **Curso**: Clase 1 (*Busca*, 17/11/2026) completa. Clase 2 (*Lee*): hechos los
  pasos 1-6 y 8 del plan (`.env` del LLM, resumen estructurado, modelo
  intercambiable, ejemplo, flujo LangGraph con CLI, herramientas y agente con
  Deep Agents). Siguen pendientes el 7 (votación en clase), el 9 (UI) y el 10
  (preparación de la Clase 3).
- **Calidad**: 265 tests pasan, sin red, en 3-42 s según la caché de importación
  (la primera carga de LangChain, LangGraph, Deep Agents y Pydantic tarda más);
  `ruff check` y `ruff format --check` en verde.
- **PRs abiertas**: sin comprobar (no hay `gh`).
- **Funciona**:
  - modelo `Articulo` y `Biblioteca` (dedup por DOI, BibTeX, CSV, JSON);
  - seis fuentes: OpenAlex, Crossref, Europe PMC, arXiv, PANGAEA, Zotero; todas
    admiten `desde` (año mínimo);
  - CLI: `litmar buscar "…" --fuente openalex,europepmc --desde 2020 --bibtex
    refs.bib --guardar biblioteca.json`, con salida en tabla; `litmar exportar`;
    `litmar ui`; `litmar revisar "pregunta"` (flujo con seis pasos, informe y
    BibTeX de lo citado) y `litmar revisar "pregunta" --modo agente --aprobar`
    (agente Deep Agents: tareas, subagente buscador y pausa antes de buscar);
  - interfaz web con Streamlit: búsqueda en varias fuentes, tabla y descargas
    BibTeX/CSV;
  - configuración por `.env` (plantilla en `.env.example`; todo opcional salvo
    Zotero para buscar y `LITMAR_MODELO` + clave para el LLM);
  - `resumir(articulo, pregunta, modelo)` → `ResumenArticulo` (Pydantic) con
    `with_structured_output`; sin resumen devuelve `None` sin llamar al modelo;
  - `crear_modelo()` crea el chat model de `LITMAR_MODELO` con
    `init_chat_model`, clave según el proveedor y límite de 10 llamadas/min;
  - `ejemplos/resumir.py` busca 3 artículos sobre posidonia en OpenAlex y Europe
    PMC y resume cada uno; sirve de referencia para la práctica 1;
  - `crear_grafo(modelo, crear=...)` compila el flujo de seis nodos;
    `verificar_citas` detecta DOI inventados con código y reescribe como máximo
    dos veces; la CLI imprime cada paso y guarda informe y BibTeX de lo citado;
  - `herramientas.py` (`buscar_articulos` para todas las fuentes, tope 10,
    errores como texto, dedup por DOI y `RegistroBusquedas`) y `agente.py`
    (`crear_agente` con lista de tareas, subagente `buscador` e
    `interrupt_on` opcional). Ambos modos escriben el mismo `informe.md` y
    `citas.bib`; el BibTeX solo incluye DOI entregados por las herramientas.

## Próximos pasos

Por orden de prioridad sugerido; los pasos 1-6 y 8 del plan de la Clase 2 ya están hechos.

0. [ ] **Comprobar el arnés de memoria**. `SessionStart` **funciona**: el
   18/11/2026, al reanudar la sesión, inyectó el estado de este fichero y de git.
   Falta ver en una sesión real que `Stop` pide anotar el progreso cuando hay
   trabajo sin registrar (los casos se probaron a mano con un repo de prueba).
1. [ ] **Clase 2**: seguir el «Plan de la Clase 2» (abajo). El usuario pidió los
   pasos 2, 3, 4, 5, 6 y 8 directamente (ya están hechos, igual que el 1); para
   los demás, preguntar si se construyen ya o se dejan para clase. Siguen
   pendientes el 7 (votación), el 9 (UI) y el 10 (Clase 3).
2. [ ] **Permisos del JSON**: `Biblioteca.guardar` deja `0600`; aplicar la umask
   con `os.chmod` antes de `os.replace`. Propuesto en la PR #10.
3. [ ] **Mover el helper `cliente` de `tests/test_fuentes.py` a `conftest.py`**,
   para que `test_pangaea.py` no importe de otro fichero de tests.
4. [ ] **`pyproject.toml`**: cambiar `description = "Add your description here"`.
5. [ ] **«Desde el año» en la UI**: `buscar_en_fuentes` ya admite `desde`; falta
   el campo en `ui.py`.
6. [ ] **Ideas para la UI** (sin pedir aún): guardar/cargar la biblioteca JSON,
   filtrar u ordenar resultados, mostrar de qué fuente viene cada artículo.

## Plan de la Clase 2 (de `docs/Clase2.pdf`)

Los encargos que se lanzan «en directo», en orden. Cada uno trae en la
diapositiva una columna «En qué fijarse»: el resultado debe superarla. Consultar
la documentación actual de LangChain, LangGraph y deepagents antes de programar
(cambian rápido) y proponer plan antes de código.

1. [x] **`.env`** (diapositiva 4): `LITMAR_MODELO=google_genai:gemini-3.8-flash`
   + `GOOGLE_API_KEY`, o `anthropic:claude-sonnet-5-5` + `ANTHROPIC_API_KEY`. El
   plan gratuito de Gemini tiene límites por minuto (429) y Google puede usar lo
   enviado: solo datos públicos.
2. [x] **Resumen estructurado**: `resumir(articulo, pregunta, modelo)` → objeto
   Pydantic `ResumenArticulo` (objetivo, método, hallazgos, relevancia 1-5
   respecto a la pregunta, limitaciones) con `with_structured_output`. Cada
   campo con descripción (el modelo la lee). Sin resumen → no llamar al modelo.
   Test con modelo falso, sin clave ni red.
3. [x] **Modelo intercambiable**: `src/litmar/llm.py` con `crear_modelo()` que lee
   `LITMAR_MODELO` y usa `init_chat_model`; límite de llamadas por minuto para el
   plan gratuito; si falta la clave, error claro que diga qué poner en el `.env`.
   Ningún nombre de modelo ni clave en el código; cambiar de modelo = cambiar el
   `.env`.
4. [x] **Práctica 1** de los alumnos: `ejemplos/resumir.py` (busca 3 artículos y
   los resume). Sirve de referencia.
5. [x] **Flujo LangGraph** (`src/litmar/flujo.py`): estado `TypedDict`
   (`EstadoRevision`: pregunta, artículos, resúmenes, informe…); nodos
   `planificar` (LLM: pregunta → 2-3 búsquedas), `buscar` y `filtrar` (código:
   fuentes y Biblioteca; con resumen, sin duplicados, los N mejores),
   `resumir_articulos` (con `resumir()`), `sintetizar` (LLM, cita por DOI) y
   `verificar_citas` (código: cada DOI citado está entre los seleccionados; si
   no, vuelve a `sintetizar`, máximo 2 veces). Comando `litmar revisar
   "pregunta" --modo flujo` que muestra cada paso (ver demo, diapositiva 21) y
   guarda el informe y el BibTeX de lo citado. Primero plan y diagrama Mermaid.
   Hecho: D-18; `langgraph` es dependencia directa; 18 tests nuevos (14 de flujo
   y 4 de CLI). Sin probar con modelo real ni red: solo dobles.
6. [x] **Herramientas** (`src/litmar/herramientas.py`): `buscar_articulos(consulta,
   fuente, n)` (reutiliza `crear_fuente`) y `listar_fuentes` (usa
   `fuentes_disponibles`), con `@tool` de LangChain. Máximo 10 en el código;
   errores como mensaje; devuelven título, año, DOI, citas y resumen recortado;
   docstrings pensados para el modelo; avisar de que PANGAEA da datos, no
   artículos. Tests sin red. Hecho: D-19; 7 tests nuevos.
7. [ ] **Votación en clase** (una de tres): Zotero por MCP
   (`github.com/Sapere-IA/zotero-mcp`, solo herramientas de lectura, arranque en
   el `.env`; el MCP solo para PDFs y notas, sin duplicar la búsqueda), Semantic
   Scholar como herramienta de citas, o una fuente de CSV/BD local del grupo.
8. [x] **Agente con Deep Agents**: `litmar revisar … --modo agente` con
   `create_deep_agent` y `herramientas.py`; instrucciones: planificar con lista
   de tareas, buscar en varias fuentes, citar solo DOIs que den las herramientas
   y decir lo que no encontró. Mismo formato de informe y BibTeX que el flujo.
   Subagente buscador. `--aprobar` con `interrupt_on` para pedir permiso antes de
   buscar. Hecho: D-19; 15 tests nuevos (7 de herramientas, 4 de agente y 4 de
   CLI). Queda una mejora: `recursion_limit=40` está en la config y se comprueba
   en un test, pero falta un test que alcance el límite y escriba en `informe.md`
   hasta dónde se llegó (diapositiva 42).
9. [ ] **Pestaña «Revisión» en la UI**: pregunta, modo flujo/agente, fuentes y
   número de artículos; pasos en vivo; informe con los DOI como enlaces; mensaje
   claro si falta la clave. Reutilizar las funciones de revisión (refactor
   mínimo si imprimen por pantalla) sin romper la terminal.
10. [ ] **Para la Clase 3**: los alumnos deben comprobar `docker run hello-world`.

## Cabos sueltos

- **Memoria privada del agente duplicada**: en la máquina del usuario queda
  `~/.claude/projects/-Users-presindev-dev-scratch-litmar/memory/atributos-en-ingles.md`
  (y su línea en `MEMORY.md` de esa carpeta) con la convención de atributos en
  inglés, que ya está en `AGENTS.md` §7. El sistema de permisos impidió borrarla;
  puede borrarla el usuario. No molesta, pero no hay que mantenerla.
- **El PDF de `docs/` incluye el correo y el LinkedIn del usuario** (portada y
  cierre); el repositorio es público. El usuario lo subió a sabiendas.

## Pendiente de terceros

Mejoras pedidas a colaboradores en comentarios de PR. Si llega una PR, revisarla
contra esto.

- **arXiv** (@ddietor, comentario en #11): aplicar la pausa de 3 s también a los
  reintentos (`backoff=3.0`) y pasar los nombres a español.
- **Zotero** (@acanari, #12 cerrada por duplicada): se le invitó a aportar sus
  mejoras sobre la fuente existente: DOI desde el campo «Extra» y usar
  `/items/top`.
- **Throttle genérico** (@rsune8, #9 cerrada por duplicada): se le invitó a
  proponer su hook `_antes_de_peticion` en `Fuente`.

## Registro de sesiones

### 2026-11-18 — Sesión 8: herramientas y agente con Deep Agents (Clase 2, pasos 6 y 8)

- El usuario pidió literalmente el encargo de la diapositiva 36: agente revisor
  con Deep Agents que use `herramientas.py`, como segundo modo de `litmar revisar
  (--modo agente)`, con planificación, búsqueda en varias fuentes, citas solo de
  DOI entregados por herramientas, sección de lo no encontrado, subagente
  buscador, `--aprobar` y mismo formato que el flujo. Pidió además consultar la
  documentación actual. Se presentó **plan y diagrama Mermaid** antes del
  código; respondió «adelante» sin cambios.
- Consultada la doc actual de Deep Agents (overview, HITL y referencia de
  `create_deep_agent`) y leídas las diapositivas 28 y 34-39. Versión instalada:
  `deepagents==0.7.39` (`uv add deepagents`). Hallazgos que condicionaron el
  código: `TodoListMiddleware` se importa de `langchain.agents.middleware` (no de
  `deepagents`) y es opt-in desde v0.7; `SubAgent` se invoca con `task` y hereda
  `interrupt_on`; HITL necesita checkpointer y reanudarse con el mismo
  `thread_id`. Verificado con un modelo falso que el subagente en efecto pide
  aprobación.
- `src/litmar/herramientas.py` nuevo: `crear_herramientas(...)` construye
  `buscar_articulos` y `listar_fuentes` con `@tool`; reutiliza `crear_fuente`,
  acepta id o nombre canónico, aplica `--fuente`, `--desde` y el tope de 10 en
  código, deduplica por DOI antes de mostrar los resultados y devuelve errores
  como texto sin URL ni cabeceras. `RegistroBusquedas` guarda los DOI entregados,
  las llamadas y los avisos. Aviso de PANGAEA en los docstrings (D-19).
- `src/litmar/agente.py` nuevo: `crear_agente(modelo, crear=..., fuentes=..., n=...,
  desde=..., aprobar=..., registro=...)` → `(agente, registro)`. System prompt
  con las seis instrucciones, `TodoListMiddleware`, `SubAgent("buscador")`,
  `InMemorySaver` e `interrupt_on={"buscar_articulos": True}` solo con
  `--aprobar`. El agente no escribe ficheros ni ejecuta código: la CLI guarda su
  respuesta final.
- CLI: `--modo agente` ya funciona y `--aprobar` solo se admite con ese modo.
  La CLI muestra tareas, `task(buscador)` y llamadas a herramientas en vivo;
  si aparece `__interrupt__`, imprime la llamada y ofrece aprobar/editar
  (argumentos JSON)/rechazar con `Command(resume=...)` y el mismo `thread_id`;
  sin terminal rechaza. Al terminar reutiliza `extraer_citas` y exporta el BibTeX
  solo de los DOI del registro; los inventados se avisan por `stderr`. Refactor
  mínimo: `_guardar_revision()` comparten ambos modos.
- Tests: `tests/test_herramientas.py` (7), `tests/test_agente.py` (4) y 4 nuevos
  en `test_cli.py` (el antiguo test de rechazo del modo agente desaparece).
  Modelo falso con `BaseChatModel` + `_generate`/`bind_tools`: `FakeListChatModel`
  de esta versión no acepta `AIMessage` con `tool_calls`. 265 tests en verde;
  `ruff check` y `ruff format --check` en verde.
- Documentación: README con diagrama del agente, herramientas, aprobación y
  verificación; `DECISIONS.md` D-19; `AGENTS.md` (estructura, comandos y cuatro
  trampas nuevas).
- El usuario pidió después pasar todo el trabajo del día a `main` de su fork.
  Se commiteó lo pendiente en la rama de trabajo como `ba51237` («Add agent
  review mode with scoped tools and human approval»), se fusionó en `main` con
  `merge --ff-only` y, con su visto bueno explícito, se hizo push a
  `origin/main` (`0083af3..ba51237`). `main` local y remoto quedan iguales;
  comprobado de nuevo tras la fusión: 265 tests y ruff en verde.
- Queda pendiente probar ambos modos con clave real y red (una llamada manual a
  OpenAlex desde un experimento devolvió artículos, pero no se ha ejecutado
  `revisar` con un LLM real). Tampoco hay todavía test del límite de pasos
  alcanzado; ni la pestaña «Revisión» de la UI (paso 9).

### 2026-11-18 — Sesión 7: flujo LangGraph y comando `litmar revisar` (Clase 2, paso 5)

- El usuario pidió el encargo de las diapositivas 17-21: flujo con los nodos
  `planificar`, `buscar`, `filtrar`, `resumir_articulos`, `sintetizar` y
  `verificar_citas`, y comando `litmar revisar "pregunta"` que muestre cada paso
  y guarde informe y BibTeX de lo citado. Pidió **primero plan y diagrama**; se
  presentó el diagrama Mermaid, el estado, los límites y las decisiones
  pendientes (formato de cita, qué hacer con citas no corregidas y `--n`). Respondió
  «adelante» sin cambios al plan.
- Consultados antes de programar: `PROGRESS.md`, `DECISIONS.md`, diapositivas
  17-21 y la referencia actual de LangGraph (`StateGraph`,
  `add_conditional_edges`, `stream`, `recursion_limit`). `langgraph` 1.2.22 ya
  estaba instalado como transitiva de `langchain`: `uv add langgraph` lo declara
  directo en `pyproject.toml` y `uv.lock`.
- `src/litmar/flujo.py` nuevo: `EstadoRevision` (`TypedDict`), `PlanBusqueda` e
  `InformeRedaccion` (Pydantic), `estado_inicial()`, `extraer_citas()`, los seis
  nodos como funciones de módulo, `decidir()`, `biblioteca_de_citas()` y
  `crear_grafo(modelo, crear=...)`. El modelo y la fábrica de fuentes se inyectan
  por `functools.partial` al construir el grafo, no viajan en el estado (D-18).
  `buscar` y `filtrar` no llaman al modelo; usan `buscar_en_fuentes` y
  `Biblioteca`. `verificar_citas` normaliza los DOI entre corchetes y compara con
  los seleccionados; `decidir` permite 3 escrituras como máximo. Cota
  `recursion_limit=20`.
- CLI: subcomando `revisar` con `--modo` (flujo por defecto; `agente` da error
  claro), `--fuente`, `-n` (6), `--desde`, `--informe` (informe.md) y `--bibtex`
  (citas.bib). `_revisar` usa `grafo.stream(..., stream_mode="updates")` e
  imprime `> nodo  detalle` en cuanto cada nodo termina. Guarda el informe y el
  BibTeX de los DOI verificados; si tras dos reescrituras quedan citas inválidas,
  avisa en `stderr` pero conserva lo verificable. `crear_grafo` se exporta desde
  `litmar`.
- Tests: `tests/test_flujo.py` (14) con modelo y fuentes falsos comprueba el
  diagrama de aristas, el recorte de consultas, que `buscar`/`filtrar` no gastan
  LLM, la deduplicación, el tope de seleccionados, la detección de DOI
  inventado, el feedback de reescritura, las 3 escrituras máximas y los seis pasos
  del `stream`. `tests/test_cli.py` (4 nuevos) comprueba pasos, archivos,
  rechazo de `--modo agente`, rutas distintas y error sin modelo. 250 tests en
  verde; `ruff check` y `ruff format --check` en verde.
- Documentación: README con diagrama Mermaid, tabla de nodos, ejemplo y salida
  prevista; `DECISIONS.md` D-18. Sin commit ni push; rama
  `feature/2nd-class-development`.
- Queda pendiente probar `revisar` con clave real y red: aquí solo se han usado
  dobles. El modo agente (paso 8) y las herramientas (paso 6) siguen sin
  construirse.

### 2026-11-18 — Sesión 6: corrección del ejemplo (ids → nombres canónicos)

- El usuario ejecutó `uv run python ejemplos/resumir.py` y salió
  `Aviso: openalex: fuente desconocida: 'openalex'` (y lo mismo para
  `europepmc`), sin artículos. Se explicó la diferencia entre el fork
  (`origin` = `ddietor/litmar`) y el repo del curso (`upstream` =
  `sapere-ia/litmar`), y que el error no era por historial desactualizado: la
  rama ya partía de `upstream/main` (`2b5422e`).
- Causa: `buscar_en_fuentes` → `crear_fuente` indexa `_CONSTRUCTORES[nombre]`
  con nombres canónicos (`"OpenAlex"`, `"Europe PMC"`); el ejemplo pasaba los
  ids de CLI (`"openalex"`, `"europepmc"`). La CLI ya los convierte en
  `_fuentes()` con `nombre_fuente()`.
- Arreglo (D-17): `ejemplos/resumir.py` importa `nombre_fuente` y define
  `FUENTES = tuple(map(nombre_fuente, ("openalex", "europepmc")))`. Igual en la
  línea de tema alternativo que el usuario tenía comentada (ruido marino en
  hidrófonos), conservada tal cual; a esa línea larga se le añadió
  `# noqa: E501` para no tocar su texto. También corregido el encabezado para
  que diga «1 artículo» cuando solo se encuentra uno.
- `tests/test_ejemplo_resumir.py`: nuevo test que exige
  `FUENTES == ("OpenAlex", "Europe PMC")` y que todas estén en
  `configuracion.FUENTES`. Los tests anteriores falsificaban
  `buscar_en_fuentes` y no detectaban el fallo. 232 tests en verde; ruff en
  verde. Comprobación manual: `crear_fuente` construye `OpenAlex` y `EuropePMC`
  con los nombres ya convertidos, sin red.
- README: nota en «Ejemplo completo»; `AGENTS.md`: trampa de ids vs nombres.
  Sigue todo sin commitear en `feature/2nd-class-development`.

### 2026-11-18 — Sesión 5: ejemplo de resumen (Clase 2, paso 4)

- El usuario pidió el encargo de la diapositiva 14: `ejemplos/resumir.py` que
  busque 3 artículos y los resuma. Se leyó la diapositiva: los alumnos deben
  ejecutarlo, contrastar los hallazgos con el DOI original y cambiar de modelo
  para comparar.
- Nuevo `ejemplos/resumir.py`: constantes `CONSULTA` (posidonia), `PREGUNTA`,
  `FUENTES` (OpenAlex y Europe PMC, sin clave) y `NUM_ARTICULOS = 3`; carga el
  `.env` por sí mismo porque no pasa por la CLI; usa `buscar_en_fuentes` y
  `crear_modelo`, avisa de fuentes fallidas y artículos sin `abstract`, e imprime
  los cinco campos del resumen con el DOI de cada artículo.
- `tests/test_ejemplo_resumir.py` carga el script con `importlib` y sustituye
  búsqueda, modelo y resumen: 5 tests sin red comprueban los tres artículos, los
  parámetros de búsqueda, los avisos, el caso sin resultados y el error claro si
  no hay modelo. 231 tests en verde; ruff en verde.
- README: apartado «Ejemplo completo» en «Resumen estructurado». Todo sigue sin
  commitear en `feature/2nd-class-development`. No se ha ejecutado con clave
  real (no hay clave ni red).

### 2026-11-18 — Sesión 4: modelo intercambiable (Clase 2, paso 3)

- El usuario lanzó el encargo de la diapositiva 12. Se extrajo esa diapositiva
  con `pypdf` y se consultaron las referencias actuales de `init_chat_model`,
  `InMemoryRateLimiter` y la integración de Gemini antes de programar.
- `uv add langchain langchain-google-genai langchain-anthropic` (D-16): la
  fábrica y los dos proveedores de las diapositivas, como dependencias normales
  para poder cambiar de proveedor solo con el `.env`.
- Nuevo `src/litmar/llm.py`: `crear_modelo(entorno=None)` valida
  `LITMAR_MODELO=proveedor:modelo`, exige `GOOGLE_API_KEY` o
  `ANTHROPIC_API_KEY` según el proveedor (error que dice qué línea añadir al
  `.env`) y pasa un `InMemoryRateLimiter` de 10 llamadas/min con cubo de 1 a
  `init_chat_model`. No hay nombres de modelo ni claves en el código. Se
  comprobó por introspección que `BaseChatModel` aplica el limitador también a
  `with_structured_output`. Exportado en `litmar.__init__`.
- `.env.example`: variables del LLM; README: sección «Modelo de lenguaje» y
  tabla de configuración; `AGENTS.md`: módulo nuevo y trampa de `load_dotenv`.
- `tests/test_llm.py`: fábrica falsa que captura los argumentos; cubre los dos
  proveedores, el limitador, el recorte de espacios, los errores de modelo
  ausente/mal escrito, clave ausente/vacía y proveedor no integrado. El test
  comprueba que la clave del `entorno` llega a `init_chat_model` como `api_key`.
  Sin clave ni red. 226 tests en verde; ruff en verde.
- La comprobación manual con la fábrica real encontró un fallo que los tests con
  fábrica falsa no veían: `ChatGoogleGenerativeAI` lee `GOOGLE_API_KEY` de
  `os.environ`, no del diccionario; `crear_modelo(entorno)` validaba la clave
  pero no la pasaba y fallaba al construir. Arreglado pasando `api_key=clave` a
  `init_chat_model` (D-16). Repetida la comprobación: se construyen
  `ChatGoogleGenerativeAI` y `ChatAnthropic` desde el diccionario, sin red.
- El trabajo anterior (`resumir`) ya estaba commiteado como `caf9d01`; lo de
  esta sesión sigue sin commitear en `feature/2nd-class-development`. No se ha
  probado con un modelo real ni con clave real (no hay clave). `gh` sigue sin
  estar instalado.

### 2026-11-18 — Sesión 3: resumen estructurado (Clase 2, paso 2)

- El usuario lanzó literalmente el encargo de la diapositiva 11 de
  `docs/Clase2.pdf`; se leyó esa diapositiva antes de programar (en este entorno
  el PDF se extrajo con `pypdf`, porque el modelo no puede ver PDFs).
- `uv add pydantic langchain-core` (pydantic 2.14.3, langchain-core 1.8.2). No se
  han añadido proveedores ni claves: `resumir` recibe el modelo inyectado.
- Nuevo `src/litmar/resumen.py`: `ResumenArticulo` con los cinco campos y
  `Field(description=...)` (la relevancia validada con `ge=1, le=5`), prompt con
  el título, año, DOI, resumen y pregunta, y `resumir()` con
  `model.with_structured_output(ResumenArticulo).invoke(...)`. Sin resumen →
  `None` antes de enlazar el esquema (D-15). Exportado en `litmar.__init__`.
- `tests/test_resumen.py`: modelo falso que registra esquema, mensajes y
  llamadas; cubre el objeto devuelto, el contenido del prompt, tres variantes de
  `abstract` vacío, las descripciones de todos los campos y los extremos de la
  relevancia. Sin clave ni red. 213 tests en verde; ruff en verde.
- README: sección «Resumen estructurado» y nota en «Tests». `AGENTS.md`: módulo
  nuevo y excepción D-2 para los campos del esquema.
- Comprobación manual con modelo falso: las cinco descripciones llegan al
  esquema y el mensaje del usuario contiene pregunta, título, año, DOI y texto
  del resumen. No se ha podido comparar con un modelo real (no hay clave).
- Sin commit y sin push: el trabajo queda en `feature/2nd-class-development`.
  `gh` no está instalado, así que no se han revisado PRs.

### 2026-11-18 — Sesión 2: comprobación de los hooks

- El hook `SessionStart` funciona en una sesión real (al reanudar inyectó el
  estado de `PROGRESS.md` y de git). Paso 0 actualizado.
- Dudas del usuario sobre `Stop`: se ejecuta al final de **cada turno** (no al
  salir, ni con Esc, ni si se apaga el ordenador; para la salida existe
  `SessionEnd`, que no puede pedir nada al agente). Cuesta 0 tokens cuando deja
  terminar; si bloquea, ~100 tokens más la edición de `PROGRESS.md`, una vez por
  turno. Se le ofreció una versión más silenciosa (ignorar commits ya hechos);
  de momento se queda como está.
- Sin cambios de código. La Clase 2 sigue sin empezar.

### 2026-11-17 — Sesión 1 (cierre 2): diapositivas de la Clase 2

- El usuario añadió `docs/Clase2.pdf`. De ella salen: el «Plan de la Clase 2»
  de este fichero, la hoja de ruta y los principios de `AGENTS.md` §2, y D-14
  (variables `LITMAR_MODELO` + clave del proveedor; `CROSSREF_MAILTO` se queda),
  que resuelve la duda pendiente sobre `LITMAR_EMAIL`.
- No se ha escrito código de la Clase 2. Queda por preguntar al usuario si se
  construye ya o en directo en clase.

### 2026-11-17 — Sesión 1 (cierre): memoria lista para la siguiente sesión

- Repaso completo de los ficheros de memoria para que una sesión con contexto
  vacío pueda retomar: calendario del curso (`AGENTS.md` §2), cómo trabaja el
  usuario (§10), procedimiento para revisar PRs de alumnos (§11), acciones que
  bloquea el sistema de permisos (§9), «Cabos sueltos» y el paso 0 (comprobar los
  hooks) en este fichero.
- Estado al cerrar: `main` sincronizado con `origin/main`, árbol limpio, 204
  tests y ruff en verde, ninguna PR abierta.

### 2026-11-17 — Sesión 1 (cont.): CLI de la demo y ruff

- **CLI como en la diapositiva 8 de `docs/Clase1.pdf`**: `--fuente` (varias,
  separadas por comas, sin distinguir mayúsculas), `--desde AÑO`, `--bibtex` en
  `buscar`, `--n` además de `-n`, y salida en tabla `AÑO CITAS AUTORES TÍTULO`
  ajustada a la terminal (ya no imprime los DOI: van en BibTeX/JSON). Era lo que
  se propuso a @eloyleonorozco en la PR #10; lo hizo el mantenedor.
- **`desde` en las seis fuentes** (D-11): filtros comprobados contra las APIs
  reales. Nuevo `tests/test_desde.py`.
- **`busqueda.py`** (D-12): la búsqueda multifuente que tenía `ui.py` pasa a un
  módulo compartido; la CLI y la UI lo usan. `Articulo.short_authors` nuevo.
  Zotero sin configurar da un error que explica qué variable falta.
- **ruff** (D-13): grupo dev, configuración en `pyproject.toml`, todo el
  proyecto formateado y en verde.
- Probado de verdad: la búsqueda de la demo devuelve los mismos artículos que la
  diapositiva; `--fuente openalex,europepmc --desde 2020 --bibtex` exporta 20.
- Ruido en el diff: el formateo de ruff toca casi todos los ficheros de
  colaboradores. Si alguien tiene una PR abierta contra el `main` anterior, puede
  tener conflictos de formato: que haga `uv run ruff format` tras actualizar.

### 2026-11-17 — Sesión 1: del proyecto vacío a seis fuentes, CLI e interfaz web

Todo el proyecto se construyó en esta sesión (Roberto Bada con Claude Code).

- **Arranque**: proyecto uv con layout `src/` (`30725fa`) y push a
  `Sapere-IA/litmar`.
- **Modelo** (`0083af3`): `Articulo`, `Biblioteca` con BibTeX, clase abstracta
  `Fuente` con reintentos y fuente OpenAlex con test offline. El usuario pidió
  **atributos de clase en inglés** y el resto en español.
- **PRs de colaboradores**, revisadas y comentadas una a una:
  - aceptadas: #3 Crossref (@mattosnh), #6 PANGAEA (@pablo-icm), #4 Europe PMC
    (@aleixop), #7 Zotero (@PurpleFunkyBird), #11 arXiv (@ddietor), #10 CLI y
    persistencia JSON (@eloyleonorozco);
  - cerradas: #8, #9 (arXiv) y #12 (Zotero) por duplicadas, explicando el motivo
    e invitando a aportar sus mejoras (ver «Pendiente de terceros»); #8 además
    tenía un test que fallaba. #2 y #5 las cerró otra persona.
  - #10 tenía conflicto en el README: se fusionaron los dos y se añadió una
    sección por fuente.
- **Seguridad** (`d342dcd`, `621bae5`): `.claude/settings.json` bloquea leer
  `.env` y `.env.*` salvo `.env.example`. Hicieron falta varios intentos por las
  limitaciones de los globs (ver `AGENTS.md` §9).
- **Interfaz web** (`00411b7`, `fae30af`): `src/litmar/ui.py` con Streamlit
  (fuentes, número de resultados, tabla con enlace al DOI, descargas BibTeX y
  CSV), `litmar ui`, `configuracion.py`, `Biblioteca.a_csv()`, `.env.example`,
  carga de `.env` con python-dotenv. Estadísticas de uso de Streamlit
  desactivadas. Probada con búsqueda real en cinco fuentes (25 artículos).
- **Harness de memoria**: `AGENTS.md`, `CLAUDE.md`, `PROGRESS.md`,
  `DECISIONS.md` y hooks `SessionStart`/`Stop`. El usuario eligió: ficheros en el
  repo, el agente anota el progreso solo, y hooks además de instrucciones.
- **Diapositivas**: el usuario añadió `docs/Clase1.pdf` (Clase 1 del curso). De
  ellas salen el contexto del curso y la hoja de ruta de `AGENTS.md` §2, y los
  próximos pasos 1-3 (CLI de la demo, ruff, preparación de la Clase 2).
