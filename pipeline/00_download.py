"""Stage 0 - download the raw Amazon Reviews 2023 'Fashion' files (public, no account / API key)."""
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"; RAW.mkdir(parents=True, exist_ok=True)
BASE = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw"
FILES = {"meta_Amazon_Fashion.jsonl.gz": f"{BASE}/meta_categories/meta_Amazon_Fashion.jsonl.gz",
         "Amazon_Fashion.jsonl.gz": f"{BASE}/review_categories/Amazon_Fashion.jsonl.gz"}
for name, url in FILES.items():
    dest = RAW / name
    if dest.exists() and dest.stat().st_size > 10_000_000:
        print("have", name); continue
    print("downloading", url); urllib.request.urlretrieve(url, dest)
