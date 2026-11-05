"""Hybrid, sustainability-aware recommender.

Signals
  content  : item-item cosine over TF-IDF + attribute one-hots      (u @ C)
  cf       : item-item collaborative cosine from user-item matrix    (u @ K)
  pref     : explicit onboarding preferences (type / gender / colour / budget)
  pop      : Bayesian-rating x log(popularity) prior (cold-start fallback)
Re-ranking
  sustainability blend (user slider lambda) -> MMR diversification -> explanations
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
import scipy.sparse as sp

EVENT_WEIGHTS = {"view": 0.25, "click": 0.25, "like": 1.0, "wishlist": 1.5, "dislike": -1.0}
DEFAULT_WEIGHTS = {"content": 0.50, "cf": 0.30, "pref": 0.12, "pop": 0.08}
CANDIDATES = 300


def _scale(x: np.ndarray) -> np.ndarray:
    m = x.max() if x.size else 0.0
    return x / m if m > 0 else x


@dataclass
class Prefs:
    types: list[str] = field(default_factory=list)
    genders: list[str] = field(default_factory=list)
    colours: list[str] = field(default_factory=list)
    max_price: float | None = None

    def empty(self) -> bool:
        return not (self.types or self.genders or self.colours or self.max_price)


class Recommender:
    def __init__(self, products: pd.DataFrame, C: sp.csr_matrix, K: sp.csr_matrix, F: sp.csr_matrix):
        self.p = products.reset_index(drop=True)
        self.N = len(self.p)
        self.C, self.K, self.F = C.tocsr(), K.tocsr(), F.tocsr()
        self.Ccsc = self.C.tocsc()
        self.Kcsc = self.K.tocsc()
        pop = np.sqrt(self.p.n_ratings.to_numpy(float)) * (self.p.bayes_rating.to_numpy(float) / 5.0)
        self.pop = _scale(pop)
        conf = self.p.sus_confidence.to_numpy(float)
        sc = self.p.sustainability_score.to_numpy(float)
        self.sus_eff = (conf * sc + (1 - conf) * sc.mean()) / 100.0   # low-evidence items shrink to mean
        self._type = self.p.article_type.to_numpy()
        self._gender = self.p.gender.to_numpy()
        self._colour = self.p.colour.fillna("").to_numpy()
        self._price = self.p.price.to_numpy(float)

    # ------------------------------------------------------------------ signals
    def _vec(self, pairs: dict[int, float]) -> sp.csr_matrix:
        if not pairs:
            return sp.csr_matrix((1, self.N), dtype=np.float32)
        idx = np.fromiter(pairs.keys(), int); val = np.fromiter(pairs.values(), np.float32)
        return sp.csr_matrix((val, (np.zeros(len(idx), int), idx)), shape=(1, self.N))

    def pref_score(self, prefs: Prefs) -> np.ndarray:
        s = np.zeros(self.N, np.float32); w = 0.0
        if prefs.types: s += 0.5 * np.isin(self._type, prefs.types); w += 0.5
        if prefs.genders: s += 0.3 * np.isin(self._gender, prefs.genders + ["Unisex"]); w += 0.3
        if prefs.colours: s += 0.2 * np.isin(self._colour, prefs.colours); w += 0.2
        s = s / w if w else s
        if prefs.max_price:
            over = np.nan_to_num(self._price, nan=0) > prefs.max_price
            s = np.where(over, s * 0.4, s)
        return s

    def relevance(self, events: dict[int, float], prefs: Prefs, weights: dict | None = None):
        """Return (rel, parts, u_pos). `events` maps pid -> signed weight."""
        w = {**DEFAULT_WEIGHTS, **(weights or {})}
        pos = {i: min(v, 2.5) for i, v in events.items() if v > 0}
        neg = {i: -v for i, v in events.items() if v < 0}
        u = self._vec(pos)
        parts = {"content": np.zeros(self.N), "cf": np.zeros(self.N), "pref": np.zeros(self.N), "pop": self.pop}
        if pos:
            parts["content"] = _scale((u @ self.C).toarray().ravel())
            parts["cf"] = _scale((u @ self.K).toarray().ravel())
        if not prefs.empty():
            parts["pref"] = self.pref_score(prefs)
        if not pos:   # cold start: preferences (if any) + popularity
            rel = (0.75 * parts["pref"] + 0.25 * self.pop) if not prefs.empty() else self.pop.copy()
        else:
            ww = dict(w)
            if parts["cf"].max() == 0: ww["content"] += ww.pop("cf")  # no CF evidence -> content takes its share
            if prefs.empty(): ww["content"] += ww.get("pref", 0); ww["pref"] = 0
            rel = sum(ww.get(k, 0) * parts[k] for k in ("content", "cf", "pref", "pop"))
        if neg:
            pen = _scale((self._vec(neg) @ self.C).toarray().ravel())
            rel = rel - 0.6 * pen * (rel.max() if rel.max() > 0 else 1)
        return rel, parts, pos

    # ------------------------------------------------------------------ main API
    def recommend(self, events: dict[int, float], prefs: Prefs | None = None, sustain: float = 0.0, k: int = 12,
                  diversity: float = 0.15, mask: np.ndarray | None = None, weights: dict | None = None,
                  exclude: set[int] | None = None) -> list[dict]:
        prefs = prefs or Prefs()
        rel, parts, pos = self.relevance(events, prefs, weights)
        rel = rel.astype(np.float64).copy()
        banned = set(events) | (exclude or set())
        if banned: rel[list(banned)] = -np.inf
        if mask is not None: rel[~mask] = -np.inf
        cand = np.argpartition(-rel, min(CANDIDATES, self.N - 1))[:CANDIDATES]
        cand = cand[np.isfinite(rel[cand])]
        if cand.size == 0: return []
        r = rel[cand]; r = (r - r.min()) / (r.max() - r.min() + 1e-9)
        s = self.sus_eff[cand]; s = (s - s.min()) / (s.max() - s.min() + 1e-9)
        final = (1 - sustain) * r + sustain * s
        picked = self._mmr(cand, final, k, diversity)
        out = []
        for j_local in picked:
            j = int(cand[j_local])
            out.append({"pid": j, "score": float(final[j_local]), "relevance": float(r[j_local]), "sustainability_component": float(s[j_local]),
                        "parts": {kk: float(parts[kk][j]) for kk in ("content", "cf", "pref", "pop")},
                        "reasons": self.explain(j, pos, prefs, parts, sustain)})
        return out

    def _mmr(self, cand: np.ndarray, score: np.ndarray, k: int, div: float) -> list[int]:
        if div <= 0 or len(cand) <= k:
            return list(np.argsort(-score)[:k])
        sim = (self.F[cand] @ self.F[cand].T).toarray()
        chosen = [int(np.argmax(score))]
        while len(chosen) < min(k, len(cand)):
            red = sim[:, chosen].max(axis=1)
            mmr = (1 - div) * score - div * red
            mmr[chosen] = -np.inf
            chosen.append(int(np.argmax(mmr)))
        return chosen

    # ------------------------------------------------------------------ explanations
    def explain(self, j: int, pos: dict[int, float], prefs: Prefs, parts: dict, sustain: float) -> list[dict]:
        row = self.p.iloc[j]
        reasons: list[dict] = []
        if pos:
            ids = np.fromiter(pos.keys(), int); wts = np.fromiter(pos.values(), float)
            c_col = self.Ccsc[:, j].toarray().ravel()[ids] * wts
            k_col = self.Kcsc[:, j].toarray().ravel()[ids] * wts
            ci, ki = int(np.argmax(c_col)), int(np.argmax(k_col))
            if k_col[ki] > 0 and k_col[ki] >= 0.8 * c_col[ci]:
                reasons.append({"type": "collaborative", "text": f"Shoppers who liked “{self._short(ids[ki])}” also liked this", "source_pid": int(ids[ki])})
            if c_col[ci] > 0:
                reasons.append({"type": "content", "text": f"Similar style to “{self._short(ids[ci])}” you showed interest in", "source_pid": int(ids[ci])})
        if not prefs.empty() and parts["pref"][j] > 0.45:
            bits = [x for x in (row.article_type if row.article_type in prefs.types else None,
                                row.gender if row.gender in prefs.genders else None,
                                row.colour if isinstance(row.colour, str) and row.colour in prefs.colours else None) if x]
            reasons.append({"type": "preference", "text": "Matches your preferences: " + " · ".join(bits)})
        # sustainability explanation (always grounded in real fields)
        notes = []
        if row.dur_pos and row.dur_pos > 0: notes.append(f"{int(row.dur_pos)} customer(s) praise its durability or quality")
        if row.dur_neg == 0 and row.n_text_reviews >= 5: notes.append("no durability complaints")
        if row.fit_neg == 0 and row.n_text_reviews >= 5: notes.append("no fit or return complaints")
        if row.neutral_colour: notes.append("neutral colour that goes with more outfits")
        if row.natural_fibre: notes.append("made with natural fibres")
        if notes and (sustain > 0 or row.sustainability_score >= 70):
            reasons.append({"type": "sustainability", "text": f"Built to last ({row.sustainability_score:.0f}/100): " + "; ".join(notes[:3])})
        if not reasons:
            reasons.append({"type": "popular", "text": f"Popular pick: rated {row.avg_rating:.1f}★ by {int(row.n_ratings)} shoppers"})
        return reasons

    def _short(self, pid: int) -> str:
        t = str(self.p.title.iat[int(pid)])
        return t if len(t) <= 60 else t[:57] + "…"

    # ------------------------------------------------------------------ item-to-item
    def similar(self, pid: int, k: int = 8, mask: np.ndarray | None = None) -> list[tuple[int, float]]:
        row = self.C[pid]
        sc = row.toarray().ravel() * 0.6 + self.K[pid].toarray().ravel() * 0.4
        sc[pid] = -1
        if mask is not None: sc[~mask] = -1
        top = np.argpartition(-sc, k)[:k]
        top = top[sc[top] > 0]
        return [(int(i), float(sc[i])) for i in top[np.argsort(-sc[top])]]

    def owned_alternatives(self, pid: int, owned: list[int], thr: float = 0.45) -> list[dict]:
        """Items the user already saved that are similar to `pid` -> 'consider what you already have' nudge."""
        if not owned: return []
        sims = (self.F[pid] @ self.F[owned].T).toarray().ravel()
        return [{"pid": int(o), "similarity": float(s)} for o, s in zip(owned, sims) if s >= thr and o != pid]

    def longevity_alternatives(self, pid: int, k: int = 4) -> list[dict]:
        """Similar items with a higher sustainability proxy score (swap-suggestion)."""
        base = self.sus_eff[pid]
        cands = [(i, s) for i, s in self.similar(pid, 30) if self.sus_eff[i] > base + 0.03]
        cands.sort(key=lambda x: -(x[1] * 0.5 + self.sus_eff[x[0]]))
        return [{"pid": i, "similarity": s, "delta": float(self.sus_eff[i] - base) * 100} for i, s in cands[:k]]
