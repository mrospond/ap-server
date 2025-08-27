import os
import shutil
import subprocess
import shlex
from pathlib import Path
from typing import List, Optional, Tuple, Iterator
import asyncio

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


# --- Models ---
class Experiment(BaseModel):
    name: str
    ref: str
    code: str
    entrypoint: str = ""
    artifacts_path: str = ""


class NameRequest(BaseModel):
    experiment_name: str


# --- Experiment configs ---
EXPERIMENTS: List[Experiment] = [
    Experiment(
        name="analysing_pii_leakage",
        ref="https://arxiv.org/abs/2302.00539",
        code="https://github.com/microsoft/analysing_pii_leakage",
        entrypoint="hello.py hello world 123",
    ),
    Experiment(
        name="LM_PersonalInfoLeak",
        ref="https://arxiv.org/abs/2205.12628",
        code="https://github.com/jeffhj/LM_PersonalInfoLeak",
        entrypoint="main.py",
    ),
    Experiment(
        name="test",
        ref="https://arxiv.org/abs/2205.12628",
        code="https://github.com/jeffhj/LM_PersonalInfoLeak",
        artifacts_path="results",
    ),
]

# --- Paths ---
BASE_PATH = Path(os.path.abspath(".."))
LOGS_PATH = Path("./var/log/docker_service")
LOGS_PATH.mkdir(parents=True, exist_ok=True)

# --- FastAPI ---
app = FastAPI(title="Docker Experiment Manager")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Helpers ---
def _get_config(name: str) -> Experiment:
    for cfg in EXPERIMENTS:
        if cfg.name == name:
            return cfg
    raise HTTPException(status_code=404, detail=f"Experiment '{name}' not found")


def _exp_paths(name: str) -> Tuple[Experiment, Path, Optional[Path]]:
    cfg = _get_config(name)
    exp_dir = BASE_PATH / cfg.name
    art_rel = cfg.artifacts_path.strip() or None
    art_dir = exp_dir / art_rel if art_rel else None
    return cfg, exp_dir, art_dir


def _run_cli(cmd: List[str], cwd: Optional[Path] = None, timeout: Optional[int] = None) -> str:
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
            timeout=timeout
        )
        return res.stdout
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Command timed out")


def _container_name(name: str) -> str:
    return name.replace("_", "-") + "-container"


def _remove_container_if_exists(cname: str):
    try:
        _run_cli(["docker", "inspect", cname])
        _run_cli(["docker", "rm", "-f", cname])
    except HTTPException:
        pass


def _stream_process(cmd: List[str], cwd: Optional[Path] = None) -> Iterator[str]:
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    for line in proc.stdout:
        yield line
    proc.wait()
    yield "[build complete]"  # ensure consistent final message


def _dockerfile_for_arch(exp_dir: Path) -> Path:
    dockerfile_name = "Dockerfile.arm64" if os.uname().machine == "aarch64" else "Dockerfile"
    dockerfile_path = exp_dir / dockerfile_name
    if not dockerfile_path.exists():
        raise HTTPException(status_code=404, detail=f"{dockerfile_name} not found")
    return dockerfile_path


# --- Routes ---
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/logs", include_in_schema=False)
def logs_page():
    return FileResponse("static/logs.html")


@app.get("/experiments", summary="List all experiments with full configs")
def list_experiments():
    return {"experiments": [cfg.dict() for cfg in EXPERIMENTS]}


@app.post("/build", summary="Build Docker image (streaming logs)")
def build_image(req: NameRequest):
    cfg, exp_dir, _ = _exp_paths(req.experiment_name)
    dockerfile = _dockerfile_for_arch(exp_dir)
    tag = cfg.name.lower().replace("_", "-")
    return StreamingResponse(
        _stream_process(["docker", "build", "-t", tag, "-f", str(dockerfile), "."]),
        media_type="text/plain"
    )


@app.post("/run", summary="Run container for experiment")
def run_container(req: NameRequest):
    cfg, exp_dir, _ = _exp_paths(req.experiment_name)
    cname = _container_name(cfg.name)
    _remove_container_if_exists(cname)

    tag = cfg.name.lower().replace("_", "-")
    cmd = [
        "docker", "run",
        "--name", cname,
        "--detach",
        "--volume", f"{exp_dir}:/app",
        "--workdir", "/app",
        tag
    ]
    if cfg.entrypoint.strip():
        cmd += shlex.split(cfg.entrypoint)
    cid = _run_cli(cmd).strip()
    return {"container_id": cid}


@app.post("/remove", summary="Remove container for experiment")
def remove_container(req: NameRequest):
    cname = _container_name(req.experiment_name)
    _remove_container_if_exists(cname)
    return {"removed": cname}


@app.get("/artifacts/{experiment_name}", summary="Download experiment artifacts")
def download_artifacts(experiment_name: str):
    cfg, _, art_dir = _exp_paths(experiment_name)
    if not art_dir:
        raise HTTPException(
            status_code=404,
            detail=f"No artifacts_path configured for experiment '{experiment_name}'"
        )
    if not art_dir.exists() or not art_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Artifacts for experiment '{experiment_name}' not found"
        )

    zip_path = shutil.make_archive(str(art_dir), 'zip', root_dir=str(art_dir))
    return FileResponse(
        path=zip_path,
        filename=f"{cfg.name}-artifacts.zip",
        media_type="application/zip"
    )


@app.websocket("/ws/logs/container/{container_id}")
async def websocket_logs(ws: WebSocket, container_id: str):
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
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        await proc.wait()
        try:
            await ws.close()
        except RuntimeError:
            pass


# --- Main ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
