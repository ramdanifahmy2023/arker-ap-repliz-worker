from __future__ import annotations

import json
from pathlib import Path
import time

from arker.backup import digest
from arker.config import bank_path
from arker.locks import DataLock


def cleanup_plan(store, *, at: float | None = None) -> dict:
    stamp = time.time() if at is None else at
    eligible, held = [], []
    cache = (store.data_dir / "work").resolve()
    with store.connect() as db:
        rows = db.execute("SELECT * FROM artifacts").fetchall()
        bank_roots = [bank_path(json.loads(row[0])["storage"]["bank_directory"], store.data_dir) for row in db.execute("SELECT config FROM configurations")]
        references = {}
        for row in rows:
            references.setdefault(str(Path(row["path"]).resolve()), set()).add(row["asset_id"])
        for item in rows:
            path = Path(item["path"])
            resolved = path.resolve()
            if not resolved.is_relative_to(cache):
                continue
            reason = None
            if any(part.is_symlink() or part.is_junction() for part in (path, *path.parents)) or any(resolved == bank or resolved.is_relative_to(bank) for bank in bank_roots):
                reason = "File atau lokasi bank dilindungi."
            elif len(references[str(resolved)]) != 1:
                reason = "File masih dirujuk aset lain."
            asset = db.execute("SELECT * FROM assets WHERE id=?", (item["asset_id"],)).fetchone()
            context = json.loads(asset["context"]) if asset else {}
            frames = db.execute("SELECT * FROM artifacts WHERE asset_id=? AND kind LIKE 'frame-%'", (item["asset_id"],)).fetchall()
            if not context or len(frames) != 6 or any(not Path(frame["path"]).is_file() for frame in frames):
                reason = "Konteks atau enam frame arsip belum lengkap."
            deliveries = db.execute("SELECT state,published_at FROM deliveries WHERE asset_id=?", (item["asset_id"],)).fetchall()
            if asset and asset["lease_until"] and asset["lease_until"] > stamp:
                reason = "Aset sedang dikerjakan."
            if len(deliveries) != 3 or any(row["state"] != "published" or not row["published_at"] for row in deliveries):
                reason = "Belum semua tujuan terverifikasi tayang."
            elif stamp - max(row["published_at"] for row in deliveries) < max(24, store.config_at(asset["config_version"])["cleanup"]["retention_hours"]) * 3600:
                reason = "Retensi sejak tujuan terakhir belum terpenuhi."
            evidence = db.execute("SELECT * FROM artifacts WHERE asset_id=? AND drive_id IS NOT NULL AND verified_at IS NOT NULL", (item["asset_id"],)).fetchall()
            bank_evidence = [e for e in evidence if any(Path(e["path"]).resolve().is_relative_to(bank) for bank in bank_roots)]
            if not bank_evidence:
                reason = "Bukti Bank/Drive belum lengkap."
            elif any(not Path(e["path"]).is_file() or not e["sha256"] or digest(Path(e["path"])) != e["sha256"] for e in bank_evidence):
                reason = "Isi bank tidak cocok dengan bukti checksum."
            if item["kind"] not in ("download", "source", "work"):
                reason = "Frame, transkrip, render dan konteks tetap disimpan."
            if not path.is_file():
                reason = "File kerja tidak tersedia."
            elif path.stat().st_nlink > 1:
                reason = "File memiliki referensi hard link lain."
            elif not item["sha256"] or digest(path) != item["sha256"]:
                reason = "Checksum file kerja tidak cocok."
            record = {"id": item["id"], "asset_id": item["asset_id"], "bytes": item["size"] or 0}
            if reason:
                held.append({**record, "reason": reason})
            else:
                eligible.append(record)
    return {"eligible": eligible, "held": held, "bytes": sum(row["bytes"] for row in eligible), "generated_at": stamp}


def apply_cleanup(store) -> dict:
    applied = store.get_meta("applied_version", 0)
    if not applied or not store.config_at(applied)["cleanup"]["enabled"]:
        raise ValueError("Cleanup belum diaktifkan.")
    deleted = []
    with DataLock(store.data_dir, "cleanup", blocking=True):
        plan = cleanup_plan(store)
        for candidate in plan["eligible"]:
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                latest = cleanup_plan(store)
                if not any(row["id"] == candidate["id"] for row in latest["eligible"]):
                    continue
                artifact = db.execute("SELECT path FROM artifacts WHERE id=?", (candidate["id"],)).fetchone()
                from arker.lifecycle import atomic_json
                payload = {"artifact_id": candidate["id"], "asset_id": candidate["asset_id"], "created_at": time.time()}
                atomic_json(store.data_dir / "cleanup-journals" / (candidate["id"] + ".json"), payload)
                Path(artifact["path"]).unlink(missing_ok=True)
                db.execute("INSERT INTO events(kind,entity_id,payload,created_at) VALUES (?,?,?,?)", ("cleanup.deleted", candidate["id"], json.dumps(payload), time.time()))
                deleted.append(candidate["id"])
    return {"deleted": deleted, "held": len(plan["held"])}
