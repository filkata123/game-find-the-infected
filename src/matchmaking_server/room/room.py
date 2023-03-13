import sys
import socket
import json
import random
import paho.mqtt.client as mqtt
from dataclasses import dataclass

# Global game variables
MAX_PLAYERS_PER_ROOM = 4
EXIT_CODE = 67
game_full = False
game_finished = False

# Global player variables
# Player object that holds the socket, address and unique id of client, 
@dataclass
class Player:
    conn: socket
    addr: tuple[str, str]
    client_id: str
leader : Player = None 
infected : Player = None
player_list: Player = []
infected_found = False
game_info_string =  ""

# Global mqtt variables
MQTT_PORT = 1883
TIMEOUT = 60
broker = 'mqtt'
topic_list = []

'''
 Publish game info to tell the leader who the infected person is
'''
def publish_game_info(mqtt_client):
    print("Publishing game info.")
    # TODO: Improvement: if the game is to be difficult, the game info should be something more obscure
    mqtt_client.publish(topic_list[0], "The infected is " + game_info_string)

'''
Subscribe to all topics in list
'''
def on_connect(client, userdata, flags, rc):
    print("Subscribing to topics.")
    for topic in topic_list:
        client.subscribe(topic)

'''
Parse messages from subscribed MQTT topics
'''
def on_message(client, userdata, msg):
    global leader
    global infected_found

    message = msg.payload.decode()
    if (msg.topic == topic_list[0]): #/game
        if (message == "help"):
            # reprint game info upon leader request
            print("Game info requested!")
            publish_game_info(client) 
    # If new leader was elected by clients, update own variables and remove old leader
    elif (msg.topic == topic_list[1]): #/new_leader
        if (leader):
            leader.conn.close()
            player_list.remove(leader)

        # elect new leader
        for player in player_list:
            if (message == player.client_id):
                leader = player
        print("New leader elected.")
    # Check whether the proposed infected by the clients is the true infected player
    elif (msg.topic == topic_list[2]): #/proposed_infected
        # Iff message is id of the infected end game
        if (infected.client_id in message): # == client_id
            infected_found = True
            # Currently, nothing happens if the players make an incorrect guess
            # TODO: Ideally, the incorrect guess will have repricussions
    else:
        print ("Unknown topic.")

'''
Listen for clients and start game once the maximum number of players are reached
'''
def setup_game(room_serve_socket):
    global leader
    global infected
    global game_full
    global infected_found

    # Accept client and tell them to wait until game start
    conn, addr = room_serve_socket.accept()
    conn.sendall(json.dumps({"command":"wait"}).encode())

    # Get client id
    client_id = conn.recv(1024)
    client_id = client_id.decode()
    player_list.append(Player(conn, addr, client_id))

    # Choose initial leader - the first client that manages to connect
    if (leader is None):
        leader = player_list[0]

    # Start game once maximum player count is reached
    if (len(player_list) == MAX_PLAYERS_PER_ROOM):  
        # Chose infected by creating a random number between 1 and the amount of players without the leader
        infected_number = random.randint(1, MAX_PLAYERS_PER_ROOM - 1) 
        
        # Inform all players of game start and their roles
        for i, player in enumerate(player_list):
            try:
                if (player is leader):
                    player.conn.sendall(json.dumps({"command": "start", "option": "leader"}).encode())
                else:
                    # if there is no infected, assign them to the player whose index matches with the random number selected earlier
                    if (infected is None):
                        if (i == infected_number):
                            infected = player
                    
                    if (player is infected):
                        player.conn.sendall(json.dumps({"command": "start", "option": "infected"}).encode())
                    else:
                        player.conn.sendall(json.dumps({"command": "start", "option": "commoner"}).encode())
            except socket.error:
                # Even if a player leaves before the game has started, room will start
                # If they are the leader, the players will do an election
                
                # If the player who left is the infected, finish the game
                if (player is infected):
                    infected_found = True
                # TODO: In the future, if full game functionality is desired, a new infected should be elected
                player.conn.close()
        game_full = True 

'''
Handle players who were previously playing a game in a room which crashed
'''
def continue_game(room_serve_socket):
    global leader
    global infected
    global game_full
    global infected_found

    try:
        conn, addr = room_serve_socket.accept()

        # Get client id
        conn.sendall(json.dumps({"command":"id"}).encode())
        client_id = conn.recv(1024)
        client_id = client_id.decode()

        player = Player(conn, addr, client_id)
        player_list.append(player)

        # Get established client role
        conn.sendall(json.dumps({"command":"role"}).encode())
        client_role = conn.recv(1024)
        client_role = client_role.decode()

        if(client_role == "infected"):
            infected = player
        elif (client_role == "leader"):
            leader = player
        
        if (len(player_list) == MAX_PLAYERS_PER_ROOM):
            game_full = True
    except socket.timeout:
        # Timeout occurs if somebody left the room while the room was restarting
        # or the original room started with less than max people
        game_full = True

        # if the infected player has left, the game should finish
        # the same is not done for the leader, because the clients can just hold an election upon start
        if(not infected):
            infected_found = True
        

def main():
    global game_info_string
    global game_finished

    if len(sys.argv) != 4:
        print("Correct usage: room.py <ip_addr> <port_num> <restarted_room>")
        exit()

    # Get host, port and whether the game is being resumed from matchmaker
    HOST = str(sys.argv[1])
    PORT = int(sys.argv[2]) 
    resuming_game = int(sys.argv[3])

    # Start server
    room_serve_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    room_serve_socket.bind((HOST, PORT))
    room_serve_socket.listen(5)

    print("Room setup finished.")
    if (not resuming_game):
        # Start game from scratch
        while not game_full:
            setup_game(room_serve_socket)
            print(f'Waiting for clients ... ({len(player_list)}/{MAX_PLAYERS_PER_ROOM})')
    else:
        # Resume game, in which the room crashed
        # Wait for players to connect to new room instance, get their id and role and 
        # restart the game where it left off
        room_serve_socket.settimeout(60)
        while not game_full:
            continue_game(room_serve_socket)
            print(f'Waiting for clients to reconnect ... ({len(player_list)}/{MAX_PLAYERS_PER_ROOM})')
        
    room_name = "room" + str(PORT)
    print("Server " + room_name + " started.")

    # Subscribe to necessary topics
    topic_list.append(room_name + "/game")
    topic_list.append(room_name + "/new_leader")
    topic_list.append(room_name + "/proposed_infected")

    # Start MQTT client
    mqtt_client = mqtt.Client(room_name)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    try:
        mqtt_client.connect(broker, MQTT_PORT, TIMEOUT)
    except Exception as e:
        print("MQTT connection failed: " + str(e))
        exit(1)
    mqtt_client.loop_start()
    print("Connection with MQTT broker established.")

    # Publish game info once upon game start
    if (infected):
        game_info_string = str(infected.client_id)
        publish_game_info(mqtt_client) 

    # Wait until the infected player has been found
    while (not game_finished):
        if (infected_found):
            # Inform players of game finishing and close their connection
            print("Informing players of finished game.")
            for player in player_list:
                try:
                    player.conn.sendall(json.dumps({"command": "finish"}).encode())
                finally:
                    player.conn.close()
            game_finished = True
                
    # stop the mqtt loop and exit the program
    mqtt_client.loop_stop()
    sys.exit(EXIT_CODE)

if __name__ == '__main__':
    main()