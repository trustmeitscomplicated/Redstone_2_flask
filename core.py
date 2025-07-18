# ==============================================================================
# core.py - Core Business Logic
# ==============================================================================
# This file contains the "brain" of the application. It's responsible for:
# 1. Fetching data from the DeFiLlama API.
# 2. Saving and managing data snapshot files.
# 3. Comparing two snapshots to find changes, new protocols, etc.
# 4. Generating the final report data structure based on user-defined filters.
# ==============================================================================

# --- 1. Import necessary libraries ---
import os
import json
import datetime as dt
import logging
import pathlib
import requests
from utils import parse_file_date, pretty_usd

# --- 2. Constants and Configuration ---
# This defines the base directory of the project to build absolute paths.
# This makes the script work correctly regardless of where you run it from.
BASE_DIR = pathlib.Path(__file__).resolve().parent
# Defines the 'data' directory where snapshots are stored.
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
DATA_DIR.mkdir(exist_ok=True) # Create the directory if it doesn't exist.

# The URL of the DeFiLlama API we are fetching data from.
LLAMA_URL = "https://api.llama.fi/protocols"

# A predefined set of DeFi categories we are interested in.
# This acts as a base filter to exclude irrelevant protocols.
ALLOWED_CATEGORIES = {
    'lending', 'options', 'rwa lending', 'cdp', 'derivatives', 
    'yield aggregator', 'yield', 'dexs', 'algo-stables', 'anchor btc', 
    'indexes', 'leveraged farming', 'liquid restaking', 'liquid staking', 
    'liquidity manager'
}

# --- 3. Basic Data Operations ---

def fetch_snapshot() -> list:
    """
    Fetches the current protocol data from the DeFiLlama API.
    The `-> list` is a type hint, indicating this function is expected to return a list.
    """
    try:
        # Make an HTTP GET request to the API.
        r = requests.get(LLAMA_URL, timeout=30)
        # This will raise an error if the response status code is an error (like 404 or 500).
        r.raise_for_status()
        logging.info("Successfully fetched data from DeFiLlama API.")
        # Return the response content, parsed from JSON into a Python list of dictionaries.
        return r.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching data from DeFiLlama: {e}")
        raise

def save_snapshot(payload: list) -> pathlib.Path:
    """
    Saves the fetched data to a JSON file with a timestamp in its name.
    `payload: list` means this function expects a list as input.
    `-> pathlib.Path` means it's expected to return a Path object representing the new file.
    """
    # Create a timestamp string in the format YYYY-MM-DD HH_MM.
    ts = dt.datetime.now().strftime("%Y-%m-%d %H_%M")
    # Construct the full file path.
    fp = DATA_DIR / f"{ts}.json"
    try:
        # Write the data to the file. `separators` makes the file smaller.
        fp.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        logging.info(f"Snapshot saved -> {fp.name}")
        return fp
    except IOError as e:
        logging.error(f"Error writing to file {fp}: {e}")
        raise

def _get_all_snapshot_paths():
    """A helper function to get a sorted list of all snapshot file paths."""
    snapshots = [
        (p, parsed_date)
        for p in DATA_DIR.glob("*.json")
        if (parsed_date := parse_file_date(p.name)) is not None
    ]
    return sorted(snapshots, key=lambda item: item[1], reverse=True)

def pick_week_old(latest_ts: dt.datetime) -> pathlib.Path | None:
    """Selects a snapshot from approximately 7 days ago."""
    candidates = []
    target_date = latest_ts - dt.timedelta(days=7)
    for fp, d in _get_all_snapshot_paths():
        if dt.timedelta(days=6) <= (latest_ts - d) <= dt.timedelta(days=8):
             candidates.append((abs(d - target_date), fp))
    if not candidates:
        return None
    return min(candidates, key=lambda t: t[0])[1]

# --- 4. Advanced and Dynamic Comparison Logic ---

def compare_snapshots(start_data: list, end_data: list, min_tvl: int, max_tvl: int | None) -> dict:
    """
    Compares two snapshots, applying dynamic TVL filters.
    This is a core function that calculates all the differences.
    """
    if not isinstance(start_data, list) or not isinstance(end_data, list):
        return {"changes": [], "new_protocols": [], "removed_protocols": []}

    # Step 1: Filter the input data based on dynamic criteria from the user.
    def is_valid(protocol):
        category = protocol.get("category", "").lower()
        tvl = protocol.get("tvl") or 0
        
        # Check if the protocol is in an allowed category and meets the min TVL.
        if category not in ALLOWED_CATEGORIES or tvl < min_tvl:
            return False
        # Check if it exceeds the max TVL, if one is provided.
        if max_tvl is not None and tvl > max_tvl:
            return False
            
        return True

    # Convert lists to dictionaries (maps) for fast lookups by protocol ID.
    start_map = {p["id"]: p for p in start_data if isinstance(p, dict) and is_valid(p)}
    end_map = {p["id"]: p for p in end_data if isinstance(p, dict) and is_valid(p)}

    # Step 2: Calculate changes for protocols that exist in both snapshots.
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
            # This protocol exists in both snapshots, so we calculate the difference.
            start_tvl = float(start_protocol.get("tvl") or 0)
            if start_tvl > 0:
                diff_usd = current_tvl - start_tvl
                pct = (diff_usd / start_tvl) * 100
                protocol_info.update({"diff": diff_usd, "pct": pct})
                tvl_changes.append(protocol_info)
        else:
            # This protocol only exists in the end snapshot, so it's new.
            new_protocols.append(protocol_info)
            
    # Step 3: Detect protocols that were removed.
    # These are protocols that exist in the start map but not in the end map.
    removed_protocols = [p for p_id, p in start_map.items() if p_id not in end_map]

    return {
        "changes": tvl_changes, 
        "new_protocols": new_protocols, 
        "removed_protocols": removed_protocols
    }


def generate_report_data(start_data: list, end_data: list, start_date: dt.datetime, end_date: dt.datetime, 
                         min_tvl: int = 0, max_tvl: int | None = None, top_n: int | None = None) -> dict:
    """
    Creates the final report structure with dynamic ranking.
    This function takes the raw comparison data and formats it for the API response.
    """
    comparison = compare_snapshots(start_data, end_data, min_tvl, max_tvl)
    tvl_changes = comparison["changes"]

    increases = [c for c in tvl_changes if c.get("diff", 0) > 0]
    decreases = [c for c in tvl_changes if c.get("diff", 0) < 0]

    # Use `top_n` to limit the results. If it's None, return everything.
    # A "slice" is a way to select a portion of a list.
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
    """Calculates the global KPI statistics for the dashboard header."""
    if not isinstance(latest_data, list):
        return {"totalTVL": 0, "change24h": 0, "protocolCount": 0}

    # The `or 0` is a safeguard against missing 'tvl' keys or `null` values.
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

# --- 5. Main Execution Function ---

def run_sync():
    """
    The main function that downloads and saves the data.
    This is called by the scheduler and the manual sync button.
    """
    logging.info("Starting data synchronization with DeFiLlama...")
    try:
        latest_data = fetch_snapshot()
        save_snapshot(latest_data)
        logging.info("Synchronization completed successfully.")
    except Exception as e:
        logging.critical(f"A critical error occurred during synchronization: {e}", exc_info=True)
        raise
