import socket
import threading

HOST = '127.0.0.1'
PORT = 1234

def receive_messages(sock):
    while True:
        data = sock.recv(1024)
        if not data:
            break
        print('Received:', data.decode())

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print('Connected to server')

    # Start a new thread to receive messages
    thread = threading.Thread(target=receive_messages, args=(s,))
    thread.daemon = True
    thread.start()

    while True:
        message = input('Enter message: ')
        s.sendall(message.encode())
        if message.lower() == 'exit':
            break

    # Wait for the thread to finish
    thread.join()