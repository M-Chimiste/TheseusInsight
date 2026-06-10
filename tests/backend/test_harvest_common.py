"""Pin the harvest-script checkpoint format (frozen contract: {stage}.pkl)."""
import pickle
import time


def test_checkpoint_roundtrip(tmp_path):
    from theseus_insight.utils.harvest_common import (
        _checkpoint_path, load_checkpoint, save_checkpoint
    )

    data = {"papers": [1, 2, 3], "nested": {"a": "b"}}
    save_checkpoint(str(tmp_path), "download", data, verbose=False)

    path = _checkpoint_path(str(tmp_path), "download")
    assert path == tmp_path / "download.pkl"
    assert path.exists()

    # On-disk wrapper format is frozen: {'data', 'timestamp', 'stage'}
    with open(path, "rb") as f:
        wrapper = pickle.load(f)
    assert set(wrapper.keys()) == {"data", "timestamp", "stage"}
    assert wrapper["stage"] == "download"

    assert load_checkpoint(str(tmp_path), "download", verbose=False) == data
    assert load_checkpoint(str(tmp_path), "missing-stage", verbose=False) is None


def test_old_checkpoints_still_load(tmp_path):
    """A checkpoint written by the pre-refactor code must keep loading."""
    from theseus_insight.utils.harvest_common import load_checkpoint

    legacy = {"data": ["legacy"], "timestamp": time.time(), "stage": "embed"}
    with open(tmp_path / "embed.pkl", "wb") as f:
        pickle.dump(legacy, f)

    assert load_checkpoint(str(tmp_path), "embed", verbose=False) == ["legacy"]
