from pathlib import Path
import socket
import tempfile
import unittest

import httpx

from arker.lifecycle import atomic_json, request_stop, start_detached, status


class LifecycleReadinessTests(unittest.TestCase):
    def test_occupied_port_never_reports_success_or_stale_url(self):
        with tempfile.TemporaryDirectory() as temporary, socket.socket() as occupied:
            root = Path(temporary).resolve()
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            atomic_json(root / "control/status.json", {"pid": 1, "api_pid": 2, "url": "http://localhost:1"})
            atomic_json(root / "control/api-ready.json", {"pid": 2, "port": 1})
            try:
                with self.assertRaisesRegex(RuntimeError, "gagal"):
                    start_detached(root, "127.0.0.1", port)
                self.assertFalse(status(root)["running"])
                self.assertFalse(status(root)["api_ready"])
            finally:
                request_stop(root)

    def test_success_means_own_api_is_bound_and_accepting_requests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            try:
                state = start_detached(root, "127.0.0.1", port)
                self.assertTrue(state["api_ready"])
                self.assertEqual(state["url"], f"http://127.0.0.1:{port}")
                with httpx.Client() as client:
                    result = client.get(state["url"] + "/api/auth/session")
                self.assertEqual(result.status_code, 200)
                self.assertTrue(result.json()["setup_required"])
            finally:
                self.assertTrue(request_stop(root)["stopped"])
