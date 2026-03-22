from dataclasses import dataclass
import docker
import logging
from cradle.config import Config

logger = logging.getLogger(__name__)

@dataclass
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int = 0




class Sandbox:
    def __init__(self, config_obj: Config, cpus=None, memory=None):
        self.config = config_obj
        self.client = docker.from_env()
        self.cpus = cpus or config_obj.docker_cpu_limit
        self.memory = memory or config_obj.docker_memory_limit


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

        container = self.client.containers.run(**run_args, nano_cpus=int(float(self.cpus) * 1e9), mem_limit=self.memory)
        return container.logs(stream=True)

    def stop_container(self, container_id):
        container = self.client.containers.get(container_id)
        container.stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()