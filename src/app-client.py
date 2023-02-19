#!/usr/bin/env python3

import sys
import socket
import selectors
import traceback

import libclient

sel = selectors.DefaultSelector()


def create_request(action, value):
    # change the possible actions
    if action == "search":
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=value),
        )
    else:
        return dict(
            type="binary/custom-client-binary-type",
            encoding="binary",
            content=bytes(action + value, encoding="utf-8"),
        )


def start_connection(host, port, request):
    addr = (host, port)
    print(f"Starting connection to {addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = libclient.Message(sel, sock, addr, request)
    sel.register(sock, events, data=message)
    ROOMIP = 0 
    ROOMPORT = 0
    try:
        while True:
            events = sel.select(timeout=1)
            for key, mask in events:
                message = key.data
                try:
                    message.process_events(mask)
                    ROOMIP = message.get_ROOM_IP()
                    ROOMPORT = message.get_ROOM_PORT()                   
                except Exception:
                    print(
                        f"Main: Error: Exception for {message.addr}:\n"
                        f"{traceback.format_exc()}"
                    )
                    message.close()
            # Check for a socket being monitored to continue.
            if not sel.get_map():
                break
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")
    finally:
        sel.close()       
    return ROOMIP, ROOMPORT
def start_connection_ToRoom(host, port):
        addr = (host, port)
        print(f"Starting connection to {addr}")
        sockRoom = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sockRoom.setblocking(False)
        sockRoom.connect(addr)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        sel.register(sockRoom, events, data=message)
        try:
            while True:
        
                # maintains a list of possible input streams
                sockets_list = [sys.stdin, sockRoom]
                read_sockets,write_socket, error_socket = sockRoom.select(sockets_list,[],[])
            
                for socks in read_sockets:
                    if socks == sockRoom:
                        message = socks.recv(2048)
                        print (message)
                    else:
                        message = sys.stdin.readline()
                        sockRoom.send(message)
                        sys.stdout.write("<You>")
                        sys.stdout.write(message)
                        sys.stdout.flush()
                sockRoom.close()
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")
        finally:
            sel.close() 
        

if len(sys.argv) != 5:
    print(f"Usage: {sys.argv[0]} <host> <port> <action> <value>")
    sys.exit(1)

host, port = sys.argv[1], int(sys.argv[2])
action, value = sys.argv[3], sys.argv[4]
request = create_request(action, value)
[ip, port]= start_connection(host, port, request)

start_connection_ToRoom(ip , port)


