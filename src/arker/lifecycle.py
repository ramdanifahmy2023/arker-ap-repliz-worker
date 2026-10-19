from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from arker.locks import DataLock, is_locked

_detached_processes: dict[str, subprocess.Popen] = {}


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            temporary.chmod(0o600)
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def status(data_dir: Path) -> dict:
    running = is_locked(data_dir, "supervisor")
    path = data_dir / "control/status.json"
    value = {}
    if path.exists():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    worker_running = is_locked(data_dir, "worker")
    return {**value, "running": running, "worker_running": worker_running,
            "worker_state": value.get("worker_state", "running") if worker_running else "stopped"}


def request_stop(data_dir: Path, *, timeout: float = 20) -> dict:
    if not is_locked(data_dir, "supervisor"):
        return {"stopped": True, "note": "Supervisor tidak berjalan."}
    atomic_json(data_dir / "control/stop.json", {"requested_at": time.time()})
    deadline = time.monotonic() + timeout
    while is_locked(data_dir, "supervisor") and time.monotonic() < deadline:
        time.sleep(.1)
    stopped = not is_locked(data_dir, "supervisor")
    if stopped and (process := _detached_processes.pop(str(data_dir), None)):
        process.wait(timeout=5)
    return {"stopped": stopped, "note": "Berhenti." if stopped else "Masih menyelesaikan operasi; periksa status."}


def command(data_dir: Path, action: str, *args) -> list[str]:
    return [sys.executable, "-m", "arker", "--data-dir", str(data_dir), action, *args]


def start_detached(data_dir: Path, host: str, port: int) -> dict:
    if is_locked(data_dir, "supervisor"):
        return status(data_dir)
    folder = data_dir / "logs"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS} if os.name == "nt" else {"start_new_session": True}
    with (folder / "supervisor.log").open("ab") as log:
        child = subprocess.Popen(command(data_dir, "run", "--host", host, "--port", str(port)), stdin=subprocess.DEVNULL, stdout=log, stderr=log, **options)
        _detached_processes[str(data_dir)] = child
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if is_locked(data_dir, "supervisor"):
            return status(data_dir)
        if child.poll() is not None:
            _detached_processes.pop(str(data_dir), None)
            raise RuntimeError("Supervisor gagal dimulai; periksa log lokal.")
        time.sleep(.1)
    raise RuntimeError("Supervisor belum siap; periksa log lokal.")


def worker_action(data_dir: Path, action: str) -> dict:
    if action not in {"start", "stop", "restart"}:
        raise ValueError("Tindakan worker tidak dikenali.")
    if not is_locked(data_dir, "supervisor"):
        raise ValueError("Supervisor belum berjalan. Jalankan arker start di mesin worker.")
    identifier = uuid.uuid4().hex
    atomic_json(data_dir / "control/requests" / (identifier + ".json"), {"id": identifier, "action": action, "created_at": time.time()})
    return {"accepted": True, "id": identifier, "action": action, "note": "Permintaan diterima supervisor; periksa status worker."}


def supervise(data_dir: Path, host: str, port: int) -> int:
    from arker.db import Store
    with DataLock(data_dir, "supervisor"):
        store = Store(data_dir)
        stop_path = data_dir / "control/stop.json"
        requests = data_dir / "control/requests"
        requests.mkdir(parents=True, exist_ok=True, mode=0o700)
        stop_path.unlink(missing_ok=True)
        stop = False
        def signal_stop(signum, frame):
            nonlocal stop
            stop = True
        previous = {sig: signal.signal(sig, signal_stop) for sig in (signal.SIGINT, signal.SIGTERM)}
        logs = []
        folder = data_dir / "logs"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        api, worker = None, None
        outcome = 0
        desired, stopping_worker = True, False
        started = time.time()
        def spawn(name, *arguments):
            path = folder / (name + ".log")
            stream = path.open("ab")
            path.chmod(0o600)
            logs.append(stream)
            return subprocess.Popen(command(data_dir, arguments[0], *arguments[1:]), stdin=subprocess.DEVNULL, stdout=stream, stderr=stream)
        def stop_worker():
            nonlocal stopping_worker
            if worker and worker.poll() is None and not stopping_worker:
                store.command("stop_worker", {}, "supervisor-stop-" + uuid.uuid4().hex)
                stopping_worker = True
        try:
            api = spawn("api", "serve", "--host", host, "--port", str(port))
            while not stop and not stop_path.exists():
                if api.poll() is not None:
                    outcome = 1
                    break
                for request in sorted(requests.glob("*.json"), key=lambda p: p.stat().st_mtime_ns):
                    try:
                        action = json.loads(request.read_text(encoding="utf-8"))["action"]
                        if action in ("stop", "restart"):
                            desired = action == "restart"
                            stop_worker()
                        elif action == "start":
                            desired = True
                    finally:
                        request.unlink(missing_ok=True)
                if worker and worker.poll() is not None:
                    if not stopping_worker:
                        desired = False
                        if worker.returncode:
                            store.event("supervisor.worker_exited", payload={"exit_code": worker.returncode})
                    worker = None
                    stopping_worker = False
                if desired and worker is None:
                    worker = spawn("worker", "worker")
                atomic_json(data_dir / "control/status.json", {"pid": os.getpid(), "started_at": started,
                    "url": f"http://{host}:{port}", "api_pid": api.pid, "worker_pid": worker.pid if worker else None,
                    "worker_desired": desired, "worker_state": "stopping" if stopping_worker else "running" if worker else "stopped"})
                time.sleep(.2)
        finally:
            children = [child for child in (worker, api) if child]
            for child in children:
                if child.poll() is None:
                    child.terminate()
            for child in children:
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
            for stream in logs:
                stream.close()
            stop_path.unlink(missing_ok=True)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        return outcome
