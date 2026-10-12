import threading
from shared.protocol import (
    decode_packet,
    decode_message_data,
    decode_file_chunk,
    TYPE_JSON,
    TYPE_BINARY
)

def receive_messages(sock, file_transfer, stop_event=None, session=None):
    while True:
        try:
            packet_type, data = decode_packet(sock)

            if packet_type == TYPE_JSON:
                message = decode_message_data(data)
                message_type = message.get("type")

                if message_type == "chat":
                    print(f"[{message['sender']}]: {message['message']}")

                elif message_type == "private_message":
                    print(f"[DM from {message['sender']}]: {message['message']}")

                elif message_type == "system":
                    print(f"[System]: {message['message']}")

                elif message_type == "users":
                    print("\nOnline users:")
                    for user in message["users"]:
                        print(f" - {user}")

                elif message_type == "login_success":
                    print(f"[Server]: {message['message']}")

                elif message_type == "error":
                    print(f"[Error]: {message['message']}")

                elif message_type == "file_request":
                    print(
                        f"\n[File Request] "
                        f"{message['sender']} wants to send "
                        f"{message['filename']}"
                    )
                    print(f"Transfer ID: {message['transfer_id']}")
                    print(f"Type: /accept {message['transfer_id']}")

                elif message_type == "file_ready":
                    print(
                        f"\n[File] Transfer created: "
                        f"{message['filename']}"
                    )
                    print(
                        f"[File] Transfer ID: "
                        f"{message['transfer_id']}"
                    )

                    stored_path = file_transfer.pending_files.get(
                        message["filename"],
                        message["filename"]
                    )
                    file_transfer.add_pending_file(
                        message["transfer_id"],
                        stored_path
                    )

                elif message_type == "file_accepted":
                    print(
                        f"\n[File] "
                        f"{message['receiver']} accepted "
                        f"{message['filename']}"
                    )

                    file_path = file_transfer.pending_files.get(
                        message["transfer_id"]
                    )
                    if file_path is None:
                        file_path = file_transfer.pending_files.get(
                            message["filename"]
                        )

                    if file_path is None:
                        print("[File Error]: Original file not found")
                        continue

                    # Send file in a background worker thread to keep receiver thread unblocked
                    def send_worker(fpath, tid):
                        try:
                            result = file_transfer.send_file(
                                fpath,
                                tid
                            )
                            print(f"[File] Sent {result['size']} bytes")
                        except (OSError, ValueError) as e:
                            print(f"[File Error]: {e}")

                    threading.Thread(
                        target=send_worker,
                        args=(file_path, message["transfer_id"]),
                        daemon=True
                    ).start()

                elif message_type == "file_started":
                    print(
                        f"\n[File] Starting transfer: "
                        f"{message['filename']}"
                    )

                elif message_type == "file_complete":
                    print(
                        f"\n[File] Finalizing "
                        f"{message['filename']}..."
                    )

                    try:
                        file_path = file_transfer.complete_receive(
                            transfer_id=message["transfer_id"],
                            filename=message["filename"],
                            expected_size=message["size"],
                            expected_hash=message["sha256"]
                        )

                        print(
                            f"[File] Successfully received: "
                            f"{file_path}"
                        )

                    except (OSError, ValueError) as e:
                        print(f"[File Error]: {e}")

            elif packet_type == TYPE_BINARY:
                transfer_id, chunk = decode_file_chunk(data)

                file_transfer.receive_chunk(
                    transfer_id,
                    chunk
                )

            else:
                print("[Error]: Unknown packet type")

        except (ConnectionError, OSError, ValueError):
            print("\nDisconnected from server.")
            if stop_event:
                stop_event.set()
            if session and session.app and session.app.is_running:
                session.app.exit()
            break