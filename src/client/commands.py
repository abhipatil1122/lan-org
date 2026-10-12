from typing import Any

def parse_command(message: str) -> dict[str, Any] | None:
    message = message.strip()
    if not message:
        return None

    if message in ("/help", "?"):
        return {
            "type": "help"
        }

    if message == "/users":
        return {
            "type": "users"
        }

    if message == "/quit":
        return {
            "type": "quit"
        }

    if message == "/accept" or message.startswith("/accept "):
        parts = message.split(" ", 1)
        if len(parts) != 2 or not parts[1].strip():
            return None

        return {
            "type": "file_accept",
            "transfer_id": parts[1].strip()
        }

    if message == "/msg" or message.startswith("/msg "):
        parts = message.split(" ", 2)
        if len(parts) != 3 or not parts[1].strip() or not parts[2].strip():
            return None

        return {
            "type": "private_message",
            "receiver": parts[1].strip(),
            "message": parts[2].strip()
        }

    if message == "/send" or message.startswith("/send "):
        parts = message.split(" ", 2)
        if len(parts) != 3 or not parts[1].strip() or not parts[2].strip():
            return None

        return {
            "type": "file_send",
            "receiver": parts[1].strip(),
            "filename": parts[2].strip()
        }

    return {
        "type": "chat",
        "message": message
    }