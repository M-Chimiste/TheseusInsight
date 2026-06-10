"""Profile-filter parsing and resolution shared by routers.

Consolidates the comma-separated id/tag parsing and tag->profile-id
resolution that was previously copy-pasted across papers, trends, and
profiles routers. Behavior notes preserved from the originals:

- ``ProfileRepository.get_by_tags`` already filters ``is_active = TRUE``
  in SQL, so no additional active check is needed (papers.py used to
  re-filter on is_active redundantly).
- Routers differ on whether blank CSV segments ("1,") are skipped or
  raise: pass ``skip_blank`` accordingly.
- Routers differ on the 400 detail string: pass ``detail``. Passing
  ``detail=None`` lets the ValueError propagate (some endpoints rely on
  their blanket exception handler instead).
"""
from typing import List, Optional

from fastapi import HTTPException

from ...data_access.profiles import ProfileRepository


def parse_id_csv(
    raw: Optional[str], *, detail: Optional[str] = None, skip_blank: bool = True
) -> Optional[List[int]]:
    """Parse a comma-separated integer list; None/empty input -> None."""
    if not raw:
        return None
    try:
        segments = raw.split(",")
        if skip_blank:
            return [int(s.strip()) for s in segments if s.strip()]
        return [int(s.strip()) for s in segments]
    except ValueError:
        if detail is None:
            raise
        raise HTTPException(status_code=400, detail=detail)


def parse_tag_csv(tag: Optional[str], tags_csv: Optional[str]) -> List[str]:
    """Combine a single tag and a comma-separated tag list into one list."""
    tags: List[str] = []
    if tag:
        tags.append(tag)
    if tags_csv:
        tags.extend(t.strip() for t in tags_csv.split(",") if t.strip())
    return tags


def resolve_tag_profile_ids(tags: List[str]) -> List[int]:
    """Resolve tag names to ids of active profiles carrying any of them."""
    if not tags:
        return []
    return [p["id"] for p in ProfileRepository.get_by_tags(tags)]


def merge_id_filters(
    explicit_ids: Optional[List[int]], tag_ids: List[int]
) -> List[int]:
    """Merge explicit profile ids with tag-resolved ids.

    Intersection when explicit ids were given (both filters must match),
    otherwise just the tag-resolved ids — the exact semantics every
    router implemented inline.
    """
    if explicit_ids:
        return list(set(explicit_ids) & set(tag_ids))
    return tag_ids
