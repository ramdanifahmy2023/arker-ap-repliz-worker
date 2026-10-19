from __future__ import annotations

import argparse
import asyncio
from getpass import getpass
import importlib.util
import json
from pathlib import Path
import shutil
import signal
import sys
import webbrowser

from arker import __version__
from arker.db import Store
from arker.paths import default_data_dir, frontend_directory


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="arker", description="Panel dan worker Arker. Data privat terpisah dari source.")
    result.add_argument("--version", action="version", version=__version__)
    result.add_argument("--data-dir", type=Path, default=default_data_dir())
    commands = result.add_subparsers(dest="action", required=True)
    commands.add_parser("init", help="Buat admin secara interaktif; password tidak masuk argumen shell.")
    for name in ("serve", "run", "start"):
        command = commands.add_parser(name, help={"serve": "Jalankan API saja.", "run": "Jalankan API dan worker di foreground.", "start": "Jalankan API dan worker di background."}[name])
        command.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
        command.add_argument("--port", type=int, default=8765)
    commands.add_parser("worker", help="Jalankan satu worker; lock mencegah proses kedua.")
    commands.add_parser("stop", help="Hentikan proses yang dimiliki supervisor Arker.")
    commands.add_parser("status", help="Periksa supervisor dan lock worker.")
    commands.add_parser("doctor", help="Periksa prasyarat lokal tanpa menghubungi provider.")
    commands.add_parser("open", help="Buka panel di browser; menutup browser tidak menghentikan worker.")
    commands.add_parser("desktop", help="Buka panel lokal dalam jendela desktop opsional.")
    commands.add_parser("backup", help="Backup konsisten DB dan jurnal, tanpa credential/media.")
    restore = commands.add_parser("restore", help="Pulihkan ke folder --data-dir baru dalam keadaan shadow dan paused.")
    restore.add_argument("source", type=Path)
    commands.add_parser("cleanup", help="Periksa kandidat cleanup. Penghapusan hanya melalui worker.")
    preview = commands.add_parser("preview", help="Render video buatan lokal; tanpa download, provider, atau publikasi.")
    preview.add_argument("--output", type=Path, required=True, help="Folder baru untuk bukti render.")
    service = commands.add_parser("service", help="Kelola autostart milik user saat login.")
    service.add_argument("operation", choices=("install", "start", "stop", "status", "uninstall"))
    service.add_argument("--port", type=int, default=8765)
    return result


def doctor(data_dir: Path) -> dict:
    from arker.locks import is_locked
    directory = data_dir.expanduser().resolve()
    return {"version": __version__, "platform": sys.platform, "python": sys.version.split()[0],
            "data_directory_exists": directory.is_dir(), "frontend_built": frontend_directory() is not None,
            "ffmpeg": bool(shutil.which("ffmpeg")), "ffprobe": bool(shutil.which("ffprobe")),
            "whisper_cli_optional": bool(shutil.which("whisper-cli")),
            "desktop_optional": importlib.util.find_spec("webview") is not None,
            "worker_running": is_locked(directory, "worker") if directory.exists() else False,
            "network_tested": False}


async def run_worker(store: Store):
    from arker.worker import Worker
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, lambda *_: loop.call_soon_threadsafe(stop.set))
    try:
        await Worker(store).run(stop_event=stop)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if hasattr(args, "port") and not 1024 <= args.port <= 65535:
        parser().error("Port harus 1024 sampai 65535.")
    data_dir = args.data_dir.expanduser().resolve()
    try:
        if args.action == "restore":
            from arker.backup import restore_backup
            result = restore_backup(args.source, data_dir)
        elif args.action == "doctor":
            result = doctor(data_dir)
        elif args.action == "preview":
            from arker.preview import render_preview
            result = asyncio.run(render_preview(args.output))
        elif args.action in ("status", "stop", "start", "run", "open", "desktop"):
            from arker.lifecycle import request_stop, start_detached, status, supervise
            if args.action == "run":
                return supervise(data_dir, args.host, args.port)
            if args.action == "start":
                result = start_detached(data_dir, args.host, args.port)
            elif args.action == "stop":
                result = request_stop(data_dir)
            elif args.action == "status":
                result = status(data_dir)
            else:
                state = status(data_dir)
                if not state["running"]:
                    raise ValueError("Jalankan arker start terlebih dahulu.")
                url = state.get("url", "http://127.0.0.1:8765")
                if args.action == "desktop":
                    try:
                        import webview
                    except ImportError as exc:
                        raise ValueError("Paket desktop belum dipasang. Pasang extra [desktop] atau gunakan arker open.") from exc
                    webview.create_window("Arker", url, width=1440, height=900, min_size=(400, 600))
                    webview.start(private_mode=True)
                else:
                    webbrowser.open(url)
                result = {"opened": True, "worker_independent_of_window": True}
        elif args.action == "service":
            from arker.service import service_action
            result = service_action(args.operation, data_dir, args.port)
        else:
            store = Store(data_dir)
            if args.action == "init":
                from arker.auth import bootstrap_admin
                with store.connect() as db:
                    if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                        raise ValueError("Admin sudah ada; bootstrap tidak menimpa akun.")
                email = input("Email admin: ").strip()
                password = getpass("Password baru (minimal 12 karakter): ")
                if password != getpass("Ulangi password: "):
                    raise ValueError("Password tidak cocok.")
                bootstrap_admin(store, email, password)
                result = {"initialized": True, "mode": "shadow", "publish_enabled": False}
            elif args.action == "serve":
                import uvicorn
                from arker.api import create_app
                from arker.locks import DataLock
                with DataLock(data_dir, "api"):
                    uvicorn.run(create_app(data_dir, web_dir=frontend_directory()), host=args.host, port=args.port, access_log=False, server_header=False, proxy_headers=False)
                return 0
            elif args.action == "worker":
                asyncio.run(run_worker(store))
                return 0
            elif args.action == "backup":
                from arker.backup import create_backup
                result = create_backup(store)
            elif args.action == "cleanup":
                from arker.cleanup import cleanup_plan
                result = cleanup_plan(store)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Arker: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
