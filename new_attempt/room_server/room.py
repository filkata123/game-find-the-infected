class Room():
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

#TODO ensure that this can be run by itself and containerize (no need for class)