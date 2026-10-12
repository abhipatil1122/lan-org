import socket
import threading
from server.connection_manager import ConnectionManager
from server.message_router import MessageRouter
from server.transfer_manager import TransferManager
from server.client_handler import ClientHandler
from shared.protocol import encode_message, decode_message


def test_login_validation_rules():
    conn_mgr = ConnectionManager()
    router = MessageRouter(conn_mgr)
    xfer_mgr = TransferManager()

    # 1. Empty username rejected
    srv_sock, cli_sock = socket.socketpair()
    handler = ClientHandler(srv_sock, ("127.0.0.1", 10001), conn_mgr, router, xfer_mgr)
    t = threading.Thread(target=handler.run, daemon=True)
    t.start()

    cli_sock.sendall(encode_message({"type": "login", "username": ""}))
    err_msg = decode_message(cli_sock)
    assert err_msg["type"] == "error"
    assert "empty" in err_msg["message"].lower()
    cli_sock.close()
    srv_sock.close()

    # 2. Username too long rejected (> 20 chars)
    srv_sock, cli_sock = socket.socketpair()
    handler = ClientHandler(srv_sock, ("127.0.0.1", 10002), conn_mgr, router, xfer_mgr)
    t = threading.Thread(target=handler.run, daemon=True)
    t.start()

    cli_sock.sendall(encode_message({"type": "login", "username": "a" * 21}))
    err_msg = decode_message(cli_sock)
    assert err_msg["type"] == "error"
    assert "20" in err_msg["message"]
    cli_sock.close()
    srv_sock.close()

    # 3. Invalid characters rejected
    srv_sock, cli_sock = socket.socketpair()
    handler = ClientHandler(srv_sock, ("127.0.0.1", 10003), conn_mgr, router, xfer_mgr)
    t = threading.Thread(target=handler.run, daemon=True)
    t.start()

    cli_sock.sendall(encode_message({"type": "login", "username": "bad user!"}))
    err_msg = decode_message(cli_sock)
    assert err_msg["type"] == "error"
    assert "letters, numbers" in err_msg["message"].lower()
    cli_sock.close()
    srv_sock.close()

    # 4. Duplicate username rejected
    srv_sock1, cli_sock1 = socket.socketpair()
    handler1 = ClientHandler(srv_sock1, ("127.0.0.1", 10004), conn_mgr, router, xfer_mgr)
    t1 = threading.Thread(target=handler1.run, daemon=True)
    t1.start()

    cli_sock1.sendall(encode_message({"type": "login", "username": "Alice"}))
    resp1 = decode_message(cli_sock1)
    assert resp1["type"] == "login_success"

    srv_sock2, cli_sock2 = socket.socketpair()
    handler2 = ClientHandler(srv_sock2, ("127.0.0.1", 10005), conn_mgr, router, xfer_mgr)
    t2 = threading.Thread(target=handler2.run, daemon=True)
    t2.start()

    cli_sock2.sendall(encode_message({"type": "login", "username": "Alice"}))
    resp2 = decode_message(cli_sock2)
    assert resp2["type"] == "error"
    assert "already exists" in resp2["message"].lower()

    cli_sock1.close()
    srv_sock1.close()
    cli_sock2.close()
    srv_sock2.close()
