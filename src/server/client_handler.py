from shared.config import (
    MAX_USERNAME_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_FILE_SIZE
)
from shared.protocol import (
    encode_message,
    encode_file_chunk,
    decode_packet,
    decode_message_data,
    decode_file_chunk,
    TYPE_JSON,
    TYPE_BINARY
)

class ClientHandler:
    def __init__(
        self,
        client_socket,
        address,
        connection_manager,
        router,
        transfer_manager
    ):
        self.client_socket = client_socket
        self.address = address
        self.connection_manager = connection_manager
        self.router = router
        self.transfer_manager = transfer_manager
        self.username = None
        self.active_transfer = None

    def run(self):
        try:
            self.login()

            while True:
                packet_type, data = decode_packet(
                    self.client_socket
                )

                if packet_type == TYPE_JSON:
                    message = decode_message_data(data)
                    message_type = message.get("type")

                    if message_type == "chat":
                        self.handle_chat(message)

                    elif message_type == "private_message":
                        self.handle_private_message(message)

                    elif message_type == "users":
                        self.send_users()

                    elif message_type == "file_send":
                        self.handle_file_send(message)

                    elif message_type == "file_accept":
                        self.handle_file_accept(message)

                    elif message_type == "quit":
                        break

                    else:
                        self.send_error(
                            "Unknown message type"
                        )

                elif packet_type == TYPE_BINARY:
                    self.handle_file_chunk(data)

                else:
                    self.send_error(
                        "Unknown packet type"
                    )

        except (
            ConnectionError,
            OSError,
            ValueError
        ):
            pass

        finally:
            self.disconnect()

    def login(self):
        packet_type, data = decode_packet(
            self.client_socket
        )

        if packet_type != TYPE_JSON:
            raise ConnectionError(
                "Login required"
            )

        message = decode_message_data(data)

        if message.get("type") != "login":
            raise ConnectionError(
                "Login required"
            )

        username = message.get(
            "username",
            ""
        ).strip()

        if not username:
            self.send_error(
                "Username cannot be empty"
            )
            raise ConnectionError(
                "Empty username"
            )

        if len(username) > MAX_USERNAME_LENGTH:
            self.send_error(
                f"Username must be {MAX_USERNAME_LENGTH} characters or less"
            )
            raise ConnectionError(
                "Username too long"
            )

        if not username.replace(
            "_",
            ""
        ).isalnum():
            self.send_error(
                "Username can contain only "
                "letters, numbers and _"
            )
            raise ConnectionError(
                "Invalid username"
            )

        if not self.connection_manager.add_client(
            username,
            self.client_socket
        ):
            self.send_error(
                "Username already exists"
            )
            raise ConnectionError(
                "Duplicate username"
            )

        self.username = username

        print(f"User logged in: {username} from {self.address}")

        self.client_socket.sendall(
            encode_message({
                "type": "login_success",
                "message": f"Welcome {username}"
            })
        )

        self.connection_manager.broadcast(
            encode_message({
                "type": "system",
                "message": (
                    f"{username} joined the chat"
                )
            }),
            exclude=username
        )

    def handle_chat(self, message):
        text = message.get(
            "message",
            ""
        ).strip()

        if not text:
            return

        if len(text) > MAX_MESSAGE_LENGTH:
            self.send_error(
                f"Message is too long. Maximum {MAX_MESSAGE_LENGTH} characters."
            )
            return

        self.router.broadcast_message(
            self.username,
            text
        )

    def handle_private_message(self, message):
        receiver = message.get(
            "receiver",
            ""
        ).strip()

        text = message.get(
            "message",
            ""
        ).strip()

        if not receiver or not text:
            self.send_error(
                "Invalid private message"
            )
            return

        if len(text) > MAX_MESSAGE_LENGTH:
            self.send_error(
                f"Message is too long. Maximum {MAX_MESSAGE_LENGTH} characters."
            )
            return

        success = self.router.private_message(
            self.username,
            receiver,
            text
        )

        if not success:
            self.send_error(
                f"User '{receiver}' is not online"
            )

    def send_users(self):
        self.client_socket.sendall(
            encode_message({
                "type": "users",
                "users": (
                    self.connection_manager
                    .get_users()
                )
            })
        )

    def handle_file_send(self, message):
        receiver = message.get(
            "receiver",
            ""
        ).strip()

        filename = message.get(
            "filename",
            ""
        ).strip()

        file_size = message.get("size")
        file_hash = message.get("sha256")

        if not receiver or not filename:
            self.send_error(
                "Invalid file transfer request"
            )
            return

        if file_size is None or not file_hash:
            self.send_error(
                "File metadata is missing"
            )
            return

        if not isinstance(file_size, int) or file_size < 0 or file_size > MAX_FILE_SIZE:
            self.send_error(
                f"File size must be between 0 and {MAX_FILE_SIZE} bytes"
            )
            return

        receiver_socket = (
            self.connection_manager
            .get_client(receiver)
        )

        if receiver_socket is None:
            self.send_error(
                f"User '{receiver}' is not online"
            )
            return

        transfer = (
            self.transfer_manager.create_transfer(
                sender=self.username,
                receiver=receiver,
                filename=filename,
                size=file_size,
                sha256=file_hash
            )
        )

        transfer_id = transfer["transfer_id"]

        # Track transferred bytes
        transfer["bytes_transferred"] = 0

        self.client_socket.sendall(
            encode_message({
                "type": "file_ready",
                "receiver": receiver,
                "filename": filename,
                "transfer_id": transfer_id
            })
        )

        receiver_socket.sendall(
            encode_message({
                "type": "file_request",
                "sender": self.username,
                "filename": filename,
                "transfer_id": transfer_id,
                "size": file_size,
                "sha256": file_hash
            })
        )

    def handle_file_accept(self, message):
        transfer_id = message.get(
            "transfer_id"
        )

        if not transfer_id:
            self.send_error(
                "Transfer ID is required"
            )
            return

        transfer = (
            self.transfer_manager
            .accept_transfer(transfer_id)
        )

        if transfer is None:
            self.send_error(
                "Invalid or expired file transfer"
            )
            return

        if transfer["receiver"] != self.username:
            self.send_error(
                "You cannot accept this transfer"
            )
            return

        sender_socket = (
            self.connection_manager
            .get_client(
                transfer["sender"]
            )
        )

        if sender_socket is None:
            self.send_error(
                "Sender is no longer online"
            )
            return

        sender_socket.sendall(
            encode_message({
                "type": "file_accepted",
                "transfer_id": transfer_id,
                "receiver": self.username,
                "filename": transfer["filename"]
            })
        )

        self.client_socket.sendall(
            encode_message({
                "type": "file_started",
                "transfer_id": transfer_id,
                "filename": transfer["filename"]
            })
        )

        if transfer["size"] == 0:
            transfer["status"] = "completed"
            self.client_socket.sendall(
                encode_message({
                    "type": "file_complete",
                    "transfer_id": transfer_id,
                    "filename": transfer["filename"],
                    "size": 0,
                    "sha256": transfer["sha256"]
                })
            )

    def handle_file_chunk(self, data):
        transfer_id, chunk = (
            decode_file_chunk(data)
        )

        transfer = (
            self.transfer_manager
            .get_transfer(transfer_id)
        )

        if transfer is None:
            self.send_error(
                "Invalid transfer ID"
            )
            return

        if transfer["sender"] != self.username:
            self.send_error(
                "You are not the sender"
            )
            return

        if transfer["status"] != "accepted":
            self.send_error(
                "File transfer has not been accepted"
            )
            return

        receiver_socket = (
            self.connection_manager
            .get_client(
                transfer["receiver"]
            )
        )

        if receiver_socket is None:
            self.send_error(
                "Receiver is no longer online"
            )
            return

        # Count transferred bytes
        transfer["bytes_transferred"] += len(chunk)

        # Prevent sender from sending more than declared size
        if transfer["bytes_transferred"] > transfer["size"]:
            self.send_error(
                "File size exceeds declared size"
            )

            transfer["status"] = "failed"
            return

        # Forward chunk to receiver
        receiver_socket.sendall(
            encode_file_chunk(
                transfer_id,
                chunk
            )
        )

        # Check if complete
        if transfer["bytes_transferred"] == transfer["size"]:

            transfer["status"] = "completed"

            receiver_socket.sendall(
                encode_message({
                    "type": "file_complete",
                    "transfer_id": transfer_id,
                    "filename": transfer["filename"],
                    "size": transfer["size"],
                    "sha256": transfer["sha256"]
                })
            )

    def send_error(self, message):
        try:
            self.client_socket.sendall(
                encode_message({
                    "type": "error",
                    "message": message
                })
            )
        except OSError:
            pass

    def disconnect(self):
        if self.username:
            print(f"User disconnected: {self.username}")
            self.connection_manager.remove_client(
                self.username
            )

            self.connection_manager.broadcast(
                encode_message({
                    "type": "system",
                    "message": (
                        f"{self.username} "
                        "left the chat"
                    )
                })
            )

            self.username = None

        try:
            self.client_socket.close()
        except OSError:
            pass