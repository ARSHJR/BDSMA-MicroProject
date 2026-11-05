"""API tests against the real processed artifacts (skipped if the pipeline has not been run)."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not (ROOT / "data" / "models" / "config.json").exists() or not (ROOT / "data" / "processed" / "analytics" / "evaluation.json").exists(),
                                reason="run the pipeline first")


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def H(s): return {"X-Session-Id": s}


def test_health(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["products"] > 1000


def test_products_filter_sort_paginate(client):
    r = client.get("/api/products", params={"article_type": "Dresses", "sort": "rating", "page_size": 5}).json()
    assert r["total"] > 100 and len(r["items"]) == 5 and all(i["article_type"] == "Dresses" for i in r["items"])
    p2 = client.get("/api/products", params={"article_type": "Dresses", "sort": "rating", "page_size": 5, "page": 2}).json()
    assert {i["pid"] for i in r["items"]}.isdisjoint({i["pid"] for i in p2["items"]})
    cheap = client.get("/api/products", params={"max_price": 20, "sort": "price_asc", "page_size": 10}).json()
    prices = [i["price"] for i in cheap["items"]]
    assert prices == sorted(prices) and all(p is not None and p <= 20 for p in prices)
    assert client.get("/api/products", params={"q": "zzzzqqqq"}).json()["total"] == 0
    assert client.get("/api/products", params={"sort": "bogus"}).status_code == 400
    assert client.get("/api/products", params={"page_size": 1000}).status_code == 422


def test_product_detail_and_404(client):
    d = client.get("/api/products/5").json()
    assert d["pid"] == 5 and d["related"] and "sustainability_breakdown" in d and "reviews" in d
    assert client.get("/api/products/99999999").status_code == 404


def test_facets(client):
    f = client.get("/api/facets").json()
    assert f["total_products"] > 0 and f["priced_products"] < f["total_products"]


def test_session_header_required(client):
    assert client.get("/api/recommendations").status_code == 400


def test_cold_start_then_interactions_change_recommendations(client):
    s = "t-cold-1"
    r0 = client.get("/api/recommendations", headers=H(s), params={"k": 12}).json()
    assert r0["mode"] == "cold_start" and len(r0["items"]) == 12
    # like three items of one type -> personalised, different list, excludes liked
    sneakers = client.get("/api/products", params={"article_type": "Boots", "page_size": 3}).json()["items"]
    for it in sneakers:
        assert client.post("/api/interactions", headers=H(s), json={"pid": it["pid"], "event": "like"}).status_code == 200
    r1 = client.get("/api/recommendations", headers=H(s), params={"k": 12}).json()
    assert r1["mode"] == "personalised"
    assert {i["pid"] for i in r1["items"]} != {i["pid"] for i in r0["items"]}
    assert not ({i["pid"] for i in r1["items"]} & {i["pid"] for i in sneakers})
    assert sum(i["article_type"] == "Boots" for i in r1["items"]) >= 3
    assert all(i["reasons"] for i in r1["items"])


def test_preferences_drive_recommendations_and_validate(client):
    s = "t-pref-1"
    assert client.put("/api/preferences", headers=H(s), json={"types": ["Watches"], "genders": [], "colours": [], "sustain": 0.2}).status_code == 200
    r = client.get("/api/recommendations", headers=H(s)).json()
    assert r["mode"] == "preferences" and sum(i["article_type"] == "Watches" for i in r["items"]) >= 8
    assert client.put("/api/preferences", headers=H(s), json={"types": ["NotAType"], "sustain": 0.2}).status_code == 422
    assert client.put("/api/preferences", headers=H(s), json={"types": [], "sustain": 7}).status_code == 422


def test_sustainability_slider_changes_ranking(client):
    s = "t-sus-1"
    client.put("/api/preferences", headers=H(s), json={"types": ["Dresses"], "sustain": 0.0})
    lo = client.get("/api/recommendations", headers=H(s), params={"sustain": 0, "k": 12}).json()["items"]
    hi = client.get("/api/recommendations", headers=H(s), params={"sustain": 1, "k": 12}).json()["items"]
    avg = lambda xs: sum(i["sustainability_score"] for i in xs) / len(xs)
    assert avg(hi) > avg(lo)


def test_wishlist_roundtrip_and_validation(client):
    s = "t-wish-1"
    assert client.post("/api/wishlist", headers=H(s), json={"pid": 7}).status_code == 200
    assert [i["pid"] for i in client.get("/api/wishlist", headers=H(s)).json()["items"]] == [7]
    assert client.post("/api/wishlist", headers=H(s), json={"pid": 99999999}).status_code == 404
    assert client.delete("/api/wishlist/7", headers=H(s)).status_code == 200
    assert client.get("/api/wishlist", headers=H(s)).json()["items"] == []
    assert client.post("/api/interactions", headers=H(s), json={"pid": 1, "event": "explode"}).status_code == 422


def test_own_before_buy_flag(client):
    s = "t-own-1"
    sim = client.get("/api/products/10").json()["related"][0]["pid"]
    client.post("/api/wishlist", headers=H(s), json={"pid": sim})
    d = client.get("/api/products/10", headers=H(s)).json()
    assert any(a["pid"] == sim for a in d["already_saved_similar"])


def test_analytics_endpoints(client):
    dash = client.get("/api/dashboard").json()
    assert dash["dataset"]["products"] > 0 and dash["by_category"] and dash["price_distribution"] and "price_note" in dash
    assert client.get("/api/trends").json()["emerging_categories"]
    assert client.get("/api/sentiment").json()["n_reviews_scored"] > 1000
    s = client.get("/api/sustainability").json()
    assert "HEURISTIC" in s["disclaimer"] and s["tradeoff"]
    e = client.get("/api/evaluation").json()
    assert "Popularity (baseline)" in e["models"] and "Hybrid (content + CF + popularity)" in e["models"]
    assert client.get("/api/social/demo").json()["is_synthetic"] is True
    assert client.get("/api/datasets").json()["sources"]


def test_social_csv_upload(client):
    csv = "text,created_at,likes\nLove my new #denim jacket,2024-01-02,10\nAwful fit #fastfashion,2024-02-03,2\nGreat #denim,2024-03-04,7\n"
    r = client.post("/api/social/analyse", json={"csv_text": csv}).json()
    assert r["is_synthetic"] is False and r["n_posts"] == 3 and r["top_hashtags"][0]["hashtag"] == "#denim"
    assert client.post("/api/social/analyse", json={"csv_text": "a,b\n1,2\n3,4\n"}).status_code == 422
