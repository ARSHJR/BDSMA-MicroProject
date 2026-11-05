"""Stage 5 - processing benchmark: baseline (pandas chunked JSON) vs optimised (DuckDB streaming).

Task (identical for both): per-product review count and mean rating over all 2.5M raw reviews (292 MB gz).
Each method runs in its own subprocess so peak RSS is measured fairly. NOTE: both run single-machine; no
distributed processing is claimed.   Run: python pipeline/05_benchmark.py
"""
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REV = (ROOT / "data" / "raw" / "Amazon_Fashion.jsonl.gz").as_posix()


def run_pandas():
    import pandas as pd
    acc = None
    for ch in pd.read_json(REV, lines=True, chunksize=50_000, dtype={"rating": "float32"}):
        g = ch.groupby("parent_asin").rating.agg(["count", "sum"])
        acc = g if acc is None else acc.add(g, fill_value=0)
    out = (acc["sum"] / acc["count"])
    return {"products": int(len(out)), "check": round(float(out.mean()), 6)}


def run_duckdb():
    import duckdb
    con = duckdb.connect()
    r = con.execute(f"""select count(*), avg(m) from (select parent_asin, avg(rating) m from read_json('{REV}', format='newline_delimited',
        columns={{parent_asin:'VARCHAR', rating:'DOUBLE'}}) group by 1)""").fetchone()
    return {"products": int(r[0]), "check": round(float(r[1]), 6)}


if len(sys.argv) > 1:
    t = time.perf_counter(); res = {"pandas": run_pandas, "duckdb": run_duckdb}[sys.argv[1]]()
    print(json.dumps({**res, "seconds": time.perf_counter() - t})); sys.exit()

import psutil
results = {}
for name in ("pandas", "duckdb"):
    p = subprocess.Popen([sys.executable, "-I", __file__, name], stdout=subprocess.PIPE, text=True)
    ps, peak = psutil.Process(p.pid), 0
    while p.poll() is None:
        try: peak = max(peak, ps.memory_info().rss)
        except psutil.Error: break
        time.sleep(0.1)
    o = json.loads(p.stdout.read().strip().splitlines()[-1])
    results[name] = {"seconds": round(o["seconds"], 1), "peak_rss_mb": round(peak / 2**20), "products_found": o["products"], "mean_of_means": o["check"]}
    print(name, results[name])
results["speedup_x"] = round(results["pandas"]["seconds"] / results["duckdb"]["seconds"], 2)
results["task"] = "per-product review count + mean rating over 2,500,939 raw reviews (gzipped JSONL, 292 MB)"
results["baseline"] = "pandas.read_json(lines=True, chunksize=50k) + incremental groupby"
results["optimised"] = "DuckDB vectorised streaming scan with projection push-down (only 2 of 10 JSON fields parsed)"
out = ROOT / "data" / "processed" / "analytics" / "benchmark.json"
out.write_text(json.dumps(results, indent=2)); print(json.dumps(results, indent=2))
