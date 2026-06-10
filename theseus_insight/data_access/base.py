"""Shared helpers and utilities for Postgres repositories."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple
import numpy as np


def build_set_clause(
    updates: Dict[str, Any], *, extra: Sequence[str] = ()
) -> Tuple[str, List[Any]]:
    """Build a dynamic ``SET`` clause from a column->value dict.

    Callers filter the dict to the columns they actually want to update
    (the repos' convention is "include when not None"). ``extra`` appends
    literal fragments that carry no bind value, e.g.
    ``"updated_at = CURRENT_TIMESTAMP"`` or ``"run_count = run_count + 1"``.
    Column names must come from code, never from request input.

    Returns ("col1 = %s, col2 = %s, <extra...>", [v1, v2]).
    """
    clauses = [f"{column} = %s" for column in updates]
    clauses.extend(extra)
    return ", ".join(clauses), list(updates.values())

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