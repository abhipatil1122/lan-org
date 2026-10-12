from shared.protocol import encode_message


class MessageRouter:

    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    def broadcast_message(self, sender, message):
        data = {
            "type": "chat",
            "sender": sender,
            "message": message
        }

        encoded = encode_message(data)

        self.connection_manager.broadcast(
            encoded,
            exclude=sender
        )

    def private_message(self, sender, receiver, message):
        client = self.connection_manager.get_client(receiver)

        if not client:
            return False

        data = {
            "type": "private_message",
            "sender": sender,
            "message": message
        }

        client.sendall(encode_message(data))

        return True