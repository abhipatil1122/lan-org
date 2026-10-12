from server.transfer_manager import TransferManager


def test_create_transfer():
    manager = TransferManager()
    transfer = manager.create_transfer(
        sender="Alice",
        receiver="Bob",
        filename="test.txt",
        size=1024,
        sha256="abc123hash"
    )

    assert transfer is not None
    assert "transfer_id" in transfer
    assert transfer["sender"] == "Alice"
    assert transfer["receiver"] == "Bob"
    assert transfer["filename"] == "test.txt"
    assert transfer["size"] == 1024
    assert transfer["sha256"] == "abc123hash"
    assert transfer["status"] == "pending"
    assert transfer["bytes_transferred"] == 0


def test_get_transfer():
    manager = TransferManager()
    created = manager.create_transfer("Alice", "Bob", "file.pdf", 500, "hash1")
    fetched = manager.get_transfer(created["transfer_id"])

    assert fetched == created
    assert manager.get_transfer("non-existent-id") is None


def test_accept_transfer():
    manager = TransferManager()
    transfer = manager.create_transfer("Alice", "Bob", "file.pdf", 500, "hash1")
    tid = transfer["transfer_id"]

    accepted = manager.accept_transfer(tid)
    assert accepted is not None
    assert accepted["status"] == "accepted"

    # Cannot accept already accepted transfer
    second_accept = manager.accept_transfer(tid)
    assert second_accept is None


def test_complete_transfer():
    manager = TransferManager()
    transfer = manager.create_transfer("Alice", "Bob", "file.pdf", 500, "hash1")
    tid = transfer["transfer_id"]

    completed = manager.complete_transfer(tid)
    assert completed is not None
    assert completed["status"] == "completed"


def test_remove_transfer():
    manager = TransferManager()
    transfer = manager.create_transfer("Alice", "Bob", "file.pdf", 500, "hash1")
    tid = transfer["transfer_id"]

    manager.remove_transfer(tid)
    assert manager.get_transfer(tid) is None
