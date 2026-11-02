from locust import HttpUser, task, between


class MyUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def home(self):
        self.client.get("/")
