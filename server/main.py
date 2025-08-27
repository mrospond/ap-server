import os
import signal
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio, threading, time, platform

# --- Experiment Configuration ---
EXPERIMENTS: List[Dict[str, str]] = [
    {
        "experimentName": "analysing_pii_leakage",
        "ref": "https://arxiv.org/abs/2302.00539",
        "code": "https://github.com/microsoft/analysing_pii_leakage",
        "entrypoint": "hello.py",
        "artifacts_path": ""
    },
    {
        "experimentName": "LM_PersonalInfoLeak",
        "ref": "https://arxiv.org/abs/2205.12628",
        "code": "https://github.com/jeffhj/LM_PersonalInfoLeak",
        "entrypoint": "python main.py",
        "artifacts_path": ""
    },
    {
        "experimentName": "test",
        "ref": "https://arxiv.org/abs/2205.12628",
        "code": "https://github.com/jeffhj/LM_PersonalInfoLeak",
        "entrypoint": "",
        "artifacts_path": "results"
    }
]

EXPERIMENTS_PATH = Path(os.path.abspath(".."))
LOGS_PATH = Path("./var/log/docker_service")
LOGS_PATH.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Docker Experiment Manager")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/logs", include_in_schema=False)
def logs_page():
    return FileResponse("static/logs.html")


class NameRequest(BaseModel):
    experiment_name: str


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


@app.get("/experiments", summary="List all experiments")
def list_experiments():
    return {"experiments": [cfg["experimentName"] for cfg in EXPERIMENTS]}


@app.post("/build", summary="Build Docker image (streaming logs)")
def build_image(req: NameRequest):
    dockerfile = "Dockerfile"
    if platform.machine() == "aarch64":
        dockerfile += ".arm64"
    cfg = _get_experiment_config(req.experiment_name)
    exp_dir = EXPERIMENTS_PATH / cfg["experimentName"]
    if not (exp_dir / dockerfile).exists():
        raise HTTPException(status_code=404, detail=f"{dockerfile} not found")
    tag = cfg["experimentName"].lower().replace("_", "-")
    proc = subprocess.Popen(
        ["docker", "build", "-t", tag, "-f", dockerfile, "."],
        cwd=str(exp_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    def log_stream():
        for line in proc.stdout:
            yield line
        proc.wait()

    return StreamingResponse(log_stream(), media_type="text/plain")


@app.post("/run", summary="Run container for experiment")
def run_container(req: NameRequest):
    cfg = _get_experiment_config(req.experiment_name)
    exp_dir = EXPERIMENTS_PATH / cfg["experimentName"]
    tag = cfg["experimentName"].lower().replace("_", "-")
    cname = _container_name(cfg["experimentName"])

    # Remove existing container if any
    try:
        _run_cli(["docker", "inspect", cname])
        _run_cli(["docker", "rm", "-f", cname])
    except HTTPException:
        pass

    volume_spec = f"{exp_dir}:/app"
    workdir = "/app"
    cmd = [
        "docker", "run",
        "--name", cname,
        "--detach",
        "--volume", volume_spec,
        "--workdir", workdir,
        tag
    ]
    entry = cfg.get("entrypoint", "").strip()
    if entry:
        cmd += entry.split()

    cid = _run_cli(cmd).strip()
    return {"container_id": cid}


@app.post("/remove", summary="Remove container for experiment")
def remove_container(req: NameRequest):
    cname = _container_name(req.experiment_name)
    _run_cli(["docker", "rm", "-f", cname])
    return {"removed": cname}


@app.get("/artifacts/{experiment_name}", summary="Download experiment artifacts")
def download_artifacts(experiment_name: str):
    cfg = _get_experiment_config(experiment_name)
    artifact_rel = cfg.get("artifacts_path", "").strip()
    if not artifact_rel:
        raise HTTPException(status_code=404, detail="No artifacts_path configured")

    # **Correctly resolve artifacts directory under each experiment**
    artifact_dir = EXPERIMENTS_PATH / cfg["experimentName"] / artifact_rel
    if not artifact_dir.exists() or not artifact_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Artifacts for '{experiment_name}' not found")

    # Create zip file alongside the directory
    zip_path = artifact_dir.with_suffix(".zip")
    shutil.make_archive(str(artifact_dir), 'zip', root_dir=str(artifact_dir))

    return FileResponse(
        path=str(zip_path),
        filename=f"{cfg['experimentName']}-artifacts.zip",
        media_type="application/zip"
    )


@app.websocket("/ws/logs/container/{container_id}")
async def websocket_logs_container(ws: WebSocket, container_id: str):
    await ws.accept()
    proc = subprocess.Popen(
        ["docker", "logs", "-f", container_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    loop = asyncio.get_running_loop()
    stop_event = threading.Event()

    def forward_logs():
        for line in proc.stdout:
            if stop_event.is_set():
                break
            asyncio.run_coroutine_threadsafe(ws.send_text(line.rstrip("\n")), loop)
        proc.stdout.close()

    thread = threading.Thread(target=forward_logs, daemon=True)
    thread.start()
    deadline = time.time() + 600  # 10 minutes

    try:
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            if time.time() >= deadline:
                await ws.send_text("[server] session timeout after 10 minutes")
                break
    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        proc.terminate()
        thread.join()
        try:
            await ws.close()
        except RuntimeError:
            pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
