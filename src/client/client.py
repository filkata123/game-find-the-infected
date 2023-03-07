import socket
import threading
import paho.mqtt.client as mqtt
import time
import datetime
import uuid
import errno

HOST = '127.0.0.1'
PORT = 1234

ROOM_PORT = 0

room_socket =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)

room_connected = False
game_started = False
game_finished = False
game_quit = False
client_role = None
ping_thread = None

client_arrival_time = None # ntp utc time
client_id = None
leader_timer = None
election_candidate = True

MQTT_PORT = 1883
TIMEOUT = 60
broker = 'localhost' # specify address or 'mqtt' in Linux
topic_list = []

def election_daemon(client):
    global client_role
    global ping_thread 
    global election_candidate
    global leader_timer

    while not game_finished and not game_quit:
        if (client_role == "commoner"): # redundant check?
            if (time.time() - leader_timer > 5):
                # propose myself as leader
                client.publish(topic_list[5], str(client_arrival_time))

                time.sleep(5)

                # if I am still the election_candidate, elect me as leader
                if (election_candidate):
                    client.publish(topic_list[1], client_id)
                    client_role = "leader"

                    ping_thread = threading.Thread(target=leader_ping, args=(client,))
                    ping_thread.daemon = True
                    ping_thread.start()
                    break

                # reset for future elections
                election_candidate = True
                leader_timer = time.time()
    if (ping_thread):
        ping_thread.join()  
        print("Closed ping thread.")
    print("election daemon finished")
            
def leader_ping(client):
    while not game_finished and not game_quit:
        client.publish(topic_list[4], "ping")
        time.sleep(1)
    print("leader ping finished")

def on_connect(client, userdata, flags, rc):
    for topic in topic_list:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    global leader_timer
    global election_candidate
    
    message = msg.payload.decode()

    if (msg.topic != topic_list[3]): # if not /chat 
        if (client_role == "leader"):
            if (msg.topic == topic_list[0]): #/game
                print("The game whispers: " + message)
        elif (client_role == "commoner"):
            if (msg.topic == topic_list[1]): #/new_leader
                print("New leader elected.")
            if (msg.topic == topic_list[4]): #/alive_ping
                leader_timer = time.time()

        # leader should be able to hold the crown if necessary
        if (msg.topic == topic_list[5]): #/election - no infected
            if (client_role == "leader" or client_role == "commoner"):
                contender_time = float(message)
                print("Am I supposed to be the new leader...")
                if (contender_time > client_arrival_time):
                    # no reprecautions if client is leader as this variable is not used anywhere in that case
                    print("No... :(")
                    election_candidate = False
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
                            if not topic_list: # don't resetup mqtt topics as room has same port
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
    print("handle room finished")


def receive_messages(matchmaker_sock):
    global room_connected
    global room_socket
    global client_arrival_time
    global ROOM_PORT

    print("Connected to matchmaker.")
    
    while not game_finished and not game_quit:
        try:
            data = matchmaker_sock.recv(1024)
            message = data.decode()

            # ensure that ping isn't concatenated to a message
            message = message.replace("ping", '')
            if message != '': 
                print(message)
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
    print("receive messages finished")

def main():
    global ping_thread
    global leader_timer
    global game_quit

    matchmaker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    matchmaker_socket.connect((HOST, PORT))
    matchmaker_socket.setblocking(False)
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

    # GAME STARTED

    client = mqtt.Client(client_id)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(broker, MQTT_PORT, TIMEOUT)
    except Exception as e:
        print("MQTT connection failed: " + str(e))
        exit(1)
    client.loop_start()

    # schedule leader to ping other clients
    if (client_role == "leader"):
        ping_thread = threading.Thread(target=leader_ping, args=(client,))
        ping_thread.daemon = True
        ping_thread.start()
    elif (client_role == "commoner"):
        leader_timer = time.time()
        # election thread
        election_thread = threading.Thread(target=election_daemon, args=(client,))
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
            client.publish(topic_list[3], message)
        elif (client_input.lower() == "i"):
            infected = input("Write infected client name:")
            client.publish(topic_list[2], infected)
        elif (client_input.lower() == "h" and client_role == "leader"):
            client.publish(topic_list[0], "help")
        else:
            print("Please choose an existing option.")


    # End cleanup
    client.loop_stop()
    print("Closed mqtt loop.")
    # Wait for the thread to finish
    if (client_role == "commoner"):
        election_thread.join()
        print("Closed election thread.")
    else:
        if (ping_thread):
            ping_thread.join()
            print("Closed ping thread.")
    thread_room.join()
    print("Closed room thread.")
    thread.join()
    print("Closed main thread.")

if __name__ == '__main__':
    main()