import re
import datetime as dt
from dateutil import parser
import logging

def parse_file_date(name: str) -> dt.datetime | None:
    """
    Bardzo elastyczna funkcja do parsowania daty z nazwy pliku, odporna na różne separatory.
    Wykorzystuje wyrażenia regularne do znalezienia wszystkich liczb w nazwie pliku.
    """
    stem = name.rsplit('.', 1)[0]
    
    # Znajdź wszystkie sekwencje cyfr w nazwie pliku
    numbers = re.findall(r'\d+', stem)
    
    # Oczekujemy od 3 do 6 grup liczb (rok, miesiąc, dzień, opcjonalnie godzina, minuta, sekunda)
    if not (3 <= len(numbers) <= 6):
        logging.warning(f"Znaleziono nieoczekiwaną liczbę komponentów daty w '{name}'. Pomijam plik.")
        return None
        
    try:
        # Uzupełnij brakujące części (godzina, minuta, sekunda) zerami, jeśli ich nie ma
        while len(numbers) < 6:
            numbers.append('0')
            
        # Przekształć znalezione stringi na liczby całkowite
        parts = [int(n) for n in numbers]
        
        # Stwórz obiekt datetime
        return dt.datetime(year=parts[0], month=parts[1], day=parts[2], 
                           hour=parts[3], minute=parts[4], second=parts[5])
                           
    except (ValueError, IndexError) as e:
        logging.error(f"Nie udało się złożyć daty z komponentów {numbers} dla pliku '{name}'. Błąd: {e}")
        return None


def pretty_usd(n: float | int) -> str:
    """Formatuje liczbę jako walutę USD w skróconej formie (np. $1.23M, $45K)."""
    if not isinstance(n, (int, float)):
        return "$0"
        
    sign = "-" if n < 0 else ""
    n = abs(n)
    
    if n >= 1_000_000_000:
        return f"{sign}${n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{sign}${n/1_000_000:.2f}M"
    if n >= 1000:
        return f"{sign}${n/1000:.1f}K"
    return f"{sign}${n:.2f}"

def format_percentage(n: float | int) -> str:
    """Formatuje liczbę jako procent ze znakiem."""
    if not isinstance(n, (int, float)):
        return "0.0%"
    sign = "+" if n > 0 else ""
    return f"{sign}{n:.2f}%"
