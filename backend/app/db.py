"""User-state persistence (SQLAlchemy Core). SQLite by default; set DATABASE_URL to a Supabase
Postgres URL (see supabase/schema.sql) to migrate - no code change required."""
from __future__ import annotations
import json, time
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, Text, UniqueConstraint, select, delete, insert, update, func
from .config import settings

engine = create_engine(settings.database_url, future=True)
meta = MetaData()
sessions = Table("sessions", meta, Column("id", String(64), primary_key=True), Column("created_at", Float), Column("prefs_json", Text, default="{}"),
                 Column("sustain", Float, default=0.3))
events = Table("events", meta, Column("id", Integer, primary_key=True, autoincrement=True), Column("session_id", String(64), index=True),
               Column("pid", Integer), Column("event", String(16)), Column("ts", Float))
reactions = Table("reactions", meta, Column("session_id", String(64)), Column("pid", Integer), Column("reaction", String(8)), Column("ts", Float),
                  UniqueConstraint("session_id", "pid"))
wishlist = Table("wishlist", meta, Column("session_id", String(64)), Column("pid", Integer), Column("ts", Float), UniqueConstraint("session_id", "pid"))
meta.create_all(engine)


def ensure_session(sid: str) -> None:
    with engine.begin() as c:
        if not c.execute(select(sessions.c.id).where(sessions.c.id == sid)).first():
            c.execute(insert(sessions).values(id=sid, created_at=time.time(), prefs_json="{}", sustain=0.3))


def get_prefs(sid: str) -> dict:
    ensure_session(sid)
    with engine.begin() as c:
        r = c.execute(select(sessions.c.prefs_json, sessions.c.sustain).where(sessions.c.id == sid)).first()
    d = {"types": [], "genders": [], "colours": [], "max_price": None, **json.loads(r[0] or "{}")}
    d["sustain"] = r[1] if r[1] is not None else 0.3
    return d


def set_prefs(sid: str, prefs: dict, sustain: float) -> None:
    ensure_session(sid)
    with engine.begin() as c:
        c.execute(update(sessions).where(sessions.c.id == sid).values(prefs_json=json.dumps(prefs), sustain=sustain))


def add_event(sid: str, pid: int, event: str) -> None:
    ensure_session(sid)
    with engine.begin() as c:
        c.execute(insert(events).values(session_id=sid, pid=pid, event=event, ts=time.time()))


def set_reaction(sid: str, pid: int, reaction: str | None) -> None:
    ensure_session(sid)
    with engine.begin() as c:
        c.execute(delete(reactions).where((reactions.c.session_id == sid) & (reactions.c.pid == pid)))
        if reaction:
            c.execute(insert(reactions).values(session_id=sid, pid=pid, reaction=reaction, ts=time.time()))


def set_wishlist(sid: str, pid: int, on: bool) -> None:
    ensure_session(sid)
    with engine.begin() as c:
        c.execute(delete(wishlist).where((wishlist.c.session_id == sid) & (wishlist.c.pid == pid)))
        if on:
            c.execute(insert(wishlist).values(session_id=sid, pid=pid, ts=time.time()))


def get_wishlist(sid: str) -> list[int]:
    with engine.begin() as c:
        return [r[0] for r in c.execute(select(wishlist.c.pid).where(wishlist.c.session_id == sid).order_by(wishlist.c.ts.desc()))]


def get_reactions(sid: str) -> dict[int, str]:
    with engine.begin() as c:
        return {r[0]: r[1] for r in c.execute(select(reactions.c.pid, reactions.c.reaction).where(reactions.c.session_id == sid))}


def get_views(sid: str) -> dict[int, int]:
    with engine.begin() as c:
        rows = c.execute(select(events.c.pid, func.count()).where((events.c.session_id == sid) & (events.c.event.in_(("view", "click")))).group_by(events.c.pid))
        return {r[0]: r[1] for r in rows}


def stats() -> dict:
    with engine.begin() as c:
        return {"sessions": c.execute(select(func.count()).select_from(sessions)).scalar(),
                "events": c.execute(select(func.count()).select_from(events)).scalar(),
                "reactions": c.execute(select(func.count()).select_from(reactions)).scalar(),
                "wishlist_items": c.execute(select(func.count()).select_from(wishlist)).scalar()}


def build_events(sid: str) -> dict[int, float]:
    """Collapse the user's behaviour into a signed weight per product (used by the recommender)."""
    from .services.recommender import EVENT_WEIGHTS
    ev: dict[int, float] = {}
    for pid, n in get_views(sid).items():
        ev[pid] = min(n, 3) * EVENT_WEIGHTS["view"]
    for pid, r in get_reactions(sid).items():
        ev[pid] = ev.get(pid, 0) * 0 + EVENT_WEIGHTS[r]
    for pid in get_wishlist(sid):
        ev[pid] = max(ev.get(pid, 0), 0) + EVENT_WEIGHTS["wishlist"]
    return ev
