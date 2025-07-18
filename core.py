import os
import json
import datetime as dt
import logging
import pathlib
import requests
from utils import parse_file_date, pretty_usd

# --- Stałe i Konfiguracja ---
BASE_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
DATA_DIR.mkdir(exist_ok=True)

LLAMA_URL = "https://api.llama.fi/protocols"

# Kategorie do uwzględnienia w analizie - pozostaje jako bazowy filtr
ALLOWED_CATEGORIES = {
    'lending', 'options', 'rwa lending', 'cdp', 'derivatives', 
    'yield aggregator', 'yield', 'dexs', 'algo-stables', 'anchor btc', 
    'indexes', 'leveraged farming', 'liquid restaking', 'liquid staking', 
    'liquidity manager'
}

# --- Podstawowe operacje na danych ---

def fetch_snapshot() -> list:
    try:
        r = requests.get(LLAMA_URL, timeout=30)
        r.raise_for_status()
        logging.info("Pomyślnie pobrano dane z DeFiLlama API.")
        return r.json()
    except requests.RequestException as e:
        logging.error(f"Błąd podczas pobierania danych z DeFiLlama: {e}")
        raise

def save_snapshot(payload: list) -> pathlib.Path:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H_%M")
    fp = DATA_DIR / f"{ts}.json"
    try:
        fp.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        logging.info(f"Zapisano snapshot -> {fp.name}")
        return fp
    except IOError as e:
        logging.error(f"Błąd zapisu do pliku {fp}: {e}")
        raise

def _get_all_snapshot_paths():
    snapshots = [
        (p, parsed_date)
        for p in DATA_DIR.glob("*.json")
        if (parsed_date := parse_file_date(p.name)) is not None
    ]
    return sorted(snapshots, key=lambda item: item[1], reverse=True)

def pick_week_old(latest_ts: dt.datetime) -> pathlib.Path | None:
    candidates = []
    target_date = latest_ts - dt.timedelta(days=7)
    for fp, d in _get_all_snapshot_paths():
        if dt.timedelta(days=6) <= (latest_ts - d) <= dt.timedelta(days=8):
             candidates.append((abs(d - target_date), fp))
    if not candidates:
        return None
    return min(candidates, key=lambda t: t[0])[1]

# --- NOWA, ZAAWANSOWANA I DYNAMICZNA LOGIKA PORÓWNAWCZA ---

def compare_snapshots(start_data: list, end_data: list, min_tvl: int, max_tvl: int | None) -> dict:
    """
    Porównuje dwa snapshoty, uwzględniając DYNAMICZNE filtrowanie TVL.
    """
    if not isinstance(start_data, list) or not isinstance(end_data, list):
        return {"changes": [], "new_protocols": [], "removed_protocols": []}

    # 1. Filtrowanie danych wejściowych na podstawie dynamicznych kryteriów
    def is_valid(protocol):
        category = protocol.get("category", "").lower()
        tvl = protocol.get("tvl") or 0
        
        # Sprawdzenie kategorii i dolnego progu TVL
        if category not in ALLOWED_CATEGORIES or tvl < min_tvl:
            return False
        # Sprawdzenie górnego progu TVL, jeśli został zdefiniowany
        if max_tvl is not None and tvl > max_tvl:
            return False
            
        return True

    start_map = {p["id"]: p for p in start_data if isinstance(p, dict) and is_valid(p)}
    end_map = {p["id"]: p for p in end_data if isinstance(p, dict) and is_valid(p)}

    # 2. Obliczanie zmian
    tvl_changes = []
    new_protocols = []
    for end_id, end_protocol in end_map.items():
        current_tvl = float(end_protocol.get("tvl") or 0)
        
        protocol_info = {
            "name": end_protocol.get("name"), "slug": end_protocol.get("slug"),
            "category": end_protocol.get("category", "N/A"), "tvl": current_tvl,
            "logo": end_protocol.get("logo"), "url": end_protocol.get("url"),
            "chains": end_protocol.get("chains", [])
        }

        if start_protocol := start_map.get(end_id):
            start_tvl = float(start_protocol.get("tvl") or 0)
            if start_tvl > 0:
                diff_usd = current_tvl - start_tvl
                pct = (diff_usd / start_tvl) * 100
                protocol_info.update({"diff": diff_usd, "pct": pct})
                tvl_changes.append(protocol_info)
        else:
            new_protocols.append(protocol_info)
            
    # 3. Wykrywanie usuniętych protokołów
    removed_protocols = [p for p_id, p in start_map.items() if p_id not in end_map]

    return {
        "changes": tvl_changes, 
        "new_protocols": new_protocols, 
        "removed_protocols": removed_protocols
    }


def generate_report_data(start_data: list, end_data: list, start_date: dt.datetime, end_date: dt.datetime, 
                         min_tvl: int = 0, max_tvl: int | None = None, top_n: int | None = None) -> dict:
    """
    Tworzy finalną strukturę raportu z DYNAMICZNYM rankingiem.
    """
    comparison = compare_snapshots(start_data, end_data, min_tvl, max_tvl)
    tvl_changes = comparison["changes"]

    increases = [c for c in tvl_changes if c.get("diff", 0) > 0]
    decreases = [c for c in tvl_changes if c.get("diff", 0) < 0]

    # Użyj `top_n` do ograniczenia wyników. Jeśli None, zwróć wszystko.
    slicer = slice(None) if top_n is None else slice(top_n)
    
    return {
        "reportMetadata": {
            "reportDate": end_date.isoformat(),
            "comparisonDate": start_date.isoformat(),
            "protocolCount": len(end_data) if isinstance(end_data, list) else 0,
            "minTvlSet": min_tvl,
            "maxTvlSet": max_tvl,
            "topNSet": top_n,
            "categories": list(ALLOWED_CATEGORIES)
        },
        "topIncreasesPct": sorted(increases, key=lambda c: c.get("pct", 0), reverse=True)[slicer],
        "topIncreasesAbs": sorted(increases, key=lambda c: c.get("diff", 0), reverse=True)[slicer],
        "topDecreasesPct": sorted(decreases, key=lambda c: c.get("pct", 0))[slicer],
        "topDecreasesAbs": sorted(decreases, key=lambda c: c.get("diff", 0))[slicer],
        "newProtocols": sorted(comparison["new_protocols"], key=lambda p: p.get("tvl", 0), reverse=True)[slicer],
        "removedProtocols": sorted(comparison["removed_protocols"], key=lambda p: p.get("tvl", 0), reverse=True)[slicer],
        "allProtocols": sorted(tvl_changes + comparison["new_protocols"], key=lambda p: p.get("tvl", 0), reverse=True)
    }

def generate_global_stats(latest_data: list | None, previous_data: list | None) -> dict:
    """Oblicza globalne statystyki dla panelu KPI."""
    if not isinstance(latest_data, list):
        return {"totalTVL": 0, "change24h": 0, "protocolCount": 0}

    latest_tvl = sum(p.get('tvl') or 0 for p in latest_data if isinstance(p, dict))
    protocol_count = len(latest_data)
    
    change_24h = 0
    if isinstance(previous_data, list):
        previous_tvl = sum(p.get('tvl') or 0 for p in previous_data if isinstance(p, dict))
        if previous_tvl > 0:
            change_24h = ((latest_tvl - previous_tvl) / previous_tvl) * 100

    return {
        "totalTVL": latest_tvl,
        "change24h": change_24h,
        "protocolCount": protocol_count
    }

# --- Funkcja wykonawcza ---

def run_sync():
    """Główna funkcja, która pobiera i zapisuje dane."""
    logging.info("Rozpoczynam synchronizację danych z DeFiLlama...")
    try:
        latest_data = fetch_snapshot()
        save_snapshot(latest_data)
        logging.info("Synchronizacja zakończona pomyślnie.")
    except Exception as e:
        logging.critical(f"Krytyczny błąd podczas synchronizacji: {e}", exc_info=True)
        raise
