from cradle import config
import config

import docker
from . import config
from . import config


class Sandbox:
    def __init__(self):
        self.config = config.Config()

    def __init__(self, cpus=None, memory=None):
        self.client = docker.from_env()
        self.cpus = cpus
        self.memory = memory

    def run_container(self, image, command):
        run_args = {
            'image': image,
            'command': command,
            'detach': True,
            'remove': True,
        }
        if self.cpus:
            run_args['cpus'] = self.cpus
        if self.memory:
            run_args['mem_limit'] = self.memory

        container = self.client.containers.run(**run_args, cpus=config.DOCKER_CPU_LIMIT, mem_limit=config.DOCKER_MEMORY_LIMIT)
        return container.logs(stream=True)

    def stop_container(self, container_id):
        container = self.client.containers.get(container_id)
        container.stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()