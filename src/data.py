"""Téléchargement (par script) et nettoyage des ventes DVF 2023-2024 en Île-de-France."""
from pathlib import Path

import pandas as pd
import requests

from .config import DATA_DIR

DEPARTEMENTS = ["75", "77", "78", "91", "92", "93", "94", "95"]
YEARS = (2023, 2024)
DVF_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv/{year}/departements/{dep}.csv.gz"
GEO_URL = (
    "https://geo.api.gouv.fr/communes?codeRegion=11"
    "&type=arrondissement-municipal,commune-actuelle&format=geojson&geometry=contour"
)
TYPES = ("Appartement", "Maison")
COLS = ["id_mutation", "date_mutation", "nature_mutation", "code_commune",
        "nom_commune", "type_local", "surface_reelle_bati", "valeur_fonciere"]
GEOJSON = DATA_DIR / "communes.geojson"


def clean_mutations(raw: pd.DataFrame) -> pd.DataFrame:
    """Une vente = un id_mutation (souvent plusieurs lignes).

    On ne garde que les ventes d'un seul logement (appartement ou maison) : le prix
    d'une vente multi-logements ne peut pas être réparti de façon fiable.
    """
    df = raw[raw["nature_mutation"] == "Vente"]
    df = df[df["type_local"].isin(TYPES)]
    df = df.dropna(subset=["valeur_fonciere", "surface_reelle_bati", "code_commune"])
    df = df[df.groupby("id_mutation")["id_mutation"].transform("size") == 1].copy()
    df = df[df["surface_reelle_bati"] > 0]
    df["prix_m2"] = df["valeur_fonciere"] / df["surface_reelle_bati"]
    df = df[df["prix_m2"].between(1000, 30000) & df["surface_reelle_bati"].between(9, 400)]
    return df[["id_mutation", "date_mutation", "code_commune", "nom_commune",
               "type_local", "surface_reelle_bati", "valeur_fonciere", "prix_m2"]]


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    print(f"Téléchargement : {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    return dest


def ensure_data(refresh: bool = False) -> None:
    """Télécharge et prépare les données si elles sont absentes (premier lancement)."""
    out = DATA_DIR / "processed"
    out.mkdir(parents=True, exist_ok=True)
    for year in YEARS:
        target = out / f"ventes_{year}.csv.gz"
        if target.exists() and not refresh:
            continue
        parts = []
        for dep in DEPARTEMENTS:
            raw = _download(DVF_URL.format(year=year, dep=dep), DATA_DIR / "raw" / f"{year}_{dep}.csv.gz")
            df = pd.read_csv(raw, usecols=COLS, dtype={"code_commune": str, "id_mutation": str})
            parts.append(clean_mutations(df))
        pd.concat(parts).assign(annee=year).to_csv(target, index=False)
    if refresh and GEOJSON.exists():
        GEOJSON.unlink()
    _download(GEO_URL, GEOJSON)


def load_sales() -> pd.DataFrame:
    frames = [pd.read_csv(DATA_DIR / "processed" / f"ventes_{y}.csv.gz", dtype={"code_commune": str})
              for y in YEARS]
    return pd.concat(frames, ignore_index=True)
