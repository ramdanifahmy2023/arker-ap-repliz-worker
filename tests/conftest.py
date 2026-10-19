import socket

import pytest


@pytest.fixture(autouse=True)
def prevent_provider_network(monkeypatch):
    original = socket.socket.connect
    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError("Tests must use injected transports; provider networking is disabled.")
        return original(sock, address)
    monkeypatch.setattr(socket.socket, "connect", connect)
