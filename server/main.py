import os
import shutil
import subprocess
import shlex
from pathlib import Path
from typing import List, Optional, Tuple, Iterator
import asyncio
import logging

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import EXPERIMENTS, EXPERIMENTS_PATH
from models import Experiment, NameRequest


# Logger config
logger = logging.getLogger("uvicorn")


# FastAPI
app = FastAPI(title="Docker Experiment Manager")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Helpers
def _get_config(name: str) -> Experiment:
    """
    Retrieves the experiment configuration by name.
    Args:
        name: The experiment name.
    Returns:
        Experiment: Matching experiment configuration.
    Raises:
        HTTPException: If the experiment name does not exist.
    """
    for cfg in EXPERIMENTS:
        if cfg.name == name:
            return cfg
    raise HTTPException(status_code=404, detail=f"Experiment '{name}' not found")

def _get_exp_paths(name: str) -> Tuple[Experiment, Path, Optional[Path]]:
    """
    Resolves experiment paths based on configuration.
    Args:
        name: The experiment name.
    Returns:
        Tuple of:
            - Experiment configuration
            - Experiment directory path
            - Artifacts directory path (if defined)
    """
    cfg = _get_config(name)
    exp_dir = EXPERIMENTS_PATH / cfg.name
    art_dir = exp_dir / cfg.artifacts_path.strip() if cfg.artifacts_path.strip() else None
    return cfg, exp_dir, art_dir

def _run_cli(cmd: List[str], cwd: Optional[Path] = None, timeout: Optional[int] = None) -> str:
    """
    Runs a shell command and return its output.
    Args:
        cmd: Command and arguments as a list.
        cwd: Working directory for the command.
        timeout: Optional timeout in seconds.
    Returns:
        Captured stdout as a string.
    Raises:
        HTTPException: On failure or timeout.
    """
    try:
        logger.info(f"Running command: {' '.join(cmd)}")
        res = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
            timeout=timeout,
        )
        return res.stdout
    except subprocess.CalledProcessError as e:
        logger.info("Docker error: %s", e.stdout.strip().splitlines()[0] if e.stdout else "")
        raise HTTPException(status_code=404, detail=e.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Command timed out")

def _container_name(name: str) -> str:
    """
    Derives a standardized Docker container name.
    Args:
        name: Experiment name.
    Returns:
        Container name string.
    """
    return name.replace("_", "-") + "-container"

def _remove_container(cname: str):
    """
    Force removes a Docker container.
    Args:
        cname: Container name.
    """
    try:
        _run_cli(["docker", "rm", "-f", cname])
    except HTTPException:
        pass

def _stream_process(cmd: List[str], cwd: Optional[Path] = None) -> Iterator[str]:
    """
    Runs a process and streams its stdout line by line.
    Args:
        cmd: Command and arguments as a list.
        cwd: Working directory for the process.
    Yields:
        Output lines as strings.
    """
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for line in proc.stdout:
        yield line
    proc.wait()

def _select_dockerfile(exp_dir: Path) -> Path:
    """
    Selects Dockerfile based on architecture.
    Args:
        exp_dir: Experiment directory.
    Returns:
        Path to Dockerfile.
    Raises:
        HTTPException: If the file is missing.
    """
    dockerfile_name = "Dockerfile.arm64" if os.uname().machine == "aarch64" else "Dockerfile"
    path = exp_dir / dockerfile_name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{dockerfile_name} not found")
    return path

# Routes
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")

# @app.get("/logs", include_in_schema=False)
# def logs_page():
#     return FileResponse("static/logs.html")

@app.get("/experiments", summary="List all experiments with full configs")
def list_experiments():
    return {"experiments": [cfg.dict() for cfg in EXPERIMENTS]}

@app.post("/build", summary="Build Docker image (streaming logs)")
def build_image(req: NameRequest):
    """
    Builds a Docker image for the experiment.
    Args:
        req: Request containing experiment name.
    Returns:
        StreamingResponse of Docker build logs.
    """
    cfg, exp_dir, _ = _get_exp_paths(req.experiment_name)
    dockerfile = _select_dockerfile(exp_dir)
    tag = cfg.name.lower().replace("_", "-")
    logger.info(f"Building image with tag {tag} from {dockerfile}")
    return StreamingResponse(
        _stream_process(["docker", "build", "-t", tag, "-f", str(dockerfile), "."], cwd=exp_dir),
        media_type="text/plain",
    )

@app.post("/run", summary="Run container for experiment")
def run_container(req: NameRequest):
    """
    Runs a Docker container for the specified experiment.
    Args:
        req: Request containing experiment name.
    Returns:
        JSON with container ID.
    """
    cfg, exp_dir, _ = _get_exp_paths(req.experiment_name)
    cname = _container_name(cfg.name)
    _remove_container(cname)
    tag = cfg.name.lower().replace("_", "-")
    cmd = ["docker", "run", "--name", cname, "--detach", "--volume", f"{exp_dir}:/app", "--workdir", "/app", tag]
    if cfg.entrypoint.strip():
        cmd += shlex.split(cfg.entrypoint)
    cid = _run_cli(cmd, cwd=exp_dir).strip()
    return {"container_id": cid}

@app.post("/remove", summary="Remove container for experiment")
def remove_container(req: NameRequest):
    cname = _container_name(req.experiment_name)
    _remove_container(cname)
    return {"removed": cname}

@app.get("/artifacts/{experiment_name}", summary="Download experiment artifacts")
def download_artifacts(experiment_name: str):
    """
    Downloads experiment artifacts as a zip archive.
    Args:
        experiment_name: The experiment name.
    Returns:
        FileResponse with zip file of artifacts.
    Raises:
        HTTPException: If artifacts are not found.
    """
    cfg, _, art_dir = _get_exp_paths(experiment_name)
    if not art_dir or not art_dir.exists() or not art_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Artifacts not found for '{experiment_name}'")
    zip_path = shutil.make_archive(str(art_dir), 'zip', root_dir=str(art_dir))
    return FileResponse(path=zip_path, filename=f"{cfg.name}-artifacts.zip", media_type="application/zip")

@app.websocket("/ws/logs/container/{container_id}")
async def websocket_logs(ws: WebSocket, container_id: str):
    """
    Streams Docker container logs over WebSocket.
    Args:
        ws: WebSocket connection.
        container_id: Target container ID.
    """
    await ws.accept()
    proc = await asyncio.create_subprocess_exec(
        "docker", "logs", "-f", container_id,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    try:
        async for line in proc.stdout:
            if line:
                await ws.send_text(line.decode().rstrip())
    except WebSocketDisconnect:
        pass
    finally:
        try:
            if proc.returncode is None:
                proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
        try:
            await ws.close()
        except RuntimeError:
            pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
