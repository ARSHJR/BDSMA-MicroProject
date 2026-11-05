"""In-memory data store: catalogue, models, analytics JSON. Loaded once at startup."""
from __future__ import annotations
import importlib.util, json, sys
from functools import lru_cache
import duckdb
import pandas as pd
import scipy.sparse as sp
from .config import settings, ROOT
from .services.recommender import Recommender, DEFAULT_WEIGHTS

sys.path.insert(0, str(ROOT / "pipeline"))


def _load_social():
    spec = importlib.util.spec_from_file_location("social_pipeline", ROOT / "pipeline" / "03_social.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _s(v):
    return None if (v is None or (isinstance(v, float) and v != v)) else v


def _i(v):
    return 0 if v is None or v != v else int(v)


class Store:
    def __init__(self):
        d, m = settings.data_dir, settings.model_dir
        self.products = pd.read_parquet(d / "products_enriched.parquet").sort_values("pid").reset_index(drop=True)
        cfg = json.loads((m / "config.json").read_text())
        self.weights = {**DEFAULT_WEIGHTS, **cfg["weights"]}
        self.rec = Recommender(self.products, sp.load_npz(m / "content_topk.npz"), sp.load_npz(m / "cf_topk.npz"), sp.load_npz(m / "features.npz"))
        self.analytics = {p.stem: json.loads(p.read_text()) for p in (d / "analytics").glob("*.json")}
        self.quality = json.loads((d / "quality_report.json").read_text())
        self.duck = duckdb.connect()
        self.reviews_path = (d / "reviews.parquet").as_posix()
        self.sent_path = (d / "review_sentiment.parquet").as_posix()
        self.social = _load_social()

    # ------------------------------------------------------------------ serialisation
    def card(self, pid: int) -> dict:
        r = self.products.iloc[pid]
        return {"pid": int(pid), "title": r.title, "brand": r.brand, "article_type": r.article_type, "category_group": r.category_group,
                "gender": r.gender, "colour": r.colour if isinstance(r.colour, str) else None,
                "price": None if pd.isna(r.price) else float(r.price),
                "avg_rating": None if pd.isna(r.avg_rating) else round(float(r.avg_rating), 2),
                "n_ratings": int(r.n_ratings), "image": _s(r.image_large), "image_thumb": _s(r.image_thumb),
                "sustainability_score": float(r.sustainability_score), "sus_confidence": float(r.sus_confidence)}

    def detail(self, pid: int) -> dict:
        r = self.products.iloc[pid]
        c = self.card(pid)
        c.update({"asin": r.asin, "description": (_s(r.description_text) or "")[:1200], "features": (_s(r.features_text) or "")[:900],
                  "materials": [x for x in (r.materials or "").split(",") if x], "natural_fibre": bool(r.natural_fibre),
                  "image_hires": _s(r.image_hires), "n_text_reviews": int(r.n_text_reviews),
                  "sustainability_breakdown": {"rating_quality": float(r.sus_quality), "durability_signals": float(r.sus_durability),
                                               "fit_reliability": float(r.sus_fit), "versatility": float(r.sus_versatility)},
                  "signals": {"durability_praise_reviews": _i(r.dur_pos), "durability_complaint_reviews": _i(r.dur_neg),
                              "fit_or_return_complaint_reviews": _i(r.fit_neg), "versatility_mentions": _i(r.versatile)}})
        return c

    def review_summary(self, pid: int) -> dict:
        pid = int(pid)
        q = self.duck.execute(f"select sentiment, count(*) from read_parquet('{self.sent_path}') where pid={pid} group by 1").fetchall()
        snips = self.duck.execute(
            f"select rating, left(text, 260), helpful_vote from read_parquet('{self.reviews_path}') "
            f"where pid={pid} order by helpful_vote desc, length(text) desc limit 3").fetchall()
        return {"sentiment": {k: v for k, v in q},
                "top_reviews": [{"rating": a, "text": b, "helpful_votes": c} for a, b, c in snips],
                "source": "Amazon product reviews (not social-media posts)"}


@lru_cache
def get_store() -> Store:
    return Store()
