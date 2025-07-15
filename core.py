import os
import json
import datetime as dt
import logging
import pathlib
import requests
from utils import parse_file_date, pretty_usd

# --- Stałe i Konfiguracja ---
DATA_DIR = pathlib.Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(exist_ok=True)

LLAMA_URL = "https://api.llama.fi/protocols"
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")

# Zaktualizowana lista kategorii zgodnie z prośbą
KEEP_CATEGORIES = {
    'lending', 'options', 'rwa lending', 'cdp', 'derivatives', 
    'yield aggregator', 'yield', 'dexs', 'algo-stables', 'anchor btc', 
    'indexes', 'leveraged farming', 'liquid restaking', 'liquid staking', 
    'liquidity manager'
}
DIFF_THRESHOLD = 2_000_000  # Minimalna zmiana TVL (w USD)

# --- Podstawowe operacje na danych ---

def fetch_snapshot() -> list:
    """Pobiera aktualne dane o protokołach z DeFiLlama."""
    try:
        r = requests.get(LLAMA_URL, timeout=20)
        r.raise_for_status()
        logging.info("Pomyślnie pobrano dane z DeFiLlama API.")
        return r.json()
    except requests.RequestException as e:
        logging.error(f"Błąd podczas pobierania danych z DeFiLlama: {e}")
        raise

def save_snapshot(payload: list) -> pathlib.Path:
    """Zapisuje pobrane dane do pliku JSON z sygnaturą czasową."""
    ts = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    fp = DATA_DIR / f"{ts}.json"
    try:
        fp.write_text(json.dumps(payload, separators=(",", ":")))
        logging.info(f"Zapisano snapshot -> {fp.name}")
        return fp
    except IOError as e:
        logging.error(f"Błąd zapisu do pliku {fp}: {e}")
        raise

def _get_all_snapshots():
    """Zwraca listę posortowanych snapshotów ( кортеж: ścieżka, data)."""
    snapshots = [
        (p, parsed_date)
        for p in DATA_DIR.glob("*.json")
        if (parsed_date := parse_file_date(p.name)) is not None
    ]
    return sorted(snapshots, key=lambda item: item[1], reverse=True)

def pick_week_old(latest_ts: dt.datetime):
    """Wybiera snapshot sprzed około 7 dni."""
    candidates = []
    target_date = latest_ts - dt.timedelta(days=7)
    for fp, d in _get_all_snapshots():
        if dt.timedelta(days=6) <= (latest_ts - d) <= dt.timedelta(days=8):
             candidates.append((abs(d - target_date), fp))
    if not candidates:
        return None
    return min(candidates, key=lambda t: t[0])[1]

# --- Logika porównawcza i generowanie raportów ---

def compare_snapshots(start_data: list, end_data: list) -> dict:
    """
    Porównuje dwa snapshoty i zwraca słownik ze zmianami i nowymi protokołami.
    """
    filt = lambda p: p.get("category", "").lower() in KEEP_CATEGORIES and "tvl" in p
    
    start_map = {p["id"]: p for p in start_data if filt(p)}
    end_map = {p["id"]: p for p in end_data if filt(p)}

    changes = []
    new_protocols = []

    for end_id, end_protocol in end_map.items():
        start_protocol = start_map.get(end_id)
        
        try:
            current_tvl = float(end_protocol["tvl"])
        except (ValueError, TypeError):
            continue # Pomiń, jeśli TVL jest nieprawidłowy

        if start_protocol:
            # Protokół istniał - oblicz zmianę
            try:
                start_tvl = float(start_protocol.get("tvl", 0))
                if start_tvl == 0: continue

                diff = current_tvl - start_tvl
                pct = (diff / start_tvl) * 100 if start_tvl else 0
                
                changes.append({
                    "name": end_protocol.get("name"),
                    "slug": end_protocol.get("slug"),
                    "category": end_protocol.get("category"),
                    "diff": diff,
                    "pct": pct,
                    "tvl": current_tvl,
                    "logo": end_protocol.get("logo")
                })
            except (ValueError, TypeError):
                continue
        else:
            # Nowy protokół
            new_protocols.append({
                "name": end_protocol.get("name"),
                "slug": end_protocol.get("slug"),
                "category": end_protocol.get("category"),
                "tvl": current_tvl,
                "logo": end_protocol.get("logo")
            })

    return {"changes": changes, "new_protocols": new_protocols}


def generate_report_data(start_data: list, end_data: list, start_date: dt.datetime, end_date: dt.datetime) -> dict:
    """Tworzy ustrukturyzowane dane raportu dla API na podstawie porównania."""
    comparison_result = compare_snapshots(start_data, end_data)
    
    all_changes = comparison_result["changes"]
    
    # Filtrujemy tylko wzrosty
    increases = [c for c in all_changes if c["diff"] > 0]
    
    # Sortowanie
    top_increases_abs = sorted(increases, key=lambda c: c["diff"], reverse=True)
    top_increases_pct = sorted(increases, key=lambda c: c["pct"], reverse=True)
    new_protocols_sorted = sorted(comparison_result["new_protocols"], key=lambda p: p["tvl"], reverse=True)

    return {
        "reportDate": end_date.isoformat(),
        "comparisonDate": start_date.isoformat(),
        "top_increases_abs": top_increases_abs,
        "top_increases_pct": top_increases_pct,
        "new_protocols": new_protocols_sorted
    }

def build_slack_message(report_data: dict) -> str:
    """Tworzy sformatowaną wiadomość na Slacka z nowych danych raportu."""
    date_str = dt.datetime.fromisoformat(report_data['reportDate']).strftime('%d-%m-%Y')
    lines = [f":bar_chart: *DeFiLlama Weekly Report – {date_str}*"]

    # Wzrosty absolutne
    if report_data['top_increases_abs']:
        lines.append("\n*:chart_with_upwards_trend: Top 5 Increases (absolute)*")
        for c in report_data['top_increases_abs'][:5]:
            pct_str = f"({c['pct']:+.1f}%)"
            lines.append(f"• *{c['name']}* ({c['category']}): `{pretty_usd(c['diff'])}` {pct_str}")

    # Wzrosty procentowe
    if report_data['top_increases_pct']:
        lines.append("\n*:rocket: Top 5 Increases (%)*")
        for c in report_data['top_increases_pct'][:5]:
            pct_str = f"({c['pct']:+.1f}%)"
            lines.append(f"• *{c['name']}* ({c['category']}): `{pretty_usd(c['diff'])}` {pct_str}")

    # Nowe protokoły
    if report_data['new_protocols']:
        lines.append(f"\n*:sparkles: New Protocols ({len(report_data['new_protocols'])})*")
        for p in report_data['new_protocols'][:5]:
            lines.append(f"• *{p['name']}* ({p['category']}): `{pretty_usd(p['tvl'])}`")

    if len(lines) == 1:
        return f":zzz: DeFiLlama Weekly Report – {date_str} – No significant movements."

    return "\n".join(lines)

# --- Główna funkcja wykonawcza ---

def run():
    """Główna funkcja, która pobiera dane, porównuje i wysyła raport na Slacka."""
    logging.info("Rozpoczynam generowanie raportu tygodniowego...")
    try:
        # Pobieranie i zapisywanie najnowszych danych
        latest_data = fetch_snapshot()
        latest_fp = save_snapshot(latest_data)
        latest_dt = parse_file_date(latest_fp.name)
        if not latest_dt:
            logging.error("Nie udało się sparsować daty z najnowszego pliku. Przerywam.")
            return

        # Wybieranie danych sprzed tygodnia
        week_fp = pick_week_old(latest_dt)
        if not week_fp:
            logging.warning("Brak snapshotu sprzed ~7 dni – raport Slack pominięty.")
            return

        logging.info(f"Porównuję {latest_fp.name} z {week_fp.name} dla raportu Slack.")
        week_data = json.loads(week_fp.read_text())
        week_dt = parse_file_date(week_fp.name)

        # Generowanie danych i wiadomości
        report_data = generate_report_data(week_data, latest_data, week_dt, latest_dt)
        message = build_slack_message(report_data)
        
        send_to_slack(message)
        logging.info("Zakończono generowanie raportu tygodniowego.")
    except Exception as e:
        logging.critical(f"Krytyczny błąd w funkcji `run`: {e}", exc_info=True)

def send_to_slack(text: str):
    """Wysyła wiadomość na skonfigurowany kanał Slacka."""
    if not SLACK_WEBHOOK:
        logging.warning("SLACK_WEBHOOK_URL nie jest ustawiony – pomijam wysyłkę na Slacka.")
        print("--- SLACK MESSAGE PREVIEW ---\n" + text + "\n-----------------------------")
        return
    try:
        r = requests.post(SLACK_WEBHOOK, json={"text": text, "mrkdwn": True}, timeout=10)
        r.raise_for_status()
        logging.info("Wysłano raport na Slacka.")
    except requests.RequestException as e:
        logging.error(f"Błąd podczas wysyłania na Slacka: {e}")
