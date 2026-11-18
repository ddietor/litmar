"""Interfaz de terminal para buscar, conservar y exportar bibliografía."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import uuid
from collections.abc import Iterable
from pathlib import Path

from langgraph.types import Command

from litmar.agente import LIMITE_PASOS, crear_agente
from litmar.articulo import Articulo
from litmar.biblioteca import Biblioteca
from litmar.busqueda import buscar_en_fuentes
from litmar.configuracion import FUENTES, id_fuente, nombre_fuente
from litmar.flujo import (
    LIMITE_RECURSION,
    biblioteca_de_citas,
    crear_grafo,
    estado_inicial,
    extraer_citas,
)
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
        help="Modo de revisión: flujo (pasos fijos) o agente (decide el modelo)",
    )
    revisar.add_argument(
        "--aprobar",
        action="store_true",
        help="Pedir permiso antes de cada búsqueda (solo con --modo agente)",
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


def _texto(contenido: object) -> str:
    """Extrae el texto de un mensaje, tanto si es str como una lista de bloques."""
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "".join(
            bloque.get("text", "")
            for bloque in contenido
            if isinstance(bloque, dict) and bloque.get("type") == "text"
        )
    return str(contenido) if contenido else ""


def _pedir_decisiones(interrupciones: list) -> list[dict]:
    """Muestra las llamadas pendientes y pregunta: aprobar, editar o rechazar."""
    decisiones: list[dict] = []
    for interrupcion in interrupciones:
        for peticion in interrupcion.value["action_requests"]:
            args = peticion["args"]
            print("\nEl agente quiere ejecutar:")
            print(f"  {peticion['name']}({json.dumps(args, ensure_ascii=False)})")
            while True:
                try:
                    opcion = input("¿Aprobar, editar o rechazar? [a/e/r] ").strip().lower()
                except EOFError:
                    opcion = "r"  # sin terminal: no se autoriza nada por defecto
                if opcion in ("", "a", "s", "aprobar"):
                    decisiones.append({"type": "approve"})
                    break
                if opcion in ("r", "n", "rechazar"):
                    decisiones.append(
                        {"type": "reject", "message": "El usuario ha rechazado la búsqueda."}
                    )
                    break
                if opcion in ("e", "editar"):
                    try:
                        nuevos = json.loads(input("Nuevos argumentos (JSON): "))
                        if not isinstance(nuevos, dict):
                            raise ValueError("debe ser un objeto JSON")
                    except (EOFError, ValueError) as exc:
                        print(f"  No se pudo editar ({exc}). Prueba de nuevo.")
                        continue
                    decisiones.append({"type": "edit", "args": nuevos})
                    break
                print("  Escribe a (aprobar), e (editar) o r (rechazar).")
    print()
    return decisiones


def _procesar_fragmento(fragmento: dict) -> tuple[list, list[dict] | None]:
    """Imprime tareas y llamadas del agente; devuelve mensajes y decisiones si hay pausa."""
    mensajes: list = []
    decisiones: list[dict] | None = None
    for nombre, actualizacion in fragmento.items():
        if nombre == "__interrupt__":
            decisiones = _pedir_decisiones(actualizacion)
            continue
        if not isinstance(actualizacion, dict):
            continue
        for tarea in actualizacion.get("todos", []):
            print(f"> tarea           [{tarea.get('status', '?')}] {tarea.get('content', '')}")
        for mensaje in actualizacion.get("messages", []):
            mensajes.append(mensaje)
            tipo = getattr(mensaje, "type", "")
            if tipo == "ai":
                for llamada in getattr(mensaje, "tool_calls", []):
                    herramienta = llamada.get("name", "?")
                    argumentos = llamada.get("args", {})
                    if herramienta == "write_todos":
                        continue  # ya se ha mostrado la lista de tareas
                    if herramienta == "task":
                        destino = argumentos.get("subagent_type", "subagente")
                        print(f"→ task({destino}): {argumentos.get('description', '')}")
                    else:
                        print(f"→ {herramienta}({json.dumps(argumentos, ensure_ascii=False)})")
            elif tipo == "tool":
                resultado = " ".join(_texto(mensaje.content).split())
                print(f"> {getattr(mensaje, 'name', 'herramienta'):<17} {_recortar(resultado, 90)}")
    return mensajes, decisiones


def _revisar_agente(args: argparse.Namespace) -> int:
    """Ejecuta el agente, atiende las aprobaciones y guarda informe y BibTeX."""
    agente, registro = crear_agente(
        crear_modelo(),
        fuentes=args.fuente,
        n=args.n,
        desde=args.desde,
        aprobar=args.aprobar,
    )
    config = {"configurable": {"thread_id": uuid.uuid4().hex}, "recursion_limit": LIMITE_PASOS}
    entrada = {"messages": [{"role": "user", "content": args.pregunta}]}
    mensajes: list = []
    while True:
        interrumpido = False
        for fragmento in agente.stream(entrada, config=config, stream_mode="updates"):
            nuevos, decisiones = _procesar_fragmento(fragmento)
            mensajes.extend(nuevos)
            if decisiones is not None:
                # El mismo `thread_id` reanuda el grafo justo donde se paró.
                entrada = Command(resume={"decisions": decisiones})
                interrumpido = True
                break
        if not interrumpido:
            break

    informe = ""
    for mensaje in reversed(mensajes):
        if getattr(mensaje, "type", "") == "ai":
            texto = _texto(mensaje.content).strip()
            if texto:
                informe = texto
                break
    if not informe:
        print("Aviso: el agente no devolvió texto para el informe.", file=sys.stderr)

    # Comprobación con código: solo entran en el .bib los DOI que dieron las herramientas.
    citas = extraer_citas(informe)
    permitidos = set(registro.articulos)
    invalidas = [doi for doi in citas if doi not in permitidos]
    biblioteca = Biblioteca(registro.articulos[doi] for doi in citas if doi in permitidos)
    avisos = list(registro.avisos)
    if invalidas:
        avisos.append(
            "Citas sin respaldo de las herramientas: "
            + ", ".join(invalidas)
            + ". No se han incluido en el BibTeX."
        )
    if not citas:
        avisos.append("El informe no contiene citas con DOI.")
    print(
        f"> verificar_citas   {len(biblioteca)} citas válidas"
        + (f", {len(invalidas)} inválidas" if invalidas else "")
    )
    _guardar_revision(args, informe, biblioteca, avisos)
    return 0


def _revisar_flujo(args: argparse.Namespace) -> int:
    """Ejecuta el flujo de pasos fijos y guarda informe y BibTeX de lo citado."""
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
    _guardar_revision(
        args,
        resultado.get("informe", ""),
        biblioteca_de_citas(resultado),
        resultado.get("avisos", []),
    )
    return 0


def _guardar_revision(
    args: argparse.Namespace, informe: str, citas: Biblioteca, avisos: Iterable[str]
) -> None:
    """Escribe los dos archivos con el mismo formato en ambos modos."""
    Path(args.informe).write_text(informe, encoding="utf-8")
    citas.exportar_bibtex(args.bibtex)
    for aviso in avisos:
        print(f"Aviso: {aviso}", file=sys.stderr)
    sufijo = "" if len(citas) == 1 else "s"
    print(f"Informe: {args.informe}")
    print(f"BibTeX:  {args.bibtex} ({len(citas)} artículo{sufijo})")


def _revisar(args: argparse.Namespace) -> int:
    """Valida las opciones comunes y delega en el modo elegido."""
    if args.informe.resolve() == args.bibtex.resolve():
        raise ValueError("el informe y el archivo BibTeX deben ser distintos")
    if args.aprobar and args.modo != "agente":
        print("Error: --aprobar solo se usa con --modo agente.", file=sys.stderr)
        return 1
    return _revisar_agente(args) if args.modo == "agente" else _revisar_flujo(args)


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
