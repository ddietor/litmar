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
