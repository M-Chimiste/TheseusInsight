"""Profile-filter SQL composition for the trends repositories.

Collapses the three-way branch (profile_ids IN (...) / profile_id = %s /
no filter) that every trends query used to spell out in full triplicate.
Column names come from code, never request input.
"""
from typing import List, Optional, Tuple


def profile_filter_clause(
    profile_id: Optional[int],
    profile_ids: Optional[List[int]],
    *,
    column: str = "t.profile_id",
    prefix: str = " AND ",
) -> Tuple[str, List[int]]:
    """Build the profile-filter SQL fragment and its bind params.

    Returns ("", []) when no filter applies; otherwise the fragment
    starts with ``prefix`` (use " WHERE " when it's the only condition).
    profile_ids wins over profile_id, matching the original branch order.
    """
    if profile_ids:
        placeholders = ",".join(["%s"] * len(profile_ids))
        return f"{prefix}{column} IN ({placeholders})", list(profile_ids)
    if profile_id:
        return f"{prefix}{column} = %s", [profile_id]
    return "", []
