from __future__ import annotations

import hashlib
from contextlib import closing
import json
import re
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import time
import uuid

from arker.locks import DataLock


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def create_backup(store) -> dict:
    identifier = "bundle-" + uuid.uuid4().hex
    folder = store.data_dir / "backups" / identifier
    folder.mkdir(parents=True, mode=0o700)
    with DataLock(store.data_dir, "journal-snapshot", blocking=True):
        with store.connect() as source, closing(sqlite3.connect(folder / "arker.sqlite3")) as destination:
            source.backup(destination)
        journals = store.data_dir / "journals"
        if journals.exists():
            for path in sorted(journals.rglob("*.json")):
                if path.is_symlink():
                    raise ValueError("Jurnal symlink tidak boleh masuk backup.")
                target = folder / path.relative_to(store.data_dir)
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copyfile(path, target)
    files = []
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            path.chmod(0o600)
            files.append({"path": path.relative_to(folder).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)})
    manifest = {"schema": 1, "id": identifier, "created_at": time.time(), "credentials_included": False, "media_included": False, "files": files}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (folder / "manifest.json").chmod(0o600)
    verify_backup(folder)
    store.event("backup.created", identifier, {"files": len(files), "credentials_included": False})
    return {"id": identifier, "created_at": manifest["created_at"], "files": len(files), "verified": True, "media_included": False, "credentials_included": False}


def verify_backup(folder: Path) -> dict:
    folder = Path(folder).resolve()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != 1 or manifest.get("credentials_included") is not False or not isinstance(manifest.get("files"), list) or not 1 <= len(manifest["files"]) <= 100000:
        raise ValueError("Manifest backup tidak didukung.")
    seen = set()
    for item in manifest["files"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"] or type(item.get("bytes")) is not int or item["bytes"] < 0 or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            raise ValueError("Entri manifest backup tidak valid.")
        relative = PurePosixPath(item["path"])
        if not relative.parts or relative.is_absolute() or ".." in relative.parts or "\\" in item["path"] or ":" in item["path"] or item["path"] in seen:
            raise ValueError("Path manifest backup tidak aman.")
        if item["path"] != "arker.sqlite3" and not (relative.parts[0] == "journals" and relative.suffix == ".json"):
            raise ValueError("Isi backup tidak diizinkan.")
        seen.add(item["path"])
        path = folder / relative
        if any(part.is_symlink() or part.is_junction() for part in (path, *path.parents)) or not path.resolve().is_relative_to(folder) or not path.is_file():
            raise ValueError("File backup hilang atau bukan file lokal biasa.")
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise ValueError("Checksum backup tidak cocok.")
    if "arker.sqlite3" not in seen:
        raise ValueError("Database tidak ada dalam backup.")
    with closing(sqlite3.connect((folder / "arker.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database backup tidak utuh.")
        for identifier, request_key in db.execute("SELECT id,request_key FROM attempts"):
            name = f"journals/{identifier}-intent.json"
            if name not in seen:
                raise ValueError("Backup kehilangan jurnal intent pengiriman.")
            intent = json.loads((folder / name).read_text(encoding="utf-8"))
            if intent.get("id") != identifier or intent.get("request_key") != request_key:
                raise ValueError("Identitas jurnal intent tidak cocok dengan database.")
    return manifest


def list_backups(store) -> list[dict]:
    items = []
    root = store.data_dir / "backups"
    if root.exists():
        for path in sorted(root.glob("bundle-*/manifest.json"), reverse=True):
            try:
                value = verify_backup(path.parent)
                items.append({"id": value["id"], "created_at": value["created_at"], "files": len(value["files"]), "size": sum(item["bytes"] for item in value["files"]), "verified": True, "credentials_included": False, "media_included": False})
            except (OSError, ValueError, KeyError):
                items.append({"id": path.parent.name, "verified": False, "status": "failed", "error": "Backup tidak lolos pemeriksaan manifest, jurnal, atau checksum."})
    return items


def restore_backup(source: Path, target: Path) -> dict:
    manifest = verify_backup(source)
    target = Path(target).expanduser()
    if target.exists() or target.is_symlink() or any(parent.is_symlink() for parent in target.absolute().parents):
        raise ValueError("Restore memerlukan folder tujuan baru.")
    target.mkdir(parents=True, mode=0o700)
    for item in manifest["files"]:
        destination = target / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(Path(source) / item["path"], destination)
        destination.chmod(0o600)
    from arker.db import Store
    store = Store(target)
    with store.connect() as db:
        db.execute("DELETE FROM sessions")
        db.execute("UPDATE accounts SET enabled=0,ownership_instance=NULL,snapshot_at=NULL")
        db.execute("UPDATE commands SET status='rejected',result=? WHERE status IN ('pending','running','accepted')", (json.dumps({"reason": "Restore memerlukan pemeriksaan ulang."}),))
    previous = store.configuration()
    config = previous["config"]
    config["application"].update(mode="shadow", publish_enabled=False)
    for section in ("reply", "reports", "cleanup", "telegram"):
        config.get(section, {})["enabled"] = False
    config.get("ownership", {}).update(acknowledged=False, account_ids=[])
    config["storage"]["bank_directory"] = str(target.resolve() / "bank")
    config["drive"]["folder_url"] = ""
    for provider in config.get("credentials", {}):
        config["credentials"][provider] = 0
    store.save_configuration(config, previous["desired_version"], "restore")
    for key, value in {"applied_version": 0, "processing_paused": True, "reply_paused": True, "reports_paused": True, "restore_requires_reconciliation": True, "worker_heartbeat": None, "worker_state": "stopped", "accounts_snapshot_at": None, "instance_id": uuid.uuid4().hex}.items():
        store.set_meta(key, value)
    store.event("backup.restored", manifest["id"], {"mode": "shadow", "requires_reconciliation": True})
    return {"restored": True, "mode": "shadow", "requires_reconciliation": True, "credentials_restored": False, "media_restored": False}
