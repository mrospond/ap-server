from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import docker
import os

from configs import EXPERIMENTS, EXPERIMENTS_PATH

app = FastAPI()
client = docker.from_env()

app.mount("/index", StaticFiles(directory="static", html=True), name="static")

CONTAINER_NAME = "experiment-container"

# --- Request models ---
class RunRequest(BaseModel):
    experimentName: str
    args: str = ""  # optional extra arguments


@app.get("/experiments")
def get_experiments():
    """Return list of implemented experiments"""
    return {"experiments": [e["experimentName"] for e in EXPERIMENTS]}



@app.post("/run")
def run_experiment(req: RunRequest):
    """Run an experiment container"""
    experiment = next((e for e in EXPERIMENTS if e["experimentName"] == req.experimentName), None)
    
    # experimentName exists in the config
    if experiment is None:
        raise HTTPException(status_code=501, detail=f"Experiment '{req.experimentName}' not implemented")

    # experimentName directory exists in current path
    if not experiment_exists(req.experimentName):
        raise FileNotFoundError(f"No experiment found: '{experiment_name}'")
        return

    try:
        build_image(req.experimentName)
        print("ok")
    except:
        pass
    # Force remove existing container
    try:
        print("OK")
        pass
        old = client.containers.get(CONTAINER_NAME)
        old.remove(force=True)
    except docker.errors.NotFound:
        pass

    pass
    # exp_cfg = EXPERIMENTS[req.experimentName]

    # container = client.containers.run(
    #     exp_cfg["image"],
    #     command=exp_cfg["default_cmd"] + req.args.split(),
    #     name=CONTAINER_NAME,
    #     runtime="nvidia",
    #     detach=True,
    #     stdout=True,
    #     stderr=True,
    #     volumes={".": {"bind": "/app", "mode": "rw"}}
    # )
    return True#{"status": "started", "container_id": container.id[:12]}

@app.post("/stop")
def stop_experiment():
    """Force stop the running experiment container"""
    try:
        container = client.containers.get(CONTAINER_NAME)
        container.remove(force=True)
        return {"status": "stopped", "container_id": container.id[:12]}
    except docker.errors.NotFound:
        return {"status": "error", "message": "No container found"}

@app.get("/logs")
def experiment_logs():
    """Return last 100 lines of container logs"""
    try:
        container = client.containers.get(CONTAINER_NAME)
        logs = container.logs(tail=100).decode("utf-8")
        return {"logs": logs}
    except docker.errors.NotFound:
        return {"logs": "No container running."}

@app.get("/status")
def experiment_status():
    """Return current container status"""
    try:
        container = client.containers.get(CONTAINER_NAME)
        return {"status": container.status, "id": container.id[:12]}
    except docker.errors.NotFound:
        return {"status": "not running"}
