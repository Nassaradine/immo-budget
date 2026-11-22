"""Serveur Flask : API JSON + interface web statique."""
from flask import Flask, jsonify, request, send_from_directory

from . import analysis
from .config import DATA_DIR, MIN_SALES, ROOT

TYPES = {"Appartement", "Maison"}


def create_app(sales, geojson_path=None, min_sales=MIN_SALES):
    app = Flask(__name__, static_folder=None)
    static_dir = ROOT / "static"
    geo = geojson_path or DATA_DIR / "communes.geojson"

    def number(name, lo, hi):
        try:
            value = float(request.args[name])
        except (KeyError, ValueError):
            raise ValueError(f"Paramètre invalide ou manquant : {name}")
        if not lo <= value <= hi:
            raise ValueError(f"{name} doit être compris entre {lo:g} et {hi:g}.")
        return value

    def type_local():
        t = request.args.get("type", "Appartement")
        if t not in TYPES:
            raise ValueError("Type de bien invalide (Appartement ou Maison).")
        return t

    @app.errorhandler(ValueError)
    def bad_request(e):
        return jsonify(error=str(e)), 400

    @app.get("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.get("/geojson")
    def geojson():
        return send_from_directory(geo.parent, geo.name, mimetype="application/geo+json")

    @app.get("/api/top")
    def top():
        return jsonify(analysis.top_communes(sales, min_sales=max(min_sales, 30)))

    @app.get("/api/communes")
    def communes():
        return jsonify(analysis.communes_list(sales))

    @app.get("/api/search")
    def search():
        return jsonify(analysis.search(sales, number("budget", 10_000, 50_000_000),
                                       number("surface", 9, 400), type_local(), min_sales))

    @app.get("/api/estimate")
    def estimate():
        code = request.args.get("code", "")
        return jsonify(analysis.estimate(sales, code, type_local(), number("surface", 9, 400)))

    return app
