"""Stage 2 - sentiment, review-derived signals, sustainability proxy, trends.

In : data/processed/{products,reviews}.parquet
Out: data/processed/products_enriched.parquet, data/processed/analytics/{sentiment,trends,sustainability}.json
Run: python pipeline/02_text_features.py
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.feature_extraction.text import CountVectorizer

sys.path.insert(0, str(Path(__file__).parent))
import text_analytics as ta

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
A = P / "analytics"; A.mkdir(exist_ok=True)
t0 = time.time()
prod = pd.read_parquet(P / "products.parquet")
rev = pd.read_parquet(P / "reviews.parquet")
rev["ts"] = pd.to_datetime(rev.ts, utc=True)
print("reviews", len(rev))

# ------------------------------------------------------------ sentiment (VADER lexicon method)
rev["compound"] = ta.vader_compound(rev.text)
rev["sentiment"] = rev.compound.map(ta.label)
flags = ta.signal_flags(rev.text)
rev = pd.concat([rev.reset_index(drop=True), flags], axis=1)
rev["year"] = rev.ts.dt.year

rho = spearmanr(rev.compound, rev.rating).statistic
# rating-derived "silver label" for sanity-check: 4-5 stars = pos, 1-2 = neg
sub = rev[rev.rating != 3]
silver = np.where(sub.rating >= 4, "positive", "negative")
pred = np.where(sub.compound >= 0.05, "positive", np.where(sub.compound <= -0.05, "negative", "neutral"))
acc_binary = float(((pred == silver)[pred != "neutral"]).mean())
sent = {
    "method": "VADER (rule/lexicon-based) on review text",
    "n_reviews_scored": int(len(rev)),
    "distribution": rev.sentiment.value_counts().to_dict(),
    "spearman_vs_star_rating": round(float(rho), 4),
    "agreement_with_star_rating_pos_vs_neg": round(acc_binary, 4),
    "agreement_note": "Agreement computed only on non-3-star reviews where VADER is non-neutral; stars are a noisy proxy label.",
    "by_rating": rev.groupby("rating").compound.mean().round(4).to_dict(),
    "by_year": rev.groupby("year").agg(n=("compound", "size"), mean=("compound", "mean")).round(4).reset_index().to_dict("records"),
    "signal_rates": {k: round(float(rev[k].mean()), 4) for k in ta.SIGNALS},
    "data_source": "Amazon Reviews 2023 (Fashion) - product reviews, NOT social-media posts",
}

# ------------------------------------------------------------ per-product aggregates
g = rev.groupby("pid")
agg = g.agg(n_text_reviews=("compound", "size"), mean_sentiment=("compound", "mean"),
            dur_neg=("dur_neg", "sum"), dur_pos=("dur_pos", "sum"), fit_neg=("fit_neg", "sum"), versatile=("versatile", "sum"),
            pct_negative=("sentiment", lambda s: (s == "negative").mean()))
prod = prod.merge(agg, left_on="pid", right_index=True, how="left")
prod["n_text_reviews"] = prod.n_text_reviews.fillna(0).astype(int)

# ------------------------------------------------------------ sustainability PROXY (heuristic - transparent)
# Empirical-Bayes shrinkage of every rate toward the catalogue mean so that items with few reviews
# are not rewarded/penalised on noise. K = prior strength in "pseudo-reviews".
K = 8.0
n = prod.n_text_reviews.to_numpy(float)
def shrink(count_col: str) -> np.ndarray:
    c = prod[count_col].fillna(0).to_numpy(float)
    prior = c.sum() / max(n.sum(), 1)
    return (c + K * prior) / (n + K)

r_durneg, r_durpos, r_fit, r_vers = shrink("dur_neg"), shrink("dur_pos"), shrink("fit_neg"), shrink("versatile")
gm = float(np.nansum(prod.avg_rating * prod.n_ratings) / prod.n_ratings.sum())
m = 10.0
bayes_rating = (prod.n_ratings * prod.avg_rating.fillna(gm) + m * gm) / (prod.n_ratings + m)

def minmax(x, lo, hi): return np.clip((x - lo) / (hi - lo), 0, 1)
NEUTRAL = {"black", "white", "grey", "navy", "beige", "tan", "brown", "khaki", "cream", "olive"}
prod["neutral_colour"] = prod.colour.isin(NEUTRAL)

comp_quality = minmax(bayes_rating.to_numpy(), 3.0, 4.8)                              # rated durability/satisfaction
comp_durability = np.clip(0.5 + 3.0 * (r_durpos - r_durneg), 0, 1)                    # explicit durability mentions
comp_fit = 1 - minmax(r_fit, 0.0, 0.35)                                               # fewer fit/return complaints -> fewer returns
comp_versatile = np.clip(0.35 * prod.neutral_colour.to_numpy(float) + 4.0 * r_vers + 0.0, 0, 1)
score = 0.30 * comp_quality + 0.30 * comp_durability + 0.25 * comp_fit + 0.15 * comp_versatile
prod["bayes_rating"] = bayes_rating.round(3)
prod["sus_quality"] = comp_quality.round(3)
prod["sus_durability"] = comp_durability.round(3)
prod["sus_fit"] = comp_fit.round(3)
prod["sus_versatility"] = comp_versatile.round(3)
prod["sustainability_score"] = (100 * score).round(1)
# confidence: share of evidence behind the score (more reviews -> more trustworthy)
prod["sus_confidence"] = np.clip(n / 15.0, 0.1, 1.0).round(2)
prod["natural_fibre"] = prod.materials.fillna("").apply(lambda s: any(x in s.split(",") for x in
                        ("cotton", "wool", "linen", "silk", "leather", "cashmere", "bamboo", "hemp", "suede", "canvas")))

sus = {
    "disclaimer": "HEURISTIC PROXY. Not a measured environmental impact, carbon footprint, or certification. "
                  "Built only from ratings and review-text signals; shrunk toward the catalogue mean for low-evidence items.",
    "weights": {"quality_rating": 0.30, "durability_mentions": 0.30, "fit_reliability(fewer returns)": 0.25, "versatility": 0.15},
    "shrinkage_prior_strength": K,
    "score_distribution": {q: round(float(prod.sustainability_score.quantile(q)), 1) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
    "by_article_type": prod.groupby("article_type").sustainability_score.agg(["mean", "count"]).round(2).reset_index()
                           .rename(columns={"mean": "avg_score", "count": "n"}).sort_values("avg_score", ascending=False).to_dict("records"),
    "natural_fibre_items": int(prod.natural_fibre.sum()),
    "items_with_material_text": int((prod.materials.fillna("") != "").sum()),
    "corr_score_vs_rating": round(float(np.corrcoef(prod.sustainability_score, prod.bayes_rating)[0, 1]), 3),
}

# ------------------------------------------------------------ trends over time
rev = rev.merge(prod[["pid", "article_type", "category_group"]], on="pid")
rev["quarter"] = rev.ts.dt.to_period("Q").astype(str)
yearly = rev[rev.year >= 2012].groupby(["year", "article_type"]).size().reset_index(name="reviews")
top_types = rev.article_type.value_counts().head(8).index.tolist()
last = rev.year.max()
recent = rev[rev.year.isin([last - 1, last])].article_type.value_counts(normalize=True)
before = rev[rev.year.isin([last - 4, last - 3, last - 2])].article_type.value_counts(normalize=True)
emerging = ((recent / before) - 1).dropna().sort_values(ascending=False)
counts_recent = rev[rev.year.isin([last - 1, last])].article_type.value_counts()
emerging = emerging[counts_recent.reindex(emerging.index) >= 1000]

# emerging terms ("hashtag-like" keywords) - recent vs earlier review text, bigrams
def terms(df, n=4000):
    s = df.text.sample(min(len(df), 150000), random_state=0)
    cv = CountVectorizer(ngram_range=(2, 2), stop_words="english", min_df=20, max_features=30000)
    X = cv.fit_transform(s)
    return pd.Series(np.asarray(X.sum(0)).ravel() / len(s), index=cv.get_feature_names_out())
tr, tb = terms(rev[rev.year.isin([last - 1, last])]), terms(rev[rev.year.isin([last - 5, last - 4, last - 3, last - 2])])
ratio = (tr / (tb.reindex(tr.index).fillna(tb.min()))).sort_values(ascending=False)
emerging_terms = [{"term": t, "lift": round(float(ratio[t]), 2), "recent_rate": round(float(tr[t]) * 1000, 2)}
                  for t in ratio.index if tr[t] * 1000 > 0.4][:25]
trends = {
    "volume_by_year": rev.groupby("year").size().reset_index(name="reviews").to_dict("records"),
    "category_by_year": yearly[yearly.article_type.isin(top_types)].to_dict("records"),
    "sentiment_by_year_category": rev[rev.year >= 2014].groupby(["year", "category_group"]).compound.mean().round(4).reset_index().to_dict("records"),
    "emerging_categories": [{"article_type": k, "growth_pct": round(100 * float(v), 1)} for k, v in emerging.head(10).items()],
    "declining_categories": [{"article_type": k, "growth_pct": round(100 * float(v), 1)} for k, v in emerging.tail(5).items()],
    "emerging_terms": emerging_terms,
    "window": {"recent_years": [int(last - 1), int(last)], "baseline_years": [int(last - 4), int(last - 2)]},
    "note": "Trends are computed from timestamped product-review activity (engagement proxy), not from social-media posts.",
}

prod.to_parquet(P / "products_enriched.parquet", index=False)
rev[["pid", "rating", "ts", "compound", "sentiment"]].to_parquet(P / "review_sentiment.parquet", index=False)
for name, obj in (("sentiment", sent), ("trends", trends), ("sustainability", sus)):
    (A / f"{name}.json").write_text(json.dumps(obj, indent=2, default=str))
print(json.dumps({"sent": {k: sent[k] for k in ("distribution", "spearman_vs_star_rating", "agreement_with_star_rating_pos_vs_neg", "signal_rates")},
                  "sus": sus["score_distribution"], "emerging": trends["emerging_categories"][:4], "terms": emerging_terms[:8],
                  "elapsed": round(time.time() - t0, 1)}, indent=1))
