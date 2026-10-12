import os
import socket
import pytest
import hashlib
from client.file_transfer import FileTransfer
from shared.config import FILE_CHUNK_SIZE
from shared.protocol import decode_packet, decode_file_chunk, TYPE_BINARY


def test_file_validation_and_hash(tmp_path):
    test_file = tmp_path / "sample.txt"
    content = b"Hello Bob, this is a test file.\n"
    test_file.write_bytes(content)

    ft = FileTransfer(socket=None)

    valid, err = ft.validate_file(str(test_file))
    assert valid is True
    assert err is None

    # Non-existent file
    valid, err = ft.validate_file(str(tmp_path / "ghost.txt"))
    assert valid is False
    assert err is not None
    assert "not exist" in err

    # Check size
    assert ft.get_file_size(str(test_file)) == len(content)

    # Check sha256
    expected_hash = hashlib.sha256(content).hexdigest()
    assert ft.calculate_hash(str(test_file)) == expected_hash


def test_send_file(tmp_path):
    server_sock, client_sock = socket.socketpair()

    test_file = tmp_path / "send_sample.bin"
    # Create data larger than one chunk
    data = b"X" * (FILE_CHUNK_SIZE + 128)
    test_file.write_bytes(data)

    sender_ft = FileTransfer(socket=client_sock)
    transfer_id = "test-transfer-uuid"

    # Send in a thread or synchronous
    import threading
    send_result = []
    def do_send():
        res = sender_ft.send_file(str(test_file), transfer_id)
        send_result.append(res)

    t = threading.Thread(target=do_send)
    t.start()

    # Receive chunks on server side
    received_bytes = b""
    while len(received_bytes) < len(data):
        pkt_type, payload = decode_packet(server_sock)
        assert pkt_type == TYPE_BINARY
        tid, chunk = decode_file_chunk(payload)
        assert tid == transfer_id
        received_bytes += chunk

    t.join()
    assert received_bytes == data
    assert send_result[0]["size"] == len(data)

    server_sock.close()
    client_sock.close()


def test_receive_chunks_and_complete(tmp_path, monkeypatch):
    # Change working directory to tmp_path so received_files is in tmp_path
    monkeypatch.chdir(tmp_path)

    ft = FileTransfer(socket=None)
    transfer_id = "uuid-12345"
    content = b"Testing complete file transfer reception with SHA-256."
    content_hash = hashlib.sha256(content).hexdigest()

    # Split into two chunks
    chunk1 = content[:20]
    chunk2 = content[20:]

    ft.receive_chunk(transfer_id, chunk1)
    # Check that temporary .part file exists
    part_file = tmp_path / "received_files" / f".{transfer_id}.part"
    assert part_file.exists()

    ft.receive_chunk(transfer_id, chunk2)
    assert part_file.stat().st_size == len(content)

    # Complete receive
    final_path = ft.complete_receive(
        transfer_id=transfer_id,
        filename="test.txt",
        expected_size=len(content),
        expected_hash=content_hash
    )

    assert os.path.exists(final_path)
    assert not part_file.exists()
    with open(final_path, "rb") as f:
        assert f.read() == content


def test_complete_receive_size_mismatch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    ft = FileTransfer(socket=None)
    transfer_id = "uuid-mismatch-size"
    content = b"Short content"
    content_hash = hashlib.sha256(content).hexdigest()

    ft.receive_chunk(transfer_id, content)
    part_file = tmp_path / "received_files" / f".{transfer_id}.part"
    assert part_file.exists()

    # Expected size is different
    with pytest.raises(ValueError, match="File size mismatch"):
        ft.complete_receive(
            transfer_id=transfer_id,
            filename="bad_size.txt",
            expected_size=len(content) + 50,
            expected_hash=content_hash
        )

    # .part file must be cleaned up / deleted
    assert not part_file.exists()


def test_complete_receive_hash_mismatch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    ft = FileTransfer(socket=None)
    transfer_id = "uuid-mismatch-hash"
    content = b"Corrupted content"
    fake_hash = "0" * 64

    ft.receive_chunk(transfer_id, content)
    part_file = tmp_path / "received_files" / f".{transfer_id}.part"
    assert part_file.exists()

    # Expected hash is different
    with pytest.raises(ValueError, match="SHA-256 hash mismatch"):
        ft.complete_receive(
            transfer_id=transfer_id,
            filename="corrupt.txt",
            expected_size=len(content),
            expected_hash=fake_hash
        )

    # .part file must be cleaned up / deleted
    assert not part_file.exists()
