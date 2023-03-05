import socket
import threading
import subprocess
import time
import json

HOST = 'localhost'
PORT = 1234
MAX_PLAYERS_PER_ROOM = 4
EXIT_CODE = 67

#TODO: identify clients

class Room:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.player_count = 0
        self.players : socket = []

        self.__start()
        
        self.thread = threading.Thread(target=self.keep_alive)
        self.thread.daemon = True
        self.thread.start()

        print('Room with port: ' + str(self.port) + " started!")

    def get_port(self):
        return self.port
    
    def get_player_count(self):
        return self.player_count

    # soft increment | possible improvement: actually check data from server process
    def increment_player_count(self, conn):
        if self.player_count == MAX_PLAYERS_PER_ROOM:
            return 0
        self.player_count = self.player_count + 1
        self.players.append(conn)
        return 1
    
    # create room server process and pass host and port
    def __start(self, restart_game = 0):
        self.proc = subprocess.Popen(['python', '../room_server/room.py', str(self.host), str(self.port), str(restart_game)]) #TODO: absolute path reference should be done here
        #self.proc = subprocess.Popen(f'new_attempt/room_server/room.py {str(self.host)} {str(self.port)}')

    # ensure that room is kept alive even if process crashes
    def keep_alive(self):
        while True:
            time.sleep(1)

            # handle clients that are no longer reachable
            for player in self.players:
                try:
                    player.sendall(f'ping'.encode())
                except socket.error:
                    player.close()
                    self.players.remove(player)
                    self.player_count = self.player_count - 1

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
                    player.close()
                break
            else:
                #reconnect clients
                print('Room with port: ' + str(self.port) + " crashed, reconnecting!")
                self.__start(1) # restart game
                for player in self.players:
                    try:
                        reconnection_object = json.dumps({"command":"reconnect", "options":""})
                        player.sendall(reconnection_object.encode())
                    except socket.error:
                        player.close()
                        self.players.remove(player)
                        self.player_count = self.player_count - 1

        # room deletes itself after game has finished
        rooms.remove(self)
        print('Room with port: ' + str(self.port) + " closed!")
        del self

# Create a list to store the list of clients in each room
rooms : Room = []

# Define a function to handle each client connection
def handle_client(conn, addr):
    print(f'New client connected: {addr}')

    if not rooms: 
        print('No rooms exist, creating first room...')
        room = Room(HOST, PORT + 1)
        rooms.append(room)
    else:
        room = rooms[-1]
        if room.get_player_count() == MAX_PLAYERS_PER_ROOM:
            print('Creating new room...')
            room = Room(HOST, room.get_port() + 1)
            rooms.append(room)
        
    # TODO: implement mutex here to ensure that multiple clients don't get assigned to the same server at the same time 

    room_connection_object = json.dumps({"command":"connect", "options":room.get_port()})
    conn.sendall(room_connection_object.encode())
    room.increment_player_count(conn)
    print(f'Client {addr} added to room {room.get_port()}')

# Define a function to start the main server loop
def start_server():
    # Create a socket object
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)

    print(f'Server started on {HOST}:{PORT}')

    # Accept incoming connections
    while True:
        ## TODO: thread for keybind listening? (ctrl + C)
        conn, addr = server_socket.accept()
        # Start a new thread to handle each client connection
        handle_client(conn, addr)

if __name__ == '__main__':
    start_server()