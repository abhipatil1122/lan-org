from client.commands import parse_command


def test_parse_users():
    cmd = parse_command("/users")
    assert cmd == {"type": "users"}


def test_parse_quit():
    cmd = parse_command("/quit")
    assert cmd == {"type": "quit"}


def test_parse_help():
    cmd = parse_command("/help")
    assert cmd == {"type": "help"}


def test_parse_private_message():
    cmd = parse_command("/msg Bob Hello Bob")
    assert cmd == {
        "type": "private_message",
        "receiver": "Bob",
        "message": "Hello Bob"
    }


def test_parse_file_send():
    cmd = parse_command("/send Bob test.txt")
    assert cmd == {
        "type": "file_send",
        "receiver": "Bob",
        "filename": "test.txt"
    }


def test_parse_file_accept():
    cmd = parse_command("/accept 2fdb91c6-a635-4008-ad0e-56de694c363e")
    assert cmd == {
        "type": "file_accept",
        "transfer_id": "2fdb91c6-a635-4008-ad0e-56de694c363e"
    }


def test_parse_normal_chat():
    cmd = parse_command("Hello everyone")
    assert cmd == {
        "type": "chat",
        "message": "Hello everyone"
    }


def test_parse_invalid():
    assert parse_command("") is None
    assert parse_command("   ") is None
    assert parse_command("/msg") is None
    assert parse_command("/msg Bob") is None
    assert parse_command("/send") is None
    assert parse_command("/send Bob") is None
    assert parse_command("/accept") is None
