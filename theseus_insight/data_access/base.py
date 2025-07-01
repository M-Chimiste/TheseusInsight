"""Shared helpers and utilities for Postgres repositories."""
from __future__ import annotations

from typing import List
import numpy as np

# ---------------------------------------------------------------------------
# pgvector helpers
# ---------------------------------------------------------------------------


def to_pgvector(values: List[float] | np.ndarray | None) -> str | None:
    """Convert Python list / ndarray → pgvector literal.

    Postgres expects literal form like '[1,2,3]'. Returning None keeps NULL.
    """
    if values is None:
        return None
    if isinstance(values, np.ndarray):
        seq = values.tolist()
    else:
        seq = values
    return "[" + ",".join(str(float(x)) for x in seq) + "]" 