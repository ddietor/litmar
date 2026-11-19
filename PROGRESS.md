# PROGRESS — estado y registro de litmar

Memoria viva del proyecto. Cómo se usa y cuándo se actualiza: `AGENTS.md`, §1.
«Estado actual» y «Próximos pasos» se reescriben para que siempre sean ciertos;
el registro solo crece (entradas nuevas arriba).

## Estado actual

_Actualizado: 2026-11-18._

<<<<<<< HEAD
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
=======
- **`main`**: al día con `Sapere-IA/litmar/main` y `origin/main` en
  `db90288`. Último trabajo: selección combinada por relevancia y citas
  anualizadas, con recuentos no disponibles identificados.
- **Curso**: Clase 1 (*Busca*, 17/11/2026) completa respecto a las
  diapositivas. La siguiente es la Clase 2 (*Lee*), el **18/11/2026**; sus
  diapositivas están en `docs/Clase2.pdf` y su plan, abajo. Se está
  construyendo como ensayo, encargo a encargo: hechos los pasos 1 a 6, el 8 y el 9 (`.env.example`, `resumir`, `llm.py`,
  Práctica 1, flujo LangGraph, herramientas, agente, pestaña «Revisión»); la
  votación (7) se hace en clase, probados con un modelo real (Anthropic).
- **Calidad**: 312 tests pasan sin red; `ruff check`, `ruff format --check` y
  `uv lock --check` en verde.
  La Clase 3 (*APIs, reproducibilidad y transferencia*, **19/11/2026**) tiene
  sus diapositivas en `docs/Clase3.pdf` y su plan abajo; no hay nada empezado.
- **Calidad**: 299 tests pasan, sin red, en ~1,5 s; `ruff check` y
  `ruff format --check` en verde.
- **PRs abiertas**: ninguna.
>>>>>>> upstream/main
- **Funciona**:
  - modelo `Articulo` y `Biblioteca` (dedup por DOI, BibTeX, CSV, JSON);
  - seis fuentes: OpenAlex, Crossref, Europe PMC, arXiv, PANGAEA, Zotero; todas
    admiten `desde` (año mínimo);
  - CLI: `litmar buscar "…" --fuente openalex,europepmc --desde 2020 --bibtex
    refs.bib --guardar biblioteca.json`, con salida en tabla; `litmar exportar`;
<<<<<<< HEAD
    `litmar ui`; `litmar revisar "pregunta"` (flujo con seis pasos, informe y
    BibTeX de lo citado) y `litmar revisar "pregunta" --modo agente --aprobar`
    (agente Deep Agents: tareas, subagente buscador y pausa antes de buscar);
  - interfaz web con Streamlit: búsqueda en varias fuentes, tabla y descargas
    BibTeX/CSV;
=======
    `litmar ui`;
  - interfaz web con Streamlit: pestaña «Búsqueda» (varias fuentes, tabla,
    descargas BibTeX/CSV) y pestaña «Revisión» (flujo o agente, pasos en vivo,
    informe con DOI enlazados, descargas);
  - `resumir(articulo, pregunta, modelo)` → `ResumenArticulo` (Pydantic,
    `with_structured_output`), en `src/litmar/resumen.py`;
  - `crear_modelo()` en `src/litmar/llm.py`: modelo de `LITMAR_MODELO` con
    `init_chat_model`, límite de llamadas por minuto y errores claros;
  - `litmar revisar "pregunta"`: flujo LangGraph de seis pasos
    (`src/litmar/flujo.py`) con verificación de citas por código; guarda
    `revision.md` y `revision.bib` (solo lo citado) en
    `ejemplos/revisiones/<fecha_hora_pregunta>/` (ignorado en git);
  - herramientas de LangChain `buscar_articulos` y `listar_fuentes`
    (`src/litmar/herramientas.py`), listas para el agente;
  - `litmar revisar … --modo agente [--aprobar]`: agente de Deep Agents con
    subagente buscador, lista de tareas, límites y citas comprobadas
    (`src/litmar/agente.py`); mismo informe y BibTeX que el flujo;
  - selección por 70 % de relevancia y 30 % de citas/año ajustadas; si falta el
    recuento, se usa solo la relevancia y se avisa. `citations=None` distingue
    el dato ausente de un recuento real de cero;
>>>>>>> upstream/main
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
<<<<<<< HEAD
1. [ ] **Clase 2**: seguir el «Plan de la Clase 2» (abajo). El usuario pidió los
   pasos 2, 3, 4, 5, 6 y 8 directamente (ya están hechos, igual que el 1); para
   los demás, preguntar si se construyen ya o se dejan para clase. Siguen
   pendientes el 7 (votación), el 9 (UI) y el 10 (Clase 3).
2. [ ] **Permisos del JSON**: `Biblioteca.guardar` deja `0600`; aplicar la umask
=======
1. [ ] **Clase 3** (19/11/2026): seguir el «Plan de la Clase 3» (abajo),
   encargo a encargo y con el contrato propuesto antes del código. Para probar
   los encargos 4-6 hace falta Docker (no instalado en la máquina del ensayo).
2. [ ] **Clase 2**: seguir el «Plan de la Clase 2» (abajo). El usuario lanza
   los prompts de las diapositivas uno a uno (ensayo). La Clase 2
   está construida; queda la votación (paso 7, en clase). Pendiente: probar con Gemini (solo se ha probado con
   Anthropic). Ojo: con el límite por defecto la primera llamada espera ~6 s (el
   limitador empieza vacío).
3. [ ] **Permisos del JSON**: `Biblioteca.guardar` deja `0600`; aplicar la umask
>>>>>>> upstream/main
   con `os.chmod` antes de `os.replace`. Propuesto en la PR #10.
4. [ ] **Mover el helper `cliente` de `tests/test_fuentes.py` a `conftest.py`**,
   para que `test_pangaea.py` no importe de otro fichero de tests.
5. [ ] **`pyproject.toml`**: cambiar `description = "Add your description here"`.
6. [ ] **«Desde el año» en la UI**: `buscar_en_fuentes` ya admite `desde`; falta
   el campo en `ui.py`.
7. [ ] **Ideas para la UI** (sin pedir aún): guardar/cargar la biblioteca JSON,
   filtrar u ordenar resultados, mostrar de qué fuente viene cada artículo.

## Plan de la Clase 2 (de `docs/Clase2.pdf`)

Los encargos que se lanzan «en directo», en orden. Cada uno trae en la
diapositiva una columna «En qué fijarse»: el resultado debe superarla. Consultar
la documentación actual de LangChain, LangGraph y deepagents antes de programar
(cambian rápido) y proponer plan antes de código.

<<<<<<< HEAD
1. [x] **`.env`** (diapositiva 4): `LITMAR_MODELO=google_genai:gemini-3.8-flash`
   + `GOOGLE_API_KEY`, o `anthropic:claude-sonnet-5-5` + `ANTHROPIC_API_KEY`. El
   plan gratuito de Gemini tiene límites por minuto (429) y Google puede usar lo
   enviado: solo datos públicos.
2. [x] **Resumen estructurado**: `resumir(articulo, pregunta, modelo)` → objeto
=======
1. [x] **`.env`** (diapositiva 4; en `.env.example` el 18/11): `LITMAR_MODELO=google_genai:gemini-3.8-flash`
   + `GOOGLE_API_KEY`, o `anthropic:claude-sonnet-5-5` + `ANTHROPIC_API_KEY`. El
   plan gratuito de Gemini tiene límites por minuto (429) y Google puede usar lo
   enviado: solo datos públicos.
2. [x] **Resumen estructurado** (18/11, `resumen.py`; probar con modelo real): `resumir(articulo, pregunta, modelo)` → objeto
>>>>>>> upstream/main
   Pydantic `ResumenArticulo` (objetivo, método, hallazgos, relevancia 1-5
   respecto a la pregunta, limitaciones) con `with_structured_output`. Cada
   campo con descripción (el modelo la lee). Sin resumen → no llamar al modelo.
   Test con modelo falso, sin clave ni red.
<<<<<<< HEAD
3. [x] **Modelo intercambiable**: `src/litmar/llm.py` con `crear_modelo()` que lee
=======
3. [x] **Modelo intercambiable** (18/11, `llm.py`): `src/litmar/llm.py` con `crear_modelo()` que lee
>>>>>>> upstream/main
   `LITMAR_MODELO` y usa `init_chat_model`; límite de llamadas por minuto para el
   plan gratuito; si falta la clave, error claro que diga qué poner en el `.env`.
   Ningún nombre de modelo ni clave en el código; cambiar de modelo = cambiar el
   `.env`.
<<<<<<< HEAD
4. [x] **Práctica 1** de los alumnos: `ejemplos/resumir.py` (busca 3 artículos y
   los resume). Sirve de referencia.
5. [x] **Flujo LangGraph** (`src/litmar/flujo.py`): estado `TypedDict`
=======
4. [x] **Práctica 1** (18/11) de los alumnos: `ejemplos/resumir.py` (busca 3 artículos y
   los resume). Puede convenir tenerlo hecho como referencia.
5. [x] **Flujo LangGraph** (18/11; D-17, D-18) (`src/litmar/flujo.py`): estado `TypedDict`
>>>>>>> upstream/main
   (`EstadoRevision`: pregunta, artículos, resúmenes, informe…); nodos
   `planificar` (LLM: pregunta → 2-3 búsquedas), `buscar` y `filtrar` (código:
   fuentes y Biblioteca; sin duplicados, los N con mejor puntuación),
   `resumir_articulos` (con `resumir()` para los candidatos con resumen),
   `sintetizar` (LLM, cita por DOI) y
   `verificar_citas` (código: cada DOI citado está entre los seleccionados; si
   no, vuelve a `sintetizar`, máximo 2 veces). Comando `litmar revisar
   "pregunta" --modo flujo` que muestra cada paso (ver demo, diapositiva 21) y
   guarda el informe y el BibTeX de lo citado. Primero plan y diagrama Mermaid.
<<<<<<< HEAD
   Hecho: D-18; `langgraph` es dependencia directa; 18 tests nuevos (14 de flujo
   y 4 de CLI). Sin probar con modelo real ni red: solo dobles.
6. [x] **Herramientas** (`src/litmar/herramientas.py`): `buscar_articulos(consulta,
=======
6. [x] **Herramientas** (18/11, D-20) (`src/litmar/herramientas.py`): `buscar_articulos(consulta,
>>>>>>> upstream/main
   fuente, n)` (reutiliza `crear_fuente`) y `listar_fuentes` (usa
   `fuentes_disponibles`), con `@tool` de LangChain. Máximo 10 en el código;
   errores como mensaje; devuelven título, año, DOI, citas y resumen recortado;
   docstrings pensados para el modelo; avisar de que PANGAEA da datos, no
   artículos. Tests sin red. Hecho: D-19; 7 tests nuevos.
7. [ ] **Votación en clase** (una de tres): Zotero por MCP
   (`github.com/Sapere-IA/zotero-mcp`, solo herramientas de lectura, arranque en
   el `.env`; el MCP solo para PDFs y notas, sin duplicar la búsqueda), Semantic
   Scholar como herramienta de citas, o una fuente de CSV/BD local del grupo.
<<<<<<< HEAD
8. [x] **Agente con Deep Agents**: `litmar revisar … --modo agente` con
=======
8. [x] **Agente con Deep Agents** (18/11, D-21): `litmar revisar … --modo agente` con
>>>>>>> upstream/main
   `create_deep_agent` y `herramientas.py`; instrucciones: planificar con lista
   de tareas, buscar en varias fuentes, citar solo DOIs que den las herramientas
   y decir lo que no encontró. Mismo formato de informe y BibTeX que el flujo.
   Subagente buscador. `--aprobar` con `interrupt_on` para pedir permiso antes de
<<<<<<< HEAD
   buscar. Hecho: D-19; 15 tests nuevos (7 de herramientas, 4 de agente y 4 de
   CLI). Queda una mejora: `recursion_limit=40` está en la config y se comprueba
   en un test, pero falta un test que alcance el límite y escriba en `informe.md`
   hasta dónde se llegó (diapositiva 42).
9. [ ] **Pestaña «Revisión» en la UI**: pregunta, modo flujo/agente, fuentes y
=======
   buscar. Límite de pasos (si se alcanza, escribir hasta dónde llegó) con test de
   modelo falso.
9. [x] **Pestaña «Revisión» en la UI** (18/11, D-22): pregunta, modo flujo/agente, fuentes y
>>>>>>> upstream/main
   número de artículos; pasos en vivo; informe con los DOI como enlaces; mensaje
   claro si falta la clave. Reutilizar las funciones de revisión (refactor
   mínimo si imprimen por pantalla) sin romper la terminal.
10. [ ] **Para la Clase 3**: los alumnos deben comprobar `docker run hello-world`
    (la Práctica 2 de la Clase 3 lo necesita; sin Docker, en parejas).

## Plan de la Clase 3 (de `docs/Clase3.pdf`)

*APIs, reproducibilidad y transferencia*, 19/11/2026. Mismo método que la
Clase 2: encargos «en directo» copiados de las diapositivas, cada uno con su
columna «En qué fijarse», y **plan antes que código** (las diapositivas lo
piden explícitamente: «Primero propón el contrato», «Antes, dime qué rutas
usará»). Consultar la documentación actual de FastAPI, uvicorn, uv (guía de
Docker) y nginx antes de escribir código.

Guion de la clase: repaso (d. 3) → **01 Tu propia API** (d. 4-14: vocabulario
HTTP, FastAPI, encargos 1 y 2, Práctica 1) → descanso → **02 Docker** (d. 16-28:
imagen/contenedor/capas, Dockerfile, ciclo de vida, secretos, compose,
encargos 3 y 4, Práctica 2, checklist de reproducibilidad) → **03 Cierre**
(d. 29-34: recapitulación, lluvia de ideas, «del caso de uso al primer
encargo», cómo seguir).

1. [ ] **API con FastAPI** (diapositiva 9) en `src/litmar/api.py`.
   Prompt: «Expón litmar como API con FastAPI en src/litmar/api.py: GET /salud,
   GET /fuentes, GET /buscar (varias fuentes y año mínimo, con
   buscar_en_fuentes) y POST /revisiones (flujo o agente, con flujo.revisar y
   agente.revisar; devuelve el informe y el BibTeX, no los guarda en disco).
   Primero propón el contrato: parámetros, modelos de entrada y salida y códigos
   de error de cada ruta. Token opcional desde el .env. Tests con TestClient,
   sin red, y un comando litmar servir.»
   - En qué fijarse: (1) ¿el contrato tiene sentido antes de programar?
     (2) ¿llama a `buscar_en_fuentes` y a `revisar` o duplica lógica? (3) `n=0`
     en `/docs` da 422; (4) ¿qué devuelve si falla una fuente o falta la clave
     del LLM?
   - Lo que hay que decidir al proponer el contrato (anotar en `DECISIONS.md`):
     - **Errores** (d. 6 y 11: 200, 422, 401, 502): `buscar_en_fuentes` ya
       recoge los errores por fuente; propuesta: 200 con una lista `errores` si
       alguna fuente responde, **502** solo si fallan todas. Falta de
       configuración del modelo (`ErrorDeConfiguracion`): **503** con el mensaje
       de qué poner en el `.env`, sin claves ni peticiones (§7).
     - **Token**: `LITMAR_API_TOKEN` (nombre a confirmar) en `.env.example`;
       sin él la API es abierta; con él, `Authorization: Bearer …` comparado con
       `secrets.compare_digest`, 401 si no cuadra. ¿`/salud` y `/` sin token?
       Si hay token, la web (encargo 2) necesita pedirlo o la API no la deja
       buscar: decidir antes de ese encargo.
     - **`/revisiones` es síncrona** y tarda minutos (d. 11 «Tareas largas»: en
       producción se devolvería un id; aquí no, a propósito). `--aprobar` no
       tiene sentido en HTTP: el modo agente va sin aprobación.
     - **Límites**: `n` entre 1 y 50 (`Query(ge=1, le=50)`, d. 8) en `/buscar`;
       en `/revisiones`, el `MAX_SELECCIONADOS` del flujo. «Límites de uso» por
       cliente (d. 11) solo se menciona.
     - **Modelos de salida Pydantic** (`ArticuloSalida.desde(articulo)`, d. 8):
       mismos campos que el JSON de `Biblioteca`.
   - `litmar servir [--host 127.0.0.1] [--puerto 8000] [--recargar]` con
     uvicorn (con `--recargar` hay que pasar la app como texto,
     `"litmar.api:app"`). `uv add fastapi uvicorn` (TestClient usa httpx, que ya
     está). Sección en el README.
   - Demo (d. 10): `uv run litmar servir --recargar`, `/docs`, `curl
     "http://127.0.0.1:8000/buscar?consulta=posidonia&n=2"`.
2. [ ] **Web en HTML y JavaScript** (diapositiva 13) en
   `src/litmar/web/index.html`. Prompt: «Crea una página web en
   src/litmar/web/index.html (HTML, CSS y JavaScript, sin npm ni compilación)
   que use nuestra API: búsqueda con fuentes y año mínimo, tabla con los DOI
   enlazados y un botón Revisar que llame a POST /revisiones, muestre el
   informe y deje descargar el BibTeX. Que la API la sirva en /. Avisa de que
   una revisión tarda minutos y muestra los errores con claridad. Usa rutas
   relativas (/buscar), sin la dirección del servidor. Antes, dime qué rutas
   usará y con qué parámetros.»
   - En qué fijarse: (1) solo rutas del contrato, sin cambiar la API; (2) F12 >
     Red: qué pide y qué devuelve; (3) por qué no hace falta CORS (mismo origen)
     y qué pasaría en otro dominio; (4) qué ve el usuario mientras espera o si
     algo falla.
   - Comprobar que `uv_build` mete `web/index.html` en el paquete (la API la
     lee del paquete, no de la carpeta del repo) y test de que `/` devuelve la
     página. El informe llega en Markdown: decidir si se muestra como texto o
     con una conversión mínima sin librerías externas (sin npm).
3. [ ] **Práctica 1** de los alumnos (d. 14, 20 min): `litmar servir`, web en
   `/` y `/docs`, F12 > Red, provocar un 422, pedir a la IA una mejora o una
   ruta nueva (exportar en BibTeX) con su test. Puede convenir tener hecha la
   ruta de BibTeX como referencia (sin integrarla).
4. [ ] **Dockerfile** (diapositivas 19-20). Prompt: «Crea un Dockerfile para
   litmar usando uv con la imagen oficial de Astral y Python 3.12 slim. Instala
   las dependencias desde uv.lock antes de copiar el código para aprovechar la
   caché, sin dependencias de desarrollo (pytest, ruff y Streamlit no hacen
   falta en el servidor), usuario no root, y nada de secretos dentro: añade un
   .dockerignore. Comenta cada línea.» Y la revisión: «Revisa este Dockerfile
   como un experto en seguridad y reproducibilidad. ¿Qué se copia que no
   debería? ¿Qué capa se rompe en cada cambio? No cambies nada.»
   - Referencia: el Dockerfile de la d. 19 (`FROM python:3.12-slim`, `COPY
     --from=ghcr.io/astral-sh/uv`, `UV_NO_DEV=1`, `uv sync --locked
     --no-install-project`, `COPY . .`, `uv sync --locked`, `useradd`, `USER
     app`, `EXPOSE 8000`, `CMD … litmar servir --host 0.0.0.0`).
   - Ojo: Streamlit está en el extra `ui` y en el grupo `dev`, así que no entra
     en la imagen; `litmar ui` dentro del contenedor debe dar un error claro
     (ya importa Streamlit solo al usarlo). El `.dockerignore` debe excluir
     `.env`, `.env.*` (salvo `.env.example`), `.venv` (binarios de macOS),
     `.git`, cachés, `tests/`, `docs/` (PDFs) y `ejemplos/revisiones/`, pero
     **no** `README.md` (`pyproject` lo declara y `uv_build` lo necesita).
     Comprobar que `uv run` como usuario `app` no intenta reescribir `.venv`
     (propiedad de root); si lo hace, `--no-sync` o `chown`.
5. [ ] **compose.yaml con dos servicios** (diapositiva 24). Prompt: «Crea un
   compose.yaml con dos servicios: api (nuestra imagen, litmar servir en
   0.0.0.0, puerto 8000, .env al arrancar) y web (imagen oficial de nginx,
   puerto 8080) que sirva src/litmar/web y reenvíe a api las rutas de la API
   usando el nombre del servicio, con tiempo de espera de varios minutos para
   las revisiones. Explícame cada línea y cómo arrancar, ver los logs y parar.»
   - En qué fijarse: (1) cómo encuentra `web` a `api` (DNS de compose por
     nombre de servicio); (2) qué rutas reenvía nginx y si funciona `/docs`
     (necesita también `/openapi.json`); (3) el `.env` llega solo a `api` y no
     está en ninguna imagen; (4) si se para `api`, qué muestra la web (502 de
     nginx: la web debe mostrarlo claro, enlaza con el encargo 2).
   - nginx con `proxy_read_timeout` (y `proxy_send_timeout`) de varios minutos;
     su configuración en un fichero del repo montado de solo lectura. Demo
     (d. 25): `docker compose up --build`, `docker compose ps`,
     `localhost:8080` (web) y `localhost:8000/docs` (API). Variante de
     desarrollo comentada (d. 23): `volumes: [./src:/app/src]` y `--recargar`.
6. [ ] **Práctica 2** (d. 27, 30 min; sin Docker, en parejas): `docker compose
   up --build` (o `podman compose`), una búsqueda y una revisión en `:8080`,
   comprobar que el `.env` no está en la imagen (p. ej. `docker run --rm litmar
   ls -la /app`), cambiar código y ver qué capas se rehacen.
7. [ ] **Checklist de reproducibilidad** (d. 28): `uv.lock`, `.env.example`
   documentado, ningún secreto en git ni en la imagen, tests sin internet,
   README con cómo instalar y ejecutar (añadir API y Docker), funciona en una
   máquina limpia. Aprovechar para cerrar el paso 5 de «Próximos pasos»
   (`description` de `pyproject.toml`).
8. [ ] **Cierre** (d. 29-34): sin código. Lluvia de ideas (datos, literatura,
   servicios), prompt «del caso de uso al primer encargo» (d. 32). La d. 33
   avisa de que la clave del curso caduca el 19/11 a las 14:00 y recomienda
   Gemini con plan gratuito.

Requisitos en la máquina del ensayo: **Docker no está instalado** (comprobado
el 18/11, tampoco Podman). Sin él se pueden escribir el Dockerfile y el
compose, pero no probarlos (encargos 4-6).

## Cabos sueltos

- **Subagente `general-purpose` del agente**: Deep Agents lo ofrece siempre en
  `task`, con las herramientas del principal (no puede buscar). Si en clase
  molesta, se quita con `register_harness_profile(<clave del modelo>,
  HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)))`.
- **El buscador ve resúmenes recortados a 400 caracteres** (`LARGO_RESUMEN` en
  `herramientas.py`): en la prueba real el informe del agente dice varias veces
  que «los resúmenes recibidos no permiten…». Buen ejemplo para el taller
  (flujo contra agente: el flujo resume el resumen completo).
- **Europe PMC deja HTML en títulos y resúmenes** (`<i>…</i>`, `&lt;i&gt;`),
  visto el 18/11 al probar `buscar_articulos`. Afecta a la tabla de la CLI, al
  BibTeX y a lo que ve el modelo. Limpiarlo en `fuentes/europepmc.py` (con
  `html.unescape` y quitar etiquetas) y añadir un test con un título así.
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

<<<<<<< HEAD
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
=======
### 2026-11-18 — Selección por relevancia y citas anualizadas

- D-23 sustituye el orden por citas totales (D-17): se combina 70 % de
  relevancia (1–5) con 30 % de la puntuación de citas anualizadas, ajustada a
  escala 1–5. Sin recuento disponible, se usa solo relevancia.
- `Articulo.citations` ahora permite `None`; arXiv, Zotero y PANGAEA lo usan al
  no ofrecer recuento. OpenAlex, Crossref y Europe PMC preservan el cero y
  distinguen un campo ausente. UI, CLI, herramientas e informes identifican el
  dato ausente.
- El flujo resume todos los candidatos con resumen antes de escoger los N, por
  lo que puede hacer más llamadas al modelo. En modo agente, las herramientas
  exponen la tasa/ajuste y el prompt pide la misma puntuación.
- Preparado para PR en la rama local `feat/citation-aware-selection`; el commit
  no se ha enviado.
- Validación: 312 tests, Ruff, formato y lockfile en verde.

### 2026-11-18 — Sincronización con `Sapere-IA/litmar/main`

- Se actualizó `main` hasta `db90288` (cuatro commits; coincide con
  `origin/main`), incluyendo el arreglo de aprobaciones paralelas y la pestaña
  «Revisión».
- Al reaplicar cambios locales staged hubo solapamientos con esas
  implementaciones. Se eligió upstream como versión autoritativa; el trabajo
  local completo se conserva en `stash@{0}` por si hay que recuperar alguna
  diferencia.
- Validación: 299 tests; `ruff check`, `ruff format --check` y `uv lock --check`
  pasan.
### 2026-11-18 — Sesión 2: diapositivas de la Clase 3

- Añadido `docs/Clase3.pdf` (*APIs, reproducibilidad y transferencia*,
  19/11/2026, 35 diapositivas); commit `9dbd220`. Hoja de ruta de `AGENTS.md`
  actualizada.
- Leídas enteras y volcadas en «Plan de la Clase 3»: cuatro encargos en
  directo (API FastAPI en `api.py` + `litmar servir`, web en
  `src/litmar/web/index.html`, Dockerfile con uv, `compose.yaml` con api +
  nginx), dos prácticas, la checklist de reproducibilidad y el cierre. Para
  cada encargo se anotaron el prompt literal, «En qué fijarse» y las decisiones
  que habrá que tomar al proponer el contrato (códigos 502/503, token, revisión
  síncrona, sin `--aprobar` en HTTP). Principios de la Clase 3 añadidos a
  `AGENTS.md` §2. Docker no está instalado en esta máquina: avisado en el plan.

### 2026-11-18 — Sesión 2: pestaña «Revisión» en la UI (Clase 2, encargo 9)

- Prompt literal de la diapositiva 40. Refactor mínimo (D-22): `flujo.revisar()`
  y `agente.revisar()` con `mostrar`; la CLI las usa y su salida no cambia.
- `ui.py`: `app()` con pestañas; `busqueda()` (lo de antes) y `revision()`:
  pregunta, modo, fuentes, número de artículos; pasos en vivo con `st.status`;
  informe con `flujo.enlazar_dois` (DOI → enlaces) y descargas; aviso del
  `.env` y botón desactivado sin modelo. Sin `--aprobar` en la UI.
- Tests: 6 nuevos en `tests/test_ui.py` (sin modelo, flujo completo con modelo
  falso, pregunta vacía, agente con `agente.revisar` sustituido, límite,
  `enlazar_dois`). 299 tests.
- Prueba real: la pestaña con `AppTest` y el modelo del `.env` (flujo, Europe
  PMC, 3 artículos): 6 pasos, 3 citas enlazadas, 46 s. `litmar ui --server.headless
  true` arranca (health ok). No se ha visto en un navegador.

### 2026-11-18 — Sesión 2: arreglo de `--aprobar` con buscadores en paralelo

- El usuario probó `--modo agente --aprobar` y falló tras aprobar dos
  búsquedas: «When there are multiple pending interrupts, you must specify the
  interrupt id when resuming». El agente lanzó dos buscadores a la vez, cada uno
  con su pausa; el código solo guardaba la última y reanudaba sin id.
- Arreglo: `agente.ejecutar()` recoge todas las interrupciones del principal
  por `id`, pide una decisión por cada búsqueda y reanuda con
  `Command(resume={id: {"decisions": [...]}})`. El bucle, que estaba duplicado
  en la CLI y en los tests (por eso los tests no lo vieron), vive ahora solo
  ahí. Trampa en `AGENTS.md` §9.
- 2 tests de regresión (dos encargos en paralelo, aprobar uno y rechazar otro, y
  la CLI); se comprobó que fallan con el código anterior con el mismo error.
  293 tests.

### 2026-11-18 — Sesión 2: agente con Deep Agents (Clase 2, encargo 8)

- Prompt literal de la diapositiva 36. Antes, documentación actual: subagente
  `web-fetch` sobre docs.langchain.com (HITL, subagentes, backends, perfiles,
  streaming) y comprobación en el código instalado (deepagents 0.7.39) de lo
  que no aclaraban. Hallazgos en `AGENTS.md` §9.
- `src/litmar/agente.py` (D-21): `crear_agente`, `Registro`, `Narrador`,
  `interrupcion`, `estado_final`. `herramientas.py` se partió en `buscar()` y
  `describir_fuentes()` (con `permitidas` y `desde`) para reutilizarlas.
- CLI: `--modo agente`, `--aprobar` (pregunta S/n/e en la terminal), `-n` como
  máximo de artículos del agente; `_revisar` dividido en `_con_flujo` y
  `_con_agente`.
- `tests/test_agente.py` (18 tests): modelo de guion, herramientas de cada
  agente, recorrido completo, DOI inventado, límite de pasos y de búsquedas,
  fuentes permitidas, aprobar/rechazar/editar, CLI. 291 tests.
- Prueba real (Anthropic, pregunta de la demo): plan de 4 tareas, 3 encargos al
  buscador en paralelo, 9 búsquedas, 6 citas verificadas, «Lo que no se
  encontró» bien hecho; 1:52 min. `--aprobar` no se probó con el modelo real
  (necesita terminal interactiva); sí con tests.

### 2026-11-18 — Sesión 2: herramientas (Clase 2, encargo 6)

- Prompt literal de la diapositiva 28. `src/litmar/herramientas.py`:
  `buscar_articulos(consulta, fuente="OpenAlex", n=5)` y `listar_fuentes()` con
  `@tool(parse_docstring=True)`; `HERRAMIENTAS` para el agente. D-20.
- «En qué fijarse»: (1) una herramienta para todas las fuentes, con `fuente`
  como parámetro; (2) los docstrings dicen qué devuelve, cuándo usarla, que solo
  se citen sus DOI y que PANGAEA da datos; (3) `n = max(1, min(n, 10))` en el
  código; (4) si una fuente falla, el modelo recibe «Error: OpenAlex respondió
  con HTTP 503. Prueba con otra fuente.», sin la URL.
- Refactor: `busqueda.mensaje_de_error()` (lo usan `buscar_en_fuentes` y la
  herramienta), con un caso para errores inesperados (solo el tipo).
- `tests/test_herramientas.py` (23 tests, sin red). 273 tests.
- Prueba real: las dos herramientas contra las APIs (Europe PMC, PANGAEA, una
  fuente inexistente) y `bind_tools` con Claude: pidió
  `buscar_articulos(consulta="ocean acidification coral", n=3)`. Se vio HTML en
  los títulos de Europe PMC (anotado en «Cabos sueltos»).

### 2026-11-18 — Sesión 2: salidas de `litmar revisar` en `ejemplos/revisiones/`

- Petición del usuario: guardar las salidas en `ejemplos/`, cada una en su
  subdirectorio. Decidió (herramienta de preguntas) nombre con fecha, hora y
  pregunta, y no versionarlas (D-19).
- `cli.py`: `nombre_carpeta()` y `carpeta_revision()`; `--informe` y `--bibtex`
  ya no tienen valor por defecto (si faltan, van a la carpeta de la ejecución).
  `.gitignore`: `ejemplos/revisiones/`. 4 tests nuevos (nombre, no pisar, CLI
  sin rutas, una revisión que falla no deja carpeta). 250 tests.

### 2026-11-18 — Sesión 2: flujo LangGraph y `litmar revisar` (Clase 2, encargo 5)

- Prompt literal de la diapositiva 19. Primero plan y diagrama Mermaid; el
  usuario pidió alinearlo con la diapositiva 18 (cambio: `planificar` da 2-3
  búsquedas, no 1-3) y decidió, con la herramienta de preguntas: «mejores» = más
  citados (D-17), marcar las citas inválidas tras 2 reescrituras (D-18), estado
  en inglés (D-2), y commit previo de la Práctica 1 (3416434, ya en `origin`).
- `src/litmar/flujo.py`: `EstadoRevision` (TypedDict; `warnings` con reductor
  `operator.add`), seis nodos como clausuras dentro de `crear_flujo(modelo,
  fuentes, n, desde, crear_fuente)`, arista condicional `decidir`. Límites en
  código: 3 consultas, 10 seleccionados, 2 reescrituras. `planificar` y
  `resumir` usan `method="json_schema"`. `sintetizar` sin resúmenes no llama al
  modelo; al reescribir le pasa su informe y los DOI inválidos. Las citas se
  extraen con una regex (`[doi:…]` o `doi.org/…`) y se normalizan con
  `normalizar_doi`. `describir_paso` da las líneas de la demo (no imprime: la
  UI la reutilizará). Las referencias del informe las genera el código.
- CLI: `litmar revisar "pregunta" [--modo flujo] [--fuente] [-n ≤10] [--desde]
  [--informe revision.md] [--bibtex revision.bib]`, con `stream(stream_mode=
  ["updates", "values"])`. Errores del modelo → mensaje y código 1.
- Dependencia nueva: `langgraph` (1.2.22). `tests/test_flujo.py` (16 tests):
  aristas del grafo = diagrama, recorrido completo, reescritura, máximo de 2,
  sin artículos, resumen que falla, CLI. 245 tests.
- Prueba real (Anthropic) con la pregunta de la demo: 3 consultas, 50
  artículos, 6 seleccionados, informe con 5 citas, todas verificadas, 1:35 min.
  El filtro por citas metió dos trabajos generales sobre olas de calor: buen
  ejemplo para la Práctica 2. No se vio una reescritura real (el modelo no
  inventó); el camino está cubierto por tests.
- A petición del usuario, `docs/flujo.md`: el diagrama Mermaid didáctico (LLM /
  CÓDIGO, como la diapositiva 18), una tabla de qué lee y escribe cada nodo en
  el estado, y el Mermaid que genera LangGraph (`get_graph().draw_mermaid()`).
  Un test falla si este último deja de coincidir con el grafo. 246 tests.

### 2026-11-18 — Sesión 2: Práctica 1 (`ejemplos/resumir.py`) y prueba real

- `ejemplos/resumir.py`: carga `.env`, crea el modelo (si falta algo, imprime el
  error y sale con 1), busca en OpenAlex los 3 primeros artículos sobre «ocean
  acidification» que tienen resumen (pide 12) y muestra el resumen de cada uno
  con su enlace al DOI. Si un resumen falla (p. ej. 429), sigue con los demás.
  `TEMA` y `PREGUNTA` arriba para que cada alumno ponga los suyos. Test en
  `tests/test_ejemplos.py` con fuente y modelo falsos.
- **Primera prueba real** (el usuario ya tiene `anthropic:claude-sonnet-5-5` en
  el `.env`): los tres resúmenes salen bien y marcan lo que no está en el
  resumen («No consta…»). `langchain-anthropic` avisaba de que el método por
  defecto (`function_calling`) puede fallar en ese modelo: `resumir` pasa ahora
  `method="json_schema"`, válido también en Gemini. Trampa anotada en
  `AGENTS.md` §9.
- 229 tests.

### 2026-11-18 — Sesión 2: `llm.py` (Clase 2, encargo 3)

- Prompt literal de la diapositiva 12. `src/litmar/llm.py`: `crear_modelo()` lee
  `LITMAR_MODELO` (formato `proveedor:modelo`), comprueba la clave del proveedor
  (`GOOGLE_API_KEY`/`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) y
  llama a `init_chat_model` con un `InMemoryRateLimiter`. Si falta algo,
  `ErrorDeConfiguracion` con la línea exacta que hay que añadir al `.env`.
- Límite: 10 llamadas/min por defecto, `LITMAR_LLAMADAS_POR_MINUTO` (0 = sin
  límite). Decisiones D-15 (dependencias) y D-16 (límite, `.env` no se carga en
  `llm.py`).
- Dependencias nuevas: `langchain`, `langchain-google-genai`,
  `langchain-anthropic` («En qué fijarse» 3).
- `.env.example`: sección del modelo de lenguaje. README: tabla de variables y
  ejemplo con `crear_modelo`.
- `tests/test_llm.py` (16 tests): crean el objeto del modelo con claves falsas,
  sin llamarlo. 227 tests.
- Prueba real: no se pudo, el `.env` no tiene `LITMAR_MODELO` (se vio el
  mensaje de error, que es el punto 2 de la diapositiva).

### 2026-11-18 — Sesión 2: `resumir` (Clase 2, encargo 2)

- Prompt literal de la diapositiva 11. Nuevo `src/litmar/resumen.py`:
  `ResumenArticulo` (Pydantic) con `objective`, `method`, `findings` (lista),
  `relevance` (1-5, validado con `ge`/`le`) y `limitations`, todos con
  descripción porque el modelo las lee. `resumir()` devuelve `None` sin llamar
  al modelo si no hay resumen, y las instrucciones piden usar solo título y
  resumen y escribir «No consta en el resumen.» en vez de inventar.
- Campos en inglés aunque la diapositiva los nombra en español: convención D-2.
- El modelo se recibe como parámetro (lo creará `llm.py`); `resumen.py` no lee
  claves ni conoce proveedores. Dependencias nuevas: `pydantic` y
  `langchain-core` (de ahí viene `with_structured_output`).
- `tests/test_resumen.py`: modelo falso propio (solo `with_structured_output` e
  `invoke`), sin clave ni red. 211 tests. Sección en el README.
- Sin probar con un modelo real: falta `llm.py` (siguiente encargo).
>>>>>>> upstream/main

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
