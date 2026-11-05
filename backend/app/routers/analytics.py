from __future__ import annotations
import io
import pandas as pd
from fastapi import APIRouter, HTTPException
from .. import db
from ..schemas import SocialCsvIn
from ..store import get_store

router = APIRouter(prefix="/api", tags=["analytics"])

DATASETS = [
    {"name": "Amazon Reviews 2023 - Fashion (metadata + reviews)", "url": "https://amazon-reviews-2023.github.io/",
     "files": ["meta_Amazon_Fashion.jsonl.gz", "Amazon_Fashion.jsonl.gz"],
     "license": "Released by McAuley Lab (UCSD) for academic research use; cite Hou et al. 2024, Bridging Language and Items for "
                "Retrieval and Recommendation. Images remain property of Amazon/sellers and are hot-linked, not redistributed.",
     "why": "Real catalogue + real timestamped user-item ratings + review text, downloadable without an account or API key."},
    {"name": "Synthetic social demo posts", "url": None, "files": ["data/social/synthetic_demo_posts.csv"],
     "license": "Generated locally by pipeline/03_social.py (seeded). SYNTHETIC - not real social-media data.",
     "why": "No open fashion social-media corpus could be obtained without restricted scraping/APIs. Demonstrates the CSV-import analytics workflow."},
]


def _vc(s: pd.Series, n: int | None = None):
    d = s.value_counts().head(n).rename_axis("name").reset_index(name="value")
    return d.to_dict("records")


@router.get("/health")
def health():
    st = get_store()
    return {"status": "ok", "products": st.rec.N, "models_loaded": True, "db": db.stats()}


@router.get("/dashboard")
def dashboard():
    st = get_store()
    p, q = st.products, st.quality
    priced = p.price.dropna()
    bins = pd.cut(priced, [0, 10, 20, 30, 50, 75, 100, 200, 5000], labels=["<10", "10-20", "20-30", "30-50", "50-75", "75-100", "100-200", "200+"])
    sus = pd.cut(p.sustainability_score, [0, 40, 50, 60, 70, 100], labels=["<40", "40-50", "50-60", "60-70", "70+"])
    sent = st.analytics["sentiment"]
    return {
        "dataset": {"products": len(p), "interactions": q["interactions_after_core"], "users": q["users_after_core"],
                    "reviews_with_text": q["reviews_with_text"], "raw_products": q["raw_products"], "raw_reviews": q["raw_reviews"],
                    "priced_products": q["priced_products"], "sparsity_pct": q["sparsity_pct"]},
        "by_category": _vc(p.article_type), "by_group": _vc(p.category_group), "by_gender": _vc(p.gender),
        "top_brands": _vc(p.brand[p.brand != "Unknown"], 12),
        "price_distribution": [{"name": str(k), "value": int(v)} for k, v in bins.value_counts(sort=False).items()],
        "price_note": f"Only {len(priced):,} of {len(p):,} products ({100 * len(priced) / len(p):.0f}%) have a listed price in the source data.",
        "sentiment": sent["distribution"], "sentiment_by_year": sent["by_year"],
        "sustainability_distribution": [{"name": str(k), "value": int(v)} for k, v in sus.value_counts(sort=False).items()],
        "sustainability_by_type": st.analytics["sustainability"]["by_article_type"][:12],
        "evaluation_headline": {k: {m: v[m] for m in ("precision@k", "recall@k", "ndcg@k", "coverage")}
                                for k, v in st.analytics["evaluation"]["models"].items()},
        "app_usage": db.stats(),
    }


@router.get("/trends")
def trends():
    return get_store().analytics["trends"]


@router.get("/sentiment")
def sentiment():
    return get_store().analytics["sentiment"]


@router.get("/sustainability")
def sustainability():
    st = get_store()
    a, p = st.analytics["sustainability"], st.products
    top = p[p.sus_confidence >= 0.6].sort_values("sustainability_score", ascending=False).head(8).index
    return {**a, "top_products": [st.card(int(i)) for i in top], "tradeoff": st.analytics["evaluation"]["sustainability_tradeoff"],
            "how_it_supports_sdg12": [
                "Longevity first: ranking rewards items whose reviews report durability and few fit-related returns - longer use means fewer replacement purchases (SDG 12.5 waste reduction).",
                "Own-before-buy: product pages flag similar items you already saved, and suggest higher-longevity alternatives instead of another purchase.",
                "Versatility: neutral colours and 'goes with everything' mentions raise the score, encouraging capsule wardrobes.",
                "User control & transparency: a sustainability slider changes the ranking; every recommendation explains how the proxy contributed.",
            ]}


@router.get("/social/demo")
def social_demo():
    return get_store().analytics["social_demo"]


@router.post("/social/analyse")
def social_analyse(body: SocialCsvIn):
    st = get_store()
    try:
        return st.social.analyse(pd.read_csv(io.StringIO(body.csv_text)), "uploaded.csv", False)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(422, f"Could not parse CSV: {e}")


@router.get("/evaluation")
def evaluation():
    return get_store().analytics["evaluation"]


@router.get("/datasets")
def datasets():
    st = get_store()
    return {"sources": DATASETS, "quality_report": st.quality,
            "pipeline": ["Raw JSONL.gz (DuckDB streaming)", "Clean & dedupe", "k-core filter (user>=2, item>=3)", "Feature engineering (taxonomy, TF-IDF)",
                         "Sentiment + sustainability proxy", "Similarity models + evaluation", "FastAPI", "React"],
            "benchmark": st.analytics.get("benchmark")}
