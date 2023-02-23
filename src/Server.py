import socket
import select
import sys
import paho.mqtt.client as mqtt
import random
HEADER_LENGTH = 10
PORT_MQTT = 1883
TIMEOUT = 60

leader = True
GameInfo = True
Game_Full = False
index = 0
if len(sys.argv) != 2:
	print ("Correct usage: IP address, port number")
	exit()
Rooms_IP = str(sys.argv[2])
Rooms_PORT = int(sys.argv[2])                
room_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
room_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
room_socket.bind((Rooms_IP, Rooms_PORT))
room_socket.listen(4)
messages = []
broker = 'mqtt'
topic_chat = "chat"+ str(Rooms_PORT)
topic_election = "bully" + str(Rooms_PORT)
topic_master = "master" + str(Rooms_PORT)

sockets_list = [room_socket]
# List of connected clients - socket as a key, user header and name as data
clients = {}
print(f'Listening for connections on {Rooms_IP}:{Rooms_PORT}...')
# Handles message receiving
def receive_message(client_socket):
    try:
        # Receive our "header" containing message length, it's size is defined and constant
        message_header = client_socket.recv(HEADER_LENGTH)
        # If we received no data, client gracefully closed a connection, for example using socket.close() or socket.shutdown(socket.SHUT_RDWR)
        if not len(message_header):
            return False
        # Convert header to int value
        message_length = int(message_header.decode('utf-8').strip())
        # Return an object of message header and message data
        return {'header': message_header, 'data': client_socket.recv(message_length)}
    except:
        # If we are here, client closed connection violently, for example by pressing ctrl+c on his script
        # or just lost his connection
        # socket.close() also invokes socket.shutdown(socket.SHUT_RDWR) what sends information about closing the socket (shutdown read/write)
        # and that's also a cause when we receive an empty message
        return False
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe(topic_master)

def on_message(client, userdata, msg):
    message = msg.payload.decode()
    messages.append(message)
def StartGame():
    infected=random.choice(list)
    return infected

Room = mqtt.Client()
Room.on_connect = on_connect
Room.on_message = on_message
Room.connect(broker, PORT_MQTT, TIMEOUT)
Room.loop_start()
while True:
    # Calls Unix select() system call or Windows select() WinSock call with three parameters:
    #   - rlist - sockets to be monitored for incoming data
    #   - wlist - sockets for data to be send to (checks if for example buffers are not full and socket is ready to send some data)
    #   - xlist - sockets to be monitored for exceptions (we want to monitor all sockets for errors, so we can use rlist)
    # Returns lists:
    #   - reading - sockets we received some data on (that way we don't have to check sockets manually)
    #   - writing - sockets ready for data to be send thru them
    #   - errors  - sockets with some exceptions
    # This is a blocking call, code execution will "wait" here and "get" notified in case any action should be taken
    read_sockets, _, exception_sockets = select.select(sockets_list, [], sockets_list)
    # Iterate over notified sockets
    for notified_socket in read_sockets:
        # If notified socket is a server socket - new connection, accept it
        if notified_socket == room_socket:
            # Accept new connection
            # That gives us new socket - client socket, connected to this given client only, it's unique for that client
            # The other returned object is ip/port set
            # if first client synchronize and give it leader role
            # leader role means infor about who is infected
            # if client fails and new leader is elected give him the same info aswell
            client_socket, client_address = room_socket.accept()           
            client_socket.send("Input your username:")
            # Client should send his name right away, receive it
            user = receive_message(client_socket)
            # If False - client disconnected before he sent his name
            if user is False:
                continue
            # Add accepted socket to select.select() list
            sockets_list.append(client_socket)           
            # Also save username and username header
            clients[client_socket] = user
            if (leader):
                index = sockets_list.len() - 1
                print ("leader found"+ client_socket)
                leader = False
            if(sockets_list.len() == 4):
                 Game_Full = True                 
            else:
                 client_socket.send("Waiting for players...")
            print('Accepted new connection from {}:{}, username: {}'.format(*client_address, user['data'].decode('utf-8')))
        # Else existing socket is sending a message
        else:
            # Receive message
            message = receive_message(notified_socket)
            # If False, client disconnected, cleanup
            if message is False:
                print('Closed connection from: {}'.format(clients[notified_socket]['data'].decode('utf-8')))
                # Remove from list for socket.socket()
                sockets_list.remove(notified_socket)
                # Remove from our list of users
                del clients[notified_socket]
                continue
            # Get user by notified socket, so we will know who sent the message
            # Iterate over connected clients and broadcast message
            if(Game_Full):
                for client_socket in clients:
                        # Send user and message (both with their headers)
                        # We are reusing here message header sent by sender, and saved username header send by user when he connected
                        client_socket.send("Game starting...")
                        if (GameInfo):                       
                            client_socket.send(PORT_MQTT+","+broker+","+topic_chat+","+topic_election+","+topic_master)
                            GameInfo = False
                        else:
                             client_socket.send(PORT_MQTT+","+broker+","+topic_chat+","+topic_election)
                        infected = StartGame()
                        Room.publish(topic_master, infected)
    # It's not really necessary to have this, but will handle some socket exceptions just in case
    for notified_socket in exception_sockets:
        # Remove from list for socket.socket()
        sockets_list.remove(notified_socket)
        # Remove from our list of users
        del clients[notified_socket]