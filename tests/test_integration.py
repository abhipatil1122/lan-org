import socket
import threading
import time
import os
import hashlib
from server.connection_manager import ConnectionManager
from server.message_router import MessageRouter
from server.transfer_manager import TransferManager
from server.client_handler import ClientHandler
from shared.protocol import (
    encode_message,
    decode_message,
    encode_file_chunk,
    decode_packet,
    decode_file_chunk,
    TYPE_JSON,
    TYPE_BINARY
)
from client.file_transfer import FileTransfer


def test_full_chat_and_file_transfer_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Setup server in memory
    conn_mgr = ConnectionManager()
    router = MessageRouter(conn_mgr)
    xfer_mgr = TransferManager()

    # Create 2 socket pairs for Alice and Bob
    alice_srv, alice_cli = socket.socketpair()
    bob_srv, bob_cli = socket.socketpair()

    alice_handler = ClientHandler(alice_srv, ("127.0.0.1", 10001), conn_mgr, router, xfer_mgr)
    bob_handler = ClientHandler(bob_srv, ("127.0.0.1", 10002), conn_mgr, router, xfer_mgr)

    t_alice = threading.Thread(target=alice_handler.run, daemon=True)
    t_bob = threading.Thread(target=bob_handler.run, daemon=True)
    t_alice.start()
    t_bob.start()

    # 1. Login Alice
    alice_cli.sendall(encode_message({"type": "login", "username": "Alice"}))
    resp_alice = decode_message(alice_cli)
    assert resp_alice["type"] == "login_success"
    assert "Welcome Alice" in resp_alice["message"]

    # 2. Login Bob
    bob_cli.sendall(encode_message({"type": "login", "username": "Bob"}))
    resp_bob = decode_message(bob_cli)
    assert resp_bob["type"] == "login_success"
    assert "Welcome Bob" in resp_bob["message"]

    # Alice gets system broadcast that Bob joined
    sys_msg = decode_message(alice_cli)
    assert sys_msg["type"] == "system"
    assert "Bob joined" in sys_msg["message"]

    # 3. Check /users
    alice_cli.sendall(encode_message({"type": "users"}))
    users_msg = decode_message(alice_cli)
    assert users_msg["type"] == "users"
    assert set(users_msg["users"]) == {"Alice", "Bob"}

    # 4. Public chat
    alice_cli.sendall(encode_message({"type": "chat", "message": "Hello everyone"}))
    chat_msg = decode_message(bob_cli)
    assert chat_msg["type"] == "chat"
    assert chat_msg["sender"] == "Alice"
    assert chat_msg["message"] == "Hello everyone"

    # 5. Private message
    alice_cli.sendall(encode_message({
        "type": "private_message",
        "receiver": "Bob",
        "message": "Secret message for Bob"
    }))
    dm_msg = decode_message(bob_cli)
    assert dm_msg["type"] == "private_message"
    assert dm_msg["sender"] == "Alice"
    assert dm_msg["message"] == "Secret message for Bob"

    # 6. File transfer
    # Prepare file
    test_file = tmp_path / "test.txt"
    file_bytes = b"Hello Bob, this is a test file.\n"  # 32 bytes
    test_file.write_bytes(file_bytes)
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    file_size = len(file_bytes)
    assert file_size == 32

    # Alice requests file transfer
    alice_cli.sendall(encode_message({
        "type": "file_send",
        "receiver": "Bob",
        "filename": "test.txt",
        "size": file_size,
        "sha256": file_hash
    }))

    # Alice gets file_ready with transfer_id
    alice_ready = decode_message(alice_cli)
    assert alice_ready["type"] == "file_ready"
    transfer_id = alice_ready["transfer_id"]

    # Bob gets file_request
    bob_req = decode_message(bob_cli)
    assert bob_req["type"] == "file_request"
    assert bob_req["sender"] == "Alice"
    assert bob_req["filename"] == "test.txt"
    assert bob_req["transfer_id"] == transfer_id
    assert bob_req["size"] == 32
    assert bob_req["sha256"] == file_hash

    # Bob accepts
    bob_cli.sendall(encode_message({
        "type": "file_accept",
        "transfer_id": transfer_id
    }))

    # Bob gets file_started
    bob_started = decode_message(bob_cli)
    assert bob_started["type"] == "file_started"

    # Alice gets file_accepted
    alice_accepted = decode_message(alice_cli)
    assert alice_accepted["type"] == "file_accepted"
    assert alice_accepted["transfer_id"] == transfer_id

    # Alice sends file chunk
    alice_cli.sendall(encode_file_chunk(transfer_id, file_bytes))

    # Bob receives binary chunk
    pkt_type, payload = decode_packet(bob_cli)
    assert pkt_type == TYPE_BINARY
    recv_tid, chunk_data = decode_file_chunk(payload)
    assert recv_tid == transfer_id
    assert chunk_data == file_bytes

    # Bob's FileTransfer helper writes chunk to temporary .part file
    bob_ft = FileTransfer(socket=bob_cli)
    bob_ft.receive_chunk(transfer_id, chunk_data)

    part_file = tmp_path / "received_files" / f".{transfer_id}.part"
    assert part_file.exists()

    # Bob receives file_complete from server
    bob_complete_msg = decode_message(bob_cli)
    assert bob_complete_msg["type"] == "file_complete"
    assert bob_complete_msg["size"] == 32
    assert bob_complete_msg["sha256"] == file_hash

    # Bob completes receive and verifies integrity
    final_path = bob_ft.complete_receive(
        transfer_id=transfer_id,
        filename=bob_complete_msg["filename"],
        expected_size=bob_complete_msg["size"],
        expected_hash=bob_complete_msg["sha256"]
    )

    assert os.path.exists(final_path)
    assert not part_file.exists()
    with open(final_path, "rb") as f:
        assert f.read() == file_bytes

    # Clean up
    alice_cli.close()
    bob_cli.close()
