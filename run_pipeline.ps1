# Reproduces every processed artifact from the raw Amazon Fashion files (about 25 min on a laptop).
$ErrorActionPreference = "Stop"
python pipeline/00_download.py          # skips files that already exist (~500 MB)
python -I pipeline/01_ingest_clean.py   # DuckDB ingest, clean, dedupe, k-core -> parquet
python -I pipeline/02_text_features.py  # sentiment, sustainability proxy, trends
python -I pipeline/03_social.py --synthetic   # labelled SYNTHETIC social demo + CSV analyser
python -I pipeline/04_train_evaluate.py # similarity models + time-split evaluation
python -I pipeline/05_benchmark.py      # pandas vs DuckDB timing
