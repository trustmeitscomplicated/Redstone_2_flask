import requests
import json
from datetime import datetime
import pathlib
import os
import logging

# --- Konfiguracja ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ustawienie ścieżki do katalogu 'data' w sposób absolutny
BASE_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LLAMA_URL = "https://api.llama.fi/protocols"

# --- Główna funkcja ---
def download_snapshot():
    """Pobiera i zapisuje aktualny snapshot danych z DeFiLlama."""
    logging.info(f"Pobieranie danych z {LLAMA_URL}...")
    try:
        response = requests.get(LLAMA_URL, timeout=30)
        response.raise_for_status()  # Rzuci wyjątkiem dla kodów błędu (4xx, 5xx)
        data = response.json()
        logging.info("Dane zostały pomyślnie pobrane.")

        # Generowanie nazwy pliku z precyzyjną sygnaturą czasową
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = DATA_DIR / f"{timestamp}.json"

        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(data, file, separators=(",", ":"), ensure_ascii=False)
        
        logging.info(f"Snapshot został pomyślnie zapisany w pliku: {filepath}")

    except requests.RequestException as e:
        logging.error(f"Błąd sieciowy podczas pobierania danych: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"Błąd podczas parsowania odpowiedzi JSON: {e}")
    except IOError as e:
        logging.error(f"Błąd zapisu do pliku: {e}")
    except Exception as e:
        logging.error(f"Wystąpił nieoczekiwany błąd: {e}")


if __name__ == "__main__":
    download_snapshot()
