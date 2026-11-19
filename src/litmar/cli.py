"""Interfaz de terminal para buscar, conservar y exportar bibliografía."""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
import unicodedata
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from litmar.articulo import Articulo
from litmar.biblioteca import Biblioteca
from litmar.busqueda import buscar_en_fuentes
from litmar.configuracion import FUENTES, id_fuente, nombre_fuente
from litmar.flujo import MAX_SELECCIONADOS

ANCHO_AUTORES = 20
# Cada `litmar revisar` guarda su informe y su BibTeX en un subdirectorio propio.
CARPETA_REVISIONES = Path("ejemplos") / "revisiones"
LARGO_NOMBRE = 50


def _positivo(valor: str) -> int:
    numero = int(valor)
    if numero < 1:
        raise argparse.ArgumentTypeError("debe ser al menos 1")
    return numero


def _hasta_maximo(valor: str) -> int:
    numero = _positivo(valor)
    if numero > MAX_SELECCIONADOS:
        raise argparse.ArgumentTypeError(f"como mucho {MAX_SELECCIONADOS}")
    return numero


def _consulta(valor: str) -> str:
    if not valor.strip():
        raise argparse.ArgumentTypeError("la consulta no puede estar vacía")
    return valor.strip()


def _fuentes(valor: str) -> list[str]:
    """«openalex,europepmc» → ["OpenAlex", "Europe PMC"], sin repetidos."""
    identificadores = [parte for parte in valor.split(",") if parte.strip()]
    if not identificadores:
        raise argparse.ArgumentTypeError("indica al menos una fuente")
    try:
        nombres = [nombre_fuente(identificador) for identificador in identificadores]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None
    return list(dict.fromkeys(nombres))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Busca y organiza artículos científicos.")
    comandos = parser.add_subparsers(dest="comando", required=True)

    buscar = comandos.add_parser("buscar", help="Buscar artículos en una o varias fuentes")
    buscar.add_argument("consulta", type=_consulta)
    buscar.add_argument(
        "-n",
        "--n",
        type=_positivo,
        default=10,
        metavar="N",
        help="Número máximo de resultados por fuente (10)",
    )
    buscar.add_argument(
        "--fuente",
        type=_fuentes,
        default=["OpenAlex"],
        metavar="F1,F2",
        help=f"Fuentes separadas por comas: {', '.join(id_fuente(f) for f in FUENTES)} (openalex)",
    )
    buscar.add_argument(
        "--desde", type=int, metavar="AÑO", help="Solo artículos publicados ese año o después"
    )
    buscar.add_argument(
        "--guardar",
        type=Path,
        metavar="ARCHIVO.json",
        help="Guardar resultados; si existe, combinar sin duplicar DOI",
    )
    buscar.add_argument(
        "--bibtex", type=Path, metavar="ARCHIVO.bib", help="Exportar los resultados a BibTeX"
    )

    exportar = comandos.add_parser("exportar", help="Exportar una biblioteca JSON a BibTeX")
    exportar.add_argument("biblioteca", type=Path)
    exportar.add_argument("--bibtex", type=Path, required=True, metavar="ARCHIVO.bib")

    revisar = comandos.add_parser(
        "revisar",
        help="Revisión de literatura con un modelo de lenguaje: informe y BibTeX de lo citado",
        description="Necesita LITMAR_MODELO y la clave de su proveedor en el .env.",
    )
    revisar.add_argument("pregunta", type=_consulta, help="La pregunta de investigación")
    revisar.add_argument(
        "--modo",
        choices=["flujo", "agente"],
        default="flujo",
        help="flujo: pasos fijos con LangGraph (por defecto); agente: decide el modelo, "
        "con Deep Agents",
    )
    revisar.add_argument(
        "--aprobar",
        action="store_true",
        help="Solo con --modo agente: pedir permiso antes de cada búsqueda",
    )
    revisar.add_argument(
        "--fuente",
        type=_fuentes,
        default=["OpenAlex", "Europe PMC"],
        metavar="F1,F2",
        help="Fuentes separadas por comas (openalex,europepmc)",
    )
    revisar.add_argument(
        "-n",
        "--n",
        type=_hasta_maximo,
        default=6,
        metavar="N",
        help=f"Artículos que se resumen en el flujo o que elige el agente para el informe "
        f"(6; máximo {MAX_SELECCIONADOS})",
    )
    revisar.add_argument(
        "--desde", type=int, metavar="AÑO", help="Solo artículos publicados ese año o después"
    )
    revisar.add_argument(
        "--informe",
        type=Path,
        metavar="ARCHIVO.md",
        help=f"Dónde guardar el informe (por defecto, {CARPETA_REVISIONES}/<fecha_pregunta>/"
        "revision.md)",
    )
    revisar.add_argument(
        "--bibtex",
        type=Path,
        metavar="ARCHIVO.bib",
        help=f"Dónde guardar el BibTeX de lo citado (por defecto, {CARPETA_REVISIONES}/"
        "<fecha_pregunta>/revision.bib)",
    )

    servir = comandos.add_parser(
        "servir",
        help="Levantar la API HTTP con uvicorn",
        description="Documentación interactiva en http://127.0.0.1:8000/docs.",
    )
    servir.add_argument("--host", default="127.0.0.1", help="Dirección de escucha (127.0.0.1)")
    servir.add_argument("--puerto", type=int, default=8000, help="Puerto (8000)")
    servir.add_argument(
        "--recargar",
        action="store_true",
        help="Reiniciar el servidor cuando cambie el código (desarrollo)",
    )

    comandos.add_parser(
        "ui",
        help="Abrir la interfaz web en el navegador",
        epilog="Las opciones adicionales se pasan a `streamlit run`, p. ej. --server.port 8600.",
    )
    return parser


def _recortar(texto: str, ancho: int) -> str:
    return texto if len(texto) <= ancho else texto[: ancho - 1] + "…"


def tabla(articulos: Iterable[Articulo], ancho: int | None = None) -> str:
    """Tabla AÑO · CITAS · AUTORES · TÍTULO ajustada al ancho de la terminal."""
    filas = [
        (
            str(a.year),
            str(a.citations) if a.citations is not None else "No disponible",
            a.short_authors,
            a.title,
        )
        for a in articulos
    ]
    if not filas:
        return ""
    ancho = ancho or shutil.get_terminal_size((100, 24)).columns
    ancho_citas = max(len("CITAS"), *(len(fila[1]) for fila in filas))
    ancho_autores = min(ANCHO_AUTORES, max(len("AUTORES"), *(len(fila[2]) for fila in filas)))
    ancho_titulo = max(20, ancho - (4 + 2 + ancho_citas + 2 + ancho_autores + 2))
    lineas = [
        f"{anio:<4}  {citas:>{ancho_citas}}  "
        f"{_recortar(autores, ancho_autores):<{ancho_autores}}  {_recortar(titulo, ancho_titulo)}"
        for anio, citas, autores, titulo in [("AÑO", "CITAS", "AUTORES", "TÍTULO"), *filas]
    ]
    return "\n".join(lineas)


def _buscar(args: argparse.Namespace) -> int:
    if args.guardar is not None and args.bibtex is not None:
        if args.guardar.resolve() == args.bibtex.resolve():
            raise ValueError("el archivo BibTeX debe ser distinto de la biblioteca JSON")
    # Se carga antes de consultar la red: un JSON inválido no gasta peticiones.
    biblioteca = (
        Biblioteca.cargar(args.guardar)
        if args.guardar is not None and args.guardar.exists()
        else Biblioteca()
    )
    resultado = buscar_en_fuentes(args.consulta, args.fuente, args.n, desde=args.desde)
    fallan_todas = len(resultado.failed) == len(args.fuente)
    for error in resultado.errors:
        print(f"{'Error' if fallan_todas else 'Aviso'}: {error}", file=sys.stderr)
    if fallan_todas:
        return 1

    encontrados = resultado.library
    if len(encontrados):
        print(tabla(encontrados))
    print(f"{len(encontrados)} resultados.")
    if args.guardar is not None:
        nuevos = sum(biblioteca.agregar(articulo) for articulo in encontrados)
        biblioteca.guardar(args.guardar)
        print(f"{nuevos} nuevos; {len(biblioteca)} artículos en {args.guardar}.")
    if args.bibtex is not None:
        encontrados.exportar_bibtex(args.bibtex)
        print(f"{len(encontrados)} artículos exportados a {args.bibtex}.")
    return 0


def _exportar(args: argparse.Namespace) -> int:
    if args.biblioteca.resolve() == args.bibtex.resolve():
        raise ValueError("el archivo BibTeX debe ser distinto de la biblioteca JSON")
    biblioteca = Biblioteca.cargar(args.biblioteca)
    biblioteca.exportar_bibtex(args.bibtex)
    print(f"{len(biblioteca)} artículos exportados a {args.bibtex}.")
    return 0


def nombre_carpeta(pregunta: str, ahora: datetime) -> str:
    """«2026-11-18_1530_como-afecta-el-calentamiento-a-las-praderas»: fecha, hora y pregunta.

    Sin acentos ni signos, en minúsculas y recortado a `LARGO_NOMBRE` caracteres
    sin partir palabras, para que sirva como nombre de carpeta en cualquier sistema.
    """
    ascii_ = unicodedata.normalize("NFKD", pregunta).encode("ascii", "ignore").decode()
    palabras = re.findall(r"[a-z0-9]+", ascii_.lower())
    resumen = ""
    for palabra in palabras:
        siguiente = f"{resumen}-{palabra}" if resumen else palabra
        if len(siguiente) > LARGO_NOMBRE:
            break
        resumen = siguiente
    resumen = resumen or (palabras[0][:LARGO_NOMBRE] if palabras else "revision")
    return f"{ahora:%Y-%m-%d_%H%M}_{resumen}"


def carpeta_revision(
    pregunta: str, base: Path = CARPETA_REVISIONES, ahora: datetime | None = None
) -> Path:
    """Subdirectorio nuevo para una revisión; si ya existe, añade -2, -3…"""
    nombre = nombre_carpeta(pregunta, ahora or datetime.now())
    carpeta = base / nombre
    numero = 2
    while carpeta.exists():
        carpeta = base / f"{nombre}-{numero}"
        numero += 1
    return carpeta


def _revisar(args: argparse.Namespace) -> int:
    # LangChain y los paquetes de los proveedores tardan en importarse: solo se cargan
    # para este comando, no para `buscar` o `exportar`.
    from litmar import flujo
    from litmar.llm import ErrorDeConfiguracion, crear_modelo

    if args.aprobar and args.modo != "agente":
        raise ValueError("--aprobar solo se usa con --modo agente")
    if args.informe and args.bibtex and args.informe.resolve() == args.bibtex.resolve():
        raise ValueError("el informe y el BibTeX deben ser archivos distintos")
    try:
        modelo = crear_modelo()
    except ErrorDeConfiguracion as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        estado = _con_agente(args, modelo) if args.modo == "agente" else _con_flujo(args, modelo)
    except Exception as exc:  # p. ej. un 429 del proveedor o una respuesta que no se entiende
        print(f"Error del modelo: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for aviso in estado.get("warnings", []) if args.modo == "agente" else []:
        print(f"  Aviso: {aviso}", file=sys.stderr)

    # La carpeta se crea al final: una revisión que falla no deja carpetas vacías.
    informe, bibtex = args.informe, args.bibtex
    if informe is None or bibtex is None:
        carpeta = carpeta_revision(args.pregunta)
        carpeta.mkdir(parents=True)
        informe = informe or carpeta / "revision.md"
        bibtex = bibtex or carpeta / "revision.bib"
    informe.write_text(flujo.informe_markdown(estado), encoding="utf-8")
    referencias = flujo.citados(estado)
    referencias.exportar_bibtex(bibtex)
    print(f"Informe guardado en {informe}.")
    print(f"{len(referencias)} artículos citados exportados a {bibtex}.")
    return 0


def _mostrar(linea: str) -> None:
    print(linea, flush=True)


def _con_flujo(args: argparse.Namespace, modelo):
    from litmar import flujo

    return flujo.revisar(
        modelo,
        args.pregunta,
        fuentes=args.fuente,
        n=args.n,
        desde=args.desde,
        mostrar=_mostrar,
        avisar=lambda aviso: print(aviso, file=sys.stderr),
    )


def _con_agente(args: argparse.Namespace, modelo):
    from litmar import agente

    return agente.revisar(
        modelo,
        args.pregunta,
        fuentes=args.fuente,
        n=args.n,
        desde=args.desde,
        aprobar=args.aprobar,
        mostrar=_mostrar,
        decidir=_decidir,
    )


def _decidir(accion: dict) -> dict:
    """Pregunta en la terminal si se aprueba una búsqueda: sí, no o editar."""
    argumentos = dict(accion["args"])
    descripcion = (
        f"«{argumentos.get('consulta', '')}» en {argumentos.get('fuente', 'OpenAlex')} "
        f"(n={argumentos.get('n', 5)})"
    )
    try:
        respuesta = input(f"? ¿Buscar {descripcion}? [S/n/e(ditar)] ").strip().lower()
        if respuesta in ("n", "no"):
            return {"type": "reject", "message": "La persona no ha aprobado esta búsqueda."}
        if respuesta in ("e", "editar"):
            for clave in ("consulta", "fuente"):
                nuevo = input(f"  {clave} [{argumentos.get(clave, '')}]: ").strip()
                if nuevo:
                    argumentos[clave] = nuevo
            return {"type": "edit", "edited_action": {"name": accion["name"], "args": argumentos}}
    except EOFError:  # sin terminal interactiva: no se busca nada sin permiso
        return {"type": "reject", "message": "No se pudo pedir aprobación."}
    return {"type": "approve"}


def _servir(args: argparse.Namespace) -> int:
    """Levantar la API. La app se pasa como texto para que `--recargar` funcione."""
    import uvicorn

    uvicorn.run("litmar.api:app", host=args.host, port=args.puerto, reload=args.recargar)
    return 0


def _lanzar_ui(opciones: list[str]) -> int:
    """Ejecuta `streamlit run ui.py` con el mismo intérprete y entorno."""
    if importlib.util.find_spec("streamlit") is None:
        print(
            "Error: la interfaz necesita Streamlit. Instálalo con "
            "`uv sync --extra ui` o `pip install 'litmar[ui]'`.",
            file=sys.stderr,
        )
        return 1
    ui = Path(__file__).with_name("ui.py")
    try:
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ui),
                # Sin estadísticas de uso para Streamlit; las opciones del usuario van
                # después y pueden cambiarlo.
                "--browser.gatherUsageStats",
                "false",
                *opciones,
            ]
        )
    except KeyboardInterrupt:  # Ctrl+C para cerrar el servidor
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args, extra = parser.parse_known_args(argv)
    if args.comando == "ui":
        return _lanzar_ui(extra)
    if extra:
        parser.error(f"argumentos no reconocidos: {' '.join(extra)}")
    try:
        if args.comando == "revisar":
            return _revisar(args)
        if args.comando == "servir":
            return _servir(args)
        return _buscar(args) if args.comando == "buscar" else _exportar(args)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
