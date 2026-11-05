# Demo guide (5–7 minutes)

## Start
```powershell
cd "C:\basicallyD\College\4th Year\Sem 7\BDSMA\Project"
./start.ps1          # API :8000 and app :5173  (or start each manually, see README)
```
Open http://localhost:5173 (first load of the API takes ~15 s while models load). Use a fresh browser profile/Incognito to demo the cold start.

## Suggested sequence
| Time | Do | Expected / say |
|---|---|---|
| 0:00 | **Home** | Real Amazon Fashion products. “No signals yet — showing popularity”: this is the **cold-start fallback** (Bayesian popularity). |
| 0:45 | **My style** → pick *Watches*, *Men*, set longevity slider → Save → **For you** | Badge “Preference-based”; list is all watches; each card carries a reason (“Matches your preferences…”, longevity facts). Preferences solve cold start. |
| 1:45 | On a card tap 👍 on 2–3 sneakers/boots (use **Shop**, filter *Boots*) then go to **For you** | Badge becomes **Personalised hybrid**; list shifts toward boots; reasons now say *“Similar style to … you showed interest in”* or *“Shoppers who liked … also liked this”*. Click **Show score breakdown** to see content / CF / preference / popularity parts. 👎 an item: similar items sink. |
| 3:00 | Drag the **sustainability slider** 0 → 80% | List re-ranks live; the longevity badges rise; open Sustainability page for the trade-off curve (up to λ≈0.4 longevity improves at no accuracy cost). |
| 3:45 | Open a **product page** | Longevity breakdown with evidence %, reviewer sentiment donut (VADER), “Longer-lasting alternatives”, and — after saving a similar item to the wishlist — the **“You may already have something like this”** own-before-buy notice. |
| 4:45 | **Trends** | Review activity per category over time, emerging categories, rising phrases, sentiment validity (ρ = 0.52 with star ratings, 91 % pos/neg agreement). Second tab: social-post analyser — banner clearly says SYNTHETIC; upload `data/social/synthetic_demo_posts.csv` to show the CSV import. |
| 5:45 | **Model & data** | Dataset counts, data-quality report, dashboard charts, evaluation table (hybrid vs baselines) and the honest caveats, benchmark (pandas vs DuckDB 9.9×). |

## ML explained (for the viva)
* **Content-based**: TF-IDF (unigrams+bigrams, sublinear tf) of title/features/description, concatenated with weighted one-hot type/gender/colour/group, L2-normalised; item–item cosine; top-40 neighbours kept (sparse). A user profile is the weighted sum of neighbour rows of the items they interacted with.
* **Collaborative (item-kNN)**: binary/weighted user–item matrix → cosine with additive shrinkage `co/(√nᵢnⱼ+2)` to damp low-support pairs. Explainable: “people who liked X also liked Y”. Compared with truncated-SVD MF (64 factors), which did poorly on this extreme sparsity.
* **Hybrid**: linear blend of content, CF and popularity with weights chosen by grid-search on a **validation** window (0.2/0.2/0.3); preference score added for new users; dislikes subtract.
* **Cold start**: no history → onboarding preferences + popularity prior; new items → content similarity only.
* **Sustainability-aware ranking**: `final = (1−λ)·relevance + λ·longevity`, with longevity shrunk by evidence; then **MMR** diversification.
* **Evaluation**: chronological split (no leakage: models and popularity use only the past), relevant = ≥4★ in the test window, history excluded; P@10, R@10, NDCG@10, coverage, intra-list diversity, latency; paired bootstrap CI.

## Likely viva questions
1. **Why is popularity so strong, and what did your hybrid add?** Review data is >99.99 % sparse and heavy-tailed; best-sellers attract most future reviews. Hybrid ≈ popularity on NDCG (CI spans 0) but personalised and covers 25 % of the catalogue vs ≈0 %; both pure content and pure CF are far below it alone.
2. **How did you avoid leakage?** Global time split; similarity matrices, popularity and tuning use only earlier data; content features come from item text only; weights tuned on validation, test touched once. Caveat: the longevity score uses review text across all time (documented), so the λ table is descriptive.
3. **Is the sustainability score real?** No — it is a transparent *proxy* (ratings + durability/fit/versatility review signals). No carbon/material data exists in the dataset, so none is claimed; confidence is shown per item.
4. **Why not a real social-media dataset?** None is openly downloadable without restricted APIs/scraping. Real trends/sentiment use timestamped reviews (labelled as such); a CSV importer + labelled synthetic demo demonstrates the social pipeline.
5. **What makes this “Big Data”?** 2.5 M reviews / 292 MB gz streamed through DuckDB (9.9× faster than chunked pandas), Parquet storage, batch similarity computation in chunks, sparse top-K representation — on one laptop; no distributed processing is claimed.
6. **How do you handle new users/items?** See cold start above.
7. **Why VADER?** Fast, lexicon-based, explainable and CPU-only; validated against star ratings (Spearman 0.52; 91 % agreement where non-neutral and ≠3★). Limitation: no sarcasm/domain adaptation.
8. **How do likes change recommendations?** Events are weighted (like 1, wishlist 1.5, view 0.25, dislike −1), turned into a sparse profile, multiplied by the neighbour matrices (`u·C`, `u·K`) at request time (~14 ms), seen items removed.

## Troubleshooting
* Blank page / “Is the API running” box → start the API (port 8000) first.
* Port busy → `Get-NetTCPConnection -LocalPort 8000` and stop the process.
* Some product images may not load (hot-linked); a placeholder is shown.
