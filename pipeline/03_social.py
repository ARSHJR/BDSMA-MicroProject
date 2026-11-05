"""Stage 3 - social-media analytics.

No open, legally redistributable fashion *social-media* corpus was obtainable without API keys/scraping
(Twitter/X, Instagram, TikTok APIs are closed). Therefore:

 1. `analyse_csv()` is a generic importer: any CSV with columns  text, created_at, [likes], [platform]
    (e.g. a user's own Reddit/X export) is analysed: hashtags, sentiment, engagement, trends.
 2. `--synthetic` writes a SYNTHETIC demo file (data/social/synthetic_demo_posts.csv). Every row is
    flagged is_synthetic=True and every output is labelled DEMONSTRATION DATA. Nothing from it is a real finding.

Run: python pipeline/03_social.py [--csv path] [--synthetic]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import text_analytics as ta

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "analytics"; OUT.mkdir(parents=True, exist_ok=True)
SOC = ROOT / "data" / "social"; SOC.mkdir(parents=True, exist_ok=True)


def synthetic(n: int = 4000, seed: int = 7) -> pd.DataFrame:
    """SYNTHETIC posts from templates; trend/sentiment shifts are *injected by design* for demo only."""
    rng = np.random.default_rng(seed)
    topics = {  # topic -> (hashtags, base weight, trend slope per month, positivity)
        "denim": (["#denim", "#y2kfashion", "#vintagejeans"], 1.0, 0.04, 0.75),
        "sneakers": (["#sneakerhead", "#streetwear", "#ootd"], 1.2, 0.01, 0.8),
        "thrift": (["#thrifted", "#secondhandfirst", "#slowfashion"], 0.6, 0.06, 0.88),
        "fastfashion": (["#fastfashion", "#sheinhaul", "#haul"], 1.4, -0.03, 0.45),
        "linen": (["#linen", "#summerstyle", "#capsulewardrobe"], 0.5, 0.05, 0.85),
        "bags": (["#handbag", "#itbag", "#accessories"], 0.9, 0.0, 0.7),
    }
    pos = ["love this", "obsessed with", "so happy with", "great quality", "perfect fit", "wearing all week"]
    neg = ["disappointed by", "fell apart after one wash", "overpriced", "poor quality", "not worth it", "returning"]
    months = pd.date_range("2024-01-01", periods=18, freq="MS")
    rows = []
    for mi, m in enumerate(months):
        w = np.array([max(0.05, b + s * mi) for (_, b, s, _) in topics.values()]); w /= w.sum()
        for _ in range(n // len(months)):
            t = rng.choice(list(topics), p=w); tags, _, _, pp = topics[t]
            good = rng.random() < pp
            tx = f"{rng.choice(pos if good else neg)} {t.replace('fastfashion', 'fast fashion')} " + " ".join(rng.choice(tags, 2, replace=False))
            rows.append((tx, m + pd.Timedelta(days=int(rng.integers(0, 28))), int(rng.lognormal(3 if good else 2.3, 1)), rng.choice(["synthetic-x", "synthetic-insta"]), True))
    return pd.DataFrame(rows, columns=["text", "created_at", "likes", "platform", "is_synthetic"])


def analyse(df: pd.DataFrame, label: str, synthetic_flag: bool) -> dict:
    df = df.copy()
    if "text" not in df or "created_at" not in df:
        raise ValueError("CSV must contain 'text' and 'created_at' columns")
    df["created_at"] = pd.to_datetime(df.created_at, errors="coerce", utc=True)
    df = df.dropna(subset=["text", "created_at"]).drop_duplicates(subset=["text", "created_at"])
    df["likes"] = pd.to_numeric(df.get("likes", 0), errors="coerce").fillna(0)
    df["platform"] = df.get("platform", "unknown")
    df["compound"] = ta.vader_compound(df.text)
    df["sentiment"] = df.compound.map(ta.label)
    df["month"] = df.created_at.dt.strftime("%Y-%m")
    df["tags"] = df.text.map(ta.extract_hashtags)
    ex = df.explode("tags").dropna(subset=["tags"])
    top = ex.groupby("tags").agg(posts=("likes", "size"), likes=("likes", "sum"), sentiment=("compound", "mean")).sort_values("posts", ascending=False)
    first_half = ex[ex.month <= sorted(df.month.unique())[len(df.month.unique()) // 2]]
    second_half = ex.drop(first_half.index)
    g = (second_half.tags.value_counts(normalize=True) / first_half.tags.value_counts(normalize=True)).dropna().sort_values(ascending=False)
    mt = ex.groupby(["month", "tags"]).size().reset_index(name="posts")
    keep = top.head(8).index
    return {
        "label": label,
        "is_synthetic": synthetic_flag,
        "banner": "SYNTHETIC DEMONSTRATION DATA - generated for UI/pipeline demo; not real social-media findings." if synthetic_flag else "User-imported social data",
        "n_posts": int(len(df)),
        "date_range": [str(df.created_at.min().date()), str(df.created_at.max().date())],
        "sentiment_distribution": df.sentiment.value_counts().to_dict(),
        "top_hashtags": [{"hashtag": "#" + k, "posts": int(r.posts), "likes": int(r.likes), "avg_sentiment": round(float(r.sentiment), 3)} for k, r in top.head(15).iterrows()],
        "hashtag_trend": mt[mt.tags.isin(keep)].rename(columns={"tags": "hashtag"}).assign(hashtag=lambda d: "#" + d.hashtag).to_dict("records"),
        "rising_hashtags": [{"hashtag": "#" + k, "growth_ratio": round(float(v), 2)} for k, v in g.head(6).items()],
        "monthly": df.groupby("month").agg(posts=("likes", "size"), avg_sentiment=("compound", "mean"), likes=("likes", "sum")).round(3).reset_index().to_dict("records"),
        "engagement_vs_sentiment": df.groupby("sentiment").likes.mean().round(2).to_dict(),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv"); ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    if a.csv:
        res = analyse(pd.read_csv(a.csv), Path(a.csv).name, False); (OUT / "social_imported.json").write_text(json.dumps(res, indent=2))
    if a.synthetic or not a.csv:
        df = synthetic(); df.to_csv(SOC / "synthetic_demo_posts.csv", index=False)
        res = analyse(df, "synthetic_demo_posts.csv", True); (OUT / "social_demo.json").write_text(json.dumps(res, indent=2))
    print(json.dumps({k: res[k] for k in ("banner", "n_posts", "sentiment_distribution", "rising_hashtags")}, indent=1))
