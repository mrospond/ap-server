# Docker Experiment Manager — User Guide

The app lets you **build, run, monitor, and manage experiments inside Docker containers** through a FastAPI backend with a simple HTTP/WebSocket interface for log streaming.

It is intended for anyone who wants to run controlled experiments with consistent environments on `x86` and `arm64` CPUs.


## Features
- Central configuration of experiments in `config.py`.
- Build experiment Docker images with a single API call.
- Start and stop experiment containers safely.
- Stream **live logs** via WebSocket.
- Archive and download experiment **artifacts as `.zip`** files.
- Simple web frontend served from `/static`.


## Prerequisites
- **Python >= 3.8**
- **Docker** installed and running
- **Pip** to install Python dependencies


## Installation & Setup

1. **Clone the repository:**
```
git clone <your-repo-url>
cd <repo-name>/server
```

2. **Install dependencies:**
```
pip install -r requirements.txt

# or if that fails:
# pip install fastapi uvicorn websockets
```

3. **Set up experiments directory**  
By default, the app expects an `../experiments` folder (relative to project root):

```
experiments/
├── analysing_pii_leakage/
│   ├── Dockerfile
│   ├── Dockerfile.arm64
│   ├── hello.py
│   └── results/
└── test/
    ├── Dockerfile
    ├── Dockerfile.arm64
    └── results/
        ├── results.csv
        └── results.png
```
- Each experiment folder must contain a **Dockerfile** for a given architecture (`Dockerfile` or `Dockerfile.arm64`).


4. **Edit `config.py` to configure your experiments:**

```
from models import Experiment

EXPERIMENTS = [
    Experiment(
      name="analysing_pii_leakage",
      ref="https://arxiv.org/abs/2302.00539",
      code="https://github.com/microsoft/analysing_pii_leakage",
      entrypoint="hello.py hello world 123", # NOTE this is an example
      artifacts_path="results",
    ),
    Experiment(
      name="LM_PersonalInfoLeak",
      ref="https://arxiv.org/abs/2205.12628",
      code="https://github.com/jeffhj/LM_PersonalInfoLeak",
      entrypoint="main.py",
    ),
]
```


- `name`: name of the directory with experiment source code, this directory must contain a Dockerfile.  
- `ref`: e.g. arXiv link.  
- `code`: source code (reference repository).  
- `entrypoint`: command executed as docker `--entrypoint` parameter when running container.  
- `artifacts_path`: directory containing results to export (relative to `name` directory).  

---

## Running the Application

Start the FastAPI app:
```
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://<IP>:8000/` in your browser



## Typical Workflow
1. Configure experiment in `config.py`.
2. Place code/Dockerfile inside `../experiments/<name>`.
3. **Build** image via `/build`.
4. **Run** the experiment via `/run`.
5. Check live **logs** via Web UI or WebSocket.
6. **Download results** as ZIP from `/artifacts/<experiment_name>`.
7. **Clean up** container via `/remove` (don't forget this step, the container will continue running on the server until it is stopped or exits).


## Security Notes
- This is a dev setup! Currently, the API is **open** (CORS `*` allowed, no authentication).  
- For production, consider:
  - Adding authentication middleware.
  - Limiting container permissions.
  - Mounting volumes in read-only mode where possible.


## Troubleshooting
- **Experiment not found?**  
  - Check `config.py` and ensure the name matches the name of the directory present in the `../experiments/` dir.
- **Artifacts missing?**  
  - Ensure the `artifacts_path` is set correctly (path relative to experiment directory), and the artifacts directory exists.
- **Docker command not found?**  
  - Ensure Docker is installed and accessible to your user (make sure the user is in the docker group).
- **Build using the wrong architecture?**  
  - The app auto-selects `Dockerfile.arm64` if running on `aarch64`, make sure the correct Dockerfile exists.


## Implementing guidelines
- `test` experiment provides a simple example setup running a Python script with keyword parameters (could be model name, size, decoding algos, etc.). The experiment directory is mounted from the host into a container by default, so that the container only encapsulates the execution environment. No experiment files are removed after calling the `/remove` endpoint.
- To start developing new experiments, clone the github repo into the `/experiments` directory.
- Make sure to include both Dockerfile and Dockerfile.arm64 if the experiment should run on both `x86` and `arm64` architectures.
- Use multistage Dockerfiles to reduce image size and improve build times.
- Keep experiment entrypoint minimal. Complex workflows should be wrapped in a script (python/bash/etc, depending on your Dockerfile) stored inside the experiment folder.
- Store all generated results inside the configured `artifacts_path` so they can be retrieved via the `/artifacts` endpoint. If some experiments log the results directly to stdout, make sure to redirect them to your results file
- Use descriptive and consistent experiment names, since they define both the folder structure and Docker image tags.
- Ensure reproducibility by pinning dependency versions wherever possible.
- Clean up unused containers and images regularly to prevent disk space issues.
