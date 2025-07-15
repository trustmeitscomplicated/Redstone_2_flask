import logging
import os
import json
import datetime as dt
import pathlib
from flask import Flask, jsonify, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
import core
from utils import parse_file_date

# --- Konfiguracja ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder="static", template_folder="templates")

# --- Harmonogram zadań ---
try:
    sched = BackgroundScheduler(timezone="Europe/Warsaw", daemon=True)
    sched.add_job(core.run, CronTrigger(day_of_week="fri", hour=6, minute=30), id="weekly_job")
    sched.start()
    logging.info("Harmonogram zadań został uruchomiony.")
except Exception as e:
    logging.error(f"Nie udało się uruchomić harmonogramu: {e}")


# --- Główne widoki (Routes) ---
@app.route("/")
def index():
    """Główny widok aplikacji - dashboard."""
    return render_template("dashboard.html")

@app.route("/run-manual")
def run_now():
    """Endpoint do ręcznego uruchomienia generowania raportu na Slacka."""
    try:
        core.run()
        return jsonify(status="ok", message="Raport został wygenerowany i wysłany na Slacka."), 200
    except Exception as e:
        logging.error(f"Błąd podczas ręcznego uruchamiania: {e}")
        return jsonify(status="error", message=str(e)), 500

# --- API ---

@app.route("/api/snapshots")
def api_get_snapshots():
    """Zwraca listę dostępnych snapshotów (dat) do wyboru na froncie."""
    try:
        snapshots = core._get_all_snapshots() # Pobiera posortowane (ścieżka, data)
        # Formatujemy dane dla frontendu
        snapshot_list = [
            {"filename": fp.name, "date": date.isoformat()}
            for fp, date in snapshots
        ]
        return jsonify(snapshot_list)
    except Exception as e:
        logging.error(f"Błąd w /api/snapshots: {e}")
        return jsonify({"error": "Nie udało się wczytać listy snapshotów."}), 500


@app.route("/api/report")
def api_report():
    """
    Główne API do generowania raportów.
    - Domyślnie: porównuje najnowszy plik z plikiem sprzed ~7 dni.
    - Z parametrami: porównuje dwa wybrane pliki.
    np. /api/report?start_file=2025-07-01_10-00-00.json&end_file=2025-07-08_10-00-00.json
    """
    try:
        start_file = request.args.get('start_file')
        end_file = request.args.get('end_file')

        all_snapshots = core._get_all_snapshots()
        if not all_snapshots:
            return jsonify({"error": "Brak plików snapshot w katalogu 'data'."}), 404

        if start_file and end_file:
            # Tryb ręcznego porównania
            start_fp = core.DATA_DIR / start_file
            end_fp = core.DATA_DIR / end_file
            if not start_fp.exists() or not end_fp.exists():
                return jsonify({"error": "Jeden z wybranych plików nie istnieje."}), 404
            
            start_data = json.loads(start_fp.read_text())
            end_data = json.loads(end_fp.read_text())
            start_dt = parse_file_date(start_fp.name)
            end_dt = parse_file_date(end_fp.name)
        else:
            # Tryb domyślny (tygodniowy)
            end_fp, end_dt = all_snapshots[0]
            start_fp = core.pick_week_old(end_dt)
            if not start_fp:
                return jsonify({"error": "Nie znaleziono snapshotu sprzed około 7 dni do porównania."}), 404
            
            end_data = json.loads(end_fp.read_text())
            start_data = json.loads(start_fp.read_text())
            start_dt = parse_file_date(start_fp.name)

        # Wygeneruj dane raportu
        report_data = core.generate_report_data(start_data, end_data, start_dt, end_dt)
        return jsonify(report_data)

    except Exception as e:
        logging.error(f"Błąd w /api/report: {e}", exc_info=True)
        return jsonify({"error": "Wystąpił wewnętrzny błąd serwera."}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
