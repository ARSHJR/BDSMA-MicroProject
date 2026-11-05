"""Sparse top-K similarity builders. Batch (chunked) processing keeps memory bounded on a laptop."""
from __future__ import annotations
import numpy as np
import scipy.sparse as sp


def _topk_rows(dense: np.ndarray, k: int, row_offset: int):
    """Return COO triplets of the top-k entries of each row of `dense` (excluding the diagonal)."""
    n = dense.shape[0]
    idx = np.arange(n)
    dense[idx, idx + row_offset] = -1.0
    part = np.argpartition(-dense, k, axis=1)[:, :k]
    vals = np.take_along_axis(dense, part, axis=1)
    mask = vals > 0
    rows = np.repeat(idx + row_offset, k).reshape(n, k)
    return rows[mask], part[mask], vals[mask]


def topk_cosine(A: sp.csr_matrix, k: int = 40, chunk: int = 600) -> sp.csr_matrix:
    """Item-item cosine neighbours for L2-normalised rows of A (content based)."""
    n = A.shape[0]
    At = A.T.tocsc()
    R, C, V = [], [], []
    for s in range(0, n, chunk):
        d = (A[s:s + chunk] @ At).toarray().astype(np.float32)
        r, c, v = _topk_rows(d, min(k, n - 1), s)
        R.append(r); C.append(c); V.append(v)
    return sp.csr_matrix((np.concatenate(V), (np.concatenate(R), np.concatenate(C))), shape=(n, n), dtype=np.float32)


def item_cf_topk(X: sp.csr_matrix, k: int = 40, chunk: int = 600, shrink: float = 2.0) -> sp.csr_matrix:
    """Item-item collaborative neighbours from a (users x items) implicit matrix.
    sim(i,j) = co(i,j) / (sqrt(n_i n_j) + shrink) - cosine with shrinkage to damp low-support pairs."""
    X = X.tocsr().astype(np.float32)
    n = X.shape[1]
    Xt = X.T.tocsr()
    norms = np.sqrt(np.asarray(X.multiply(X).sum(0)).ravel()).astype(np.float32)
    R, C, V = [], [], []
    for s in range(0, n, chunk):
        co = (Xt[s:s + chunk] @ X).toarray().astype(np.float32)
        den = norms[s:s + chunk, None] * norms[None, :] + shrink
        d = co / den
        r, c, v = _topk_rows(d, min(k, n - 1), s)
        R.append(r); C.append(c); V.append(v)
    return sp.csr_matrix((np.concatenate(V), (np.concatenate(R), np.concatenate(C))), shape=(n, n), dtype=np.float32)
