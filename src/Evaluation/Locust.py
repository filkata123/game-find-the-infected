import time
from locust import HttpUser, task, between
import subprocess

class MyUser(HttpUser):
    wait_time = between(10, 15)

    @task
    def execute_client_script(self):
        subprocess.run(["python", "../client/client.py"])

if __name__ == "__main__":
    MyUser.host = "http://localhost:1234"
    MyUser.run()