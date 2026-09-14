import pytest

from news.snapshot_storage import LocalFileSnapshotStorage, SnapshotStorageError


def storage(tmp_path):
    return LocalFileSnapshotStorage(tmp_path / "evidence")


def test_put_get_exists_delete_round_trip(tmp_path):
    store = storage(tmp_path)
    key = "1/html/deadbeef"
    assert not store.exists(key)
    artifact = store.put(key, b"captured bytes")
    assert artifact.key == key and artifact.size == len(b"captured bytes")
    assert store.exists(key)
    assert store.get(key) == b"captured bytes"
    store.delete(key)
    assert not store.exists(key)


def test_get_missing_key_raises(tmp_path):
    store = storage(tmp_path)
    with pytest.raises(SnapshotStorageError):
        store.get("missing/key")


def test_put_refuses_to_overwrite_with_different_content(tmp_path):
    store = storage(tmp_path)
    store.put("1/html/hash", b"original")
    with pytest.raises(SnapshotStorageError):
        store.put("1/html/hash", b"different")
    assert store.get("1/html/hash") == b"original"


def test_put_same_content_twice_is_idempotent(tmp_path):
    store = storage(tmp_path)
    store.put("1/html/hash", b"same")
    store.put("1/html/hash", b"same")
    assert store.get("1/html/hash") == b"same"


def test_path_traversal_is_rejected(tmp_path):
    store = storage(tmp_path)
    with pytest.raises(SnapshotStorageError):
        store.put("../escape", b"x")
    with pytest.raises(SnapshotStorageError):
        store.get("../../etc/passwd")


def test_empty_key_is_rejected(tmp_path):
    store = storage(tmp_path)
    with pytest.raises(SnapshotStorageError):
        store.put("", b"x")


def test_delete_missing_key_is_a_no_op(tmp_path):
    storage(tmp_path).delete("never/stored")
