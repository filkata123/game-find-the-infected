import socket
import threading
import paho.mqtt.client as mqtt
import time
import datetime

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

client_arrival_time = None # ntp utc time
leader_timer = None
election_timer = None
election_started = False
election_candidate = True

MQTT_PORT = 1883
TIMEOUT = 60
broker = 'mqtt'
topic_list = []

def on_connect(client, userdata, flags, rc):
    for topic in topic_list:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    global leader_timer
    global election_timer
    global election_started
    global election_candidate
    message = msg.payload.decode()
    if (msg.topic != topic_list[3]): # not /chat 
        if (client_role == "leader"):
            if (msg.topic == topic_list[0]): #/game
                print(message)
        elif (client_role == "commoner"):
            if (msg.topic == topic_list[1]): #/new_leader
                election_started = False
                election_candidate = True
            if (msg.topic == topic_list[4]): #/alive_ping
                leader_timer = time.time()
            elif (msg.topic == topic_list[5]): #/election    
                if (not election_started):
                    election_started = True
                if (message > client_arrival_time):
                    election_candidate = False
                election_timer = time.time()
    else:
        print(message)

def setup_mqtt_topics():
    room_name = "room" + str(ROOM_PORT)

    topic_list.append(room_name + "/game") # info from room
    topic_list.append(room_name + "/new_leader") # tell room to change leader
    topic_list.append(room_name + "/proposed_infected") # propose an infected
    topic_list.append(room_name + "/chat") # chat between players only
    topic_list.append(room_name + "/alive_ping") # periodic ping of leader
    topic_list.append(room_name + "/election") # election between players

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
                    setup_mqtt_topics()
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
    global client_arrival_time
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
                    client_arrival_time = datetime.datetime.utcnow()
                    print("Connecting to room...")
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

# wait for game to start
while not game_started:
    continue

client = mqtt.Client() # TODO: add id
client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, MQTT_PORT, TIMEOUT)
client.loop_start()

# TODO: leader_timer = time.time()
# TODO: check election timer - if some time has passed, publish to new_leader
while not game_finished:
    chat_message = input('Enter message: ')
    # TODO: MQTT logic here
    # TODO: leader pings every 5 sec
    #matchmaker_socket.sendall(message.encode())
    #if message.lower() == '/exit':
    #   break

print("Game has finished!")
client.loop_stop()
# Wait for the thread to finish
thread.join()
thread_room.join()
