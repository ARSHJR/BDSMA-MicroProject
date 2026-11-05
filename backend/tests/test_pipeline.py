"""Data cleaning / feature-engineering tests (rules + invariants of the processed output)."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

import taxonomy as tx
import text_analytics as ta

PROC = Path(__file__).resolve().parents[2] / "data" / "processed"
needs_data = pytest.mark.skipif(not (PROC / "products_enriched.parquet").exists(), reason="run the pipeline first")


@pytest.mark.parametrize("title,expected", [
    ("Stainless Steel Plain Band Ring; Comes with Gift Box", "Jewellery"),   # 'Steel' must not match 'tee'
    ("Women's Casual Summer Dress", "Dresses"), ("Men Running Shoes", "Sneakers"), ("Boys Athletic Socks 6 pack", "Socks"),
    ("Leather Crossbody Bag for Women", "Bags & Wallets"), ("Merax Luggage Set Spinner Suitcase", "Other"),
])
def test_article_classification(title, expected):
    assert tx.classify(title)[0] == expected


def test_gender_and_colour_extraction():
    assert tx.gender("Girls' Trapeze Dress", None) == "Girls"
    assert tx.gender("whatever", "womens") == "Women"
    assert tx.gender("whatever", float("nan")) == "Unisex"          # NaN department must not crash
    assert tx.colour("Cotton Shirt (Navy Blue, XL)") == "navy" or tx.colour("Cotton Shirt (Navy Blue, XL)") == "blue"
    assert tx.colour("plain shirt") is None
    assert tx.materials("100% cotton with polyester lining") == ["cotton", "polyester"]


def test_review_signal_regexes():
    s = pd.Series(["Fell apart after one wash, shrunk badly", "Very well made and durable", "Too small, had to return", "Versatile - goes with everything"])
    f = ta.signal_flags(s)
    assert f.dur_neg.tolist() == [1, 0, 0, 0] and f.dur_pos.tolist() == [0, 1, 0, 0]
    assert f.fit_neg.tolist() == [0, 0, 1, 0] and f.versatile.tolist() == [0, 0, 0, 1]


def test_sentiment_direction_and_hashtags():
    c = ta.vader_compound(pd.Series(["I absolutely love this, perfect!", "Terrible, awful quality, waste of money"]))
    assert c.iloc[0] > 0.5 and c.iloc[1] < -0.5
    assert ta.extract_hashtags("Love it #OOTD #slowfashion! #a") == ["ootd", "slowfashion"]


def test_social_csv_pipeline_flags_synthetic():
    import importlib.util
    spec = importlib.util.spec_from_file_location("soc", Path(__file__).resolve().parents[2] / "pipeline" / "03_social.py")
    soc = importlib.util.module_from_spec(spec); spec.loader.exec_module(soc)
    df = soc.synthetic(n=360)
    res = soc.analyse(df, "x", True)
    assert res["is_synthetic"] and "SYNTHETIC" in res["banner"] and res["n_posts"] > 300
    with pytest.raises(ValueError):
        soc.analyse(pd.DataFrame({"foo": [1]}), "bad", False)


@needs_data
def test_processed_products_quality():
    p = pd.read_parquet(PROC / "products_enriched.parquet")
    assert p.pid.is_unique and p.asin.is_unique
    assert (p.pid.to_numpy() == np.arange(len(p))).all()
    assert p.title.str.len().min() >= 8 and p.image_large.notna().all()
    assert (p.price.dropna() > 0).all() and (p.price.dropna() <= 5000).all()
    assert p.sustainability_score.between(0, 100).all() and p.sus_confidence.between(0, 1).all()
    assert not p.duplicated(subset=["title", "brand"]).any()   # duplicate listings merged


@needs_data
def test_interactions_no_duplicates_and_kcore():
    i = pd.read_parquet(PROC / "interactions.parquet")
    assert not i.duplicated(subset=["uid", "pid"]).any()
    assert i.rating.between(1, 5).all()
    assert i.groupby("uid").size().min() >= 2 and i.groupby("pid").size().min() >= 3
    p = pd.read_parquet(PROC / "products_enriched.parquet", columns=["pid"])
    assert i.pid.isin(p.pid).all()
