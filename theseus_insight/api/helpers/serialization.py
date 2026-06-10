"""Row-to-API serialization helpers shared by routers.

Replaces the seven per-router ``_convert_*_timestamps`` copies. psycopg
returns datetime/date objects for timestamp/date columns; Pydantic
response models expect ISO strings.
"""
import json
from datetime import date, datetime
from typing import Any, Dict, Sequence


def isoformat_fields(data: Dict[str, Any], fields: Sequence[str]) -> Dict[str, Any]:
    """Copy ``data`` with the named fields ISO-formatted when they are
    datetime/date objects; other values (already-strings, None) untouched."""
    converted = data.copy()
    for field in fields:
        value = converted.get(field)
        if value is not None and isinstance(value, (datetime, date)):
            converted[field] = value.isoformat()
    return converted


def decode_json_fields(data: Dict[str, Any], fields: Sequence[str]) -> Dict[str, Any]:
    """Copy ``data`` with the named fields json-decoded when they are strings.

    Undecodable values become None — the behavior the profiles router
    established for tags/email_recipients/arxiv_filters.
    """
    converted = data.copy()
    for field in fields:
        value = converted.get(field)
        if value is not None and isinstance(value, str):
            try:
                converted[field] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                converted[field] = None
    return converted
