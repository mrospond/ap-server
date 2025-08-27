import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# --- Experiment Configuration ---
EXPERIMENTS: List[Dict[str, str]] = [
    {
        "experimentName": "analysing_pii_leakage",
        "ref": "https://arxiv.org/abs/2302.00539",
        "code": "https://github.com/microsoft/analysing_pii_leakage",
        "entrypoint": "python run.py"
    },
    {
        "experimentName": "LM_PersonalInfoLeak",
        "ref": "https://arxiv.org/abs/2205.12628",
        "code": "https://github.com/jeffhj/LM_PersonalInfoLeak",
        "entrypoint": "python main.py"
    },
    {
        "experimentName": "test",
        "ref": "https://arxiv.org/abs/2205.12628",
        "code": "https://github.com/jeffhj/LM_PersonalInfoLeak",
        "entrypoint": ""
    }
]

EXPERIMENTS_PATH = Path(os.path.abspath(".."))  # Directory containing experiment folders
LOGS_PATH = Path("./var/log/docker_service")
LOGS_PATH.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Docker Experiment Manager")


# --- Request Models ---

class NameRequest(BaseModel):
    experiment_name: str


# --- Internal Helpers ---

def _get_experiment_config(name: str) -> Dict[str, str]:
    for cfg in EXPERIMENTS:
        if cfg["experimentName"] == name:
            return cfg
    raise HTTPException(status_code=404, detail=f"Experiment '{name}' not found")


def _run_cli(cmd: List[str], cwd: Optional[Path] = None, timeout: Optional[int] = None) -> str:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
            timeout=timeout
        )
        return proc.stdout
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Command timed out")


def _container_name(name: str) -> str:
    return name.replace("_", "-") + "-container"


# --- API Endpoints ---

@app.get("/experiments", summary="List all experiments")
def list_experiments():
    print([route.path for route in app.routes])
    return {"experiments": [cfg["experimentName"] for cfg in EXPERIMENTS]}


@app.post("/build", summary="Build Docker image from Dockerfile")
def build_image(req: NameRequest):
    cfg = _get_experiment_config(req.experiment_name)
    exp_dir = EXPERIMENTS_PATH / cfg["experimentName"]
    if not (exp_dir / "Dockerfile").exists():
        raise HTTPException(status_code=404, detail="Dockerfile not found")
    tag = cfg["experimentName"].lower().replace("_", "-")
    output = _run_cli(["docker", "build", "-t", tag, "."], cwd=exp_dir)
    return {"image_tag": tag, "build_log": output}


@app.post("/run", summary="Run container for experiment")
def run_container(req: NameRequest):
    cfg = _get_experiment_config(req.experiment_name)
    tag = cfg["experimentName"].lower().replace("_", "-")
    cname = _container_name(cfg["experimentName"])
    try:
        _run_cli(["docker", "inspect", cname])
        _run_cli(["docker", "rm", "-f", cname])
    except HTTPException:
        # inspect failed: container does not exist
        pass
    entry = cfg.get("entrypoint", "")
    cmd = ["docker", "run", "--name", cname, "--detach", tag]
    if entry:
        cmd = ["docker", "run", "--name", cname, "--detach", tag] + entry.split()
    cid = _run_cli(cmd).strip()
    return {"container_id": cid}


@app.post("/remove", summary="Remove container for experiment")
def remove_container(req: NameRequest):
    cname = _container_name(req.experiment_name)
    # force stop & remove
    _run_cli(["docker", "rm", "-f", cname])
    return {"removed": cname}

@app.websocket("/ws/logs/container/{container_id}")
async def websocket_logs_container(ws: WebSocket, container_id: str):
    """
    Stream real-time Docker logs for any container by name or ID.
    Connect with: ws://<server>/ws/logs/container/{container_id}
    """
    await ws.accept()
    proc = subprocess.Popen(
        ["docker", "logs", "-f", container_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            await ws.send_text(line.rstrip("\n"))
    except WebSocketDisconnect:
        proc.send_signal(signal.SIGINT)
    finally:
        proc.terminate()


# @app.websocket("/ws/logs/{experiment_name}")
# async def stream_logs(ws: WebSocket, experiment_name: str):
#     """
#     Stream real-time Docker logs for the experiment's container.
#     Connect to ws://<server>/ws/logs/{experiment_name}
#     """
#     await ws.accept()
#     cname = _container_name(experiment_name)
#     proc = subprocess.Popen(
#         ["docker", "logs", "-f", cname],
#         stdout=subprocess.PIPE,
#         stderr=subprocess.STDOUT,
#         text=True
#     )
#     try:
#         while True:
#             line = proc.stdout.readline()
#             if not line:
#                 break
#             await ws.send_text(line.rstrip("\n"))
#     except WebSocketDisconnect:
#         proc.send_signal(signal.SIGINT)
#     finally:
#         proc.terminate()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
