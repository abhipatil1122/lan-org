import hashlib
from pathlib import Path

from shared.config import RECEIVED_FILES_DIR


class FileManager:

    def __init__(self):
        self.storage_dir = Path(RECEIVED_FILES_DIR)
        self.storage_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    def get_file_hash(self, file_path):
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as file:
            while chunk := file.read(64 * 1024):
                sha256.update(chunk)

        return sha256.hexdigest()

    def get_file_size(self, file_path):
        return Path(file_path).stat().st_size

    def get_storage_path(self, filename):
        return self.storage_dir / filename