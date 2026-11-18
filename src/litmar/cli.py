"""Interfaz de terminal para buscar, conservar y exportar bibliografía."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

from litmar.articulo import Articulo
from litmar.biblioteca import Biblioteca
from litmar.busqueda import buscar_en_fuentes
from litmar.configuracion import FUENTES, id_fuente, nombre_fuente
from litmar.flujo import LIMITE_RECURSION, biblioteca_de_citas, crear_grafo, estado_inicial
from litmar.llm import crear_modelo

ANCHO_AUTORES = 20


def _positivo(valor: str) -> int:
    numero = int(valor)
    if numero < 1:
        raise argparse.ArgumentTypeError("debe ser al menos 1")
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
        help="Responder a una pregunta con un informe que solo cita artículos reales",
    )
    revisar.add_argument("pregunta", type=_consulta)
    revisar.add_argument(
        "--modo",
        choices=("flujo", "agente"),
        default="flujo",
        help="Modo de revisión (el modo agente se añadirá después)",
    )
    revisar.add_argument(
        "-n",
        "--n",
        type=_positivo,
        default=6,
        metavar="N",
        help="Máximo de artículos seleccionados (6)",
    )
    revisar.add_argument(
        "--fuente",
        type=_fuentes,
        default=["OpenAlex", "Europe PMC"],
        metavar="F1,F2",
        help="Fuentes separadas por comas (openalex,europepmc)",
    )
    revisar.add_argument(
        "--desde", type=int, metavar="AÑO", help="Solo artículos publicados ese año o después"
    )
    revisar.add_argument(
        "--informe",
        type=Path,
        default=Path("informe.md"),
        metavar="ARCHIVO.md",
        help="Archivo donde guardar el informe (informe.md)",
    )
    revisar.add_argument(
        "--bibtex",
        type=Path,
        default=Path("citas.bib"),
        metavar="ARCHIVO.bib",
        help="Archivo donde guardar el BibTeX de lo citado (citas.bib)",
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
    filas = [(str(a.year), str(a.citations), a.short_authors, a.title) for a in articulos]
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


def _revisar(args: argparse.Namespace) -> int:
    """Ejecuta el flujo, imprime cada paso y guarda informe y BibTeX de lo citado."""
    if args.modo == "agente":
        print("Error: el modo agente aún no está disponible; usa --modo flujo.", file=sys.stderr)
        return 1
    if args.informe.resolve() == args.bibtex.resolve():
        raise ValueError("el informe y el archivo BibTeX deben ser distintos")

    grafo = crear_grafo(crear_modelo())
    estado = estado_inicial(args.pregunta, args.fuente, args.n, args.desde)
    resultado: dict = {}
    for fragmento in grafo.stream(
        estado,
        config={"recursion_limit": LIMITE_RECURSION},
        stream_mode="updates",
    ):
        for nombre, actualizacion in fragmento.items():
            print(f"> {nombre:<18} {actualizacion.get('traza', '')}".rstrip())
            resultado.update(actualizacion)

    Path(args.informe).write_text(resultado.get("informe", ""), encoding="utf-8")
    citas = biblioteca_de_citas(resultado)
    citas.exportar_bibtex(args.bibtex)
    for aviso in resultado.get("avisos", []):
        print(f"Aviso: {aviso}", file=sys.stderr)
    sufijo = "" if len(citas) == 1 else "s"
    print(f"Informe: {args.informe}")
    print(f"BibTeX:  {args.bibtex} ({len(citas)} artículo{sufijo})")
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
        return _buscar(args) if args.comando == "buscar" else _exportar(args)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
