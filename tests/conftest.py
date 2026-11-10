import asyncio
import json
import socket
from collections.abc import Iterable
from typing import Any

import pytest
from websockets.exceptions import ConnectionClosedOK

from vkmax.client import MaxClient


class FakeWebSocket:
    def __init__(
        self,
        responses: Iterable[dict[str, Any]] = (),
        auto_reply: bool = True,
    ):
        self.sent: list[dict[str, Any]] = []
        self.closed = False
        self._responses = iter(responses)
        self._auto_reply = auto_reply
        self._incoming: asyncio.Queue[str | Exception] = asyncio.Queue()

    async def send(self, data: str) -> None:
        request = json.loads(data)
        self.sent.append(request)
        if not self._auto_reply:
            return
        response = next(self._responses, {"payload": {}})
        self.push_packet({"seq": request["seq"], **response})

    async def recv(self) -> str:
        item = await self._incoming.get()
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self) -> None:
        self.closed = True

    def push_packet(self, packet: dict[str, Any]) -> None:
        self._incoming.put_nowait(json.dumps(packet))

    def push_raw(self, raw: str) -> None:
        self._incoming.put_nowait(raw)

    def close_from_server(self, error: Exception | None = None) -> None:
        self.closed = True
        self._incoming.put_nowait(error or ConnectionClosedOK(None, None))


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is disabled in unit tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
async def make_client():
    clients = []

    async def create(
        cls=MaxClient,
        responses: Iterable[dict[str, Any]] = (),
        auto_reply: bool = True,
    ):
        client = cls()
        client._connection = FakeWebSocket(responses, auto_reply=auto_reply)
        client._recv_task = asyncio.create_task(client._recv_loop())
        clients.append(client)
        return client

    yield create

    for client in clients:
        if client._recv_task is not None:
            client._recv_task.cancel()
            await asyncio.gather(client._recv_task, return_exceptions=True)
