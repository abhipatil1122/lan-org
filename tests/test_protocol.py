import socket
import struct
import pytest

from shared.protocol import (
    encode_message,
    decode_message,
    encode_binary,
    decode_binary,
    encode_file_chunk,
    decode_file_chunk,
    decode_packet,
    TYPE_JSON,
    TYPE_BINARY
)


def test_encode_message():
    message = {
        "type": "chat",
        "message": "Hello Bob"
    }

    encoded = encode_message(message)
    assert isinstance(encoded, bytes)
    # Check 5-byte header
    pkt_type, length = struct.unpack("!BI", encoded[:5])
    assert pkt_type == TYPE_JSON
    assert length == len(encoded) - 5


def test_decode_message():
    server, client = socket.socketpair()

    message = {
        "type": "chat",
        "message": "Hello Bob"
    }

    client.sendall(encode_message(message))
    decoded = decode_message(server)

    assert decoded == message

    server.close()
    client.close()


def test_multiple_messages():
    server, client = socket.socketpair()

    messages = [
        {"type": "chat", "message": "Hello"},
        {"type": "chat", "message": "How are you?"},
        {"type": "chat", "message": "Bye"}
    ]

    for message in messages:
        client.sendall(encode_message(message))

    for message in messages:
        decoded = decode_message(server)
        assert decoded == message

    server.close()
    client.close()


def test_binary_packet():
    server, client = socket.socketpair()

    raw_data = b"\x00\x01\x02\x03\xff\xfe"
    client.sendall(encode_binary(raw_data))

    decoded = decode_binary(server)
    assert decoded == raw_data

    server.close()
    client.close()


def test_file_chunk_encode_decode():
    transfer_id = "test-uuid-456"
    chunk_data = b"chunk of binary bytes here"

    packet = encode_file_chunk(transfer_id, chunk_data)
    assert isinstance(packet, bytes)

    # Decode packet header first
    pkt_type, payload = struct.unpack("!BI", packet[:5])
    assert pkt_type == TYPE_BINARY
    assert payload == len(packet[5:])

    # Decode payload
    tid, chunk = decode_file_chunk(packet[5:])
    assert tid == transfer_id
    assert chunk == chunk_data


def test_invalid_packet():
    server, client = socket.socketpair()

    # Sending binary when message expected
    client.sendall(encode_binary(b"123"))
    with pytest.raises(ValueError, match="Expected JSON"):
        decode_message(server)

    server.close()
    client.close()