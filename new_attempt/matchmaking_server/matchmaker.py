import socket

# Define the host and port number
HOST = 'localhost'
PORT = 8000

# Create a socket object
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to a specific address and port
server_socket.bind((HOST, PORT))

# Listen for incoming connections
server_socket.listen(4)

clients = []
chat_rooms = []

conn, addr = server_socket.accept()  # accept new connection
print(f"New client connected: {addr}")

# Send welcome message to the client
conn.sendall(b"Welcome to the chat room! Please enter your name: ")
name = conn.recv(1024).decode().strip()  # Receive the client's name
conn.sendall(b"Enter chat room name: ")
room_name = conn.recv(1024).decode().strip()  # Receive the chat room name

# Add the client to the list of connected clients
clients.append(conn)

# Add the client to the specified chat room
if room_name not in chat_rooms:
    chat_rooms.append(name)

# Send a message to all clients in the chat room
for client_name in chat_rooms:
    if client_name != name:
        client_conn = clients[client_name]
        client_conn.sendall(f"{name} has joined the chat room.".encode())

while True:
    data = conn.recv(1024)  # Receive data from the client
    if not data:
        break
    data = data.decode().strip()
    if data.startswith("/join "):
        # Handle client request to join a new chat room
        new_room = data.split("/join ")[1]
        if new_room not in chat_rooms:
            chat_rooms[new_room] = []
        chat_rooms[new_room].append(name)
        chat_rooms[room_name].remove(name)
        room_name = new_room
        conn.sendall(f"You have joined the '{new_room}' chat room.".encode())
        # Send a message to all clients in the new chat room
        for client_name in chat_rooms[new_room]:
            if client_name != name:
                client_conn = clients[client_name]
                client_conn.sendall(f"{name} has joined the chat room.".encode())
    elif data.startswith("/leave"):
        # Handle client request to leave the chat room
        chat_rooms[room_name].remove(name)
        conn.sendall("You have left the chat room.".encode())
        # Send a message to all clients in the chat room
        for client_name in chat_rooms[room_name]:
            client_conn = clients[client_name]
            client_conn.sendall(f"{name} has left the chat room.".encode())
        break
    else:
        # Broadcast the message to all clients in the chat room
        for client_name in chat_rooms[room_name]:
            if client_name != name:
                client_conn = clients[client_name]
                client_conn.sendall(f"{name}: {data}".encode())

# Remove the client from the list of connected clients
