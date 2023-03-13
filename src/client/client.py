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

leader_ping_thread = None

# global MQTT variables
MQTT_PORT = 1883
TIMEOUT = 60
mqtt_broker = 'localhost' # specify address or 'mqtt' in Linux
mqtt_topic_list = []

def election_daemon(client):
    global client_role
    global leader_ping_thread 
    global election_candidate
    global last_leader_ping

    while not game_finished and not game_quit:
        if (client_role == "commoner"): # redundant check?
            if (time.time() - last_leader_ping > 5):
                # propose myself as leader
                client.publish(mqtt_topic_list[5], str(client_arrival_time))

                time.sleep(5)

                # if I am still the election_candidate, elect me as leader
                if (election_candidate):
                    client.publish(mqtt_topic_list[1], client_id)
                    client_role = "leader"
                    print("You are the new leader!")

                    leader_ping_thread = threading.Thread(target=leader_ping, args=(client,))
                    leader_ping_thread.daemon = True
                    leader_ping_thread.start()
                    break

                # reset for future elections
                election_candidate = True
                last_leader_ping = time.time()
    if (leader_ping_thread):
        leader_ping_thread.join()
            
def leader_ping(client):
    while not game_finished and not game_quit:
        client.publish(mqtt_topic_list[4], "ping")
        time.sleep(1)

def on_connect(client, userdata, flags, rc):
    for topic in mqtt_topic_list:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    global last_leader_ping
    global election_candidate
    
    message = msg.payload.decode()

    if (msg.topic != mqtt_topic_list[3]): # if not /chat 
        if (client_role == "leader"):
            if (msg.topic == mqtt_topic_list[0]): #/game
                print("The game whispers: " + message)
        elif (client_role == "commoner"):
            if (msg.topic == mqtt_topic_list[1]): #/new_leader
                print("New leader elected.")
            if (msg.topic == mqtt_topic_list[4]): #/alive_ping
                last_leader_ping = time.time()

        # leader should be able to hold the crown if necessary
        if (msg.topic == mqtt_topic_list[5]): #/election - no infected
            if (client_role == "leader" or client_role == "commoner"):
                contender_time = float(message)
                if (contender_time > client_arrival_time):
                    # no reprecautions if client is leader as this variable is not used anywhere in that case
                    election_candidate = False
    else:
        print(message)

def setup_mqtt_topics():
    room_name = "room" + str(ROOM_PORT)

    mqtt_topic_list.append(room_name + "/game") # info from room
    mqtt_topic_list.append(room_name + "/new_leader") # tell room to change leader
    mqtt_topic_list.append(room_name + "/proposed_infected") # propose an infected
    mqtt_topic_list.append(room_name + "/chat") # chat between players only
    mqtt_topic_list.append(room_name + "/alive_ping") # periodic ping of leader
    mqtt_topic_list.append(room_name + "/election") # election between players

def handle_room_logic(room_socket):
    global game_started
    global game_finished
    global client_role
    global client_id

    while not game_finished and not game_quit:
        try:
            if(room_connected):
                if (not game_started):
                    # Step 1: Go through room setup
                    data = room_socket.recv(1024)
                    
                    message = eval('dict('+data.decode()+')')
                    if ('command' in message):
                        if message['command'] == "wait":
                            arrival_time_formatted = int(client_arrival_time * 1000)
                            client_id = str(uuid.uuid1(node=arrival_time_formatted))
                            
                            room_socket.sendall(f"{client_id}".encode())
                            print("Waiting for players...")
                        elif message['command'] == "start":
                            client_role = message['option']
                            if not mqtt_topic_list: # don't resetup mqtt topics as room has same port
                                setup_mqtt_topics()
                            game_started = True
                            print("Game has started!")
                            print("Your role is: " + client_role)
                else:
                    # Step 2: listen for game finish or server restart
                    data = room_socket.recv(1024)

                    message = eval('dict('+data.decode()+')')
                    if ('command' in message):
                        if message['command'] == "finish":
                            print("Game has finished!")
                            print("Press any button to exit...")
                            game_finished = True
                        elif message['command'] == "id":
                            room_socket.sendall(f"{client_id}".encode())
                        elif message['command'] == "role":
                            room_socket.sendall(f"{client_role}".encode())
        except:
            pass


def receive_messages(matchmaker_socket, room_socket):
    global room_connected
    global client_arrival_time
    global ROOM_PORT
    
    while not game_finished and not game_quit:
        try:
            data = matchmaker_socket.recv(1024)
            message = data.decode()

            # ensure that ping isn't concatenated to a message
            message = message.replace("ping", '')
            if message != '': 
                message_decoded = eval('dict('+message+')')
                if ('command' in message_decoded):
                    if message_decoded['command'] == "connect":
                        # connect to server
                        ROOM_PORT = message_decoded['options']
                        room_socket.connect((HOST, ROOM_PORT))
                        room_socket.setblocking(False)
                        room_connected = True
                        client_arrival_time = datetime.datetime.utcnow().timestamp()
                        print("Connecting to room...")
                    elif message_decoded['command'] == "reconnect":
                        # reconnect
                        print("Reconnecting...")
                        room_connected = False
                        room_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        room_socket.connect((HOST, ROOM_PORT))
                        room_socket.setblocking(False)
                        room_connected = True
                    elif message_decoded['command'] == "finish":
                        break
        except socket.error as e:
            if (e.errno == errno.EWOULDBLOCK):
                # no data available
                pass
            else:
                print("Exception: " + str(e))
                break
        # TODO: handle what happens when room dies permanently? Wait some time?

def main():
    global leader_ping_thread
    global last_leader_ping
    global game_quit

    # create sockets for the matchmaker and room servers
    matchmaker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    room_socket =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
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
    matchmaker_thread = threading.Thread(target=receive_messages, args=(matchmaker_socket, room_socket,))
    matchmaker_thread.daemon = True
    matchmaker_thread.start()

    # Start a new thread to receive messages from room
    thread_room = threading.Thread(target=handle_room_logic, args=(room_socket,))
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

    # schedule leader to ping other clients
    if (client_role == "leader"):
        leader_ping_thread = threading.Thread(target=leader_ping, args=(mqtt_client,))
        leader_ping_thread.daemon = True
        leader_ping_thread.start()
    elif (client_role == "commoner"):
        last_leader_ping = time.time()
        # election thread
        election_thread = threading.Thread(target=election_daemon, args=(mqtt_client,))
        election_thread.daemon = True
        election_thread.start()

    while not game_finished and not game_quit:
        print("[C] = chat, [I] = vote for infected, [Q] = quit")
        if (client_role == "leader"):
            print("[H] = request game info")
        client_input = input('Choose option: ')

        if (client_input.lower() == "q"):
            game_quit = True 
        elif (client_input.lower() == "c"):
            # Make sure it is known who says what
            message = str(client_id) + " says: "
            message = message + input('Enter message: ')
            mqtt_client.publish(mqtt_topic_list[3], message)
        elif (client_input.lower() == "i"):
            infected = input("Write infected client name:")
            mqtt_client.publish(mqtt_topic_list[2], infected)
        elif (client_input.lower() == "h" and client_role == "leader"):
            mqtt_client.publish(mqtt_topic_list[0], "help")


    # End cleanup

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