"""Stage 1 - ingest raw Amazon Fashion (2023) JSONL.gz files, clean, derive features, write Parquet.

Raw  : data/raw/meta_Amazon_Fashion.jsonl.gz  (826k products)
       data/raw/Amazon_Fashion.jsonl.gz       (2.5M reviews)
Out  : data/processed/products.parquet, interactions.parquet, reviews.parquet, quality_report.json

DuckDB streams the gzipped JSON directly (no full load into RAM). Run: python pipeline/01_ingest_clean.py
"""
from __future__ import annotations
import json, sys, time, re
from pathlib import Path
import duckdb, pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import taxonomy as tx

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)
META, REV = RAW / "meta_Amazon_Fashion.jsonl.gz", RAW / "Amazon_Fashion.jsonl.gz"
MIN_USER_INTERACTIONS, MIN_ITEM_INTERACTIONS = 2, 3  # k-core thresholds (documented)

report: dict = {}
t0 = time.time()
WORK = ROOT / "data" / "work"; WORK.mkdir(exist_ok=True)
(WORK / "ingest.duckdb").unlink(missing_ok=True)
con = duckdb.connect(str(WORK / "ingest.duckdb"))  # on-disk DB: laptop-safe, spills instead of OOM
con.execute("PRAGMA threads=4"); con.execute("PRAGMA memory_limit='2GB'")
con.execute(f"PRAGMA temp_directory='{(WORK / 'tmp').as_posix()}'")

# ---------------------------------------------------------------- raw products
con.execute(f"""
CREATE TABLE meta_raw AS SELECT * FROM read_json('{META.as_posix()}',
  maximum_object_size=20000000, format='newline_delimited',
  columns={{title:'VARCHAR', average_rating:'DOUBLE', rating_number:'BIGINT', features:'VARCHAR[]',
           description:'VARCHAR[]', price:'VARCHAR', store:'VARCHAR', parent_asin:'VARCHAR', details:'JSON',
           images:'STRUCT(thumb VARCHAR, large VARCHAR, hi_res VARCHAR, variant VARCHAR)[]'}})
""")
report["raw_products"] = con.execute("SELECT count(*) FROM meta_raw").fetchone()[0]

con.execute("""
CREATE TABLE meta_clean AS
SELECT parent_asin AS asin, trim(title) AS title, nullif(trim(store),'') AS brand,
       average_rating AS avg_rating_meta, rating_number AS n_ratings_meta,
       TRY_CAST(regexp_extract(price, '([0-9]+\\.?[0-9]*)', 1) AS DOUBLE) AS price,
       features, description, json_extract_string(details,'$.Department') AS dept,
       json_extract_string(details,'$.Material') AS detail_material,
       json_extract_string(details,'$."Date First Available"') AS first_available,
       images[1].large AS image_large, images[1].thumb AS image_thumb, images[1].hi_res AS image_hires,
       len(images) AS n_images
FROM meta_raw
WHERE parent_asin IS NOT NULL AND title IS NOT NULL AND length(trim(title)) >= 8
  AND len(images) > 0 AND images[1].large IS NOT NULL
""")
report["products_with_title_and_image"] = con.execute("SELECT count(*) FROM meta_clean").fetchone()[0]
# prices must be positive and plausible
con.execute("UPDATE meta_clean SET price = NULL WHERE price <= 0 OR price > 5000")

# duplicate listings: same title + brand -> keep the one with most ratings
con.execute("""
CREATE TABLE dedup_map AS
SELECT asin, first_value(asin) OVER (PARTITION BY lower(title), coalesce(brand,'') ORDER BY n_ratings_meta DESC NULLS LAST, asin) AS keep_asin
FROM meta_clean
""")
report["duplicate_listings_merged"] = con.execute("SELECT count(*) FROM dedup_map WHERE asin<>keep_asin").fetchone()[0]

# ---------------------------------------------------------------- reviews -> interactions
con.execute(f"""
CREATE TABLE rev_raw AS SELECT user_id, parent_asin, rating, timestamp AS ts, helpful_vote, verified_purchase
FROM read_json('{REV.as_posix()}', format='newline_delimited',
  columns={{rating:'DOUBLE', parent_asin:'VARCHAR', user_id:'VARCHAR',
           timestamp:'BIGINT', helpful_vote:'BIGINT', verified_purchase:'BOOLEAN'}})
""")
report["raw_reviews"] = con.execute("SELECT count(*) FROM rev_raw").fetchone()[0]

con.execute("""
CREATE TABLE rev1 AS
SELECT r.user_id, d.keep_asin AS asin, r.rating, to_timestamp(r.ts/1000.0) AS ts,
       r.helpful_vote, r.verified_purchase
FROM rev_raw r JOIN dedup_map d ON d.asin = r.parent_asin
WHERE r.user_id IS NOT NULL AND r.rating BETWEEN 1 AND 5 AND r.ts BETWEEN 788918400000 AND 1735689600000
""")
report["reviews_on_valid_products"] = con.execute("SELECT count(*) FROM rev1").fetchone()[0]
# one interaction per (user, item): keep the latest
con.execute("""
CREATE TABLE inter AS
SELECT * EXCLUDE rn FROM (SELECT *, row_number() OVER (PARTITION BY user_id, asin ORDER BY ts DESC) rn FROM rev1) WHERE rn=1
""")
report["duplicate_user_item_removed"] = report["reviews_on_valid_products"] - con.execute("SELECT count(*) FROM inter").fetchone()[0]

# iterative k-core
con.execute("CREATE TABLE core AS SELECT * FROM inter")
for i in range(100):
    n0 = con.execute("SELECT count(*) FROM core").fetchone()[0]
    con.execute(f"""CREATE OR REPLACE TABLE core AS SELECT * FROM core
        WHERE user_id IN (SELECT user_id FROM core GROUP BY 1 HAVING count(*)>={MIN_USER_INTERACTIONS})
          AND asin IN (SELECT asin FROM core GROUP BY 1 HAVING count(*)>={MIN_ITEM_INTERACTIONS})""")
    if con.execute("SELECT count(*) FROM core").fetchone()[0] == n0:
        break
report["kcore"] = {"min_user": MIN_USER_INTERACTIONS, "min_item": MIN_ITEM_INTERACTIONS,
                   "rounds": i + 1}

# catalogue = products that survive the core; reviews table = ALL cleaned reviews on catalogue items (for text analytics)
con.execute("CREATE TABLE cat_items AS SELECT DISTINCT asin FROM core")
con.execute("""CREATE TABLE interactions AS SELECT user_id, asin, rating, ts, helpful_vote FROM core ORDER BY ts""")
con.execute("CREATE TABLE core_pairs AS SELECT user_id, asin, ts FROM core")
con.execute("CREATE TABLE asin_map AS SELECT d.asin AS raw_asin, d.keep_asin FROM dedup_map d JOIN cat_items c ON c.asin=d.keep_asin")
con.execute(f"""CREATE TABLE reviews AS
  SELECT m.keep_asin AS asin, r.user_id, r.rating, to_timestamp(r.timestamp/1000.0) AS ts, r.helpful_vote, r.verified_purchase,
         left(coalesce(r.title,'') || '. ' || r.text, 1200) AS text
  FROM read_json('{REV.as_posix()}', format='newline_delimited',
    columns={{rating:'DOUBLE', title:'VARCHAR', text:'VARCHAR', parent_asin:'VARCHAR', user_id:'VARCHAR',
             timestamp:'BIGINT', helpful_vote:'BIGINT', verified_purchase:'BOOLEAN'}}) r
  JOIN asin_map m ON m.raw_asin = r.parent_asin
  WHERE r.text IS NOT NULL AND length(r.text) > 3 AND r.rating BETWEEN 1 AND 5""")

prod = con.execute("""SELECT m.* FROM meta_clean m JOIN cat_items c USING(asin) JOIN dedup_map d ON d.asin=m.asin AND d.keep_asin=m.asin""").df()
inter = con.execute("SELECT * FROM interactions").df()
rev = con.execute("SELECT * FROM reviews").df()
report["catalogue_after_core"] = len(prod)
report["interactions_after_core"] = len(inter)
report["users_after_core"] = int(inter.user_id.nunique())

# ---------------------------------------------------------------- feature engineering (pandas)
def join(x): return " ".join(x) if x is not None and len(x) else ""
prod["features_text"] = prod["features"].apply(join)
prod["description_text"] = prod["description"].apply(join)
art = prod["title"].apply(tx.classify)
prod["article_type"] = art.str[0]
prod["category_group"] = art.str[1]
prod["gender"] = [tx.gender(t, d) for t, d in zip(prod.title, prod.dept)]
prod["colour"] = prod["title"].apply(tx.colour)
full_text = prod.title + " " + prod.features_text + " " + prod.description_text + " " + prod.detail_material.fillna("")
prod["materials"] = full_text.apply(tx.materials)
prod["brand"] = prod.brand.fillna("Unknown").str.replace(r"^(Brand|Visit the|Store):?\s*", "", regex=True).str.replace(r"\s+Store$", "", regex=True)
prod["n_ratings_cat"] = prod.asin.map(inter.groupby("asin").size()).fillna(0).astype(int)
prod["n_ratings"] = prod[["n_ratings_meta", "n_ratings_cat"]].max(axis=1).astype(int)
prod["avg_rating"] = prod.avg_rating_meta.fillna(prod.asin.map(inter.groupby("asin").rating.mean()))
prod["first_available"] = pd.to_datetime(prod.first_available, errors="coerce", format="%B %d, %Y")
prod["text_for_model"] = (prod.title + ". " + prod.article_type + " " + prod.gender + " " + prod.colour.fillna("") + " "
                          + prod.features_text + " " + prod.description_text.str[:600]).str.replace(r"\s+", " ", regex=True)
prod["materials"] = prod["materials"].apply(lambda m: ",".join(m))
prod = prod.drop(columns=["features", "description", "detail_material", "avg_rating_meta", "n_ratings_meta", "dept"])
prod.insert(0, "pid", range(len(prod)))

# map asin -> pid, finalize interactions
amap = dict(zip(prod.asin, prod.pid))
inter["pid"] = inter.asin.map(amap)
uids = {u: i for i, u in enumerate(inter.user_id.unique())}
inter["uid"] = inter.user_id.map(uids)
inter = inter[["uid", "pid", "rating", "ts", "helpful_vote"]].sort_values("ts").reset_index(drop=True)
rev["pid"] = rev.asin.map(amap)
rev = rev.dropna(subset=["pid"]).astype({"pid": int})[["pid", "rating", "ts", "helpful_vote", "verified_purchase", "text"]]

report["priced_products"] = int(prod.price.notna().sum())
report["missing_price_pct"] = round(100 * float(prod.price.isna().mean()), 2)
report["missing_colour_pct"] = round(100 * float(prod.colour.isna().mean()), 2)
report["other_category_pct"] = round(100 * float((prod.article_type == "Other").mean()), 2)
report["reviews_with_text"] = len(rev)
report["time_range"] = [str(inter.ts.min()), str(inter.ts.max())]
report["sparsity_pct"] = round(100 * (1 - len(inter) / (inter.uid.nunique() * inter.pid.nunique())), 4)
report["elapsed_sec"] = round(time.time() - t0, 1)

prod.to_parquet(OUT / "products.parquet", index=False)
inter.to_parquet(OUT / "interactions.parquet", index=False)
rev.to_parquet(OUT / "reviews.parquet", index=False)
(OUT / "quality_report.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
