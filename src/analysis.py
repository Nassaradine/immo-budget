"""Calculs : top communes, recherche selon le budget, estimation, 2023 vs 2024."""
from __future__ import annotations
import pandas as pd


def _sel(sales: pd.DataFrame, year: int, type_local: str | None = None) -> pd.DataFrame:
    df = sales[sales["annee"] == year]
    return df if type_local is None else df[df["type_local"] == type_local]


def top_communes(sales, year=2024, n=10, min_sales=30):
    """Les communes (ou arrondissements) au prix médian du m² le plus élevé."""
    g = (_sel(sales, year).groupby(["code_commune", "nom_commune"])["prix_m2"]
         .agg(ventes="size", prix_m2="median").reset_index())
    g = g[g["ventes"] >= min_sales].nlargest(n, "prix_m2")
    return [{"code": r.code_commune, "nom": r.nom_commune,
             "prix_m2": int(round(r.prix_m2)), "ventes": int(r.ventes)} for r in g.itertuples()]


def search(sales, budget, surface, type_local, min_sales=8, year=2024):
    """Pour chaque commune : part des ventes de l'année accessibles avec ce budget et cette surface."""
    max_m2 = budget / surface
    df = _sel(sales, year, type_local).assign(ok=lambda d: d["prix_m2"] <= max_m2)
    g = (df.groupby(["code_commune", "nom_commune"])
         .agg(ventes=("ok", "size"), part=("ok", "mean"), prix_m2=("prix_m2", "median")).reset_index())
    g = g[g["ventes"] >= min_sales].sort_values(["part", "prix_m2"], ascending=[False, True])
    communes = [{"code": r.code_commune, "nom": r.nom_commune, "ventes": int(r.ventes),
                 "part": round(float(r.part), 3), "prix_m2": int(round(r.prix_m2)),
                 "prix_estime": int(round(r.prix_m2 * surface))} for r in g.itertuples()]
    return {"max_m2": int(round(max_m2)), "communes": communes}


def estimate(sales, code, type_local, surface):
    """Estimation d'un bien (médiane 2024 de la commune, fourchette interquartile) et évolution vs 2023."""
    cur = _sel(sales, 2024, type_local)
    cur = cur[cur["code_commune"] == code]
    if len(cur) < 3:
        raise ValueError("Pas assez de ventes dans cette commune pour estimer ce bien.")
    m = cur["prix_m2"].median()
    prev = _sel(sales, 2023, type_local)
    prev = prev[prev["code_commune"] == code]
    m23 = prev["prix_m2"].median() if len(prev) >= 3 else None
    return {
        "nom": cur["nom_commune"].iloc[0], "ventes": int(len(cur)),
        "prix_m2": int(round(m)), "prix": int(round(m * surface)),
        "bas": int(round(cur["prix_m2"].quantile(.25) * surface)),
        "haut": int(round(cur["prix_m2"].quantile(.75) * surface)),
        "prix_m2_2023": None if m23 is None else int(round(m23)),
        "evolution_pct": None if m23 is None else round(float((m / m23 - 1) * 100), 1),
    }


def communes_list(sales):
    d = sales[["code_commune", "nom_commune"]].drop_duplicates().sort_values("nom_commune")
    return [{"code": r.code_commune, "nom": r.nom_commune} for r in d.itertuples()]
