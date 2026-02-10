import os
import tempfile

import pytest

from app.domain.exceptions import FileStorageError
from app.infrastructure.storage.local import LocalFileStorage


@pytest.fixture
def storage(tmp_path):
    return LocalFileStorage(base_dir=str(tmp_path))


class TestLocalFileStorage:
    def test_save_and_read(self, storage):
        data = b"hello world"
        path = storage.save_file("test/file.txt", data)
        assert storage.read_file(path) == data

    def test_file_exists(self, storage):
        storage.save_file("exists.txt", b"data")
        assert storage.file_exists("exists.txt") is True
        assert storage.file_exists("nope.txt") is False

    def test_delete(self, storage):
        storage.save_file("delete_me.txt", b"data")
        assert storage.file_exists("delete_me.txt") is True
        storage.delete_file("delete_me.txt")
        assert storage.file_exists("delete_me.txt") is False

    def test_read_nonexistent(self, storage):
        with pytest.raises(FileStorageError, match="File not found"):
            storage.read_file("nonexistent.txt")

    def test_nested_directories(self, storage):
        data = b"nested"
        path = storage.save_file("a/b/c/file.txt", data)
        assert storage.read_file(path) == data

    def test_path_traversal_blocked(self, storage):
        with pytest.raises(FileStorageError, match="Path traversal"):
            storage.save_file("../../etc/passwd", b"malicious")

    def test_delete_nonexistent_no_error(self, storage):
        # Should not raise
        storage.delete_file("nothing.txt")
