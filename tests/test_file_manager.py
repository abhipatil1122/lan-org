from server.file_manager import FileManager


def test_file_hash(tmp_path):
    file_path = tmp_path / "test.txt"

    file_path.write_text("Hello LAN Chat")

    manager = FileManager()

    file_hash = manager.get_file_hash(file_path)

    assert len(file_hash) == 64


def test_file_size(tmp_path):
    file_path = tmp_path / "test.txt"

    file_path.write_text("Hello")

    manager = FileManager()

    assert manager.get_file_size(file_path) == 5