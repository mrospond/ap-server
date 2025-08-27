import os
import subprocess
import threading
import signal
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- Configuration ---
EXPERIMENTS = [
    {
        "experimentName": "analysing_pii_leakage",
        "ref": "https://arxiv.org/abs/2302.00539",
        "code": "https://github.com/microsoft/analysing_pii_leakage"
    },
    {
        "experimentName": "LM_PersonalInfoLeak",
        "ref": "https://arxiv.org/abs/2205.12628",
        "code": "https://github.com/jeffhj/LM_PersonalInfoLeak"
    }
]

EXPERIMENTS_PATH = Path(os.path.abspath(".."))  # parent directory

# --- FastAPI App ---
app = FastAPI(title="Docker Experiment Manager")

# --- Models ---
class BuildRequest(BaseModel):
    experiment_name: str

class RunRequest(BaseModel):
    experiment_name: str
    container_name: Optional[str] = None
    command: Optional[str] = None

class ResetRequest(BaseModel):
    experiment_name: str
    container_name: Optional[str] = None
    command: Optional[str] = None

# --- Helpers ---
def _run_cli(cmd: List[str], cwd: Optional[Path] = None) -> str:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"{e.stdout.strip()}")

def _get_experiment_dir(name: str) -> Path:
    exp_dir = EXPERIMENTS_PATH / name
    if not exp_dir.is_dir() or not (exp_dir / "Dockerfile").is_file():
        raise HTTPException(status_code=404, detail=f"Experiment '{name}' not found or missing Dockerfile")
    return exp_dir

# --- Endpoints ---

@app.get("/experiments", summary="List all available experiments")
def list_experiments():
    dirs = [
        d.name for d in EXPERIMENTS_PATH.iterdir()
        if d.is_dir() and (d / "Dockerfile").exists()
    ]
    return {"experiments": dirs}

@app.post("/build", summary="Build Docker image for an experiment")
def build_image(req: BuildRequest):
    exp_dir = _get_experiment_dir(req.experiment_name)
    tag = req.experiment_name.lower().replace("_", "-")
    log = _run_cli(["docker", "build", "-t", tag, "."], cwd=exp_dir)
    return {"image_tag": tag, "build_log": log}

@app.post("/run", summary="Run a container from experiment image")
def run_container(req: RunRequest):
    image_tag = req.experiment_name.lower().replace("_", "-")
    cmd = ["docker", "run", "--detach"]
    if req.container_name:
        cmd += ["--name", req.container_name]
    cmd.append(image_tag)
    if req.command:
        cmd += req.command.split()
    cid = _run_cli(cmd).strip()
    return {"container_id": cid}

@app.post("/reset", summary="Reset a container for an experiment")
def reset_container(req: ResetRequest):
    # Stop & remove existing container if present
    name = req.container_name or req.experiment_name.lower().replace("_", "-")
    try:
        _run_cli(["docker", "stop", name])
        _run_cli(["docker", "rm", name])
    except HTTPException:
        # ignore if not found
        pass

    # Re-run container
    image_tag = req.experiment_name.lower().replace("_", "-")
    cmd = ["docker", "run", "--detach", "--name", name, image_tag]
    if req.command:
        cmd += req.command.split()
    cid = _run_cli(cmd).strip()
    return {"container_id": cid}

# --- Optional: Supervisor, Logging, WebSockets omitted for brevity ---  
