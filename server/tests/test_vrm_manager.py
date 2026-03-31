import os
import tempfile
import pytest
from pathlib import Path

GLTF_MAGIC = b'glTF'
FAKE_VRM = GLTF_MAGIC + b'\x02\x00\x00\x00' + b'\x00' * 100
INVALID_FILE = b'not a vrm file at all'


@pytest.fixture
def vrm_dir(tmp_path):
    return tmp_path / "vrm"


@pytest.fixture
def manager(vrm_dir):
    from vrm_manager import VrmManager
    return VrmManager(str(vrm_dir))


def test_save_valid_vrm(manager, vrm_dir):
    filename = manager.save(FAKE_VRM, "test_model.vrm")
    assert filename == "test_model.vrm"
    assert (vrm_dir / "test_model.vrm").exists()


def test_save_rejects_invalid_file(manager):
    with pytest.raises(ValueError, match="Invalid VRM"):
        manager.save(INVALID_FILE, "bad.vrm")


def test_save_rejects_oversized_file(manager):
    big_data = GLTF_MAGIC + b'\x02\x00\x00\x00' + b'\x00' * (50 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="exceeds"):
        manager.save(big_data, "huge.vrm")


def test_list_empty(manager):
    result = manager.list_models()
    assert result == []


def test_list_after_save(manager):
    manager.save(FAKE_VRM, "model_a.vrm")
    manager.save(FAKE_VRM, "model_b.vrm")
    result = manager.list_models()
    filenames = [r["filename"] for r in result]
    assert "model_a.vrm" in filenames
    assert "model_b.vrm" in filenames


def test_delete(manager, vrm_dir):
    manager.save(FAKE_VRM, "to_delete.vrm")
    assert (vrm_dir / "to_delete.vrm").exists()
    manager.delete("to_delete.vrm")
    assert not (vrm_dir / "to_delete.vrm").exists()


def test_delete_nonexistent(manager):
    with pytest.raises(FileNotFoundError):
        manager.delete("nonexistent.vrm")


def test_get_path(manager, vrm_dir):
    manager.save(FAKE_VRM, "my.vrm")
    path = manager.get_path("my.vrm")
    assert path == str(vrm_dir / "my.vrm")


def test_get_path_nonexistent(manager):
    with pytest.raises(FileNotFoundError):
        manager.get_path("missing.vrm")
