import socket
import threading
import paho.mqtt.client as mqtt

HOST = '127.0.0.1'
PORT = 1234

ROOM_PORT = 0

room_socket =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
room_connected = False
game_started = False
game_finished = False
client_role = None

#get list of mqtt topics
#TODO: infected should not participate in election!
#TODO: MQTT functionality

def handle_room_logic():
    global room_connected
    global game_started
    global game_finished
    global client_role
    while True:
        if(room_connected):
            if (not game_started):
                # Step 1: Go through room setup
                data = room_socket.recv(1024)
                
                if not data:
                    # if room has died #TODO test whether recv is blocking properly
                    room_connected = False
                    continue
                
                message = eval('dict('+data.decode()+')')
                if message['command'] == "wait":
                    continue
                elif message['command'] == "start":
                    client_role = message['option']
                    game_started = True
                    print("Game has started!")
                    print("Your role is: " + client_role)
            else:
                # Step 2: listen for game finish
                data = room_socket.recv(1024)

                if not data:
                    # if room has died
                    room_connected = False
                    continue
                if message['command'] == "finish":
                    game_finished = True
                    break


def receive_messages(matchmaker_sock):
    global room_connected
    global room_socket
    global ROOM_PORT
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

while not game_finished:
    if (game_started):
        chat_message = input('Enter message: ')
        # TODO: MQTT logic here
        #matchmaker_socket.sendall(message.encode())
        #if message.lower() == '/exit':
        #   break

print("Game has finished!")
# Wait for the thread to finish
thread.join()
thread_room.join()
