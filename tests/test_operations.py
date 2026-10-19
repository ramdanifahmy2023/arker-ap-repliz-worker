import asyncio
import json
import os
from pathlib import Path
import plistlib
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from arker.backup import create_backup, digest, restore_backup, verify_backup
from arker.cleanup import apply_cleanup, cleanup_plan
from arker.db import Store
from arker.ingest import intake
from arker.lifecycle import request_stop, start_detached, status, worker_action
from arker.locks import DataLock, LockBusy, is_locked
from arker.paths import default_data_dir
from arker.service import service_definition
from arker.worker import Worker


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="arker test ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.store = Store(self.root / "private")

    def test_lock_blocks_other_process_and_releases_after_crash(self):
        program = "from pathlib import Path; from arker.locks import DataLock; import sys,time; lock=DataLock(Path(sys.argv[1]),'worker'); lock.__enter__(); print('ready',flush=True); time.sleep(30)"
        child = subprocess.Popen([sys.executable, "-c", program, str(self.store.data_dir)], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "ready")
            self.assertTrue(is_locked(self.store.data_dir, "worker"))
            with self.assertRaises(LockBusy):
                with DataLock(self.store.data_dir, "worker"):
                    pass
        finally:
            child.kill()
            child.wait(timeout=5)
            child.stdout.close()
        self.assertFalse(is_locked(self.store.data_dir, "worker"))

    def test_backup_manifest_restore_preserves_journal_and_historical_config(self):
        original = self.store.config_at(1)
        worker = Worker(self.store)
        asyncio.run(worker.command("apply_configuration", {"version": 1}))
        attempt = worker.intent(None, "reply", "fixture-request", {"comment_id": "fixture-comment"})
        bundle = create_backup(self.store)
        source = self.store.data_dir / "backups" / bundle["id"]
        manifest = verify_backup(source)
        self.assertIn(f"journals/{attempt}-intent.json", {f["path"] for f in manifest["files"]})
        self.assertFalse(any("Credential" in f["path"] for f in manifest["files"]))
        target = self.root / "restored"
        result = restore_backup(source, target)
        restored = Store(target)
        self.assertTrue(result["requires_reconciliation"])
        self.assertTrue(restored.get_meta("processing_paused"))
        self.assertEqual(restored.config_at(1), original)
        self.assertFalse(restored.configuration()["config"]["application"]["publish_enabled"])
        self.assertNotEqual(restored.get_meta("instance_id"), self.store.get_meta("instance_id"))
        self.assertFalse((target / "Credential").exists())
        with self.assertRaises(ValueError):
            restore_backup(source, target)

    def test_backup_missing_journal_or_tampering_is_rejected(self):
        self.store.event("fixture")
        bundle = create_backup(self.store)
        folder = self.store.data_dir / "backups" / bundle["id"]
        with (folder / "arker.sqlite3").open("ab") as stream:
            stream.write(b"tampered")
        with self.assertRaisesRegex(ValueError, "Checksum"):
            verify_backup(folder)
        with self.store.connect() as db:
            db.execute("INSERT INTO attempts(id,operation,request_key,state,created_at,updated_at) VALUES ('missing','reply','missing','unknown',1,1)")
        with self.assertRaisesRegex(ValueError, "jurnal"):
            create_backup(self.store)

    def cleanup_fixture(self):
        accepted = intake(self.store, ["https://www.instagram.com/reel/CleanupFixture123/"])
        identifier = accepted["accepted"][0]["id"]
        work = self.store.data_dir / "work" / identifier
        bank = self.store.data_dir / "bank"
        work.mkdir(parents=True)
        bank.mkdir()
        worker = Worker(self.store)
        for kind in ("source", "render", *(f"frame-{i}" for i in range(1, 7))):
            path = work / (kind + ".fixture")
            path.write_bytes(kind.encode())
            worker.artifact(identifier, kind, path)
        archive = bank / "archive.fixture"
        archive.write_bytes(b"bank fixture")
        worker.artifact(identifier, "bank", archive, drive_id="fixture", verified_at=time.time())
        with self.store.connect() as db:
            db.execute("UPDATE assets SET context=? WHERE id=?", (json.dumps({"frames": 6, "transcript_status": "disabled"}), identifier))
            db.execute("UPDATE deliveries SET state='published',published_at=? WHERE asset_id=?", (time.time() - 25 * 3600, identifier))
        return identifier, work, archive

    def test_cleanup_retention_shared_reference_and_archive_protection(self):
        identifier, work, archive = self.cleanup_fixture()
        plan = cleanup_plan(self.store)
        self.assertEqual(len(plan["eligible"]), 1)
        self.assertEqual(len(plan["held"]), 7)
        with self.store.connect() as db:
            db.execute("UPDATE deliveries SET published_at=? WHERE asset_id=? AND platform='youtube'", (time.time(), identifier))
        self.assertEqual(cleanup_plan(self.store)["eligible"], [])
        with self.store.connect() as db:
            db.execute("UPDATE deliveries SET published_at=? WHERE asset_id=?", (time.time() - 25 * 3600, identifier))
        config = self.store.configuration()["config"]
        config["cleanup"]["enabled"] = True
        version = self.store.save_configuration(config, 1)
        with self.assertRaises(ValueError):
            apply_cleanup(self.store)
        self.store.set_meta("applied_version", version)
        result = apply_cleanup(self.store)
        self.assertEqual(len(result["deleted"]), 1)
        self.assertFalse((work / "source.fixture").exists())
        self.assertTrue((work / "render.fixture").exists())
        self.assertTrue(archive.exists())
        self.assertEqual(apply_cleanup(self.store)["deleted"], [])

    def test_cleanup_holds_bank_mismatch_missing_context_and_active_lease(self):
        identifier, work, archive = self.cleanup_fixture()
        archive.write_bytes(b"changed")
        self.assertEqual(cleanup_plan(self.store)["eligible"], [])
        archive.write_bytes(b"bank fixture")
        (work / "frame-6.fixture").unlink()
        self.assertEqual(cleanup_plan(self.store)["eligible"], [])
        (work / "frame-6.fixture").write_bytes(b"frame-6")
        with self.store.connect() as db:
            db.execute("UPDATE assets SET lease_until=? WHERE id=?", (time.time()+30, identifier))
        self.assertEqual(cleanup_plan(self.store)["eligible"], [])

    def test_service_definitions_preserve_spaces_and_platform_arguments(self):
        directory = Path("fixture folder") / "private data"
        executable = "fixture path/python"
        mac = plistlib.loads(service_definition("darwin", directory, executable))
        self.assertEqual(mac["ProgramArguments"][4], str(directory))
        self.assertEqual(mac["ProgramArguments"][0], executable)
        windows = service_definition("win32", directory, executable)
        self.assertIn('"fixture path/python"', windows)
        self.assertIn('"' + str(directory) + '"', windows)
        linux = service_definition("linux", Path("data%folder"), executable)
        self.assertIn("data%%folder", linux)
        self.assertIn("UMask=0077", linux)

    def test_supervisor_start_pause_and_stop_own_children(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        runtime = self.store.data_dir
        try:
            self.assertTrue(start_detached(runtime, "127.0.0.1", port)["running"])
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline and not status(runtime)["worker_running"]:
                time.sleep(.1)
            self.assertTrue(status(runtime)["worker_running"])
            command = self.store.command("pause_processing", {}, "fixture-pause")
            while time.monotonic() < deadline and not self.store.get_meta("processing_paused", False):
                time.sleep(.1)
            self.assertTrue(self.store.get_meta("processing_paused"))
            self.assertEqual(self.store.get_meta("applied_version"), 1)
            before = status(runtime)["worker_pid"]
            self.assertTrue(worker_action(runtime, "stop")["accepted"])
            while time.monotonic() < deadline and status(runtime)["worker_running"]:
                time.sleep(.1)
            self.assertTrue(status(runtime)["running"])
            self.assertFalse(status(runtime)["worker_running"])
            self.assertTrue(worker_action(runtime, "start")["accepted"])
            while time.monotonic() < deadline and not status(runtime)["worker_running"]:
                time.sleep(.1)
            self.assertTrue(status(runtime)["worker_running"])
            self.assertNotEqual(status(runtime)["worker_pid"], before)
        finally:
            self.assertTrue(request_stop(runtime)["stopped"])
        self.assertFalse(status(runtime)["worker_running"])


if __name__ == "__main__":
    unittest.main()
