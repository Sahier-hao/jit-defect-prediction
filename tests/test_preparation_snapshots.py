import copy
import importlib
from concurrent.futures import ThreadPoolExecutor

import pytest


def snapshot_module():
    module = importlib.import_module("jit_defect.preparation_batch")
    assert callable(getattr(module, "write_snapshot", None)), (
        "immutable snapshot writer is missing"
    )
    return module


def body():
    return {
        "formatVersion": 1,
        "kind": "offline_preparation_snapshot",
        "preparationStatus": "prepared",
        "trainingReady": False,
        "config": {"asOf": "2024-04-23T00:00:00Z"},
        "records": [{"inducingLabel": None, "message": "例子"}],
    }


def test_snapshot_replay_reuses_identical_file_without_modification(tmp_path):
    module = snapshot_module()
    expected = body()
    path = module.write_snapshot(expected, tmp_path)
    raw, modified = path.read_bytes(), path.stat().st_mtime_ns
    second = module.write_snapshot(copy.deepcopy(expected), tmp_path)
    assert second == path
    assert second.stat().st_mtime_ns == modified
    assert second.read_bytes() == raw
    assert module.read_snapshot(path) == expected
    assert path.stem == module.snapshot_id(expected)
    assert len(path.stem) == 64
    assert list(tmp_path.iterdir()) == [path]


def test_dictionary_insertion_order_does_not_change_content_identity(tmp_path):
    module = snapshot_module()
    expected = body()
    reordered = dict(reversed(list(expected.items())))
    assert module.write_snapshot(expected, tmp_path) == module.write_snapshot(
        reordered, tmp_path
    )


def test_changed_cutoff_creates_new_file_and_preserves_previous_snapshot(tmp_path):
    module = snapshot_module()
    first = module.write_snapshot(body(), tmp_path)
    original = first.read_bytes()
    changed = body()
    changed["config"]["asOf"] = "2024-04-22T00:00:00Z"
    second = module.write_snapshot(changed, tmp_path)
    assert first != second
    assert first.read_bytes() == original
    assert module.read_snapshot(second) == changed


@pytest.mark.parametrize("corruption", ["bytes", "truncated", "whitespace"])
def test_corrupted_existing_snapshot_is_never_overwritten(tmp_path, corruption):
    module = snapshot_module()
    path = module.write_snapshot(body(), tmp_path)
    raw = path.read_bytes()
    if corruption == "bytes":
        raw = raw.replace(b'"prepared"', b'"tampered"')
    elif corruption == "truncated":
        raw = raw[:20]
    else:
        raw += b" \n"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="snapshot"):
        module.read_snapshot(path)
    with pytest.raises(ValueError, match="snapshot"):
        module.write_snapshot(body(), tmp_path)
    assert path.read_bytes() == raw


def test_interrupted_atomic_publication_leaves_no_partial_or_temp_file(
    tmp_path, monkeypatch
):
    module = snapshot_module()

    def fail(*args, **kwargs):
        raise OSError("simulated interrupted publication")

    monkeypatch.setattr(module.os, "link", fail)
    with pytest.raises(OSError, match="interrupted"):
        module.write_snapshot(body(), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_concurrent_identical_writers_reuse_one_verified_snapshot(tmp_path):
    module = snapshot_module()
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(
            pool.map(lambda _: module.write_snapshot(body(), tmp_path), range(8))
        )
    assert len(set(paths)) == 1
    assert list(tmp_path.iterdir()) == [paths[0]]
    assert module.read_snapshot(paths[0]) == body()


def test_renamed_snapshot_cannot_masquerade_as_different_content_id(tmp_path):
    module = snapshot_module()
    path = module.write_snapshot(body(), tmp_path)
    renamed = tmp_path / ("0" * 64 + ".json")
    renamed.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="snapshot"):
        module.read_snapshot(renamed)
