from .config import SANDBOX_CPU_LIMIT, SANDBOX_MEMORY_LIMIT
import os
import config

import docker

class Sandbox:
    def __init__(self, cpus=None, memory=None):
        self.client = docker.from_env()
        self.cpus = cpus
        self.memory = memory

    def run_container(self, image, command, environment=None, volumes=None):
        container_config = {
            'image': image,
            'command': command,
            'detach': True,
            'remove': True,
            'environment': environment or {},
            'volumes': volumes or {},
        }
        if self.cpus is not None:
            container_config['cpus'] = self.cpus
        if self.memory is not None:
            container_config['mem_limit'] = self.memory

        container = self.client.containers.run(**container_config)
        return container.logs(stream=True)

# Placeholder for other sandbox functions or classes
