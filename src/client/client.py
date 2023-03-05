import socket
import threading
import paho.mqtt.client as mqtt
import time
import datetime
import uuid
import sched

HOST = '127.0.0.1'
PORT = 1234

ROOM_PORT = 0

room_socket =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
room_connected = False
game_started = False
game_finished = False
client_role = None

client_arrival_time = None # ntp utc time
client_id = None
leader_timer = None
election_candidate = True

MQTT_PORT = 1883
TIMEOUT = 60
broker = 'mqtt' # TODO: spin up own mqtt server and check what goes in
topic_list = []

def election_daemon(client):
    global client_role
    scheduler : sched.scheduler = None
    print("Starting election daemon.")
    while not game_finished:
        if (client_role == "commoner"): # redundant check?
            if (time.time() - leader_timer > 5):
                # propose myself as leader
                client.publish(topic_list[5], client_arrival_time)

                time.sleep(5)

                # if I am still the election_candidate, elect me as leader
                if (election_candidate):
                    client.publish(topic_list[1], client_id)
                    client_role = "leader"
                    scheduler = sched.scheduler(time.time, time.sleep)
                    scheduler.enter(0, 1, leader_ping)
                    scheduler.run
                    break

    # busy loop so that scheduler can be kept alive
    while not game_finished:
        continue
    scheduler.shutdown()
            
def leader_ping(client, scheduler):
    client.publish(topic_list[4], "ping")
    scheduler.enter(1, 1, leader_ping) # schedule ping in 1 sec

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
                print("The game  whispers: " + message)
        elif (client_role == "commoner"):
            if (msg.topic == topic_list[1]): #/new_leader
                print("New leader elected.")
                election_candidate = True
            if (msg.topic == topic_list[4]): #/alive_ping
                leader_timer = time.time()

        # leader should be able to hold the crown if necessary
        if (client_role == "leader" or client_role == "client"):
            if (msg.topic == topic_list[5]): #/election - no infected  
                contender_time = datetime.datetime.strptime(message, '%Y-%m-%d %H:%M:%S').replace(tzinfo=datetime.timezone.utc)
                print("Am I supposed to be the new leader...")
                if (contender_time > client_arrival_time.replace(tzinfo=datetime.timezone.utc)):
                    # no reprecautions if client is leader as this variable is not sued anywhere in that case
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

    while not game_finished:
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
                    arrival_time_formatted = int(client_arrival_time.timestamp() * 1000)
                    client_id = str(uuid.uuid1(node=arrival_time_formatted))
                    
                    room_socket.sendall(f"{client_id}".encode())
                    print("Waiting for players...")
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


def receive_messages(matchmaker_sock):
    global room_connected
    global room_socket
    global client_arrival_time
    global ROOM_PORT

    print("Connected to matchmaker.")
    try:
        while not game_finished:
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

def main():
    global leader_timer
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

    # GAME STARTED

    client = mqtt.Client(client_id)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(broker, MQTT_PORT, TIMEOUT)
    client.loop_start()

    # schedule leader to ping other clients
    if (client_role == "leader"):
        scheduler = sched.scheduler(time.time, time.sleep)
        scheduler.enter(0, 1, leader_ping)
        scheduler.run
    elif (client_role == "commoner"):
        leader_timer = time.time()
        # election thread
        election_thread = threading.Thread(target=election_daemon, args=(client,))
        election_thread.daemon = True
        election_thread.start()

    while not game_finished:
        print("[C] = chat, [I] = vote for infected, [Q] = quit")
        if (client_role == "leader"):
            print("[H] = request game info")
        client_input = input('Choose option: ')

        if (client_input.lower() == "q"):
            break 
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

    if (game_finished):
        print("Game has finished!")
    client.loop_stop()
    # Wait for the thread to finish
    thread.join()
    thread_room.join()
    if (client_role == "commoner"):
        election_thread.join()
    else:
        scheduler.shutdown()

if __name__ == '__main__':
    main()