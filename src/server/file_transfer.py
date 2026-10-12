import os
import uuid
import hashlib

from shared.config import FILE_CHUNK_SIZE, MAX_FILE_SIZE
from shared.protocol import encode_message, encode_binary


class FileTransferManager:

    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    def send_file(self, sender, receiver, file_path):

        if not os.path.isfile(file_path):
            return False, "File does not exist"

        file_size = os.path.getsize(file_path)

        if file_size > MAX_FILE_SIZE:
            return False, "File is too large"

        receiver_socket = self.connection_manager.get_client(receiver)

        if receiver_socket is None:
            return False, "Receiver is not online"

        transfer_id = str(uuid.uuid4())

        file_hash = self.calculate_hash(file_path)

        # Tell receiver about the incoming file
        receiver_socket.sendall(
            encode_message({
                "type": "file_request",
                "transfer_id": transfer_id,
                "sender": sender,
                "filename": os.path.basename(file_path),
                "size": file_size,
                "sha256": file_hash
            })
        )

        return True, transfer_id

    def calculate_hash(self, file_path):

        sha256 = hashlib.sha256()

        with open(file_path, "rb") as file:

            while True:

                chunk = file.read(FILE_CHUNK_SIZE)

                if not chunk:
                    break

                sha256.update(chunk)

        return sha256.hexdigest()