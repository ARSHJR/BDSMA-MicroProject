"""Content feature matrix: TF-IDF over text + weighted one-hot attributes, L2-normalised."""
from __future__ import annotations
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

ATTR_WEIGHTS = {"article_type": 0.9, "gender": 0.7, "colour": 0.35, "category_group": 0.3}


def build_content_matrix(products: pd.DataFrame, text_weight: float = 1.0):
    tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_df=0.5, max_features=60000,
                            sublinear_tf=True, stop_words="english", dtype=np.float32)
    T = tfidf.fit_transform(products.text_for_model.fillna(""))
    blocks = [normalize(T) * text_weight]
    for col, w in ATTR_WEIGHTS.items():
        vals = products[col].fillna("NA").astype(str)
        cats = {c: i for i, c in enumerate(sorted(vals.unique()))}
        M = sp.csr_matrix((np.full(len(vals), w, dtype=np.float32), (np.arange(len(vals)), vals.map(cats).to_numpy())),
                          shape=(len(vals), len(cats)))
        blocks.append(M)
    return normalize(sp.hstack(blocks).tocsr()), tfidf
