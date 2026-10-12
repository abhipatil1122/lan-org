import socket
import threading
import sys
import os
from pathlib import Path


# Ensure src directory is in sys.path for direct execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from shared.protocol import encode_message
from client.receiver import receive_messages
from client.commands import parse_command
from client.file_transfer import FileTransfer
from shared.config import PORT


def print_help():
    print("\nAvailable Commands:")
    print("  <message>                 - Send public chat message to everyone")
    print("  /msg <user> <message>     - Send private message to specific user")
    print("  /users                    - List all currently online users")
    print("  /send <user> <filepath>   - Request file transfer to user")
    print("  /accept <transfer_id>     - Accept incoming file transfer")
    print("  /help                     - Show this help menu")
    print("  /quit                     - Disconnect and exit\n")


def start_client():
    server_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    server_port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT

    client_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    try:
        client_socket.connect(
            (server_host, server_port)
        )
    except OSError as e:
        print(f"[Error]: Could not connect to server at {server_host}:{server_port}: {e}")
        return

    username = input("Username: ").strip()

    file_transfer = FileTransfer(
        client_socket
    )

    stop_event = threading.Event()
    session = PromptSession()

    # LOGIN
    login_message = {
        "type": "login",
        "username": username
    }

    try:
        client_socket.sendall(
            encode_message(login_message)
        )
    except OSError as e:
        print(f"[Error]: Failed to send login message: {e}")
        client_socket.close()
        return

    # RECEIVER THREAD
    receiver_thread = threading.Thread(
        target=receive_messages,
        args=(
            client_socket,
            file_transfer,
            stop_event,
            session
        ),
        daemon=True
    )
    receiver_thread.start()

    # COMMAND LOOP
    with patch_stdout():
        while not stop_event.is_set():
            try:
                message = session.prompt("> ")
                if stop_event.is_set():
                    break

                command = parse_command(
                    message
                )

                if command is None:
                    print("Invalid command. Type /help for available commands.")
                    continue

                if command["type"] == "help":
                    print_help()
                    continue

                # FILE SEND
                if command["type"] == "file_send":
                    raw_path = command["filename"]
                    base_filename = os.path.basename(raw_path)
                    abs_path = os.path.abspath(raw_path)

                    valid, error = (
                        file_transfer.validate_file(
                            abs_path
                        )
                    )

                    if not valid:
                        print(
                            f"[File Error]: {error}"
                        )
                        continue

                    file_size = (
                        file_transfer.get_file_size(
                            abs_path
                        )
                    )

                    file_hash = (
                        file_transfer.calculate_hash(
                            abs_path
                        )
                    )

                    file_transfer.pending_files[base_filename] = abs_path
                    file_transfer.pending_files[raw_path] = abs_path

                    command["filename"] = base_filename
                    command["size"] = file_size
                    command["sha256"] = file_hash

                    print(
                        f"[File] {raw_path}"
                    )
                    print(
                        f"[File] Size: {file_size} bytes"
                    )
                    print(
                        f"[File] SHA-256: {file_hash}"
                    )

                # PRIVATE MESSAGE LOCAL FEEDBACK
                if command["type"] == "private_message":
                    print(f"[DM to {command['receiver']}]: {command['message']}")

                # SEND COMMAND TO SERVER
                try:
                    client_socket.sendall(
                        encode_message(command)
                    )
                except OSError:
                    break

                # QUIT
                if command["type"] == "quit":
                    break

            except (KeyboardInterrupt, EOFError):
                try:
                    client_socket.sendall(
                        encode_message({
                            "type": "quit"
                        })
                    )
                except OSError:
                    pass
                break

    stop_event.set()
    try:
        client_socket.shutdown(
            socket.SHUT_RDWR
        )
    except OSError:
        pass

    client_socket.close()
    receiver_thread.join(timeout=0.5)


if __name__ == "__main__":
    start_client()