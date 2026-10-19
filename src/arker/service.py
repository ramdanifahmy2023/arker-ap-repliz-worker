from __future__ import annotations

import os
from pathlib import Path
import plistlib
import subprocess
import sys

LABEL = "io.arker.control"


def service_definition(platform: str, data_dir: Path, python: str, port: int = 8765) -> str | bytes:
    args = [python, "-m", "arker", "--data-dir", str(data_dir), "run", "--port", str(port)]
    if platform == "darwin":
        return plistlib.dumps({"Label": LABEL, "ProgramArguments": args, "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False}, "ProcessType": "Background",
            "StandardOutPath": str(data_dir / "logs/launchd.log"), "StandardErrorPath": str(data_dir / "logs/launchd-error.log")})
    if platform == "win32":
        return subprocess.list2cmdline(args)
    def quote(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'
    return "\n".join(["[Unit]", "Description=Arker control API and worker", "After=network-online.target", "", "[Service]",
        "Type=simple", "ExecStart=" + " ".join(quote(v) for v in args), "Restart=on-failure", "RestartSec=5", "TimeoutStopSec=35", "UMask=0077", "",
        "[Install]", "WantedBy=default.target", ""])


def definition_path(platform: str | None = None) -> Path:
    platform = platform or sys.platform
    if platform == "darwin":
        return Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "systemd/user/arker.service"


def service_action(action: str, data_dir: Path, port: int = 8765) -> dict:
    platform = sys.platform
    (data_dir / "logs").mkdir(parents=True, exist_ok=True, mode=0o700)
    if action == "install":
        definition = service_definition(platform, data_dir, sys.executable, port)
        if platform == "win32":
            result = subprocess.run(["schtasks", "/Create", "/TN", "Arker", "/SC", "ONLOGON", "/TR", definition, "/F"], capture_output=True)
            if result.returncode:
                raise RuntimeError("Task Scheduler menolak pemasangan Arker; periksa izin pengguna.")
            return {"installed": True, "mechanism": "Windows Task Scheduler", "note": "Berjalan saat login; mulai sekarang dengan service start."}
        path = definition_path(platform)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(definition if isinstance(definition, bytes) else definition.encode())
        path.chmod(0o600)
        if platform != "darwin":
            _run(["systemctl", "--user", "daemon-reload"])
            _run(["systemctl", "--user", "enable", "arker.service"])
        return {"installed": True, "path": str(path), "note": "Definisi dipasang; jalankan service start untuk mengaktifkan."}
    if platform == "win32":
        verbs = {"start": "/Run", "stop": "/End", "status": "/Query", "uninstall": "/Delete"}
        args = ["schtasks", verbs[action], "/TN", "Arker"] + (["/F"] if action == "uninstall" else [])
    elif platform == "darwin":
        domain = f"gui/{os.getuid()}"
        args = {"start": ["launchctl", "bootstrap", domain, str(definition_path())],
                "stop": ["launchctl", "bootout", f"{domain}/{LABEL}"],
                "status": ["launchctl", "print", f"{domain}/{LABEL}"],
                "uninstall": ["launchctl", "bootout", f"{domain}/{LABEL}"]}[action]
    else:
        args = ["systemctl", "--user", {"uninstall": "disable"}.get(action, action), "arker.service"]
        if action == "uninstall":
            args.insert(4, "--now")
    _run(args)
    if action == "uninstall" and platform != "win32":
        definition_path().unlink(missing_ok=True)
    return {"action": action, "completed": True}


def _run(args):
    result = subprocess.run(args, capture_output=True)
    if result.returncode:
        raise RuntimeError("Service manager menolak operasi; periksa status layanan Arker dan izin pengguna.")
