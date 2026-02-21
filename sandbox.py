import docker
import os
import tempfile

def execute_python_in_sandbox(script: str) -> str:
    """
    Executes a Python script inside an isolated, ephemeral Docker container and returns the output.
    Useful for safely running generated code, accessing the internet via requests, or processing data.
    """
    try:
        client = docker.from_env()
    except Exception as e:
        return f"Sandbox Error: Unable to connect to Docker daemon. {str(e)}"
    
    # Write script to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
        temp_file.write(script)
        temp_path = temp_file.name

    try:
        # Run container. Python:3.11-slim image
        # Wait for the image to pull if not present
        container = client.containers.run(
            image="python:3.11-slim",
            command=["python", "/app/script.py"],
            volumes={
                temp_path: {'bind': '/app/script.py', 'mode': 'ro'}
            },
            working_dir="/app",
            auto_remove=True,
            mem_limit="512m",
            # Removed cpus=0.5 to fix 'unexpected keyword argument cpus' error
            detach=True,
            stdout=True,
            stderr=True
        )
        try:
            # Wait up to 60 seconds for the script to finish
            result = container.wait(timeout=60)
            logs = container.logs().decode('utf-8')
            if result['StatusCode'] == 0:
                return f"Execution Successful:\n{logs}"
            else:
                return f"Execution Failed with code {result['StatusCode']}:\n{logs}"
        except Exception as e:
            # Timeout or other error during wait
            container.stop(timeout=1)
            return f"Execution Error or Timeout (60s limit reached): {str(e)}"
    except docker.errors.ContainerError as e:
        return f"Execution Failed with code {e.exit_status}:\n{e.stderr.decode('utf-8')}"
    except Exception as e:
        return f"Error spinning up sandbox: {str(e)}"
    finally:
        os.remove(temp_path)
