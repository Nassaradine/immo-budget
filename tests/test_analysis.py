import pandas as pd
import pytest

from src import analysis, data
from src.app import create_app
from src.data import clean_mutations

COMMERCE = "Local industriel. commercial ou assimilé"


def make(code, nom, type_local, prix_m2, annee, n=10, surface=50):
    return pd.DataFrame({"code_commune": code, "nom_commune": nom, "type_local": type_local,
                         "surface_reelle_bati": surface, "valeur_fonciere": prix_m2 * surface,
                         "prix_m2": float(prix_m2), "annee": annee}, index=range(n))


def raw(rows):
    cols = ["id_mutation", "nature_mutation", "type_local", "surface_reelle_bati", "valeur_fonciere"]
    return pd.DataFrame(rows, columns=cols).assign(
        date_mutation="2024-01-01", code_commune="A", nom_commune="A")


@pytest.fixture
def sales():
    return pd.concat([
        make("A", "Chère", "Appartement", 10000, 2024), make("A", "Chère", "Appartement", 9000, 2023),
        make("B", "Abordable", "Appartement", 3000, 2024), make("B", "Abordable", "Appartement", 3300, 2023),
    ], ignore_index=True)


# --- nettoyage des mutations -------------------------------------------------
def ids(df):
    return set(clean_mutations(df)["id_mutation"])


def test_clean_keeps_single_dwelling():
    assert ids(raw([("1", "Vente", "Appartement", 50, 300000)])) == {"1"}


def test_clean_drops_non_sales():
    assert ids(raw([("1", "Echange", "Appartement", 50, 300000)])) == set()


def test_clean_drops_dwelling_sold_with_commerce():
    rows = [("1", "Vente", "Appartement", 50, 500000), ("1", "Vente", COMMERCE, 80, 500000)]
    assert ids(raw(rows)) == set()


def test_clean_drops_two_dwellings_even_if_one_surface_missing():
    rows = [("1", "Vente", "Appartement", 50, 500000), ("1", "Vente", "Appartement", None, 500000)]
    assert ids(raw(rows)) == set()


def test_clean_keeps_dwelling_with_dependance():
    rows = [("1", "Vente", "Appartement", 50, 300000), ("1", "Vente", "Dépendance", 12, 300000)]
    assert ids(raw(rows)) == {"1"}


# --- analyses ------------------------------------------------------------------
def test_top_communes_sorted_by_price(sales):
    top = analysis.top_communes(sales, n=2, min_sales=5)
    assert [c["code"] for c in top] == ["A", "B"]


def test_search_filters_by_budget(sales):
    res = analysis.search(sales, 250_000, 50, "Appartement", min_sales=5)
    by_code = {c["code"]: c for c in res["communes"]}
    assert res["max_m2"] == 5000
    assert by_code["B"]["part"] == 1.0 and by_code["A"]["part"] == 0.0


def test_search_budget_boundary_is_inclusive():
    s = make("C", "Limite", "Appartement", 5000, 2024)
    res = analysis.search(s, 250_000, 50, "Appartement", min_sales=5)
    assert res["communes"][0]["part"] == 1.0


def test_search_min_sales_threshold(sales):
    assert analysis.search(sales, 250_000, 50, "Appartement", min_sales=11)["communes"] == []


def test_estimate_and_evolution(sales):
    est = analysis.estimate(sales, "A", "Appartement", 50)
    assert est["prix"] == 500_000 and est["evolution_pct"] == pytest.approx(11.1)


def test_estimate_not_enough_data(sales):
    with pytest.raises(ValueError):
        analysis.estimate(sales, "ZZ", "Appartement", 50)


# --- téléchargement ------------------------------------------------------------
def test_download_reuses_file_unless_forced(tmp_path, monkeypatch):
    calls = []

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass
        def iter_content(self, n): yield b"x"

    monkeypatch.setattr(data.requests, "get", lambda *a, **k: calls.append(1) or FakeResponse())
    dest = tmp_path / "f.gz"
    data._download("u", dest)
    data._download("u", dest)
    assert len(calls) == 1
    data._download("u", dest, force=True)
    assert len(calls) == 2


# --- API -------------------------------------------------------------------------
@pytest.fixture
def client(sales):
    return create_app(sales, min_sales=5).test_client()


def test_api_search_content(client):
    r = client.get("/api/search?budget=250000&surface=50&type=Appartement")
    body = r.get_json()
    assert r.status_code == 200 and body["max_m2"] == 5000
    assert {c["code"] for c in body["communes"]} == {"A", "B"}


def test_api_estimate_content(client):
    body = client.get("/api/estimate?code=A&type=Appartement&surface=50").get_json()
    assert body["prix"] == 500_000 and body["nom"] == "Chère"


@pytest.mark.parametrize("query", [
    "/api/search?budget=abc&surface=50",
    "/api/search?budget=250000&surface=5000",
    "/api/search?budget=250000&surface=50&type=Chateau",
    "/api/estimate?code=ZZ&type=Appartement&surface=50",
])
def test_api_rejects_bad_requests(client, query):
    assert client.get(query).status_code == 400