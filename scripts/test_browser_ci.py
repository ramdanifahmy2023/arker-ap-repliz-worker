"""Create disposable browser runtimes; never accept production credentials or data."""
from pathlib import Path
import json
import secrets
import socket
import subprocess
import sys
import time
import uuid

import httpx

from arker.auth import bootstrap_admin
from arker.db import Store
from arker.lifecycle import request_stop, start_detached

ROOT = Path(__file__).resolve().parents[1]


def fixture(name):
    directory = ROOT / ".artifacts" / (name + "-" + uuid.uuid4().hex)
    store = Store(directory)
    login = {"email": "browser@example.test", "password": secrets.token_urlsafe(24)}
    bootstrap_admin(store, **login)
    file = directory / "fixture-login.json"
    file.write_text(json.dumps(login), encoding="utf-8")
    file.chmod(0o600)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    return directory, file, port


def ready(port):
    url = f"http://127.0.0.1:{port}"
    with httpx.Client(timeout=1) as client:
        for _ in range(100):
            try:
                if client.get(url + "/api/auth/session").status_code == 200:
                    return url
            except httpx.HTTPError:
                pass
            time.sleep(.1)
    raise RuntimeError("Browser fixture API did not become ready.")


def main():
    directory, login, port = fixture("browser-ci")
    child = subprocess.Popen([sys.executable, "-m", "arker", "--data-dir", str(directory), "serve", "--port", str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = ready(port)
        previews = sorted((ROOT / ".artifacts").glob("media-*/preview.mp4"))
        if not previews:
            raise RuntimeError("Run scripts/verify.py --media before browser checks.")
        subprocess.run([sys.executable, "scripts/test_browser.py", "--base-url", url, "--credentials", str(login), "--output", ".artifacts/browser-ci-review", "--seed-data-dir", str(directory), "--preview-video", str(previews[-1])], cwd=ROOT, check=True)
    finally:
        child.terminate()
        child.wait(timeout=15)
        login.unlink(missing_ok=True)
    directory, login, port = fixture("browser-ci-lifecycle")
    try:
        start_detached(directory, "127.0.0.1", port)
        url = ready(port)
        subprocess.run([sys.executable, "scripts/test_browser.py", "--base-url", url, "--credentials", str(login), "--output", ".artifacts/browser-ci-review", "--lifecycle-only"], cwd=ROOT, check=True)
    finally:
        request_stop(directory)
        login.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
