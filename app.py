import logging
import os
import json
import datetime as dt
from flask import Flask, Blueprint, jsonify, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

import core
from utils import parse_file_date

# --- Konfiguracja Aplikacji ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False

# --- Warstwa Serwisowa (Logika Biznesowa) ---
class DataService:
    """Zarządza dostępem do danych i ich cache'owaniem."""
    def __init__(self):
        self._cache = {}

    def _read_snapshot(self, filepath):
        """Wczytuje plik JSON i cache'uje jego zawartość."""
        if filepath in self._cache:
            return self._cache[filepath]
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._cache[filepath] = data
                return data
        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Could not read or parse {filepath}: {e}")
            return None

    def get_all_snapshots_meta(self):
        """Zwraca posortowaną listę metadanych o dostępnych snapshotach."""
        snapshots = [
            {"filename": p.name, "date": parsed_date.isoformat()}
            for p in core.DATA_DIR.glob("*.json")
            if (parsed_date := parse_file_date(p.name)) is not None
        ]
        return sorted(snapshots, key=lambda item: item["date"], reverse=True)

    def get_report_data(self, start_file, end_file, min_tvl, max_tvl, top_n):
        """Generuje dane raportu, przekazując dynamiczne parametry do core."""
        all_snapshots_meta = self.get_all_snapshots_meta()
        if not all_snapshots_meta:
            raise FileNotFoundError("Brak jakichkolwiek snapshotów w katalogu 'data'.")

        start_fp = core.DATA_DIR / start_file
        end_fp = core.DATA_DIR / end_file
        if not start_fp.exists() or not end_fp.exists():
            raise FileNotFoundError("Jeden z wybranych plików snapshotu nie istnieje.")
        
        start_dt = parse_file_date(start_fp.name)
        end_dt = parse_file_date(end_fp.name)
        start_data = self._read_snapshot(start_fp)
        end_data = self._read_snapshot(end_fp)

        if start_data is None or end_data is None:
            raise ValueError("Nie można było wczytać danych z plików snapshotu.")

        return core.generate_report_data(
            start_data, end_data, start_dt, end_dt, 
            min_tvl=min_tvl, max_tvl=max_tvl, top_n=top_n
        )

    def get_stats(self):
        """Generuje globalne statystyki dla najnowszego snapshotu."""
        latest_snapshot_meta = self.get_all_snapshots_meta()
        if not latest_snapshot_meta:
            return core.generate_global_stats(None, None)

        latest_fp = core.DATA_DIR / latest_snapshot_meta[0]['filename']
        latest_data = self._read_snapshot(latest_fp)
        
        previous_data = None
        if len(latest_snapshot_meta) > 1:
            previous_fp = core.DATA_DIR / latest_snapshot_meta[1]['filename']
            previous_data = self._read_snapshot(previous_fp)
        
        return core.generate_global_stats(latest_data, previous_data)

# --- Inicjalizacja Serwisu i Harmonogramu ---
data_service = DataService()

try:
    scheduler = BackgroundScheduler(timezone="Europe/Warsaw", daemon=True)
    scheduler.add_job(core.run_sync, CronTrigger(hour=4, minute=5), id="daily_sync")
    scheduler.start()
    logging.info("Harmonogram synchronizacji został uruchomiony (codziennie o 4:05).")
except Exception as e:
    logging.error(f"Nie udało się uruchomić harmonogramu: {e}")

# --- API Endpoints ---
api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route("/report")
def get_report():
    """Zwraca dane porównawcze na podstawie dynamicznych parametrów."""
    try:
        # Odczytanie parametrów z zapytania
        start_file = request.args.get('start_file')
        end_file = request.args.get('end_file')
        
        # Konwersja parametrów z zapewnieniem wartości domyślnych i obsługą błędów
        min_tvl = int(request.args.get('min_tvl', 0))
        top_n_str = request.args.get('top_n')
        top_n = int(top_n_str) if top_n_str and top_n_str.isdigit() else None
        
        max_tvl_str = request.args.get('max_tvl')
        max_tvl = int(max_tvl_str) if max_tvl_str and max_tvl_str.isdigit() else None

        if not start_file or not end_file:
            return jsonify({"error": "Brakujące parametry: start_file i end_file są wymagane."}), 400

        report_data = data_service.get_report_data(start_file, end_file, min_tvl, max_tvl, top_n)
        return jsonify(report_data)
    except (FileNotFoundError, ValueError) as e:
        logging.warning(f"Błąd generowania raportu: {e}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Nieoczekiwany błąd w /api/report: {e}", exc_info=True)
        return jsonify({"error": "Wystąpił wewnętrzny błąd serwera."}), 500

@api_bp.route("/snapshots")
def list_snapshots():
    return jsonify(data_service.get_all_snapshots_meta())

@api_bp.route("/sync", methods=['POST'])
def trigger_sync():
    try:
        core.run_sync()
        return jsonify(status="ok", message="Synchronizacja danych zakończona pomyślnie."), 200
    except Exception as e:
        logging.error(f"Błąd podczas ręcznej synchronizacji: {e}", exc_info=True)
        return jsonify(status="error", message=f"Wystąpił błąd: {e}"), 500

@api_bp.route("/stats")
def get_global_stats():
    try:
        return jsonify(data_service.get_stats())
    except Exception as e:
        logging.error(f"Błąd w /api/stats: {e}", exc_info=True)
        return jsonify({"error": "Wystąpił wewnętrzny błąd serwera."}), 500

# --- Widoki (Frontend) ---
views_bp = Blueprint('views', __name__)

@views_bp.route("/")
def index():
    return render_template("dashboard.html")

# Rejestracja Blueprints
app.register_blueprint(api_bp)
app.register_blueprint(views_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
