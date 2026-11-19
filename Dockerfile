# Imagen de litmar para servir la API y la web.
# El orden de las capas importa: primero lo que cambia poco (sistema, uv y
# dependencias), después el código. Así, un cambio en src/ no reinstala nada.

# Base oficial de Python 3.12 en su variante slim: pequeña y con soporte largo.
FROM python:3.12-slim

# Copiamos uv desde su imagen oficial, fijada a la versión que generó uv.lock.
# Fijar la versión evita que un cambio de uv altere la instalación sin avisar.
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/

# Todo el trabajo ocurre en /app; es el directorio de trabajo del contenedor.
WORKDIR /app

# Compilar los .pyc al instalar acelera el arranque; copiar en vez de enlazar
# evita problemas de hardlinks entre el sistema de ficheros de Docker y /app.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Copiamos SOLO lo que define las dependencias: el lock, el pyproject y el
# README (pyproject lo declara como `readme`, así que uv lo necesita).
COPY uv.lock pyproject.toml README.md ./

# Instalamos desde el lock sin el grupo dev (pytest, ruff y Streamlit) y sin
# instalar el proyecto aún. Es la capa gorda: mientras uv.lock no cambie,
# Docker la reutiliza aunque cambie el código. Equivale a UV_NO_DEV=1.
RUN uv sync --locked --no-dev --no-install-project

# Ahora sí entra el código. La web va dentro del paquete (src/litmar/web) y
# por eso debe copiarse entera; no hay ficheros estáticos sueltos.
COPY src ./src

# Instalamos el proyecto en el entorno ya preparado, sin volver a resolver
# dependencias y sin desarrollo. Esto crea el script .venv/bin/litmar.
RUN uv sync --locked --no-dev

# Ponemos el entorno virtual en el PATH para ejecutar `litmar` directamente.
# No usamos `uv run` en tiempo de ejecución: como usuario sin root intentaría
# sincronizar y no podría escribir en un .venv propiedad de root.
ENV PATH="/app/.venv/bin:$PATH"

# Creamos un usuario sin privilegios y le damos dueño a /app, incluido el
# .venv creado por root en las capas anteriores. Los secretos no se copian
# a la imagen: se pasan al arrancar con `--env-file` o `env_file:` de compose.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

# Documentamos el puerto que expone la API; no lo publica (eso lo hace -p).
EXPOSE 8000

# Escuchamos en todas las interfaces: 127.0.0.1 solo respondería dentro del
# contenedor y ni el navegador ni nginx podrían llegar. Nginx tendrá que
# esperar varios minutos en las revisiones (se ajusta en el próximo encargo).
CMD ["litmar", "servir", "--host", "0.0.0.0"]
