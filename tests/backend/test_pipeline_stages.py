"""Behavior tests for extracted run_async stages (B9).

Stages take the TheseusInsight instance as context; these tests drive
them with a minimal shim so no network/LLM access is needed.
"""
import pandas as pd
import pytest

from theseus_insight.pipeline.checkpoints import CheckpointAdapter


class TiShim:
    """Just enough of TheseusInsight for stage functions."""

    def __init__(self, tmp_path, verbose=False):
        self.verbose = verbose
        self.start_date = "2025-01-01"
        self.end_date = "2025-01-07"
        self._checkpoints = CheckpointAdapter(str(tmp_path))
        self.no_papers_handled = False

    def _load_checkpoint(self, stage):
        return self._checkpoints.load(stage)

    def _save_checkpoint(self, stage, data):
        self._checkpoints.save(stage, data)

    def _handle_no_papers_found(self):
        self.no_papers_handled = True


@pytest.mark.asyncio
async def test_download_stage_resumes_from_checkpoint(tmp_path):
    from theseus_insight.pipeline.stages import download

    df = pd.DataFrame([{"title": "Alpha", "abstract": "x"}])
    ti = TiShim(tmp_path)
    ti._save_checkpoint("papers_downloaded", df)

    calls = []
    def cb(stage, pct, msg, meta=None):
        calls.append((stage, pct, meta))

    out, exit_early = await download.run(ti, None, cb)
    pd.testing.assert_frame_equal(out, df)
    assert exit_early is False
    # progress contract: 0% at start, 10% with discovered count at end
    assert calls[0] == ("download", 0, {"papers_discovered": 0})
    assert calls[-1] == ("download", 10, {"papers_discovered": 1})


@pytest.mark.asyncio
async def test_download_stage_exits_early_when_no_papers(tmp_path, monkeypatch):
    from theseus_insight.pipeline.stages import download

    class EmptyProcessor:
        def __init__(self, start_date, end_date):
            pass
        def download_and_process_data(self):
            return pd.DataFrame()

    monkeypatch.setattr(download, "ArxivDataProcessor", EmptyProcessor)
    ti = TiShim(tmp_path)
    out, exit_early = await download.run(ti, None, None)
    assert out is None
    assert exit_early is True
    assert ti.no_papers_handled is True


@pytest.mark.asyncio
async def test_download_stage_skipped_for_later_start_from(tmp_path):
    """start_from at a later stage leaves data_df None without downloading
    (and without firing the completion callback crash path — callback None,
    matching how later-stage resumes are invoked)."""
    from theseus_insight.pipeline.stages import download

    ti = TiShim(tmp_path)
    out, exit_early = await download.run(ti, "papers_ranked", None)
    assert out is None
    assert exit_early is False
