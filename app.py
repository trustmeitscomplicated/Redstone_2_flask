# ==============================================================================
# app.py - Main Application File
# ==============================================================================
# This file is the entry point for our web application. It's responsible for:
# 1. Setting up the Flask web server.
# 2. Creating a background scheduler for automatic daily tasks.
# 3. Defining the API endpoints that our frontend will communicate with.
# 4. Serving the main HTML page and the generated Markdown report.
# ==============================================================================

# --- 1. Import necessary libraries ---
import logging
import os
import json
import datetime as dt
from io import BytesIO
from flask import Flask, Blueprint, jsonify, render_template, request, send_file
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Import our own Python files.
import core
from utils import parse_file_date
# Import the Markdown report generator.
from report_generator import create_markdown_report

# --- 2. Application Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False

# --- 3. Data Service Layer ---
class DataService:
    """Manages data access and caching."""
    def __init__(self):
        self._cache = {}

    def _read_snapshot(self, filepath):
        """Reads a JSON file and caches its content."""
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
        """Returns a sorted list of metadata about available snapshots."""
        snapshots = [
            {"filename": p.name, "date": parsed_date.isoformat()}
            for p in core.DATA_DIR.glob("*.json")
            if (parsed_date := parse_file_date(p.name)) is not None
        ]
        return sorted(snapshots, key=lambda item: item["date"], reverse=True)

    def get_report_data(self, start_file, end_file, min_tvl, max_tvl, top_n):
        """Generates report data by passing dynamic parameters to the core logic."""
        all_snapshots_meta = self.get_all_snapshots_meta()
        if not all_snapshots_meta:
            raise FileNotFoundError("No data snapshots found in the 'data' directory.")

        start_fp = core.DATA_DIR / start_file
        end_fp = core.DATA_DIR / end_file
        if not start_fp.exists() or not end_fp.exists():
            raise FileNotFoundError("One of the selected snapshot files does not exist.")
        
        start_dt = parse_file_date(start_fp.name)
        end_dt = parse_file_date(end_fp.name)
        start_data = self._read_snapshot(start_fp)
        end_data = self._read_snapshot(end_fp)

        if start_data is None or end_data is None:
            raise ValueError("Could not load data from snapshot files.")

        return core.generate_report_data(
            start_data, end_data, start_dt, end_dt, 
            min_tvl=min_tvl, max_tvl=max_tvl, top_n=top_n
        )

    def get_stats(self):
        """Generates global statistics for the latest snapshot."""
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

# --- 4. Initialization of Service and Scheduler ---
data_service = DataService()

try:
    scheduler = BackgroundScheduler(timezone="Europe/Warsaw", daemon=True)
    scheduler.add_job(core.run_sync, CronTrigger(hour=4, minute=5), id="daily_sync")
    scheduler.start()
    logging.info("Background scheduler started (daily sync at 4:05 AM).")
except Exception as e:
    logging.error(f"Failed to start the scheduler: {e}")

# --- 5. API Endpoints ---
api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route("/report")
def get_report():
    """Returns comparison data based on dynamic parameters from the user."""
    try:
        start_file = request.args.get('start_file')
        end_file = request.args.get('end_file')
        min_tvl = int(request.args.get('min_tvl', 0))
        top_n_str = request.args.get('top_n')
        top_n = int(top_n_str) if top_n_str and top_n_str.isdigit() else None
        max_tvl_str = request.args.get('max_tvl')
        max_tvl = int(max_tvl_str) if max_tvl_str and max_tvl_str.isdigit() else None

        if not start_file or not end_file:
            return jsonify({"error": "Missing parameters: start_file and end_file are required."}), 400

        report_data = data_service.get_report_data(start_file, end_file, min_tvl, max_tvl, top_n)
        return jsonify(report_data)
    except (FileNotFoundError, ValueError) as e:
        logging.warning(f"Error generating report: {e}")
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Unexpected error in /api/report: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500

# --- UPDATED: Markdown Download Endpoint ---
@api_bp.route("/report/download")
def download_report():
    """Generates a Markdown report and sends it to the user for download."""
    try:
        # This part is identical to get_report, ensuring the downloaded report uses the same filters.
        start_file = request.args.get('start_file')
        end_file = request.args.get('end_file')
        min_tvl = int(request.args.get('min_tvl', 0))
        top_n_str = request.args.get('top_n')
        top_n = int(top_n_str) if top_n_str and top_n_str.isdigit() else None
        max_tvl_str = request.args.get('max_tvl')
        max_tvl = int(max_tvl_str) if max_tvl_str and max_tvl_str.isdigit() else None

        if not start_file or not end_file:
            return "Missing parameters", 400

        report_data = data_service.get_report_data(start_file, end_file, min_tvl, max_tvl, top_n)
        report_string = create_markdown_report(report_data)
        file_stream = BytesIO(report_string.encode('utf-8'))
        
        end_date_str = dt.datetime.fromisoformat(report_data['reportMetadata']['reportDate']).strftime('%Y-%m-%d')
        filename = f"DeFi_Report_{end_date_str}.md"

        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype='text/markdown'
        )
    except Exception as e:
        logging.error(f"Failed to generate Markdown report: {e}", exc_info=True)
        return "Error generating report", 500

# --- NEW: Markdown View Endpoint ---
@api_bp.route("/report/view")
def view_report():
    """
    Generates a Markdown report and returns it as text in a JSON object.
    This is for displaying the report directly on the webpage.
    """
    try:
        # This logic is identical to the other report endpoints.
        start_file = request.args.get('start_file')
        end_file = request.args.get('end_file')
        min_tvl = int(request.args.get('min_tvl', 0))
        top_n_str = request.args.get('top_n')
        top_n = int(top_n_str) if top_n_str and top_n_str.isdigit() else None
        max_tvl_str = request.args.get('max_tvl')
        max_tvl = int(max_tvl_str) if max_tvl_str and max_tvl_str.isdigit() else None

        if not start_file or not end_file:
            return jsonify({"error": "Missing parameters"}), 400

        report_data = data_service.get_report_data(start_file, end_file, min_tvl, max_tvl, top_n)
        report_string = create_markdown_report(report_data)
        
        # Return the generated Markdown text inside a JSON object.
        return jsonify({"markdown": report_string})
    except Exception as e:
        logging.error(f"Failed to generate Markdown view: {e}", exc_info=True)
        return jsonify({"error": "Error generating report view"}), 500

@api_bp.route("/snapshots")
def list_snapshots():
    return jsonify(data_service.get_all_snapshots_meta())

@api_bp.route("/sync", methods=['POST'])
def trigger_sync():
    try:
        core.run_sync()
        return jsonify(status="ok", message="Data synchronization completed successfully."), 200
    except Exception as e:
        logging.error(f"Error during manual sync: {e}", exc_info=True)
        return jsonify(status="error", message=f"An error occurred: {e}"), 500

@api_bp.route("/stats")
def get_global_stats():
    try:
        return jsonify(data_service.get_stats())
    except Exception as e:
        logging.error(f"Error in /api/stats: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500

# --- 6. Frontend Views ---
views_bp = Blueprint('views', __name__)

@views_bp.route("/")
def index():
    return render_template("dashboard.html")

# Register the blueprints with the main application.
app.register_blueprint(api_bp)
app.register_blueprint(views_bp)

# --- 7. Run the Application ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)
