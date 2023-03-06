import sys
import socket
import json
import random
import paho.mqtt.client as mqtt
from dataclasses import dataclass

# Global variables
MAX_PLAYERS_PER_ROOM = 4
EXIT_CODE = 67

@dataclass
class Player:
    conn: socket
    addr: tuple[str, str]
    client_id: str

game_full = False
player_list: Player = []
leader : Player = None 
infected : Player = None
game_info_string = ""
infected_found = False
game_finished = False

MQTT_PORT = 1883
TIMEOUT = 60
broker = 'localhost'
topic_list = []

def publish_game_info(client):
    print("Publishing game info.")
    client.publish(topic_list[0], "The infected is " + game_info_string)

def on_connect(client, userdata, flags, rc):
    print("Subscribing to topics.")
    for topic in topic_list:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    global leader
    global infected_found
    message = msg.payload.decode()
    if (msg.topic == topic_list[0]): #/game
        if (message == "help"):
            # reprint game info
            print("Game info requested!")
            publish_game_info(client) 
    elif (msg.topic == topic_list[1]): #/new_leader
        leader.conn.close()
        player_list.remove(leader)

        # elect new leader
        for player in player_list:
            if (message == player.client_id):
                leader = player
        print("New leader elected.")
    elif (msg.topic == topic_list[2]): #/proposed_infected
        # check if message is address of the infected
        if (infected.client_id in message): # == client_id
            infected_found = True
        else:
            # TODO: Do we kill the proposed person anyway? 
            client.publish(topic_list[2], "Try again!")
    else:
        print ("Unknown topic.")

def setup_game(server_socket):
    global leader
    global infected
    global game_full
    #listen for clients and add them up in an array
    conn, addr = server_socket.accept()

    room_connection_object = json.dumps({"command":"wait"})
    conn.sendall(room_connection_object.encode())

    client_id = conn.recv(1024)
    client_id = client_id.decode()
    player_list.append(Player(conn, addr, client_id))

    # choose initial leader
    if (leader is None):
        leader = player_list[0]

    if (len(player_list) == MAX_PLAYERS_PER_ROOM):
        infected_number = random.randint(1, MAX_PLAYERS_PER_ROOM - 1) # random number between 1 and the amount of players without the leader
        for i, player in enumerate(player_list):
            try:
                # send games start to all players
                if (player is leader):
                    player.conn.sendall(json.dumps({"command": "start", "option": "leader"}).encode())
                else:
                    # if there is no infected, assign them to the player, whose index matches with the random number selected earlier
                    if (infected is None):
                        if (i == infected_number):
                            infected = player
                    
                    if (player is infected):
                        player.conn.sendall(json.dumps({"command": "start", "option": "infected"}).encode())
                    else:
                        player.conn.sendall(json.dumps({"command": "start", "option": "commoner"}).encode())
            except socket.error:
                player.conn.close()
                # TODO: What do we do if a client exits while waiting?
        game_full = True 

def main():
    if len(sys.argv) != 4:
        print("Correct usage: room.py <ip_addr> <port_num> <restarted_room>")
        exit()

    HOST = str(sys.argv[1])
    PORT = int(sys.argv[2]) 
    resuming_game = int(sys.argv[3])

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)

    if (not resuming_game):
        while not game_full:
            setup_game(server_socket)
            print(f'Waiting for clients ... ({len(player_list)}/{MAX_PLAYERS_PER_ROOM})')
    else:
        # TODO: get proper roles to clients
        # listen for players to reconnect, request their client id and role
        # Basically redo setup game with proper roles and state (kinda)
        leader = None
    
    room_name = "room" + str(PORT)
    print("Server " + room_name + " started.")

    topic_list.append(room_name + "/game")
    topic_list.append(room_name + "/new_leader")
    topic_list.append(room_name + "/proposed_infected")

    client = mqtt.Client(room_name)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(broker, MQTT_PORT, TIMEOUT)
    except Exception as e:
        print("MQTT connection failed: " + str(e))
        exit(1)
    client.loop_start()
    print("Connection with MQTT broker established.")

    # handle publishing logic
    global game_info_string
    game_info_string = str(infected.client_id)
    publish_game_info(client) 

    global game_finished
    while (not game_finished):
        if (infected_found):
            # inform players of game finishing and close their connection
            print("Informing players of finished game.")
            for player in player_list:
                # game finished
                try:
                    player.conn.sendall(json.dumps({"command": "finish"}).encode())
                finally:
                    player.conn.close()
            game_finished = True
                
    # stop the network loop and exit the program
    client.loop_stop()
    sys.exit(EXIT_CODE)

if __name__ == '__main__':
    main()