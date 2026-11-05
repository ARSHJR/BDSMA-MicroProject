from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query, Header
import numpy as np
from .. import db
from ..store import get_store

router = APIRouter(prefix="/api", tags=["catalogue"])
SORTS = {"popular": ("n_ratings", False), "rating": ("bayes_rating", False), "price_asc": ("price", True), "price_desc": ("price", False),
         "sustainability": ("sustainability_score", False), "newest": ("first_available", False)}


@router.get("/products")
def list_products(q: str | None = None, category_group: str | None = None, article_type: str | None = None, gender: str | None = None,
                  colour: str | None = None, brand: str | None = None, min_price: float | None = Query(None, ge=0),
                  max_price: float | None = Query(None, ge=0), priced_only: bool = False,
                  min_sustainability: float | None = Query(None, ge=0, le=100),
                  sort: str = "popular", page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100)):
    st = get_store()
    p = st.products
    m = np.ones(len(p), bool)
    if q:
        hay = (p.title + " " + p.brand + " " + p.article_type).str.lower()
        for t in q.lower().split():
            m &= hay.str.contains(t, regex=False).to_numpy()
    for col, val in (("category_group", category_group), ("article_type", article_type), ("gender", gender),
                     ("colour", colour), ("brand", brand)):
        if val:
            m &= (p[col] == val).to_numpy()
    if priced_only or min_price is not None or max_price is not None:
        m &= p.price.notna().to_numpy()
    if min_price is not None:
        m &= (p.price >= min_price).to_numpy()
    if max_price is not None:
        m &= (p.price <= max_price).to_numpy()
    if min_sustainability is not None:
        m &= (p.sustainability_score >= min_sustainability).to_numpy()
    if sort not in SORTS:
        raise HTTPException(400, f"sort must be one of {list(SORTS)}")
    col, asc = SORTS[sort]
    idx = p[m].sort_values(col, ascending=asc, na_position="last").index.to_numpy()
    s = (page - 1) * page_size
    return {"total": len(idx), "page": page, "page_size": page_size, "items": [st.card(int(i)) for i in idx[s:s + page_size]]}


@router.get("/facets")
def facets():
    p = get_store().products

    def vc(c, n=None):
        return [{"value": k, "count": int(v)} for k, v in p[c].dropna().value_counts().head(n).items()]
    return {"category_group": vc("category_group"), "article_type": vc("article_type"), "gender": vc("gender"), "colour": vc("colour"),
            "brand": vc("brand", 40), "price_range": [float(p.price.min()), float(p.price.max())],
            "priced_products": int(p.price.notna().sum()), "total_products": len(p)}


@router.get("/products/{pid}")
def product(pid: int, x_session_id: str | None = Header(None)):
    st = get_store()
    if not 0 <= pid < st.rec.N:
        raise HTTPException(404, "Product not found")
    d = st.detail(pid)
    d["reviews"] = st.review_summary(pid)
    d["related"] = [{**st.card(i), "similarity": round(s, 3)} for i, s in st.rec.similar(pid, 8)]
    d["longevity_alternatives"] = [{**st.card(a["pid"]), "similarity": round(a["similarity"], 3), "sustainability_gain": round(a["delta"], 1)}
                                   for a in st.rec.longevity_alternatives(pid, 4)]
    owned = []
    if x_session_id:
        saved = db.get_wishlist(x_session_id) + [p for p, r in db.get_reactions(x_session_id).items() if r == "like"]
        owned = [{**st.card(a["pid"]), "similarity": round(a["similarity"], 3)}
                 for a in st.rec.owned_alternatives(pid, list(dict.fromkeys(saved)))]
    d["already_saved_similar"] = owned
    return d
