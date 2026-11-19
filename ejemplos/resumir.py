<<<<<<< HEAD
"""Busca tres artículos y los resume con un modelo de lenguaje.

Uso: ``uv run python ejemplos/resumir.py``

Cambia `CONSULTA` y `PREGUNTA` por tu tema. Necesitas `LITMAR_MODELO` y la clave
del proveedor en el `.env` (ver `.env.example`). Solo se envían datos públicos.
"""

from __future__ import annotations

from dotenv import find_dotenv, load_dotenv

from litmar import crear_modelo, resumir
from litmar.busqueda import buscar_en_fuentes
from litmar.configuracion import nombre_fuente

# CONSULTA = "Posidonia oceanica blue carbon"
# PREGUNTA = "¿Qué papel tiene la posidonia en el almacenamiento de carbono?"
# # La CLI convierte los ids con nombre_fuente: "openalex" → "OpenAlex".
# # buscar_en_fuentes espera los nombres canónicos, no los ids del --fuente.
# FUENTES = tuple(map(nombre_fuente, ("openalex", "europepmc")))
# NUM_ARTICULOS = 3
# CONSULTA = "Ruido marino en hidrófonos"
# PREGUNTA = "¿Cómo demostrar que los delfines detectados en un sólo hidrófono reciben el mismo ruido antropogénico que recibimos en el hidrófono?"  # noqa: E501
# FUENTES = tuple(map(nombre_fuente, ("openalex", "europepmc")))
# NUM_ARTICULOS = 3
CONSULTA = "Espectrogramas de ruido marino en hidrófonos"
PREGUNTA = "¿Hay artículos que hablen de cómo se deben realizar los espectrogramas de forma estándard para mediciones long-term?"  # noqa: E501
FUENTES = tuple(map(nombre_fuente, ("openalex", "europepmc")))
NUM_ARTICULOS = 3


def main() -> None:
    """Busca, resume e imprime los resultados; la CLI no carga el `.env` por nosotros."""
    load_dotenv(find_dotenv(usecwd=True))

    try:
        modelo = crear_modelo()
    except ValueError as exc:
        raise SystemExit(f"No se pudo crear el modelo: {exc}") from exc

    resultado = buscar_en_fuentes(CONSULTA, FUENTES, n=NUM_ARTICULOS)
    for error in resultado.errors:
        print(f"Aviso: {error}")

    articulos = list(resultado.library)[:NUM_ARTICULOS]
    if not articulos:
        print("No se encontraron artículos; prueba otra consulta.")
        return

    numero = len(articulos)
    sufijo = "" if numero == 1 else "s"
    print(f"Resumen de {numero} artículo{sufijo} para: {PREGUNTA}\n")
    for articulo in articulos:
        print("=" * 72)
        print(f"{articulo.short_citation} — {articulo.title}")
        print(f"DOI: https://doi.org/{articulo.doi}")
        resumen = resumir(articulo, PREGUNTA, modelo)
        if resumen is None:
            print("Sin resumen: el artículo no tiene abstract; no se llama al modelo.")
            continue
        print(f"Objetivo:     {resumen.objetivo}")
        print(f"Método:       {resumen.metodo}")
        print(f"Hallazgos:    {resumen.hallazgos}")
        print(f"Relevancia:   {resumen.relevancia}/5")
        print(f"Limitaciones: {resumen.limitaciones}")
        print()


if __name__ == "__main__":
    main()
=======
"""Práctica 1 de la Clase 2: busca 3 artículos y resume cada uno con resumir().

Ejecútalo desde la raíz del proyecto:

    uv run python ejemplos/resumir.py

Necesita LITMAR_MODELO y la clave de su proveedor en el .env (mira .env.example).
Cambia TEMA y PREGUNTA por los de tu investigación, y LITMAR_MODELO en el .env
para comparar modelos. Abre el DOI de un artículo y compara su resumen original
con lo que ha escrito el modelo: ¿los hallazgos son fieles? ¿Ha inventado algo?
"""

from dotenv import load_dotenv

from litmar.configuracion import crear_fuente
from litmar.llm import ErrorDeConfiguracion, crear_modelo
from litmar.resumen import resumir

TEMA = "ocean acidification"
PREGUNTA = "¿Cómo afecta la acidificación del océano a los organismos marinos?"
FUENTE = "OpenAlex"
N = 3


def buscar_con_resumen(tema: str, n: int) -> list:
    """Los `n` primeros artículos de `tema` que tienen resumen.

    Pide más de los necesarios porque algunos llegan sin resumen, y sin resumen
    resumir() no tiene nada que resumir.
    """
    with crear_fuente(FUENTE) as fuente:
        articulos = fuente.buscar(tema, n=n * 4)
    return [a for a in articulos if a.abstract.strip()][:n]


def mostrar(articulo, resumen) -> None:
    print(f"\n{'=' * 78}")
    print(f"{articulo.short_citation}. {articulo.title}")
    print(f"https://doi.org/{articulo.doi}")
    print(f"Relevancia para la pregunta: {resumen.relevance}/5")
    print(f"Objetivo:     {resumen.objective}")
    print(f"Método:       {resumen.method}")
    print("Hallazgos:")
    for hallazgo in resumen.findings:
        print(f"  - {hallazgo}")
    print(f"Limitaciones: {resumen.limitations}")


def main() -> int:
    load_dotenv()  # el comando `litmar` lo hace solo; un script propio, no
    try:
        modelo = crear_modelo()
    except ErrorDeConfiguracion as error:
        print(f"Error de configuración: {error}")
        return 1

    articulos = buscar_con_resumen(TEMA, N)
    print(f"Pregunta: {PREGUNTA}")
    print(f"{len(articulos)} artículos de {FUENTE} sobre «{TEMA}».")

    for articulo in articulos:
        try:
            resumen = resumir(articulo, PREGUNTA, modelo)
        except Exception as error:  # p. ej. un 429 del plan gratuito: seguimos con el resto
            print(f"\nNo se pudo resumir {articulo.doi}: {type(error).__name__}: {error}")
            continue
        mostrar(articulo, resumen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
>>>>>>> upstream/main
