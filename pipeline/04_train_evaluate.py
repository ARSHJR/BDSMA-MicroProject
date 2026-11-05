"""Stage 4 - build similarity models, evaluate against baselines on a time-based split, save artifacts.

Split (strictly chronological, global):
    train : ts <  T_val          (80th percentile of timestamps)
    val   : T_val <= ts < T_test (used ONLY to tune hybrid weights; models trained on `train`)
    test  : ts >= T_test         (final report; models trained on train+val)
Relevant item = test interaction with rating >= 4. Items the user already has in history are never recommended.
Run: python pipeline/04_train_evaluate.py
"""
from __future__ import annotations
import itertools, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd, scipy.sparse as sp
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.features import build_content_matrix
from app.services.similarity import topk_cosine, item_cf_topk
from app.services.recommender import Recommender, Prefs

P, M, A = ROOT / "data" / "processed", ROOT / "data" / "models", ROOT / "data" / "processed" / "analytics"
M.mkdir(exist_ok=True, parents=True); A.mkdir(exist_ok=True, parents=True)
K_REC, TOPK = 10, 40
t0 = time.time()

prod = pd.read_parquet(P / "products_enriched.parquet").sort_values("pid").reset_index(drop=True)
assert (prod.pid.to_numpy() == np.arange(len(prod))).all()
inter = pd.read_parquet(P / "interactions.parquet")
inter["ts"] = pd.to_datetime(inter.ts, utc=True)
N = len(prod)

# ------------------------------------------------------------------ content features (no interaction data -> no leakage)
F, _ = build_content_matrix(prod)
print("content matrix", F.shape, round(time.time() - t0, 1), "s")
t = time.time(); C = topk_cosine(F, TOPK); content_build_s = time.time() - t
print("content top-k built in", round(content_build_s, 1), "s")


def weight(r):  # implicit-feedback weights from ratings
    return np.where(r >= 4, 1.0, np.where(r == 3, 0.3, 0.0)).astype(np.float32)


def user_item(df: pd.DataFrame, n_users: int) -> sp.csr_matrix:
    w = weight(df.rating.to_numpy())
    m = w > 0
    return sp.csr_matrix((w[m], (df.uid.to_numpy()[m], df.pid.to_numpy()[m])), shape=(n_users, N))


n_users = int(inter.uid.max()) + 1
T_val, T_test = inter.ts.quantile(0.80), inter.ts.quantile(0.90)
print("T_val", T_val, "T_test", T_test)


def topn(S: np.ndarray, seen: sp.csr_matrix, n: int) -> np.ndarray:
    S = S.copy(); S[seen.nonzero()] = -np.inf
    idx = np.argpartition(-S, n, axis=1)[:, :n]
    order = np.argsort(-np.take_along_axis(S, idx, 1), axis=1)
    return np.take_along_axis(idx, order, 1)


def metrics(recs: np.ndarray, truth: list[set], k: int, F_: sp.csr_matrix) -> dict:
    prec, rec, ndcg = [], [], []
    disc = 1 / np.log2(np.arange(2, k + 2))
    for r, t_ in zip(recs, truth):
        hit = np.array([i in t_ for i in r[:k]], float)
        prec.append(hit.sum() / k); rec.append(hit.sum() / len(t_))
        idcg = disc[:min(len(t_), k)].sum(); ndcg.append((hit * disc).sum() / idcg)
    # intra-list diversity (1 - mean pairwise cosine on content vectors)
    ild = []
    for r in recs[:1500]:
        V = F_[r[:k]]; s = (V @ V.T).toarray(); ild.append(1 - (s.sum() - np.trace(s)) / (k * (k - 1)))
    return {"precision@k": float(np.mean(prec)), "recall@k": float(np.mean(rec)), "ndcg@k": float(np.mean(ndcg)),
            "coverage": float(len(np.unique(recs[:, :k])) / N), "diversity_ild": float(np.mean(ild)),
            "_ndcg_per_user": ndcg}


def run_split(train: pd.DataFrame, test: pd.DataFrame, hyb_grid=None, tune_weights=None):
    """Train models on `train`, evaluate on `test`. Returns metrics per model."""
    rel = test[test.rating >= 4]
    users = np.array(sorted(set(rel.uid) & set(train.uid)))
    truth = [set(g.pid) for _, g in rel[rel.uid.isin(users)].groupby("uid")]
    users = np.array(sorted(rel[rel.uid.isin(users)].uid.unique()))
    X = user_item(train, n_users)
    seen_all = X
    t = time.time(); Kcf = item_cf_topk(X, TOPK); cf_s = time.time() - t
    svd = TruncatedSVD(64, random_state=0).fit(X); V = normalize(svd.components_.T.astype(np.float32))
    pop = np.sqrt(np.asarray((X > 0).sum(0)).ravel()).astype(np.float32); pop /= pop.max()
    info = {"n_eval_users": int(len(users)), "n_train_interactions": int(len(train)), "n_test_positive_interactions": int(len(rel[rel.uid.isin(users)])),
            "test_item_unseen_in_train_pct": round(100 * float(np.isin(rel[rel.uid.isin(users)].pid, train.pid, invert=True).mean()), 1),
            "cf_build_seconds": round(cf_s, 2)}

    def batch(fn):
        out = []
        for s in range(0, len(users), 400):
            u = users[s:s + 400]; W = X[u]
            out.append(topn(fn(W), W, K_REC))
        return np.vstack(out)

    def sc(Mx, W): 
        D = (W @ Mx).toarray() if sp.issparse(Mx) else np.asarray(W @ Mx)
        mx = D.max(1, keepdims=True); mx[mx == 0] = 1; return D / mx
    def svd_scores(W):
        S = np.asarray((W @ V) @ V.T); mx = S.max(1, keepdims=True); mx[mx <= 0] = 1; return S / mx
    models = {
        "Random": lambda W: np.random.default_rng(0).random((W.shape[0], N)),
        "Popularity (baseline)": lambda W: np.tile(pop, (W.shape[0], 1)),
        "Content-based (TF-IDF cosine)": lambda W: sc(C, W),
        "Item-kNN collaborative": lambda W: sc(Kcf, W) + 1e-6 * pop,
        "SVD matrix factorisation (64)": lambda W: svd_scores(W),
    }
    def hybrid(wc, wk, wp):
        return lambda W: wc * sc(C, W) + wk * sc(Kcf, W) + wp * pop
    if tune_weights is None:
        res_grid = {}
        for wc, wk, wp in itertools.product([0.2, 0.5], [0.2, 0.5, 1.0], [0.1, 0.3, 0.6, 1.0, 1.5]):
            r = batch(hybrid(wc, wk, wp)); res_grid[(wc, wk, wp)] = metrics(r, truth, K_REC, F)["ndcg@k"]
        best = max(res_grid, key=res_grid.get); info["grid"] = {str(k): round(v, 5) for k, v in res_grid.items()}; info["best_weights"] = best
    else:
        best = tune_weights
    models["Hybrid (content + CF + popularity)"] = hybrid(*best)
    out = {}
    for name, fn in models.items():
        t = time.time(); recs = batch(fn); dt = time.time() - t
        m = metrics(recs, truth, K_REC, F); m["ms_per_user_batch"] = round(1000 * dt / len(users), 3); out[name] = m
        print(f"  {name:38s} P@10={m['precision@k']:.4f} R@10={m['recall@k']:.4f} NDCG@10={m['ndcg@k']:.4f} cov={m['coverage']:.3f} ild={m['diversity_ild']:.3f}")
    # sustainability trade-off on top of the hybrid
    sus = prod.sustainability_score.to_numpy() / 100.0
    conf = prod.sus_confidence.to_numpy(); sus_eff = (conf * sus + (1 - conf) * sus.mean())
    tradeoff = []
    hf = hybrid(*best)
    for lam in (0.0, 0.2, 0.4, 0.6, 0.8):
        def f(W, lam=lam):
            r = hf(W); r = (r - r.min(1, keepdims=True)) / (r.max(1, keepdims=True) - r.min(1, keepdims=True) + 1e-9)
            return (1 - lam) * r + lam * ((sus_eff - sus_eff.min()) / (sus_eff.max() - sus_eff.min()))
        recs = batch(f); m = metrics(recs, truth, K_REC, F)
        tradeoff.append({"lambda": lam, "ndcg@k": m["ndcg@k"], "recall@k": m["recall@k"], "diversity_ild": m["diversity_ild"], "coverage": m["coverage"],
                         "avg_sustainability_score": float(100 * sus[recs[:, :K_REC]].mean()),
                         "avg_item_rating": float(prod.bayes_rating.to_numpy()[recs[:, :K_REC]].mean())})
    ndcgs = {k: np.array(v.pop("_ndcg_per_user")) for k, v in out.items()}
    # paired bootstrap 95% CI of NDCG gain: hybrid vs popularity
    d = ndcgs["Hybrid (content + CF + popularity)"] - ndcgs["Popularity (baseline)"]
    rng = np.random.default_rng(0); bs = [rng.choice(d, len(d)).mean() for _ in range(1000)]
    info["hybrid_minus_popularity_ndcg_ci95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    return out, info, tradeoff, best


print("== tuning on validation (train < T_val)")
tr_v, va = inter[inter.ts < T_val], inter[(inter.ts >= T_val) & (inter.ts < T_test)]
_, info_val, _, best = run_split(tr_v, va)
print("best hybrid weights (content, cf, pop):", best)
print("== final test (train+val < T_test)")
tr_f, te = inter[inter.ts < T_test], inter[inter.ts >= T_test]
res, info_test, tradeoff, _ = run_split(tr_f, te, tune_weights=best)

# ------------------------------------------------------------------ production artifacts (all data)
Xall = user_item(inter, n_users)
Kall = item_cf_topk(Xall, TOPK)
sp.save_npz(M / "content_topk.npz", C); sp.save_npz(M / "cf_topk.npz", Kall); sp.save_npz(M / "features.npz", F)
cfg = {"weights": {"content": float(best[0]), "cf": float(best[1]), "pop": float(best[2]), "pref": 0.12}, "topk": TOPK}
(M / "config.json").write_text(json.dumps(cfg, indent=2))

# ------------------------------------------------------------------ online latency of the full production pipeline
rec = Recommender(prod, C, Kall, F)
rng = np.random.default_rng(1); uids = rng.choice(n_users, 200, replace=False)
g = inter.groupby("uid")
lat = []
for u in uids:
    ev = {int(p): 1.0 for p in g.get_group(u).pid}
    s = time.perf_counter(); rec.recommend(ev, Prefs(), sustain=0.3, k=12); lat.append((time.perf_counter() - s) * 1000)

evaluation = {
    "protocol": "Global chronological split (train < 80th pct time <= val < 90th pct <= test). Weights tuned on val; reported on test. "
                "Relevant = test interactions with rating >= 4; history items excluded from recommendations.",
    "k": K_REC, "split_times": {"val_start": str(T_val), "test_start": str(T_test)},
    "validation_info": {k: v for k, v in info_val.items() if k != "grid"}, "tuning_grid_val_ndcg": info_val.get("grid"),
    "test_info": info_test, "best_weights": {"content": best[0], "cf": best[1], "pop": best[2]},
    "models": res, "sustainability_tradeoff": tradeoff,
    "online_latency_ms": {"mean": float(np.mean(lat)), "p50": float(np.percentile(lat, 50)), "p95": float(np.percentile(lat, 95)),
                          "note": "Full production pipeline incl. sustainability blend, MMR and explanations, single user"},
    "build_seconds": {"content_topk": round(content_build_s, 1), "cf_topk_train": info_test["cf_build_seconds"]},
    "caveats": [
        "Interactions are Amazon review events (explicit ratings turned into implicit feedback) - extremely sparse (>99.99%).",
        "Sustainability scores use review text from the whole period (including the test window); the sustainability trade-off table is descriptive, not a clean held-out result.",
        "Absolute precision/recall are low by nature of sparse fashion data; compare models relatively.",
    ],
}
(A / "evaluation.json").write_text(json.dumps(evaluation, indent=2))
print("saved; total", round(time.time() - t0, 1), "s")
