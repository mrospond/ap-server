import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import asyncio

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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

BASE_PATH = Path(os.path.abspath(".."))
LOGS_PATH = Path("./var/log/docker_service")
LOGS_PATH.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Docker Experiment Manager")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")


class NameRequest(BaseModel):
    experiment_name: str


def _get_config(name: str) -> Dict[str, str]:
    for cfg in EXPERIMENTS:
        if cfg["experimentName"] == name:
            return cfg
    raise HTTPException(status_code=404, detail=f"Experiment '{name}' not found")


def _exp_paths(name: str) -> Tuple[Dict[str, str], Path, Path]:
    cfg = _get_config(name)
    exp_dir = BASE_PATH / cfg["experimentName"]
    art_rel = cfg.get("artifacts_path", "").strip()
    art_dir = exp_dir / art_rel if art_rel else None
    return cfg, exp_dir, art_dir  # art_dir may be None


def _run_cli(cmd: List[str], cwd: Optional[Path] = None, timeout: Optional[int] = None) -> str:
    try:
        res = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=True, text=True, timeout=timeout
        )
        return res.stdout
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Command timed out")


def _container_name(name: str) -> str:
    return name.replace("_", "-") + "-container"


def _stream_process(cmd: List[str], cwd: Optional[Path] = None):
    proc = subprocess.Popen(
        cmd, cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    def generator():
        for line in proc.stdout:
            yield line
        proc.wait()
    return generator()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/logs", include_in_schema=False)
def logs_page():
    return FileResponse("static/logs.html")


@app.get("/experiments", summary="List all experiments")
def list_experiments():
    return {"experiments": [cfg["experimentName"] for cfg in EXPERIMENTS]}


@app.post("/build", summary="Build Docker image (streaming logs)")
def build_image(req: NameRequest):
    cfg, exp_dir, _ = _exp_paths(req.experiment_name)
    dockerfile = "Dockerfile.arm64" if subprocess.os.uname().machine == "aarch64" else "Dockerfile"
    df = exp_dir / dockerfile
    if not df.exists():
        raise HTTPException(status_code=404, detail=f"{dockerfile} not found")
    tag = cfg["experimentName"].lower().replace("_", "-")
    return StreamingResponse(
        _stream_process(["docker", "build", "-t", tag, "-f", dockerfile, "."], cwd=exp_dir),
        media_type="text/plain"
    )


@app.post("/run", summary="Run container for experiment")
def run_container(req: NameRequest):
    cfg, exp_dir, _ = _exp_paths(req.experiment_name)
    cname = _container_name(cfg["experimentName"])
    # remove existing
    try:
        _run_cli(["docker", "inspect", cname])
        _run_cli(["docker", "rm", "-f", cname])
    except HTTPException:
        pass

    tag = cfg["experimentName"].lower().replace("_", "-")
    cmd = ["docker", "run", "--name", cname, "--detach",
           "--volume", f"{exp_dir}:/app", "--workdir", "/app", tag]
    if cfg.get("entrypoint"):
        cmd += cfg["entrypoint"].split()
    cid = _run_cli(cmd).strip()
    return {"container_id": cid}


@app.post("/remove", summary="Remove container for experiment")
def remove_container(req: NameRequest):
    cname = _container_name(req.experiment_name)
    _run_cli(["docker", "rm", "-f", cname])
    return {"removed": cname}


@app.get("/artifacts/{experiment_name}", summary="Download experiment artifacts")
def download_artifacts(experiment_name: str):
    cfg, _, art_dir = _exp_paths(experiment_name)

    if not art_dir or not art_dir.exists() or not art_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"No artifacts found for experiment '{experiment_name}'"
        )

    # Create a zip file alongside the artifacts directory
    zip_path = shutil.make_archive(str(art_dir), 'zip', root_dir=str(art_dir))
    return FileResponse(
        path=zip_path,
        filename=f"{cfg['experimentName']}-artifacts.zip",
        media_type="application/zip"
    )


@app.websocket("/ws/logs/container/{container_id}")
async def websocket_logs(ws: WebSocket, container_id: str):
    await ws.accept()
    proc = subprocess.Popen(
        ["docker", "logs", "-f", container_id],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    stop = threading.Event()
    loop = asyncio.get_running_loop()

    def forward():
        for ln in proc.stdout:
            if stop.is_set():
                break
            asyncio.run_coroutine_threadsafe(ws.send_text(ln.rstrip("\n")), loop)
        proc.stdout.close()

    thread = threading.Thread(target=forward, daemon=True)
    thread.start()
    deadline = time.time() + 600

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
        stop.set()
        proc.terminate()
        thread.join()
        try:
            await ws.close()
        except RuntimeError:
            pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
