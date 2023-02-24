import socket
import threading

HOST = '127.0.0.1'
PORT = 1234

ROOM_PORT = 0

room_socket =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
room_connected = False

def handle_room_logic():
    global room_connected
    while True:
        try:
            if(room_connected):
                room_socket.sendall(f"ping".encode())
        except Exception as e:
            room_connected = False
            print(e)

def receive_messages(matchmaker_sock):
    global room_connected
    global room_socket
    try:
        while True:
            data = matchmaker_sock.recv(1024)
            if not data:
                break
            message = data.decode()
            if "ping" not in message:
                print(message)
                message_decoded = eval('dict('+message+')')
                if message_decoded['command'] == "connect":
                    # connect to server
                    ROOM_PORT = message_decoded['options']
                    room_socket.connect((HOST, ROOM_PORT))
                    room_connected = True
                    print("Connecting...")
                elif message_decoded['command'] == "reconnect":
                    # reconnect
                    room_socket =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    room_socket.connect((HOST, ROOM_PORT))
                    room_connected = True
                    print("Reconnecting...")
    except Exception as e:
        print("Exception: " + str(e))

matchmaker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
matchmaker_socket.connect((HOST, PORT))
print('Connected to server')

# Start a new thread to receive messages
thread = threading.Thread(target=receive_messages, args=(matchmaker_socket,))
thread.daemon = True
thread.start()

thread_room = threading.Thread(target=handle_room_logic)
thread_room.daemon = True
thread_room.start()

while True:
    #message = input('Enter message: ')

    # TODO: define mqtt logic
    #matchmaker_socket.sendall(message.encode())
    #if message.lower() == '/exit':
     #   break

# Wait for the thread to finish
    thread.join()
    thread_room.join()
