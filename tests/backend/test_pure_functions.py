"""Pin pure(ish) helpers that later refactor phases will move or replace."""
from datetime import datetime, timedelta

import pytest


def test_get_n_days_ago_format():
    from theseus_insight.utils.common_utils import get_n_days_ago

    value = get_n_days_ago(7)
    parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
    assert parsed == (datetime.now() - timedelta(days=7)).date()


def test_cosine_similarity():
    from theseus_insight.utils.common_utils import cosine_similarity

    assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)
    assert cosine_similarity([1, 1, 0], [1, 0, 0]) == pytest.approx(0.7071, abs=1e-3)


def test_clean_string(golden):
    from theseus_insight.utils.common_utils import clean_string

    samples = [
        "plain text",
        "  leading and trailing  ",
        "with\nnewlines\tand tabs",
        "unicode — em dash and “quotes”",
    ]
    golden("clean_string_samples", {s: clean_string(s) for s in samples})


def test_remove_markdown_tables(golden):
    from theseus_insight.utils.common_utils import remove_markdown_tables

    text = (
        "Intro paragraph.\n\n"
        "| col a | col b |\n"
        "|-------|-------|\n"
        "| 1     | 2     |\n\n"
        "Closing paragraph."
    )
    golden("remove_markdown_tables", remove_markdown_tables(text))


def test_to_pgvector():
    from theseus_insight.data_access.base import to_pgvector
    import numpy as np

    assert to_pgvector(None) is None
    assert to_pgvector([1.0, 2.5, -3.0]) == "[1.0,2.5,-3.0]"
    assert to_pgvector(np.array([0.5, 1.5])) == "[0.5,1.5]"


def test_json_repair_judge_response_contract():
    """The judge pipeline parses LLM scoring output with json_repair.

    The parsing is currently inline in TheseusInsight (rank_papers_*); this
    contract test protects the planned extraction of parse_judge_response().
    Representative malformed outputs LLM judges actually produce:
    """
    import json_repair

    malformed_samples = [
        '```json\n{"score": 8, "related": true, "rationale": "good"}\n```',
        '{"score": 8, "related": true, "rationale": "trailing comma",}',
        "{'score': 7, 'related': false, 'rationale': 'single quotes'}",
        'Some preamble text {"score": 5, "related": true, "rationale": "noise"}',
    ]
    for sample in malformed_samples:
        parsed = json_repair.loads(sample)
        assert isinstance(parsed, dict), f"json_repair failed on: {sample!r}"
        assert int(parsed["score"]) in range(1, 11)
        assert isinstance(parsed["related"], bool)
        assert isinstance(parsed["rationale"], str)
