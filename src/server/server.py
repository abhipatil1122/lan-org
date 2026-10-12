import socket
import threading
import sys
from pathlib import Path

# Ensure src directory is in sys.path for direct execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.logger import setup_logger
from server.client_handler import ClientHandler
from server.connection_manager import ConnectionManager
from server.message_router import MessageRouter
from server.transfer_manager import TransferManager

from shared.config import HOST, PORT


def handle_server_commands(connection_manager):
    while True:
        try:
            line = input().strip()
            if not line:
                continue
            cmd = line.lower()
            if cmd in ("users", "clients", "list"):
                users = connection_manager.get_users()
                if users:
                    print(f"Online users ({len(users)}): {', '.join(users)}")
                else:
                    print("No users currently online.")
            elif cmd in ("help", "?"):
                print("Server commands:")
                print("  users / clients / list - Show all currently online users")
                print("  help                   - Show this help message")
            else:
                print(f"Unknown command: '{line}'. Type 'users' to list online users.")
        except (EOFError, KeyboardInterrupt):
            break


def start_server():

    logger = setup_logger()

    logger.info(
        f"LAN Chat Server running on {HOST}:{PORT}"
    )

    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server_socket.bind(
        (HOST, PORT)
    )

    server_socket.listen()

    connection_manager = ConnectionManager()

    router = MessageRouter(connection_manager)

    transfer_manager = TransferManager()

    # Start CLI thread for server terminal commands
    cli_thread = threading.Thread(
        target=handle_server_commands,
        args=(connection_manager,),
        daemon=True
    )
    cli_thread.start()

    print(
        f"LAN Chat Server running on {HOST}:{PORT}"
    )
    print("Type 'users' to list online clients, or 'help' for commands.")

    while True:

        client_socket, address = (
            server_socket.accept()
        )

        print(
            f"Client connected: {address}"
        )

        handler = ClientHandler(
            client_socket,
            address,
            connection_manager,
            router,
            transfer_manager
        )

        thread = threading.Thread(
            target=handler.run,
            daemon=True
        )

        thread.start()


if __name__ == "__main__":
    start_server()