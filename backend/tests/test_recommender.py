"""Unit tests of the recommendation maths on a small deterministic synthetic catalogue."""
import numpy as np
import pandas as pd
import scipy.sparse as sp
import pytest

from app.services.features import build_content_matrix
from app.services.recommender import Prefs, Recommender
from app.services.similarity import item_cf_topk, topk_cosine


@pytest.fixture(scope="module")
def rec():
    rng = np.random.default_rng(0)
    types = {"Dresses": "floral summer dress women", "Sneakers": "running sneaker athletic shoe", "Watches": "analog wrist watch steel"}
    rows = []
    for i in range(90):
        t = list(types)[i % 3]
        rows.append(dict(pid=i, title=f"{t} item {i}", article_type=t, category_group="Clothing" if t == "Dresses" else "Accessories",
                         gender="Women" if i % 2 == 0 else "Men", colour=["black", "red", "blue"][i % 3],
                         text_for_model=f"{types[t]} {i % 7}", price=10.0 + i, n_ratings=int(rng.integers(5, 400)),
                         avg_rating=4.0, bayes_rating=4.0, sus_confidence=1.0,
                         sustainability_score=float(90 - i if i < 45 else 10 + i % 20),  # first half = "durable"
                         dur_pos=1, dur_neg=0, fit_neg=0, n_text_reviews=10, neutral_colour=False, natural_fibre=False))
    P = pd.DataFrame(rows)
    F, _ = build_content_matrix(P)
    C = topk_cosine(F, 10)
    # collaborative: users who like dresses also like watches (cross-type signal content cannot know)
    ui = []
    for u in range(60):
        base = u % 3
        ui += [(u, base * 3 + k * 9 // 9 + 3 * j) for j in range(5) for k in range(1)]
    X = sp.csr_matrix((np.ones(len(ui)), ([a for a, _ in ui], [b % 90 for _, b in ui])), shape=(60, 90))
    K = item_cf_topk(X, 10)
    return Recommender(P, C, K, F)


def test_content_neighbours_share_type(rec):
    sims = rec.similar(0, 5)
    assert sims and all(rec.p.article_type.iat[i] == "Dresses" for i, _ in sims[:3])


def test_cold_start_returns_popularity_without_history(rec):
    out = rec.recommend({}, Prefs(), 0.0, 10, diversity=0)
    assert len(out) == 10
    top_pop = set(np.argsort(-rec.pop)[:10])
    assert {r["pid"] for r in out} == top_pop
    assert out[0]["reasons"][0]["type"] == "popular"


def test_preferences_change_cold_start_results(rec):
    base = {r["pid"] for r in rec.recommend({}, Prefs(), 0.0, 10)}
    pref = rec.recommend({}, Prefs(types=["Watches"]), 0.0, 10)
    assert {r["pid"] for r in pref} != base
    assert sum(rec.p.article_type.iat[r["pid"]] == "Watches" for r in pref) >= 8
    assert any(x["type"] == "preference" for r in pref for x in r["reasons"])


def test_likes_steer_recommendations_and_exclude_seen(rec):
    liked = {i: 1.0 for i in (1, 4, 7, 10)}  # Sneakers
    out = rec.recommend(liked, Prefs(), 0.0, 10)
    assert not ({r["pid"] for r in out} & set(liked))
    assert sum(rec.p.article_type.iat[r["pid"]] == "Sneakers" for r in out) >= 5
    assert any(x["type"] in ("content", "collaborative") for r in out for x in r["reasons"])


def test_dislike_pushes_type_down(rec):
    liked = {1: 1.0, 4: 1.0}
    with_dis = rec.recommend({**liked, 0: -1.0, 3: -1.0, 6: -1.0}, Prefs(), 0.0, 10, diversity=0)
    assert all(r["pid"] not in (0, 3, 6) for r in with_dis)


def test_sustainability_slider_raises_mean_longevity(rec):
    ev = {1: 1.0, 2: 1.0, 3: 1.0}
    lo = rec.recommend(ev, Prefs(), 0.0, 10, diversity=0)
    hi = rec.recommend(ev, Prefs(), 1.0, 10, diversity=0)
    m = lambda xs: np.mean([rec.p.sustainability_score.iat[r["pid"]] for r in xs])
    assert m(hi) > m(lo)


def test_low_evidence_scores_are_shrunk_to_mean():
    P = pd.DataFrame({"n_ratings": [1] * 4, "bayes_rating": [4.0] * 4, "sus_confidence": [0.1, 1.0, 1.0, 1.0],
                      "sustainability_score": [100.0, 100.0, 0.0, 0.0], "article_type": ["a"] * 4, "gender": ["Women"] * 4,
                      "colour": ["red"] * 4, "price": [1.0] * 4})
    z = sp.csr_matrix((4, 4))
    r = Recommender(P, z, z, z)
    assert r.sus_eff[0] < r.sus_eff[1]          # same raw score, little evidence -> pulled toward the catalogue mean
    assert r.sus_eff[1] == pytest.approx(1.0)   # full evidence -> unchanged


def test_budget_preference_penalises_expensive(rec):
    out = rec.recommend({}, Prefs(types=["Watches"], max_price=40), 0.0, 5, diversity=0)
    assert all(rec.p.price.iat[r["pid"]] <= 40 for r in out)


def test_owned_alternatives_flags_near_duplicates(rec):
    assert rec.owned_alternatives(0, [3, 4, 5], thr=0.2)  # same-type dresses are close
    assert rec.owned_alternatives(0, [1], thr=0.9) == []


def test_mmr_diversifies(rec):
    ev = {1: 1.0}
    a = rec.recommend(ev, Prefs(), 0.0, 8, diversity=0.0)
    b = rec.recommend(ev, Prefs(), 0.0, 8, diversity=0.6)
    ild = lambda xs: 1 - np.mean([(rec.F[x["pid"]] @ rec.F[y["pid"]].T).toarray()[0, 0] for x in xs for y in xs if x is not y])
    assert ild(b) >= ild(a) - 1e-9
