# LAN Chat & File Transfer System

A multi-threaded client-server application built with Python for real-time messaging, private communications, and reliable chunked file transfers across a Local Area Network (LAN) or Wi-Fi.

---

## 1. Project Overview & Architecture

The system uses a **Client-Server Architecture** operating over TCP sockets on a local network (LAN / Wi-Fi):

```
                 LAN / Wi-Fi
                     │
          ┌──────────┴──────────┐
          │                     │
      Alice PC               Bob PC
       Client                 Client
          │                     │
          └────────┐   ┌────────┘
                   │   │
                ┌──▼───▼──┐
                │  SERVER │
                └─────────┘
```

The **Server** manages active connections, routes messages, and relays file chunks. The **Clients** provide a terminal-based interface with auto-refreshing input powered by `prompt-toolkit`.

### Message Relay Example:
```
Alice ───► "Hello Bob" ───► Server ───► Bob
```

### File Transfer Relay Example:
```
Alice (test.txt)
   │
   │ File chunks (64 KB)
   ▼
Server
   │
   │ Binary packets (Type 2)
   ▼
Bob
   │
   ▼
received_files/test.txt
```

> **Key Design Decision:** The server operates as a pure stream relay; it does **not** permanently store files on disk. Bob's client receives the stream and saves it directly to local disk (`received_files/`).

---

## 2. Main Features

### A. Multiple Clients (Multi-Threaded Server)
The server accepts multiple simultaneous TCP connections. Each connected client is assigned a dedicated daemon thread:

```python
threading.Thread(target=handler.run, daemon=True).start()
```

- `Alice`   ──► `Thread 1`
- `Bob`     ──► `Thread 2`
- `Charlie` ──► `Thread 3`

This allows Alice, Bob, and Charlie to send messages and transfer files concurrently without blocking one another.

### B. Login & Username Validation
When a client connects, they are prompted for a username:
```
Username: Alice
```

The client transmits a JSON handshake packet:
```json
{
    "type": "login",
    "username": "Alice"
}
```

The server validates the username:
- **Non-empty:** Cannot be blank or whitespace.
- **Length:** Maximum 20 characters (`MAX_USERNAME_LENGTH`).
- **Allowed characters:** Alphanumeric and underscore characters only (`letters, numbers, _`).
- **Uniqueness:** Checked against `ConnectionManager` to ensure no duplicate online usernames.

Upon success:
```
[Server]: Welcome Alice
```
And a broadcast is sent to all existing peers: `[System]: Alice joined the chat`.

---

## 3. Normal Chat (Broadcast)
When Alice types:
```
Hello everyone
```

The client command parser constructs:
```json
{
    "type": "chat",
    "message": "Hello everyone"
}
```

The server receives the packet and broadcasts it to all connected users (excluding Alice).
Bob sees:
```
[Alice]: Hello everyone
```

---

## 4. Private Messaging (Direct Message)
To send a private message to a specific user:
```
/msg Bob Hello Bob
```

The command parser formats the payload:
```json
{
    "type": "private_message",
    "receiver": "Bob",
    "message": "Hello Bob"
}
```

The server locates Bob's socket using `ConnectionManager.get_client("Bob")` and forwards the message strictly to Bob.
- **Bob sees:** `[DM from Alice]: Hello Bob`
- **Alice sees:** `[DM to Bob]: Hello Bob`
- If Bob is not online, the server returns an error: `[Error]: User 'Bob' is not online`.

---

## 5. Online Users
To query active users on the network:
```
/users
```

The server queries `ConnectionManager.get_users()` and returns:
```
Online users:
 - Alice
 - Bob
 - Charlie
```

---

## 6. File Transfer Workflow
Alice can send any local file to Bob using:
```
/send Bob test.txt
```

### Complete Transfer Sequence:
```
Alice                                 Server                                 Bob
  │                                     │                                     │
  │─── 1. file_send (metadata) ────────►│                                     │
  │                                     │─── 2. file_request (with UUID) ────►│
  │◄── 3. file_ready (with UUID) ───────│                                     │
  │                                     │                                     │ [Bob prompts: /accept <UUID>]
  │                                     │◄── 4. file_accept ──────────────────│
  │                                     │                                     │
  │◄── 5. file_accepted ────────────────│─── 6. file_started ────────────────►│
  │                                     │                                     │
  │─── 7. Binary Chunks (Type 2) ──────►│─── 8. Binary Chunks (relayed) ─────►│ (Writes to .part file)
  │                                     │                                     │
  │                                     │─── 9. file_complete ───────────────►│ (Verifies size & SHA-256)
  │                                                                           │ (Promotes .part -> test.txt)
```

1. **Request:** Alice computes file size and SHA-256 hash, then sends `file_send`.
2. **Notification:** Bob receives:
   ```
   [File Request] Alice wants to send test.txt
   Transfer ID: 2fdb91c6-a635-4008-ad0e-56de694c363e
   Type: /accept 2fdb91c6-a635-4008-ad0e-56de694c363e
   ```
3. **Acceptance:** Bob types `/accept 2fdb91c6-a635-4008-ad0e-56de694c363e`.
4. **Streaming:** Alice streams binary chunks in a background thread without blocking chat.
5. **Finalization:** Bob verifies size and SHA-256 hash. If valid, the file is saved to `received_files/test.txt`.

---

## 7. Transfer ID (UUID Tracking)

Every file transfer is identified by a unique UUID:
```
2fdb91c6-a635-4008-ad0e-56de694c363e
```

### Why a Transfer ID is Essential:
1. **Disambiguation:** Alice could simultaneously send `test.txt` to Bob and `image.jpg` to Charlie, or David could send `document.pdf` to Bob.
2. **State Management:** `TransferManager` tracks each active transfer with thread-safety:
   ```json
   {
       "transfer_id": "2fdb91c6-a635-4008-ad0e-56de694c363e",
       "sender": "Alice",
       "receiver": "Bob",
       "filename": "test.txt",
       "size": 32,
       "sha256": "76c6a15b865a0cb5e0ac808a5fc7ae192a938e6d3fb032ec1b3a5b0fa64f85bc",
       "status": "pending",
       "bytes_transferred": 0
   }
   ```
3. **Targeted Packet Routing:** Every binary packet carries this ID, ensuring the server forwards chunks to the correct recipient.

---

## 8. Chunked File Streaming

Files are not loaded into memory or transmitted in one giant block. Instead, files are sliced into standard chunks:

```python
chunk = file.read(FILE_CHUNK_SIZE)  # 64 KB (65,536 bytes)
```

```
test.txt
   │
   ├── Chunk 1 (64 KB)
   ├── Chunk 2 (64 KB)
   ├── Chunk 3 (64 KB)
   └── Chunk 4 (remaining bytes)
```

### Advantages:
- **Low Memory Footprint:** Extremely small RAM consumption regardless of whether a file is 1 KB or 100 MB.
- **Flow Control:** Chunks are sent sequentially over TCP, allowing progress reporting and graceful handling of network delays.

---

## 9. Custom Application Protocol Framing

TCP is a **byte stream**, not a message protocol. TCP does not preserve message boundaries; packets may be fragmented or concatenated by the network.

To solve this, a custom framing structure is used for every transmission:

```
┌────────────┬──────────────┬─────────────────┐
│ Type       │ Length       │ Data Payload    │
│ 1 byte     │ 4 bytes      │ N bytes         │
└────────────┴──────────────┴─────────────────┘
```

Packets are packed using Python's `struct` module:
```python
struct.pack("!BI", packet_type, len(data))
```
- `!` : Network byte order (big-endian).
- `B` : 1 unsigned byte for `packet_type`.
- `I` : 4 unsigned bytes for `length` (up to 4 GB payload support).

The receiver reads exactly 5 bytes to inspect `(type, length)` and then performs `receive_exact(sock, length)` to retrieve the exact payload.

---

## 10. JSON Packets vs. Binary Packets

The protocol defines two packet types:
```python
TYPE_JSON = 1
TYPE_BINARY = 2
```

### JSON Packets (`TYPE_JSON = 1`)
Used for control messages, commands, and chat:
- Login (`{"type": "login", "username": "..."}`)
- Chat (`{"type": "chat", "message": "..."}`)
- Direct messages (`{"type": "private_message", "receiver": "...", ...}`)
- File invitations & acceptances (`file_send`, `file_request`, `file_accept`, `file_complete`)

### Binary Packets (`TYPE_BINARY = 2`)
Used exclusively for raw file chunk data:
```
┌──────────────────┬─────────────────┬────────────────┐
│ Transfer ID Len  │ Transfer ID     │ Raw Chunk Data │
│ 2 bytes (!H)     │ N bytes (UTF-8) │ M bytes        │
└──────────────────┴─────────────────┴────────────────┘
```
This separation avoids encoding binary data as Base64/JSON strings, eliminating 33% serialization overhead.

---

## 11. SHA-256 Integrity Verification

Before transmission, the sender computes the file's SHA-256 hash:
```
Original file ──► SHA-256 ──► 76c6a15b865a0cb5e0ac808a5fc7ae192a938e6d3fb032ec1b3a5b0fa64f85bc
```

Upon receiving the file, Bob calculates the SHA-256 hash over the received bytes:
```python
if original_hash == received_hash and original_size == received_size:
    # Integrity verified - accept file
else:
    # Data corrupted or tampered - reject and delete
```

> **Interview Distinction:** SHA-256 provides **data integrity**, not **encryption**. It guarantees that the data received matches the original byte-for-byte, but does not conceal the contents in transit.

---

## 12. Temporary `.part` Files & Atomic Promotion

When Bob receives chunks, the file is not immediately saved under its final name:

```
received_files/
└── .<transfer_id>.part
```

1. **During Transfer:** Chunks are written and flushed directly to `.<transfer_id>.part`.
2. **Verification:** When transmission completes, `size` and `SHA-256` are verified.
3. **Success:** The file is atomically renamed:
   ```
   .<transfer_id>.part  ──►  received_files/test.txt
   ```
4. **Failure:** If size or hash check fails, the `.part` file is deleted immediately.

This guarantees that incomplete or corrupted transfers never leave broken files in the user's destination folder.

---

## 13. Project Structure

```
lan/
├── pyproject.toml              # Build & dependency configuration
├── README.md                   # Complete architectural documentation
├── test.txt                    # Sample 32-byte test file
├── test2.txt                   # Sample 22-byte test file
├── received_files/             # Destination directory for incoming files
├── src/
│   ├── shared/
│   │   ├── config.py           # Host, Port (5050), Chunk size (64KB), Max limits
│   │   └── protocol.py         # Packet framing (!BI), JSON & Binary encoders/decoders
│   ├── server/
│   │   ├── server.py           # Multi-threaded TCP server & server CLI
│   │   ├── client_handler.py   # Per-client thread handler (login, chat, relay)
│   │   ├── connection_manager.py# Active client socket registry & thread-safe broadcast
│   │   ├── message_router.py   # Routing for broadcast and private DMs
│   │   ├── transfer_manager.py # UUID tracking for pending/accepted transfers
│   │   └── logger.py           # Formatted logging
│   └── client/
│       ├── client.py           # Client entrypoint, prompt session, LAN host support
│       ├── receiver.py         # Background receiver thread for incoming packets
│       ├── commands.py         # CLI slash command parser (/msg, /send, /accept, /users)
│       └── file_transfer.py    # Chunking, SHA-256 hashing, .part file management
└── tests/
    ├── test_protocol.py        # Protocol packing/unpacking unit tests
    ├── test_connection_manager.py# ConnectionManager tests
    ├── test_transfer_manager.py# TransferManager lifecycle tests
    ├── test_commands.py        # Command parser unit tests
    ├── test_file_transfer_client.py# Chunking, .part files, SHA-256 tests
    ├── test_server_rules.py    # Username and validation rule tests
    └── test_integration.py     # Full end-to-end chat & file transfer integration test
```

---

## 14. How to Run

### Requirements
- Python 3.12+
- `prompt-toolkit`

Install dependencies:
```bash
pip install -e .
# or with uv:
uv sync
```

---

### Step 1: Start the Server
Run on the host machine:
```bash
python src/server/server.py
```
Output:
```
2026-10-05 21:54:40 [INFO] LAN Chat Server running on 0.0.0.0:5050
LAN Chat Server running on 0.0.0.0:5050
Type 'users' to list online clients, or 'help' for commands.
```

The server accepts terminal commands:
- `users` — List online clients
- `help` — Show server commands

---

### Step 2: Start Clients

#### On the same machine (Localhost):
```bash
python src/client/client.py
```

#### Across the LAN / Wi-Fi:
Find the server PC's local IP address (e.g. `192.168.1.100`), then run on other PCs:
```bash
python src/client/client.py 192.168.1.100
```

---

### Step 3: Chat and Send Files

**1. Login:**
```
Username: Alice
[Server]: Welcome Alice
>
```

**2. Public Broadcast:**
```
> Hello everyone
```

**3. Online Users:**
```
> /users
Online users:
 - Alice
 - Bob
```

**4. Private Message:**
```
> /msg Bob Hello Bob!
[DM to Bob]: Hello Bob!
```

**5. Send a File:**
```
> /send Bob test.txt
[File] test.txt
[File] Size: 32 bytes
[File] SHA-256: 76c6a15b865a0cb5e0ac808a5fc7ae192a938e6d3fb032ec1b3a5b0fa64f85bc

[File] Transfer created: test.txt
[File] Transfer ID: 2fdb91c6-a635-4008-ad0e-56de694c363e
```

**6. Bob Accepts and Receives:**
```
[File Request] Alice wants to send test.txt
Transfer ID: 2fdb91c6-a635-4008-ad0e-56de694c363e
Type: /accept 2fdb91c6-a635-4008-ad0e-56de694c363e

> /accept 2fdb91c6-a635-4008-ad0e-56de694c363e
[File] Starting transfer: test.txt
[File] Receiving: 32 bytes
[File] Finalizing test.txt...
[File] Successfully received: received_files/test.txt
```

---

## 15. Running Automated Tests

Run the full test suite with `pytest`:
```bash
pytest -v
```

All 32 test cases cover framing, hashing, transfer IDs, edge cases, validation, and full end-to-end integration:
```
tests/test_commands.py PASSED
tests/test_connection_manager.py PASSED
tests/test_file_manager.py PASSED
tests/test_file_transfer_client.py PASSED
tests/test_integration.py PASSED
tests/test_protocol.py PASSED
tests/test_server_rules.py PASSED
tests/test_transfer_manager.py PASSED

32 passed in 0.05s
```
