import docker

client = docker.from_env()

def run_code(container_image, command):
    container = client.containers.run(
        container_image,
        command,
        detach=True
    )
    result = container.logs()
    container.remove()
    return result