"""Téléchargement (par script) et nettoyage des ventes DVF 2023-2024 en Île-de-France."""
from __future__ import annotations

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

    Règle : on examine la composition COMPLÈTE de la vente avant d'écarter des lignes.
    Une vente est gardée si, parmi ses lignes bâties (type de local renseigné, hors
    « Dépendance »), il y en a exactement une et que c'est un appartement ou une maison
    avec prix et surface valides. Les ventes groupées (logement + commerce, deux logements,
    logement dont la surface est manquante...) sont écartées : leur prix ne peut pas être
    attribué à un seul logement. Les dépendances (garage, cave) restent comprises dans le prix.
    """
    df = raw[raw["nature_mutation"] == "Vente"]
    bati = df[df["type_local"].notna() & (df["type_local"] != "Dépendance")]
    bati = bati[bati.groupby("id_mutation")["id_mutation"].transform("size") == 1]
    bati = bati[bati["type_local"].isin(TYPES)]
    bati = bati.dropna(subset=["valeur_fonciere", "surface_reelle_bati", "code_commune"])
    bati = bati[bati["surface_reelle_bati"] > 0].copy()
    bati["prix_m2"] = bati["valeur_fonciere"] / bati["surface_reelle_bati"]
    bati = bati[bati["prix_m2"].between(1000, 30000) & bati["surface_reelle_bati"].between(9, 400)]
    return bati[["id_mutation", "date_mutation", "code_commune", "nom_commune",
                 "type_local", "surface_reelle_bati", "valeur_fonciere", "prix_m2"]]


def _download(url: str, dest: Path, force: bool = False) -> Path:
    """Télécharge url vers dest ; un fichier déjà présent est réutilisé sauf si force=True."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return dest
    print(f"Téléchargement : {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.replace(dest)
    return dest


def ensure_data(refresh: bool = False) -> None:
    """Télécharge et prépare les données si elles sont absentes (premier lancement).

    refresh=True re-télécharge réellement tous les fichiers sources, puis recalcule.
    """
    out = DATA_DIR / "processed"
    out.mkdir(parents=True, exist_ok=True)
    for year in YEARS:
        target = out / f"ventes_{year}.csv.gz"
        if target.exists() and not refresh:
            continue
        parts = []
        for dep in DEPARTEMENTS:
            raw = _download(DVF_URL.format(year=year, dep=dep),
                            DATA_DIR / "raw" / f"{year}_{dep}.csv.gz", force=refresh)
            df = pd.read_csv(raw, usecols=COLS, dtype={"code_commune": str, "id_mutation": str})
            parts.append(clean_mutations(df))
        pd.concat(parts).assign(annee=year).to_csv(target, index=False)
    _download(GEO_URL, GEOJSON, force=refresh)


def load_sales() -> pd.DataFrame:
    frames = [pd.read_csv(DATA_DIR / "processed" / f"ventes_{y}.csv.gz", dtype={"code_commune": str})
              for y in YEARS]
    return pd.concat(frames, ignore_index=True)