import threading
import uuid


class TransferManager:

    def __init__(self):
        self.transfers = {}
        self.lock = threading.Lock()

    def create_transfer(
        self,
        sender,
        receiver,
        filename,
        size,
        sha256
    ):
        transfer_id = str(uuid.uuid4())

        transfer = {
            "transfer_id": transfer_id,
            "sender": sender,
            "receiver": receiver,
            "filename": filename,
            "size": size,
            "sha256": sha256,
            "status": "pending",
            "bytes_transferred": 0
        }

        with self.lock:
            self.transfers[transfer_id] = transfer

        return transfer

    def get_transfer(self, transfer_id):

        with self.lock:
            return self.transfers.get(
                transfer_id
            )

    def accept_transfer(self, transfer_id):

        with self.lock:

            transfer = self.transfers.get(
                transfer_id
            )

            if transfer is None:
                return None

            if transfer["status"] != "pending":
                return None

            transfer["status"] = "accepted"

            return transfer

    def complete_transfer(self, transfer_id):

        with self.lock:

            transfer = self.transfers.get(
                transfer_id
            )

            if transfer is None:
                return None

            transfer["status"] = "completed"

            return transfer

    def remove_transfer(self, transfer_id):

        with self.lock:

            self.transfers.pop(
                transfer_id,
                None
            )