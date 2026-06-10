"""Checkpoint-compat tests gating the B8/B9 god-class decomposition.

The file format ({stage}_checkpoint.pkl wrapping {'data','timestamp',
'stage'}) is a frozen contract: checkpoints written by pre-refactor code
must load through the new CheckpointAdapter and vice versa.
"""
import datetime
import os
import pickle

import pandas as pd


def _legacy_save(checkpoint_dir, stage, data):
    """Byte-for-byte copy of the pre-B8 TheseusInsight._save_checkpoint."""
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = os.path.join(checkpoint_dir, f"{stage}_checkpoint.pkl")
    checkpoint_data = {
        'data': data,
        'timestamp': datetime.datetime.now().isoformat(),
        'stage': stage
    }
    with open(checkpoint_path, 'wb') as f:
        pickle.dump(checkpoint_data, f)


def test_adapter_loads_legacy_checkpoints(tmp_path):
    from theseus_insight.pipeline.checkpoints import CheckpointAdapter

    df = pd.DataFrame([{"title": "Alpha", "score": 9.0}])
    _legacy_save(str(tmp_path), "papers_downloaded", df)
    _legacy_save(str(tmp_path), "newsletter_sections", {"sections": ["a", "b"]})

    adapter = CheckpointAdapter(str(tmp_path))
    loaded_df = adapter.load("papers_downloaded")
    pd.testing.assert_frame_equal(loaded_df, df)
    assert adapter.load("newsletter_sections") == {"sections": ["a", "b"]}
    assert adapter.load("missing_stage") is None


def test_legacy_loader_reads_adapter_checkpoints(tmp_path):
    """Simulate the OLD _load_checkpoint reading a NEW adapter write."""
    from theseus_insight.pipeline.checkpoints import CheckpointAdapter

    adapter = CheckpointAdapter(str(tmp_path))
    adapter.save("papers_ranked", [1, 2, 3])

    path = tmp_path / "papers_ranked_checkpoint.pkl"
    assert path.exists(), "filename contract broken"
    with open(path, "rb") as f:
        wrapper = pickle.load(f)
    assert set(wrapper.keys()) == {"data", "timestamp", "stage"}
    assert wrapper["stage"] == "papers_ranked"
    assert wrapper["data"] == [1, 2, 3]
    # timestamp is an ISO string in the legacy format
    datetime.datetime.fromisoformat(wrapper["timestamp"])


def test_adapter_cleanup_removes_dir(tmp_path):
    from theseus_insight.pipeline.checkpoints import CheckpointAdapter

    target = tmp_path / "ckpts"
    adapter = CheckpointAdapter(str(target))
    adapter.save("papers_stored", {"n": 1})
    assert target.exists()
    adapter.cleanup()
    assert not target.exists()


def test_god_class_delegates_share_format(tmp_path, monkeypatch):
    """The facade's _save_checkpoint/_load_checkpoint round-trip through
    the adapter with the same on-disk format."""
    from theseus_insight.pipeline.checkpoints import CheckpointAdapter

    class Shim:
        _checkpoints = CheckpointAdapter(str(tmp_path))

    from theseus_insight.theseus_insight import TheseusInsight

    shim = Shim()
    TheseusInsight._save_checkpoint(shim, "ranking_partial", {"i": 42})
    assert TheseusInsight._load_checkpoint(shim, "ranking_partial") == {"i": 42}
    assert (tmp_path / "ranking_partial_checkpoint.pkl").exists()
