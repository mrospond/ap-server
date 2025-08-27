import os
import docker
import logging
from configs import EXPERIMENTS_PATH

log_file_path = os.path.join(os.path.dirname(__file__), "docker_client.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Capture INFO and higher severity logs
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, mode='a'),  # append to file
        logging.StreamHandler()  # optional: also print to console
    ]
)

logger = logging.getLogger("DockerClientLogger")

class DockerExperimentManager:
    def __init__(self, experiment_name: str, client: docker.DockerClient = None):
        self.experiment_name = experiment_name
        self.experiment_dir = os.path.abspath(
            os.path.join(EXPERIMENTS_PATH, experiment_name)
        ) 
        self.client = client or docker.from_env()


    def __experiment_exists(self, name: str) -> bool:
        """
        Checks if docker experiment exists under specified path 
        """
        return (
            os.path.isdir(self.experiment_dir) and
            os.path.isfile(os.path.join(self.experiment_dir, "Dockerfile"))
        )

    def build_image(self) -> str:
        """
        Builds a docker image with a specified name from a Dockerfile in experiments_path directory
        """
        if not self.__experiment_exists(self.experiment_name):
            raise FileNotFoundError(f"Experiment '{self.experiment_name}' not found or missing Dockerfile")

        image_tag = self.experiment_name.lower().replace("_", "-")
        experiment_dir = os.path.join(self.experiment_dir, self.experiment_name)

        logger.info("Building Docker image '%s'...", image_tag)
        image, logs = self.client.images.build(path=self.experiment_dir, tag=image_tag)

        # for chunk in logs:
        #     print(chunk)
        #     if 'stream' in chunk:
        #         logger.debug(chunk['stream'].strip())

        logger.info("Image '%s' built successfully with ID %s", self.experiment_name, image.id)
        return image_tag

    def run_container(self, image_tag: str, name: str = None, **kwargs):
        try:
            container = client.containers.run(image=image_tag, name=name, detach=True, **kwargs)
            logger.info("Started container %s from image %s", container.id[:12], image_tag)
            return container
        except docker.errors.APIError as e:
            logger.error("Failed to run container: %s", e)
            raise

    def stop_container(self, container_id: str, remove: bool = False):
        try:
            container = client.containers.get(container_id)
            container.stop()
            logger.info("Stopped container %s", container.id[:12])
            if remove:
                container.remove()
                logger.info("Removed container %s", container.id[:12])
            return container
        except docker.errors.NotFound:
            logger.warning("Container '%s' not found", container_id)
            raise
        except docker.errors.APIError as e:
            logger.error("Error stopping container '%s': %s", container_id, e)
            raise


if __name__ == "__main__":
    d = DockerExperimentManager("test")
    d.build_image()
    print(d)
    # print("hello")
    # experimentName = "test"
    # print(build_image(experimentName))
    # print("bye")

    pass