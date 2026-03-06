from locust import HttpUser, between, task


class PlatformUser(HttpUser):
    wait_time = between(1, 3)

    @task(6)
    def health(self):
        self.client.get("/health", name="health")

    @task(3)
    def metrics(self):
        self.client.get("/metrics", name="metrics")

    @task(1)
    def openapi(self):
        self.client.get("/openapi.json", name="openapi")
