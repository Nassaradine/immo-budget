"""Point d'entrée : prépare les données au premier lancement puis démarre le site."""
import argparse
import threading
import webbrowser

from src.app import create_app
from src.config import HOST, PORT
from src.data import ensure_data, load_sales


def main():
    parser = argparse.ArgumentParser(description="Où acheter avec mon budget ? (DVF 2024)")
    parser.add_argument("--refresh", action="store_true", help="re-télécharge et recalcule les données")
    args = parser.parse_args()

    ensure_data(refresh=args.refresh)
    app = create_app(load_sales())
    url = f"http://{HOST}:{PORT}"
    print(f"Site disponible sur {url}")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=PORT)


if __name__ == "__main__":
    main()
