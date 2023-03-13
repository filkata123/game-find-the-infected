# game-find-the-infected
"Find the infected" game made for the Distributed Systems course in the University of Oulu.

```
1. docker compose build
2. docker compose up
```

Run as many client as you would like (tested on python 3.10):

```
pip install paho-mqtt
python src/client/client.py
```

Stop docker
```
docker compose down
```