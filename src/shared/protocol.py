import json
import struct


HEADER_SIZE = 5

TYPE_JSON = 1
TYPE_BINARY = 2


def encode_message(message):
    data = json.dumps(message).encode("utf-8")

    header = struct.pack(
        "!BI",
        TYPE_JSON,
        len(data)
    )

    return header + data


def encode_binary(data):
    header = struct.pack(
        "!BI",
        TYPE_BINARY,
        len(data)
    )

    return header + data


def receive_exact(sock, size):
    data = b""

    while len(data) < size:
        chunk = sock.recv(size - len(data))

        if not chunk:
            raise ConnectionError("Connection closed")

        data += chunk

    return data


def decode_packet(sock):
    header = receive_exact(sock, HEADER_SIZE)

    packet_type, length = struct.unpack(
        "!BI",
        header
    )

    data = receive_exact(sock, length)

    return packet_type, data


def decode_message(sock):
    packet_type, data = decode_packet(sock)

    if packet_type != TYPE_JSON:
        raise ValueError("Expected JSON message")

    return json.loads(data.decode("utf-8"))

def decode_binary(sock):
    packet_type, data = decode_packet(sock)

    if packet_type != TYPE_BINARY:
        raise ValueError("Expected binary packet")

    return data

def encode_file_chunk(transfer_id, data):
    transfer_id_bytes = transfer_id.encode("utf-8")

    payload = (
        struct.pack("!H", len(transfer_id_bytes))
        + transfer_id_bytes
        + data
    )

    header = struct.pack(
        "!BI",
        TYPE_BINARY,
        len(payload)
    )

    return header + payload

def decode_file_chunk(data):
    if len(data) < 2:
        raise ValueError(
            "Invalid file chunk"
        )

    transfer_id_length = struct.unpack(
        "!H",
        data[:2]
    )[0]
    if transfer_id_length == 0:
        raise ValueError(
            "Missing transfer ID"
        )

    if len(data) < 2 + transfer_id_length:
        raise ValueError(
            "Invalid transfer ID"
        )
    start = 2
    end = start + transfer_id_length

    transfer_id = data[start:end].decode(
        "utf-8"
    )

    chunk = data[end:]

    return transfer_id, chunk

def decode_message_data(data):
    return json.loads(
        data.decode("utf-8")
    )