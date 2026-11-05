# Thread — Implementation Walkthrough and Demo Playbook

A plain-language guide to how the project works, why each choice was made, and exactly how to demo it.
Companion docs: `README.md` (overview and results), `ARCHITECTURE.md` (diagrams), `DEMO_GUIDE.md` (short script).

---

## 1. One-paragraph summary

Thread is a fashion recommender built on **real Amazon Reviews 2023 (Fashion)** data. An offline **pipeline** cleans 2.5M raw reviews with DuckDB, derives product attributes, sentiment, trends and a sustainability ("longevity") proxy, and builds similarity models. A **FastAPI backend** loads those artifacts and computes recommendations live. A **React frontend** gives a shop, a personalised "For you" feed, and analytics pages. The user state (likes, wishlist, preferences) lives in **SQLite**; no Supabase is needed.

## 2. Folder map

```
Project/
├─ pipeline/            offline batch jobs (run once, in order)
│   ├─ 00_download.py       fetch raw Amazon files into data/raw
│   ├─ 01_ingest_clean.py   DuckDB ingest, clean, dedupe, k-core -> Parquet
│   ├─ 02_text_features.py  VADER sentiment, review signals, longevity proxy, trends
│   ├─ 03_social.py         social CSV analyser + SYNTHETIC demo dataset
│   ├─ 04_train_evaluate.py similarity models, chronological evaluation, tuning
│   ├─ 05_benchmark.py      pandas vs DuckDB benchmark
│   ├─ taxonomy.py          rule-based type/gender/colour/material from titles
│   └─ text_analytics.py    sentiment + regex signal helpers
├─ data/
│   ├─ raw/                 downloaded gz files (git-ignored)
│   ├─ processed/           Parquet + analytics/*.json
│   ├─ models/              content_topk.npz, cf_topk.npz, features.npz, config.json
│   ├─ social/              synthetic_demo_posts.csv
│   └─ app.db               SQLite user state (created on first run)
├─ backend/app/
│   ├─ main.py, config.py, db.py, store.py, schemas.py
│   ├─ routers/             catalog.py, user.py, analytics.py
│   └─ services/            recommender.py, similarity.py, features.py
├─ backend/tests/           34 pytest tests
├─ frontend/src/            React pages, components, api client, 4 vitest tests
├─ supabase/schema.sql      optional Postgres schema (not needed)
├─ start.ps1, run_pipeline.ps1, requirements.txt, .env.example
```

## 3. Data layer

| Step | What happens | Result |
|---|---|---|
| Download | Amazon Fashion metadata + reviews (no login needed) | 826,108 products, 2,500,939 reviews |
| Clean | Require title and image; keep prices 0–5000; drop bad timestamps; merge duplicate listings (same title+brand); collapse duplicate user-item reviews | 55,420 duplicate listings merged |
| k-core | Iteratively keep users with ≥2 and items with ≥3 interactions | 26,809 products, 170,676 interactions, 70,813 users |
| Reviews | Review texts joined only for catalogue items | 838,147 texts |

Key points to say out loud:
- DuckDB streams the gzip JSON with a 2 GB memory cap, so a laptop can process it.
- The source `categories` field is empty, so article type, gender, colour and material are **derived from title keywords** with word-boundary regexes. About 6.5% stay "Other"; some errors exist.
- Only 12% of products have a price. Missing prices are shown as "Price n/a", never imputed.

## 4. Analytics layer (pipeline stage 02 and 03)

- **Sentiment:** VADER on 838k review texts. Validated against star ratings (Spearman 0.52; 91% agreement where VADER is non-neutral and the rating isn't 3 stars).
- **Review signals:** regexes count durability praise/complaints, fit/return complaints, and "goes with everything" versatility mentions.
- **Longevity score (SDG 12 proxy):** `0.30 quality + 0.30 durability + 0.25 fit reliability + 0.15 versatility`. Each rate is shrunk toward the catalogue mean (empirical Bayes, K=8), and items with few reviews are pulled toward the mean by `confidence = min(1, reviews/15)`.
  This is a **heuristic proxy**. The dataset has no carbon, material or certification data, so none is shown.
- **Trends:** review volume per category over time, emerging categories, rising phrases.
- **Social:** `03_social.py` analyses any CSV (hashtags, sentiment, volume). The bundled dataset is **synthetic and labelled so everywhere**. Real trends in the UI come from reviews and are labelled as reviews.

## 5. Recommendation engine (`backend/app/services/recommender.py`)

Inputs per request: the guest's events (view 0.25, like 1.0, wishlist 1.5, dislike −1), saved preferences (types, genders, colours, max price), and the sustainability weight λ.

1. **Content similarity:** TF-IDF (1–2 grams) of title/features/description, joined with weighted one-hot type/gender/colour/group, L2-normalised. Cosine similarity, keeping the top 40 neighbours per item (sparse matrix).
2. **Collaborative filtering:** item-item cosine with shrinkage `co / (sqrt(ni*nj) + 2)` to damp pairs with little support.
3. **Profile scoring:** user vector `u` (event weights) multiplied by each neighbour matrix: `content = u·C`, `cf = u·K`. One sparse mat-vec, about 14 ms.
4. **Relevance:** `wc·content + wk·cf + wp·pref + popularity − dislike penalty`. Weights (0.2/0.2/0.3, pref 0.12) were tuned on a validation window.
5. **Cold start:** no history uses preferences plus Bayesian popularity (`sqrt(n) × rating/5`). New items are reachable through content similarity.
6. **Sustainability blend:** `final = (1−λ)·relevance + λ·longevity`.
7. **MMR diversification** on content vectors so the list is not one repeated item type.
8. **Explanations:** generated from the real top contributor ("Similar style to X you showed interest in", "Shoppers who liked X also liked this", preference match, longevity facts).
9. **Own-before-buy and alternatives:** on a product page, if a wishlisted item is very similar, a notice appears; higher-longevity similar items are suggested.

## 6. Evaluation (stage 04)

Global chronological split: train < 80th percentile of time, validation 80–90%, test ≥ 90%. Models and popularity use only the past. Relevant = rating ≥ 4 in the test window; history excluded. 5,926 test users, K=10.

| Model | P@10 | R@10 | NDCG@10 | Coverage |
|---|---|---|---|---|
| Random | 0.0000 | 0.0003 | 0.0002 | 13.9% |
| Popularity | 0.0029 | 0.0283 | 0.0181 | ~0% |
| Content | 0.0010 | 0.0090 | 0.0051 | 67.9% |
| Item-kNN | 0.0019 | 0.0179 | 0.0084 | 54.0% |
| SVD | 0.0001 | 0.0011 | 0.0005 | 62.3% |
| **Hybrid** | 0.0032 | 0.0310 | 0.0183 | 25.5% |

**Honest reading:** on >99.99% sparse data popularity is very strong. Hybrid vs popularity NDCG difference has a 95% bootstrap CI of [−0.0011, +0.0015], so accuracy is a statistical tie. The hybrid's value is personalisation and catalogue coverage. Sustainability: λ from 0 to 0.4 lifts average longevity 61.5 → 65.7 with no NDCG loss; at λ=0.8 accuracy drops sharply.

Big-data benchmark (per-product mean rating over 2.5M reviews): pandas chunked 55.5 s / 351 MB vs DuckDB 5.6 s / 491 MB, 9.9× faster. Single machine; no distributed processing is claimed.

## 7. Backend API

FastAPI + Pydantic v2. Guest identity is the `X-Session-Id` header (created by `POST /api/session`). User state is stored by SQLAlchemy Core in four tables: `sessions`, `events`, `reactions`, `wishlist`. Catalogue and models are read-only in memory.

Main endpoints: `/api/products`, `/api/facets`, `/api/products/{pid}`, `/api/preferences`, `/api/interactions`, `/api/wishlist`, `/api/recommendations`, `/api/trends`, `/api/sentiment`, `/api/sustainability`, `/api/social/demo`, `/api/social/analyse`, `/api/dashboard`, `/api/evaluation`, `/api/datasets`. Interactive docs at `/docs`.

## 8. Frontend pages

| Route | Purpose |
|---|---|
| `/` Home | Popular picks (cold start), category entry points |
| `/shop` | Search, 8 filters, 6 sorts, pagination |
| `/product/:id` | Detail, "Built to last" rating, customer-review donut, related items, longer-lasting alternatives, own-before-buy notice |
| `/for-you` | Personalised feed, mode badge, reasons, "built to last" slider |
| `/me` ("My style") | Preferences, wishlist, reactions |
| `/trends` | Customer-review trends: categories over time, emerging categories, rising phrases |
| `/sustainability` | Customer-facing "Buy less, wear longer" page: tips, most durable categories, top picks |
| `/insights` ("About our data", footer link) — technical page: dataset, dashboard, evaluation, durability method and slider trade-off, sentiment validity, social-post analyser (CSV upload + synthetic demo) | Dataset counts, quality report, dashboard, evaluation, benchmark |

## 9. Database: SQLite (default) — Supabase not needed

SQLite is the default and needs no setup. The file `data/app.db` is created on first API start and holds only guest sessions, events, reactions and wishlist. To reset all demo state, stop the API and delete `data/app.db`.
Supabase/Postgres is optional (`supabase/schema.sql` + `DATABASE_URL`) and untested; skip it for the demo.

## 10. Setup (one time)

```powershell
cd "C:\basicallyD\College\4th Year\Sem 7\BDSMA\Project"
pip install -r requirements.txt
cd frontend; npm install; cd ..
```
Processed data and models are already in `data/`, so the pipeline does **not** need re-running. To rebuild from scratch (about 25 min, ~500 MB download): `./run_pipeline.ps1`.

## 11. Pre-demo checklist

1. Make sure ports 8000 and 5173 are free (`Get-NetTCPConnection -State Listen -LocalPort 8000,5173`).
2. Optional clean slate: delete `data/app.db`.
3. Run `./start.ps1` (opens two PowerShell windows: API and web).
4. Wait about 15 s for the API to load models, then check http://127.0.0.1:8000/api/health returns JSON.
5. Open http://localhost:5173 in a **fresh Incognito window** (new guest session, so cold start is visible).
6. Optional proof tests: `cd backend; python -m pytest tests -q` (34 pass) and `cd frontend; npm test` (4 pass).
7. Have `data/social/synthetic_demo_posts.csv` ready for upload (used on the "About our data" page).
8. Images are hot-linked from Amazon; if offline a placeholder shows.

## 12. Step-by-step demo (about 8 minutes)

**Step 1 — Framing (30 s).** Say: real Amazon Fashion data, hybrid recommender, trend analytics, SDG 12 durability ranking. Show the nav bar. Tell the teacher the main site is the customer view; technical detail lives behind the footer link "About our data".

**Step 2 — Home and cold start (45 s).** Open Home. Point out real products and the message that there are no signals yet, so popularity is used. Explain Bayesian popularity.

**Step 3 — Catalogue (60 s).** Go to Shop. Search "leather", filter article type *Boots*, change sort, open filters for gender and colour. Note the price filter only affects the 12% with prices.

**Step 4 — Preferences solve cold start (60 s).** Go to My style. Choose *Watches* and *Men*, set the longevity slider, Save. Open For you. The badge shows *Based on your style*; every card has a reason.

**Step 5 — Behaviour changes the feed (90 s).** In Shop, filter *Boots*, press 👍 on 2–3 boots. Open For you: the badge becomes *Made for you* and boots dominate. Read a reason ("Similar style to … you showed interest in"). Press 👎 on an item and refresh: similar items sink. Mention ~14 ms latency.

**Step 6 — SDG 12 slider (60 s).** On For you, drag the sustainability slider 0 → 80%. The list re-ranks and longevity badges rise. Mention it is an estimate from reviews, not an environmental measurement (the full disclaimer is on "About our data").

**Step 7 — Product page and own-before-buy (60 s).** Wishlist a boot, open a similar boot. Show the "Built to last" rating and its breakdown, the customer-review donut, "Longer-lasting alternatives", and the "You may already have something like this" notice.

**Step 8 — Trends (30 s).** Open Trends: review activity by category, emerging categories, rising phrases. This is customer-review data.

**Step 9 — Sustainability page (30 s).** Show the customer-facing page: tips, most durable categories, top durable picks.

**Step 10 — About our data (2 min).** Click the footer link. Show: dataset counts and quality report, dashboard charts, the evaluation table and the benchmark (9.9×), the durability-rating method with its disclaimer and the slider trade-off chart (no accuracy loss up to 40%), and sentiment validity (rho 0.52, 91% agreement). Then the social-post analyser: the banner says SYNTHETIC; upload `data/social/synthetic_demo_posts.csv` to show the CSV import. Say plainly that no real social data is included. Finish: the hybrid ties popularity on accuracy but personalises and covers more of the catalogue.

**Step 11 — Proof (30 s, optional).** Show `/docs` (OpenAPI) and run pytest.

## 13. Likely questions and short answers

- **Why does popularity do so well?** Extremely sparse, heavy-tailed review data. Hybrid ties it on NDCG and adds personalisation and coverage.
- **How was leakage avoided?** Time-based split; similarity, popularity and tuning use only earlier data; test used once. The longevity score uses all-time review text, so the λ table is descriptive.
- **Is sustainability real?** It is a transparent proxy from reviews. No carbon or material data is claimed.
- **Why no real social data?** No open, licensed fashion social dataset; scraping was avoided. A CSV importer plus a labelled synthetic set demonstrate the pipeline.
- **What is "big data" here?** 2.5M reviews streamed through DuckDB and Parquet on one machine, 9.9× faster than chunked pandas. Not distributed.
- **New users and items?** Preferences + popularity for users; content similarity for items.

## 14. Troubleshooting

| Symptom | Fix |
|---|---|
| Blank page or "Is the API running" | Start the API first; wait ~15 s for model load |
| Port busy | `Get-NetTCPConnection -State Listen -LocalPort 8000,5173`, then `Stop-Process -Id <pid> -Force` |
| Memory error running pipeline | Close other apps; run stages individually; do not run pytest at the same time as stage 04 |
| Images missing | Hot-linked from Amazon; placeholder is expected offline |
| Want a clean demo | Stop API, delete `data/app.db`, restart, and use a fresh Incognito window (guest ID is kept in the browser) |

## 15. Stop everything after the demo

Close the two PowerShell windows opened by `start.ps1`, or run:
```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,5173 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## 16. Known limitations

Longevity is a heuristic; only 12% of products have prices; categories are keyword-derived; Amazon reviewers stand in for users; social data is synthetic or user-imported; guest sessions only (no login); mobile layout and a Playwright end-to-end suite were not verified; Supabase path untested.

## 17. Does my data survive a restart?

Yes. Preferences, likes, views and the wishlist are saved in `data/app.db`, and the browser keeps its guest session ID in localStorage (`thread_session`). Restarting the backend or frontend changes nothing, as long as you use the same browser profile.
State resets only if you delete `data/app.db`, clear the browser's site data, or close an Incognito window.
