# "Find the infected" game
## Introduction
This repository holds the code for the "Find the infected" game made for the Distributed Systems course in the University of Oulu.

The purpose of this game is to showcase distributed functionaliy by emulating logic from games like "Among us" and "Town of Salem". Multiple clients can connect to one matchmaking server through sockets. The matchmaker then creates a "room" server for a set number of players and informs them of the server's port and how to connect to him. Once the room is full, more rooms are spinned up. If a room crashes, a new one is created and the clients are redirected to it. The socket communication is open while the game is ongoing with the idea of informing the client about where and how they need to (re)connect and also when the game is finished. An MQTT broker is also used to allow clients to communicate between eachother and with the room. However, this communication is related to how the game itself works, instead of the server-client functionality. 

The game description is the following: "Four players join a room and find out that of them has been infected by a deadly virus! The remaining three players need to figure out who the infected one is and flush him out before they are also infected. Thankfully, one of the players has gained psychic abilities and can find out who the infected is. However, he has to convince the rest that he is not lying..."

The players can talk with eachother through MQTT, vote for who the infected player is (so that if they are right, the game can end) and for the leader (player with ppsychic abilities) to receive information about the infected. MQTT is also used to ensure that there is always a leader. In the event that the leader quits the game, an election is started by the clients (automaticall in the background, the players do not need to do anything for this) that notice his disappearance. Then, the client who joined the room first with respect to the other clients is elected as the new leader. This is a simple implementation of the "bully algorithm", as that client with the oldest timestamp will just disregard the other clients after comparing his timestamp with theirs and will elect himself as the leader.

The game has been fully dockerized by splitting it into three* containers: One for the MQTT broker, one for the matchmaker server and one for each room that is created (*the containers can be many more, as many rooms can be created. However, as the same image is used for all of them, it can be considered that they are only three).

The client program is ran standalone outside of docker.

## Installation instructions
Download [docker](https://docs.docker.com/desktop/install/windows-install/) and [python 3.10](https://www.python.org/downloads/release/python-3100/).

Start the docker containers (tested only on Windows computers.)

```
1. docker compose build
2. docker compose up
```

Install mqtt library for python

```
pip install paho-mqtt
```

Run as many client as you would like by typing te following:

```
python src/client/client.py
```
The interface for the clients listens for client input keypresses.

If **C** is pressed the player can write a single chat message.
If **I** is pressed the player can vote for the infected by passing their user id.
If **Q** is pressed the player can quit the game.
If the player is the leader they have the additional command of **H** which will give them the name of the infected player.

(Four clients should be connected in the span of 60 seconds. Otherwise, the matchmaker will kill the rooms. This was done intentionally so that empty rooms are cleaned up.)



To stop docker:
```
docker compose down
```

## Further evaluation
Locust is used to evaluate the load capabilities of the matchmaker. To install it, do
```
pip install locust
```

Then, navigate to the Evaluation folder and run