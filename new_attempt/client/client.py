import socket
import threading

# Define the host and port number
HOST = 'localhost'
PORT = 8000

# Create a socket object
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to the server
client_socket.connect((HOST, PORT))

# Define a function to receive messages from the server
def receive_messages():
    while True:
        data = client_socket.recv(1024)
        if not data:
            break
        print(data.decode())

# Start a new thread to receive messages from the server
receive_thread = threading.Thread(target=receive_messages)
receive_thread.start()

# Send the client's name and chat room name to the server
client_socket.sendall(input("Enter your name: ").encode())
client_socket.sendall(input("Enter chat room name: ").encode())

while True:
    message = input()  # Read input from the user
    if message == "/leave":
        # Handle client request to leave the chat room
        client_socket.sendall(message.encode())
        break
    elif message.startswith("/join "):
        # Handle client request to join a new chat room
        client_socket.sendall(message.encode())
        response = client_socket.recv(1024).decode()
        print(response)
    else:
        # Send the message to the server to be broadcast to the chat room
        client_socket.sendall(message.encode())

# Close the socket connection
#client_socket.close()