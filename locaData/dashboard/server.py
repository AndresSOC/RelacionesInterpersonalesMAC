import sys
import threading
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "python"))

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO
from sqlalchemy import create_engine, text
import config

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
engine = create_engine(config.DATABASE_URL)
pipeline_lock = threading.Lock()


@app.route("/")
def index():
    return render_template("dashboard.html", api_key=config.API_KEY)


@app.route("/api/coverage")
def api_coverage():
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT lat, lon, radius_m FROM coverage_cells WHERE status = 'done'")
        ).fetchall()
    return jsonify([
        {"lat": float(r[0]), "lon": float(r[1]), "radius_m": int(r[2])}
        for r in rows
    ])


@app.route("/api/heatmap")
def api_heatmap():
    min_rating = request.args.get("min_rating", type=float, default=0)
    min_reviews = request.args.get("min_reviews", type=int, default=0)
    category = request.args.get("category", type=str, default="")

    conditions = ["latitud IS NOT NULL", "longitud IS NOT NULL"]
    params = {}

    if min_rating > 0:
        conditions.append("rating >= :min_rating")
        params["min_rating"] = min_rating
    if min_reviews > 0:
        conditions.append("user_ratings_total >= :min_reviews")
        params["min_reviews"] = min_reviews
    if category:
        conditions.append(
            "place_id IN (SELECT place_id FROM place_categories WHERE category = :cat)"
        )
        params["cat"] = category

    sql = "SELECT latitud, longitud FROM places WHERE " + " AND ".join(conditions)
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return jsonify([
        {"lat": float(r[0]), "lng": float(r[1])}
        for r in rows
    ])


@app.route("/api/search")
def api_search():
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT business_name, latitud, longitud "
                "FROM places "
                "WHERE business_name IS NOT NULL AND latitud IS NOT NULL AND longitud IS NOT NULL "
                "ORDER BY user_ratings_total DESC NULLS LAST "
                "LIMIT 600"
            )
        ).fetchall()
    return jsonify([
        {"name": r[0], "lat": float(r[1]), "lng": float(r[2])}
        for r in rows
    ])


@app.route("/api/categories")
def api_categories():
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT category FROM place_categories ORDER BY category")
        ).fetchall()
    return jsonify([r[0] for r in rows])


@app.route("/api/status")
def api_status():
    with engine.connect() as conn:
        active = conn.execute(
            text("SELECT COUNT(*) FROM fetch_sessions WHERE status = 'running'")
        ).fetchone()[0]
        total_places = conn.execute(
            text("SELECT COUNT(*) FROM places")
        ).fetchone()[0]
        total_cells = conn.execute(
            text("SELECT COUNT(*) FROM coverage_cells WHERE status = 'done'")
        ).fetchone()[0]
    return jsonify({
        "active": active > 0,
        "totalPlaces": total_places,
        "totalCells": total_cells,
        "radiusKm": config.AREA_CONFIG["radius_km"]
    })


@app.route("/api/expand", methods=["POST"])
def api_expand():
    data = request.get_json() or {}
    new_radius = float(data.get("radius_km", 5.0))

    if not pipeline_lock.acquire(blocking=False):
        return jsonify({"error": "Pipeline ya esta corriendo"}), 409

    config.AREA_CONFIG["radius_km"] = new_radius

    def _run():
        try:
            from pipeline import run as run_pipeline
            run_pipeline(emit=socketio.emit)
        finally:
            pipeline_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "radius_km": new_radius})


if __name__ == "__main__":
    socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=True)
