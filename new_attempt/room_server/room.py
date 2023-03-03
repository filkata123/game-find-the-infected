import sys
import socket
import json
import random
import paho.mqtt.client as mqtt

# Global variables
MAX_PLAYERS_PER_ROOM = 4
EXIT_CODE = 67

game_full = False
player_list : socket = []
leader = None 
infected = None
game_info_string = ""
infected_found = False
game_finished = False

MQTT_PORT = 1883
TIMEOUT = 60
broker = 'mqtt'
topic_list = []

def publish_game_info(client):
    client.publish(topic_list[0], "The infected is " + game_info_string)

def on_connect(client, userdata, flags, rc):
    for topic in topic_list:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    global leader
    global infected_found
    message = msg.payload.decode()
    if (msg.topic == topic_list[0]): #/game
        # reprint game info
        # TODO: What are we even sharing here?
        publish_game_info(client) 
    elif (msg.topic == topic_list[1]): #/new_leader
        leader[0].close()
        player_list.remove(leader) # TODO: is this possible?

        # elect new leader
        for player in player_list:
            if message == player[1]:
                leader = player
    elif (msg.topic == topic_list[2]): #/proposed_infected
        # check if message is address of the infected
        if (message == infected[1]):
            infected_found = True
        else:
            # TODO: Do we kill the proposed person anyway? 
            client.publish(topic_list[2], "Try again!")
    else:
        print ("Unknown topic.")

def setup_game(server_socket):
    global leader
    global infected
    #listen for clients and add them up in an array
    conn, addr = server_socket.accept()
    player_list.append((conn,addr))

    # choose initial leader
    if (leader is None):
        leader = player_list[0]

    room_connection_object = json.dumps({"sender": "room", "command":"wait"})
    conn.sendall(room_connection_object.encode())

    if (player_list.len() == MAX_PLAYERS_PER_ROOM):
        infected_number = random.randint(1, MAX_PLAYERS_PER_ROOM - 1) # random number between 1 and the amount of players without the leader
        for i, player in enumerate(player_list):
            try:
                # send games start to all players
                if (player is leader):
                    player[0].sendall(json.dumps({"sender": "room", "command": "start", "option": "leader"}).encode())
                else:
                    # if there is no infected, assign them to the player, whose index matches with the random number selected earlier
                    if (infected is None):
                        if (i == infected_number):
                            infected = player
                    
                    if (player is infected):
                        player[0].sendall(json.dumps({"sender": "room", "command": "start", "option": "infected"}).encode())
                    else:
                        player[0].sendall(json.dumps({"sender": "room", "command": "start", "option": "commoner"}).encode())
            except socket.error:
                player[0].close()
                # TODO: What do we do if a client exits while waiting?
        global game_full
        game_full = True 

def main():
    if len(sys.argv) != 3:
        print("Correct usage: room.py <ip_addr> <port_num>")
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
    
    room_name = "room" + str(PORT)

    topic_list.append(room_name + "/game")
    topic_list.append(room_name + "/new_leader")
    topic_list.append(room_name + "/proposed_infected")

    client = mqtt.Client(room_name)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(broker, MQTT_PORT, TIMEOUT)
    client.loop_start()

    # handle publishing logic
    global game_info_string
    game_info_string = str(infected[1])
    publish_game_info(client) 


    global game_finished
    while (not game_finished):
        if (infected_found):
            # inform players of game finishing and close their connection
            for player in player_list:
                # game finished
                player[0].sendall(json.dumps({"sender": "room", "command": "finish"}).encode())
                player[0].close()
            game_finished = True
                
    # stop the network loop and exit the program
    client.loop_stop()
    sys.exit(EXIT_CODE)

if __name__ == '__main__':
    main()