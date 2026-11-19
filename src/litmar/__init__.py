from litmar.articulo import Articulo
from litmar.biblioteca import Biblioteca

__all__ = ["Articulo", "Biblioteca", "main"]


def main() -> None:
    from dotenv import find_dotenv, load_dotenv

    from litmar.cli import main as ejecutar

    # Lee el .env del directorio actual (o de uno superior). Las variables que
    # ya estén definidas en el entorno tienen prioridad.
    load_dotenv(find_dotenv(usecwd=True))

    raise SystemExit(ejecutar())
