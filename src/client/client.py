import socket
import threading
import paho.mqtt.client as mqtt
import time
import datetime
import uuid
import errno

# global socket variables
HOST = 'localhost'
PORT = 1234
ROOM_PORT = 0

# global game variables
game_started = False
game_finished = False
game_quit = False
room_connected = False

# global client info variables
client_id = None
client_role = None
client_arrival_time = None # ntp utc time
election_candidate = True
last_leader_ping = None

room_socket =  None
leader_ping_thread = None

# global MQTT variables
MQTT_PORT = 1883
TIMEOUT = 60
mqtt_broker = 'localhost' # specify address or 'mqtt' in Linux
mqtt_topic_list = []

'''
Start an election if leader has not pinged in the last 5 seconds
Check after 5 seconds whether the client is still a viable candidate and if so make him the new leader
'''
def election_daemon(mqtt_client):
    global client_role
    global leader_ping_thread 
    global election_candidate
    global last_leader_ping

    # Exit thread if game has finished or client has quit
    while not game_finished and not game_quit:
        if (client_role == "commoner"): # redundant check?
            if (time.time() - last_leader_ping > 5):
                # propose myself as leader
                mqtt_client.publish(mqtt_topic_list[5], str(client_arrival_time))

                time.sleep(5)

                # if I am still the election_candidate, elect me as leader
                if (election_candidate):
                    mqtt_client.publish(mqtt_topic_list[1], client_id)
                    client_role = "leader"
                    print("You are the new leader!")

                    leader_ping_thread = threading.Thread(target=leader_ping, args=(mqtt_client,))
                    leader_ping_thread.daemon = True
                    leader_ping_thread.start()
                    break

                # reset for future elections
                election_candidate = True
                last_leader_ping = time.time()
    if (leader_ping_thread):
        leader_ping_thread.join()

'''
Ping all clients every one second
'''
def leader_ping(mqtt_client):
    # Stop ping if game has finished or client has quit
    while not game_finished and not game_quit:
        mqtt_client.publish(mqtt_topic_list[4], "ping")
        time.sleep(1)

'''
Subscribe to all topics in list
'''
def on_connect(client, userdata, flags, rc):
    for topic in mqtt_topic_list:
        client.subscribe(topic)

'''
Parse messages from subscribed MQTT topics 
'''
def on_message(client, userdata, msg):
    global last_leader_ping
    global election_candidate
    
    message = msg.payload.decode()
    # If the topic is not /chat 
    if (msg.topic != mqtt_topic_list[3]): 
        # If client is leader parse game topic
        if (client_role == "leader"):
            if (msg.topic == mqtt_topic_list[0]): #/game
                print("The game whispers: " + message)
        # If client is commoner parse new_leader and alive_ping topics
        elif (client_role == "commoner"):
            # Check whether a new_leader has been elected
            if (msg.topic == mqtt_topic_list[1]): #/new_leader
                print("New leader elected.")
            # Update last ping time if ping received
            if (msg.topic == mqtt_topic_list[4]): #/alive_ping
                last_leader_ping = time.time()

        # If an election has been started, perform bully algorithm 
        # by comparing the connection time of the contender with own connection time
        # Infected clients are not part of the election as they shouldn't be able to become leaders
        if (msg.topic == mqtt_topic_list[5]): #/election
             # Leader should be able to hold the "crown" if necessary
            if (client_role == "leader" or client_role == "commoner"):
                contender_time = float(message)
                if (contender_time > client_arrival_time):
                    election_candidate = False # If client is already leader changing this variable doesn't affect anything
    else:
        # Print chat message
        print(message)

'''
Add all mqtt topics to list with format "room<number>/<topic>" 
'''
def setup_mqtt_topics():
    room_name = "room" + str(ROOM_PORT)

    # TODO Improvement: Subscribe to topics based on client role
    mqtt_topic_list.append(room_name + "/game") # [0] info from room
    mqtt_topic_list.append(room_name + "/new_leader") # [1] tell room to change leader
    mqtt_topic_list.append(room_name + "/proposed_infected") # [2] propose an infected
    mqtt_topic_list.append(room_name + "/chat") # [3] chat between players only
    mqtt_topic_list.append(room_name + "/alive_ping") # [4] periodic ping of leader
    mqtt_topic_list.append(room_name + "/election") # [5] election between players

'''
Asynchronously handle room communication
'''
def handle_room_messages():
    global game_started
    global game_finished
    global client_role
    global client_id

    # Handle messages until game has either ended or the client has quit
    while not game_finished and not game_quit:
        try:
            # Don't do anything until the room is connected
            if(room_connected):
                if (not game_started):
                    # Step 1: Go through room setup
                    message = room_socket.recv(1024).decode()
                    
                    message_parsed = eval('dict('+message+')')
                    if ('command' in message_parsed):
                        # Wait until all players are connected
                        if message_parsed['command'] == "wait":
                            # Calculate unique id from arrival time and send it to room
                            arrival_time_formatted = int(client_arrival_time * 1000)
                            client_id = str(uuid.uuid1(node=arrival_time_formatted))
                            room_socket.sendall(f"{client_id}".encode())

                            print("Waiting for players...")
                        # Start the game
                        elif message_parsed['command'] == "start":
                            client_role = message_parsed['option']
                            setup_mqtt_topics()
                            game_started = True
                            print("Game has started!")
                            print("Your role is: " + client_role)
                else:
                    # Step 2: Listen for game finish or server restart
                    message = room_socket.recv(1024).decode()

                    message_parsed = eval('dict('+message+')')
                    if ('command' in message_parsed):
                        # Finish game
                        if message_parsed['command'] == "finish":
                            print("Game has finished!")
                            print("Press any button to exit...")
                            game_finished = True
                        # Send ID to restarted server
                        elif message_parsed['command'] == "id":
                            room_socket.sendall(f"{client_id}".encode())
                        # Send role to restarted server
                        elif message_parsed['command'] == "role":
                            room_socket.sendall(f"{client_role}".encode())
        except:
            # Even if the room crashes, the matchmaker will handle it 
            # so this except just surpresses the connection errors
            pass

'''
Asynchronously handle incoming messages from matchmaker
'''
def handle_matchmaker_messages(matchmaker_socket):
    global room_socket
    global room_connected
    global client_arrival_time
    global ROOM_PORT
    
    # Handle messages until game has either ended or the client has quit
    while not game_finished and not game_quit:
        try:
            # Receive matchmaker data
            message = matchmaker_socket.recv(1024).decode()

            # Ensure that ping isn't concatenated to a meaningful message
            message = message.replace("ping", '')
            # If the message was meaningful, parse it
            if message != '': 
                message_parsed = eval('dict('+message+')')
                if ('command' in message_parsed):
                    if message_parsed['command'] == "connect":
                        # Connect to room
                        ROOM_PORT = message_parsed['options']
                        room_socket.connect((HOST, ROOM_PORT))
                        room_socket.setblocking(False)
                        room_connected = True

                        # Track time of connection of client
                        client_arrival_time = datetime.datetime.utcnow().timestamp()
                        print("Connecting to room...")
                    elif message_parsed['command'] == "reconnect":
                        # Recoonect to room
                        room_connected = False
                        room_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        room_socket.connect((HOST, ROOM_PORT))
                        room_socket.setblocking(False)
                        room_connected = True
                        print("Reconnected to room.")
                    elif message_parsed['command'] == "finish":
                        # Exit matchmaker thread
                        break
        except socket.error as e:
            if (e.errno == errno.EWOULDBLOCK):
                # no data available
                pass
            else:
                print("Exception: " + str(e))
                break
        # TODO: Exit client if matchmaker quits

def main():
    global leader_ping_thread
    global last_leader_ping
    global game_quit
    global room_socket

    # SETUP

    # create sockets for the matchmaker and room servers
    room_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    matchmaker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Wait until the matchmaker socket has been found
    connected = False
    while not connected:
        try:
            # This is required in the event that a new player tries to join when matchmaker is creating a room (blocking)
            # Consideration: this could be improved if matchmaker does not block when creating a room (only possible with threads),
            # but resource consumption must be taken into account, as a lot of threads are being used already.
            matchmaker_socket.connect((HOST, PORT))
            connected = True
        except Exception as e:
            #Do nothing, just try again
            pass 
    
    # Ensure that matchmaker socket does not block, so that
    # the client can notice if a game has ended or the client has quit
    matchmaker_socket.setblocking(False)
    print('Connected to matchmaker')

    # Start a new thread to receive messages from matchmaker
    matchmaker_thread = threading.Thread(target=handle_matchmaker_messages, args=(matchmaker_socket,))
    matchmaker_thread.daemon = True
    matchmaker_thread.start()

    # Start a new thread to receive messages from room
    thread_room = threading.Thread(target=handle_room_messages)
    thread_room.daemon = True
    thread_room.start()

    # Wait for game to start
    while not game_started:
        continue

    # GAME STARTED

    # Establish connection to mqtt
    mqtt_client = mqtt.Client(client_id)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    try:
        mqtt_client.connect(mqtt_broker, MQTT_PORT, TIMEOUT)
    except Exception as e:
        print("MQTT connection failed: " + str(e))
        exit(1)
    mqtt_client.loop_start()

    if (client_role == "leader"):
        # Create a thread wich periodically pings subscribers
        leader_ping_thread = threading.Thread(target=leader_ping, args=(mqtt_client,))
        leader_ping_thread.daemon = True
        leader_ping_thread.start()
    elif (client_role == "commoner"):
        # start leader ping tracking
        last_leader_ping = time.time()
        # election thread
        # Create a thread wich periodically checks whether leader is alive
        election_thread = threading.Thread(target=election_daemon, args=(mqtt_client,))
        election_thread.daemon = True
        election_thread.start()

    # Handle user input
    while not game_finished and not game_quit:
        print("[C] = chat, [I] = vote for infected, [Q] = quit")
        if (client_role == "leader"):
            print("[H] = request game info")
        client_input = input('Choose option: ')

        if (client_input.lower() == "q"):
            # Quit game
            game_quit = True 
        elif (client_input.lower() == "c"):
            # Create string which contains client id and input
            message = str(client_id) + " says: "
            message = message + input('Enter message: ')
            # Publish message to chat topic
            mqtt_client.publish(mqtt_topic_list[3], message)
        elif (client_input.lower() == "i"):
            # Vote for infected
            infected = input("Write infected client name:")
            # Publish infected candidate to proposed_infected topic
            mqtt_client.publish(mqtt_topic_list[2], infected)
        elif (client_input.lower() == "h" and client_role == "leader"):
            # Request help from game
            mqtt_client.publish(mqtt_topic_list[0], "help")


    # CLEANUP
    # Close mqtt
    mqtt_client.loop_stop()

    # Wait for the election or ping threads to finish depending on the client type
    if (client_role == "commoner"):
        election_thread.join()
    else:
        if (leader_ping_thread):
            leader_ping_thread.join()

    # Wait for room handler thread to be finished
    thread_room.join()
    #Wait for matchmaker thread to be finished
    matchmaker_thread.join()

if __name__ == '__main__':
    main()