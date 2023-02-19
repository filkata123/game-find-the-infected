from flask import Flask, jsonify, request
import paho.mqtt.client as mqtt

PORT_MQTT = 1883
PORT_FLASK = 5000
TIMEOUT = 60

app = Flask(__name__)
messages = []
broker = 'mqtt'
topic = "chat"

@app.route('/')
def index():
    return app.send_static_file('index.html')

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe(topic)

def on_message(client, userdata, msg):
    message = msg.payload.decode()
    messages.append(message)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, PORT_MQTT, TIMEOUT)
client.loop_start()

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        message = request.json.get('message')
        client.publish(topic, message)
        return jsonify({'status': 'ok'})
    else:
        return jsonify(messages)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT_FLASK)
