from server.connection_manager import ConnectionManager


def test_add_client():
    manager = ConnectionManager()

    fake_socket = object()

    result = manager.add_client(
        "Alice",
        fake_socket
    )

    assert result is True
    assert manager.get_client("Alice") is fake_socket


def test_duplicate_username():
    manager = ConnectionManager()

    socket1 = object()
    socket2 = object()

    assert manager.add_client(
        "Alice",
        socket1
    ) is True

    assert manager.add_client(
        "Alice",
        socket2
    ) is False

    assert manager.get_client("Alice") is socket1


def test_remove_client():
    manager = ConnectionManager()

    fake_socket = object()

    manager.add_client(
        "Alice",
        fake_socket
    )

    manager.remove_client("Alice")

    assert manager.get_client("Alice") is None


def test_get_users():
    manager = ConnectionManager()

    manager.add_client("Alice", object())
    manager.add_client("Bob", object())

    users = manager.get_users()

    assert set(users) == {"Alice", "Bob"}