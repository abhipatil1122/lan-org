import threading


class ConnectionManager:

    def __init__(self):
        self.clients = {}
        self.lock = threading.Lock()

    def add_client(self, username, client_socket):
        with self.lock:
            if username in self.clients:
                return False

            self.clients[username] = client_socket
            return True

    def remove_client(self, username):
        with self.lock:
            self.clients.pop(username, None)

    def get_client(self, username):
        with self.lock:
            return self.clients.get(username)

    def get_users(self):
        with self.lock:
            return list(self.clients.keys())

    def broadcast(self, message, exclude=None):
        with self.lock:
            clients = list(self.clients.items())

        for username, client_socket in clients:
            if username == exclude:
                continue

            try:
                client_socket.sendall(message)
            except OSError:
                self.remove_client(username)