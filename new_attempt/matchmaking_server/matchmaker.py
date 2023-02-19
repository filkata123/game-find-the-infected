import socket
import threading
import queue

class Room(threading.Thread):
    def __init__(self):
        super().__init__()
        self.clients = []
        self.message_queue = queue.Queue()
    
    def run(self):
        while True:
            try:
                message = self.message_queue.get(block=True, timeout=0.1)
            except queue.Empty:
                pass
            else:
                for client in self.clients:
                    client.sendall(message)
    
    def add_client(self, client_socket):
        self.clients.append(client_socket)
    
    def remove_client(self, client_socket):
        self.clients.remove(client_socket)

def handle_client(client_socket, rooms):
    # Find a room with an open slot or create a new room
    room = None
    for r in rooms:
        if len(r.clients) < 5:
            room = r
            break
    if room is None:
        room = Room()
        rooms.append(room)
        room.start()
    # Add client to the room
    room.add_client(client_socket)
    # Handle communication with client
    while True:
        data = client_socket.recv(1024)
        if not data:
            break
        # Enqueue message to be sent to other clients in the same room
        room.message_queue.put(data)
    # Client has disconnected, remove from room
    room.remove_client(client_socket)
    # If room is empty, remove from list of active rooms
    if len(room.clients) == 0:
        rooms.remove(room)
        room.join()
    client_socket.close()

def main():
    # Set up socket
    host = ''
    port = 12345
    backlog = 5
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(backlog)
    print('Server listening on {}:{}'.format(host, port))
    # Main loop
    global rooms
    rooms = []
    while True:
        client_socket, client_address = server_socket.accept()
        print('Received connection from {}'.format(client_address))
        client_thread = threading.Thread(target=handle_client, args=(client_socket, rooms))
        client_thread.start()

if __name__ == '__main__':
    main()