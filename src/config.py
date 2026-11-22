"""Configuration : chemins relatifs à la racine du projet, réglages via .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
load_dotenv(ROOT / ".env")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
MIN_SALES = int(os.getenv("MIN_SALES", "8"))
