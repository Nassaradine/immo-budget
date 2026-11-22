import pandas as pd
import pytest

from src import analysis
from src.app import create_app
from src.data import clean_mutations


def make(code, nom, type_local, prix_m2, annee, n=10, surface=50):
    return pd.DataFrame({"code_commune": code, "nom_commune": nom, "type_local": type_local,
                         "surface_reelle_bati": surface, "valeur_fonciere": prix_m2 * surface,
                         "prix_m2": float(prix_m2), "annee": annee}, index=range(n))


@pytest.fixture
def sales():
    return pd.concat([
        make("A", "Chère", "Appartement", 10000, 2024), make("A", "Chère", "Appartement", 9000, 2023),
        make("B", "Abordable", "Appartement", 3000, 2024), make("B", "Abordable", "Appartement", 3300, 2023),
    ], ignore_index=True)


def test_clean_mutations_keeps_only_single_dwelling_sales():
    raw = pd.DataFrame({
        "id_mutation": ["1", "2", "2", "3"],
        "date_mutation": ["2024-01-01"] * 4,
        "nature_mutation": ["Vente", "Vente", "Vente", "Echange"],
        "code_commune": ["A"] * 4, "nom_commune": ["A"] * 4,
        "type_local": ["Appartement"] * 4,
        "surface_reelle_bati": [50, 40, 60, 50],
        "valeur_fonciere": [300000, 400000, 400000, 300000]})
    assert set(clean_mutations(raw)["id_mutation"]) == {"1"}


def test_top_communes_sorted_by_price(sales):
    top = analysis.top_communes(sales, n=2, min_sales=5)
    assert [c["code"] for c in top] == ["A", "B"]


def test_search_filters_by_budget(sales):
    res = analysis.search(sales, 250_000, 50, "Appartement", min_sales=5)
    by_code = {c["code"]: c for c in res["communes"]}
    assert res["max_m2"] == 5000
    assert by_code["B"]["part"] == 1.0 and by_code["A"]["part"] == 0.0


def test_estimate_and_evolution(sales):
    est = analysis.estimate(sales, "A", "Appartement", 50)
    assert est["prix"] == 500_000 and est["evolution_pct"] == pytest.approx(11.1)


def test_estimate_not_enough_data(sales):
    with pytest.raises(ValueError):
        analysis.estimate(sales, "ZZ", "Appartement", 50)


def test_api(sales):
    client = create_app(sales, min_sales=5).test_client()
    assert client.get("/api/top").status_code == 200
    assert client.get("/api/search?budget=250000&surface=50&type=Maison").status_code == 200
    assert client.get("/api/search?budget=abc&surface=50").status_code == 400
