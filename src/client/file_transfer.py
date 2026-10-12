import hashlib
import os

from shared.config import FILE_CHUNK_SIZE, MAX_FILE_SIZE
from shared.protocol import encode_file_chunk


class FileTransfer:
    def __init__(self, socket):
        self.socket = socket
        self.receiving_files = {}
        self.pending_files = {}

    def add_pending_file(self, filename, file_path):
        self.pending_files[filename] = file_path

    def validate_file(self, file_path):
        if not os.path.isfile(file_path):
            return False, "File does not exist"

        file_size = os.path.getsize(file_path)

        if file_size > MAX_FILE_SIZE:
            return False, "File is too large"

        return True, None

    def get_file_size(self, file_path):
        return os.path.getsize(file_path)

    def calculate_hash(self, file_path):
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as file:
            while True:
                chunk = file.read(FILE_CHUNK_SIZE)

                if not chunk:
                    break

                sha256.update(chunk)

        return sha256.hexdigest()

    def send_file(self, file_path, transfer_id):
        valid, error = self.validate_file(file_path)

        if not valid:
            raise ValueError(error)

        file_size = self.get_file_size(file_path)
        bytes_sent = 0

        print(f"[File] Sending {file_path}")

        with open(file_path, "rb") as file:
            while True:
                chunk = file.read(FILE_CHUNK_SIZE)

                if not chunk:
                    break

                packet = encode_file_chunk(
                    transfer_id,
                    chunk
                )

                self.socket.sendall(packet)

                bytes_sent += len(chunk)

                print(
                    f"\r[File] Sent "
                    f"{bytes_sent}/{file_size} bytes",
                    end="",
                    flush=True
                )

        print()

        return {
            "size": bytes_sent,
            "sha256": self.calculate_hash(file_path)
        }

    def receive_chunk(self, transfer_id, chunk):
        if transfer_id not in self.receiving_files:
            os.makedirs("received_files", exist_ok=True)

            temp_path = os.path.join(
                "received_files",
                f".{transfer_id}.part"
            )

            file = open(temp_path, "wb")

            self.receiving_files[transfer_id] = {
                "file": file,
                "path": temp_path,
                "size": 0,
                "hash": hashlib.sha256()
            }

        transfer = self.receiving_files[transfer_id]

        transfer["file"].write(chunk)
        transfer["file"].flush()
        transfer["size"] += len(chunk)
        transfer["hash"].update(chunk)

        print(
            f"\r[File] Receiving: "
            f"{transfer['size']} bytes",
            end="",
            flush=True
        )

    def complete_receive(
        self,
        transfer_id,
        filename,
        expected_size,
        expected_hash
    ):
        if transfer_id not in self.receiving_files:
            if expected_size == 0:
                empty_hash = hashlib.sha256(b"").hexdigest()
                if expected_hash != empty_hash:
                    raise ValueError("SHA-256 hash mismatch")
                received_dir = "received_files"
                os.makedirs(received_dir, exist_ok=True)
                final_path = os.path.join(received_dir, os.path.basename(filename))
                with open(final_path, "wb") as f:
                    pass
                return final_path
            raise ValueError("Unknown transfer")

        transfer = self.receiving_files[transfer_id]

        transfer["file"].close()

        received_size = transfer["size"]
        received_hash = transfer["hash"].hexdigest()

        temp_path = transfer["path"]

        # Check file size
        if received_size != expected_size:
            if os.path.exists(temp_path):
                os.remove(temp_path)

            del self.receiving_files[transfer_id]

            raise ValueError(
                f"File size mismatch: "
                f"expected {expected_size}, "
                f"received {received_size}"
            )

        # Check SHA-256
        if received_hash != expected_hash:
            if os.path.exists(temp_path):
                os.remove(temp_path)

            del self.receiving_files[transfer_id]

            raise ValueError(
                "SHA-256 hash mismatch"
            )

        # Final filename
        received_dir = "received_files"

        os.makedirs(
            received_dir,
            exist_ok=True
        )

        final_path = os.path.join(
            received_dir,
            os.path.basename(filename)
        )

        # Replace old file if it already exists
        if os.path.exists(final_path):
            os.remove(final_path)

        # Rename temporary file
        os.replace(
            temp_path,
            final_path
        )

        del self.receiving_files[transfer_id]

        print()

        return final_path