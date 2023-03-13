import socket
import threading
import subprocess
import time
import json

# Global variables
HOST = '0.0.0.0'
PORT = 1234
MAX_PLAYERS_PER_ROOM = 4
EXIT_CODE = 67

'''
Once the room object is created, it starts a subprocess, which starts a docker container based on the room image
The room object will destory the container once the game has finished (the room container signifies this with the EXIT_CODE) or if the application crashes
If the latter happens, the room container is restarted with same state as before
'''
class Room:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.player_count = 0
        self.game_started = False
        self.proc = None
        self.players : socket = []
        self.name = "room" + str(self.port)

        self.__start()
        
        self.thread = threading.Thread(target=self.keep_alive)
        self.thread.daemon = True
        self.thread.start()

        print('Room with port: ' + str(self.port) + " started!")

    def get_port(self):
        return self.port
    
    def get_player_count(self):
        return self.player_count
    
    def is_game_started(self):
        return self.game_started
    
    # soft player increment | possible improvement: actually check data from server process
    def increment_player_count(self, conn):
        if self.player_count == MAX_PLAYERS_PER_ROOM:
            return 0
        self.player_count = self.player_count + 1
        self.players.append(conn)
        return 1

    # soft player decrement
    def decrement_player_count(self, player):
        player.close()
        self.players.remove(player)
        self.player_count = self.player_count - 1
    
    # Build docker room container on host and run on the same netowrk as matchmaker container
    def __start(self, restart_game = 0):
        port_mapping = str(self.port) + ":" + str(self.port)
        cmd = "docker build -t room --build-arg HOST={} --build-arg PORT={} --build-arg RESTARTED={} . && docker run -p {} --name {} --network game-find-the-infected_default room" \
            .format(str(self.host), str(self.port), str(restart_game), port_mapping, self.name)
        self.proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

        # Wait until the room setup has finished, before starting the keep alive thread
        while True:
            output = self.proc.stdout.readline()
            if (b'Room setup finished.' in output):
                break

    # ensure that room is kept alive even if process crashes
    def keep_alive(self):
        game_start_timer = time.time()
        while True:
            # handle clients that are no longer reachable
            if (self.game_started):
                for player in self.players:
                    try:
                        time.sleep(1)
                        player.sendall(f'ping'.encode())
                    except socket.error:
                        self.decrement_player_count(player)
                if (self.player_count == 0):
                    print("All players left...destroying!")
                    self.proc.terminate()
                    break
            else:
                # if game was not started in 60 seconds, kill the room
                if (time.time() - game_start_timer > 60):
                    print("Nobody connected to room in 60 seconds...destroying!")
                    for player in self.players:
                        try:
                            player.close()
                        except socket.error:
                            pass
                    self.proc.terminate()
                    break

            # check status of room server
            # no status = process alive
            # EXIT_CODE returned = game has finished properly
            # any other status = room has crashed, so a new process will be started
            status = self.proc.poll()
            if status is None:
                # process alive
                continue
            elif status == EXIT_CODE:
                #release clients
                for player in self.players:
                    try:
                        player.sendall(json.dumps({"command": "finish", "options":""}).encode())
                    finally:
                        player.close()
                break
            else:
                #reconnect clients
                self.game_crashed = True
                try:
                    container_delete = "docker rm {}".format(self.name)
                    subprocess.check_output(container_delete, shell=True)
                except:
                    pass
                print('Room with port: ' + str(self.port) + " crashed, reconnecting!")
                self.__start(1) # restart game
                for player in self.players:
                    try:
                        player.sendall(json.dumps({"command":"reconnect", "options":""}).encode())
                    except socket.error as e:
                        print(e)
                        player.close()
                        self.players.remove(player)
                        self.player_count = self.player_count - 1

        # room deletes itself after game has finished
        # TODO: Improvement: link room containers to matchmaking container dynamically, so that if matchmaker dies, rooms die with it
        # TODO: Improvement check whether container exists before doing docker rm instead of try except
        try:
            container_delete = "docker rm -f {}".format(self.name)
            subprocess.check_output(container_delete, shell=True)
        except:
            pass
        rooms.remove(self)
        print('Room with port: ' + str(self.port) + " closed!")
        del self

# Create a list to store the list of clients in each room
rooms : Room = []

'''
Handle each client connection
'''
def handle_client(conn, addr):
    print(f'New client connected: {addr}')

    # Rooms list can be seen as a stack
    # Add room to list if there are no rooms or if the top room on the stack is full
    if not rooms: 
        print('No rooms exist, creating first room...')
        room = Room(HOST, PORT + 1)
        rooms.append(room)
    else:
        room = rooms[-1]
        # Don't add players to full or started game
        if room.get_player_count() == MAX_PLAYERS_PER_ROOM or room.is_game_started(): 
            print('Creating new room...')
            room = Room(HOST, room.get_port() + 1)
            rooms.append(room)
        
    # TODO: Possible improvement: implement mutex here to ensure that
    # multiple clients don't get assigned to the same server at the same time 

    # Inform clients that a room has been created and they can connect to it
    conn.sendall(json.dumps({"command":"connect", "options":room.get_port()}).encode())
    room.increment_player_count(conn)
    if (room.get_player_count() == MAX_PLAYERS_PER_ROOM):
        room.game_started = True
    print(f'Client {addr} added to room {room.get_port()}')


def main():
    # Create a socket object
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)

    print(f'Server started on {HOST}:{PORT}')

    # Accept incoming connections
    while True:
        ## Can't exit from this loop. but it doesn't matter as docker will take care of that
        conn, addr = server_socket.accept()
        # Start a new thread to handle each client connection
        handle_client(conn, addr)

if __name__ == '__main__':
    main()