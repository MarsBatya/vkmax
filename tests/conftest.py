import asyncio
import json
import socket
from collections.abc import Iterable
from typing import Any

import pytest

from vkmax.client import MaxClient


class FakeWebSocket:
    def __init__(self, responses: Iterable[dict[str, Any]] = ()):
        self.sent: list[dict[str, Any]] = []
        self._responses = iter(responses)
        self._incoming: asyncio.Queue[str] = asyncio.Queue()

    async def send(self, data: str) -> None:
        request = json.loads(data)
        self.sent.append(request)
        response = next(self._responses, {"payload": {}})
        self._incoming.put_nowait(
            json.dumps({"seq": request["seq"], **response}),
        )

    async def recv(self) -> str:
        return await self._incoming.get()


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is disabled in unit tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
async def make_client():
    clients = []

    async def create(cls=MaxClient, responses: Iterable[dict[str, Any]] = ()):
        client = cls()
        client._connection = FakeWebSocket(responses)
        client._recv_task = asyncio.create_task(client._recv_loop())
        clients.append(client)
        return client

    yield create

    for client in clients:
        client._recv_task.cancel()
        await asyncio.gather(client._recv_task, return_exceptions=True)
