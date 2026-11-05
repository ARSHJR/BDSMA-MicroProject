from __future__ import annotations
import time
import uuid
from fastapi import APIRouter, Header, HTTPException, Query
from .. import db
from ..schemas import PrefsIn, InteractionIn, WishlistIn
from ..services.recommender import Prefs
from ..store import get_store

router = APIRouter(prefix="/api", tags=["user"])


def _sid(x: str | None) -> str:
    if not x or len(x) > 64:
        raise HTTPException(400, "Missing or invalid X-Session-Id header")
    return x


def _check(pid: int):
    if pid >= get_store().rec.N:
        raise HTTPException(404, "Product not found")


@router.post("/session")
def new_session():
    sid = uuid.uuid4().hex
    db.ensure_session(sid)
    return {"session_id": sid}


@router.get("/preferences")
def get_preferences(x_session_id: str | None = Header(None)):
    return db.get_prefs(_sid(x_session_id))


@router.put("/preferences")
def put_preferences(body: PrefsIn, x_session_id: str | None = Header(None)):
    st = get_store()
    sid = _sid(x_session_id)
    known_t, known_c = set(st.products.article_type), set(st.products.colour.dropna())
    bad = [t for t in body.types if t not in known_t] + [c for c in body.colours if c not in known_c]
    if bad:
        raise HTTPException(422, f"Unknown values: {bad}")
    db.set_prefs(sid, body.model_dump(exclude={"sustain"}), body.sustain)
    return db.get_prefs(sid)


@router.post("/interactions")
def interact(body: InteractionIn, x_session_id: str | None = Header(None)):
    sid = _sid(x_session_id)
    _check(body.pid)
    if body.event in ("like", "dislike"):
        db.set_reaction(sid, body.pid, body.event)
    elif body.event == "clear_reaction":
        db.set_reaction(sid, body.pid, None)
    else:
        db.add_event(sid, body.pid, body.event)
    return {"ok": True, "n_signals": len(db.build_events(sid))}


@router.get("/reactions")
def reactions(x_session_id: str | None = Header(None)):
    sid = _sid(x_session_id)
    return {"reactions": {str(k): v for k, v in db.get_reactions(sid).items()}, "wishlist": db.get_wishlist(sid)}


@router.get("/wishlist")
def wishlist(x_session_id: str | None = Header(None)):
    sid = _sid(x_session_id)
    st = get_store()
    return {"items": [st.card(p) for p in db.get_wishlist(sid)]}


@router.post("/wishlist")
def add_wish(body: WishlistIn, x_session_id: str | None = Header(None)):
    sid = _sid(x_session_id)
    _check(body.pid)
    db.set_wishlist(sid, body.pid, True)
    return {"ok": True}


@router.delete("/wishlist/{pid}")
def del_wish(pid: int, x_session_id: str | None = Header(None)):
    db.set_wishlist(_sid(x_session_id), pid, False)
    return {"ok": True}


@router.get("/recommendations")
def recommendations(k: int = Query(12, ge=1, le=48), sustain: float | None = Query(None, ge=0, le=1), category_group: str | None = None,
                    x_session_id: str | None = Header(None)):
    st = get_store()
    sid = _sid(x_session_id)
    pr = db.get_prefs(sid)
    sus = pr["sustain"] if sustain is None else sustain
    prefs = Prefs(pr.get("types", []), pr.get("genders", []), pr.get("colours", []), pr.get("max_price"))
    events = db.build_events(sid)
    mask = (st.products.category_group == category_group).to_numpy() if category_group else None
    t = time.perf_counter()
    recs = st.rec.recommend(events, prefs, sus, k, mask=mask, weights=st.weights)
    ms = (time.perf_counter() - t) * 1000
    n_pos = sum(1 for v in events.values() if v > 0)
    mode = "personalised" if n_pos else ("preferences" if not prefs.empty() else "cold_start")
    return {"mode": mode, "sustain": sus, "n_signals": len(events), "latency_ms": round(ms, 1),
            "items": [{**st.card(r["pid"]), "score": round(r["score"], 4), "relevance": round(r["relevance"], 4), "reasons": r["reasons"],
                       "parts": {a: round(b, 3) for a, b in r["parts"].items()}} for r in recs]}
