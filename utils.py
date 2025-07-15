import re
import datetime as dt
from dateutil import parser

def parse_file_date(name: str) -> dt.datetime | None:
    """
    Bardziej elastyczna funkcja do parsowania daty z nazwy pliku.
    Obsługuje formaty takie jak:
    - YYYY-MM-DD_HH-MM-SS.json
    - YYYY-MM-DD_HH-MM.json
    - YYYY-MM-DD HH_MM.json
    - I inne wariacje, które `dateutil.parser` może zrozumieć.
    """
    stem = name.rsplit('.', 1)[0] # Usuń rozszerzenie .json
    
    # Zastąp znaki, aby ułatwić parsowanie
    normalized_stem = stem.replace("_", ":")
    
    try:
        # Użyj dateutil.parser, który jest bardzo elastyczny
        return parser.parse(normalized_stem)
    except (parser.ParserError, ValueError):
        # Jeśli powyższe zawiedzie, spróbuj ręcznego parsowania dla specyficznych formatów
        # np. YYYY-MM-DD HH_MM
        try:
             # Usuwa myslnik i podkreslnik
            return dt.datetime.strptime(stem, "%Y-%m-%d %H_%M")
        except ValueError:
            pass
        try:
            # Usuwa podkreslnik i myslnik
            return dt.datetime.strptime(stem, "%Y-%m-%d_%H-%M")
        except ValueError:
            pass

        # Jeśli wszystko inne zawiedzie, zaloguj błąd i zwróć None
        # logging.warning(f"Nie udało się sparsować daty z nazwy pliku: {name}")
        return None


def pretty_usd(n: float) -> str:
    """Formatuje liczbę jako walutę USD w skróconej formie (np. $1.23M, $45K)."""
    if not isinstance(n, (int, float)):
        return "$0"
        
    sign = "-" if n < 0 else ""
    n = abs(n)
    
    if n >= 1_000_000_000:
        return f"{sign}${n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{sign}${n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{sign}${n/1_000:.1f}K"
    return f"{sign}${n:.2f}"

