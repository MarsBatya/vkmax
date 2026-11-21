import asyncio
import logging

import pytest
from websockets.exceptions import ConnectionClosedError

from vkmax.raw_client import MaxClient as RawClient

from conftest import FakeWebSocket


class DroppingWebSocket(FakeWebSocket):
    def __init__(self):
        super().__init__()
        self.send_attempts = 0

    async def send(self, data: bytes) -> None:
        self.send_attempts += 1
        raise ConnectionClosedError(None, None)


class RaisingSendWebSocket(FakeWebSocket):
    async def send(self, data: bytes) -> None:
        raise OSError("send failed")


async def wait_until(predicate):
    async def poll():
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(poll(), timeout=1)


async def test_invoke_method_times_out(make_client):
    client = await make_client(RawClient, auto_reply=False)
    client.request_timeout = 0.05

    start = asyncio.get_running_loop().time()
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(client.invoke_method(opcode=1, payload={}), timeout=1)

    assert asyncio.get_running_loop().time() - start < 0.5
    assert not client._pending


async def test_invoke_method_returns_retried_response(make_client):
    client = await make_client(RawClient)
    dropped = DroppingWebSocket()
    client._connection = dropped
    reconnected = FakeWebSocket([{"payload": {"ok": True}}])

    async def reconnect():
        await client.disconnect()
        client._connection = reconnected
        client._recv_task = asyncio.create_task(client._recv_loop())

    client.set_reconnect_callback(reconnect)

    response = await asyncio.wait_for(
        client.invoke_method(opcode=1, payload={"x": 1}),
        timeout=1,
    )

    assert response == {
        "ver": 10,
        "cmd": 1,
        "seq": 1,
        "opcode": 1,
        "payload": {"ok": True},
    }
    assert dropped.send_attempts == 1
    assert reconnected.sent[0]["payload"] == {"x": 1}
    assert not client._pending


async def test_invoke_method_retry_is_bounded(make_client):
    client = await make_client(RawClient)
    dropped = DroppingWebSocket()
    client._connection = dropped

    async def reconnect():
        pass

    client.set_reconnect_callback(reconnect)

    response = await asyncio.wait_for(
        client.invoke_method(opcode=1, payload={}),
        timeout=1,
    )

    assert response is None
    assert dropped.send_attempts == 3
    assert not client._pending


async def test_invoke_method_drop_without_callback_returns_none(make_client):
    client = await make_client(RawClient)
    client._connection = DroppingWebSocket()

    assert await client.invoke_method(opcode=1, payload={}) is None
    assert not client._pending


async def test_invoke_method_send_error_cleans_pending(make_client):
    client = await make_client(RawClient)
    client._connection = RaisingSendWebSocket()

    with pytest.raises(OSError, match="send failed"):
        await client.invoke_method(opcode=1, payload={})

    assert not client._pending


async def test_invoke_method_serialization_error_cleans_pending(make_client):
    client = await make_client(RawClient)

    with pytest.raises(TypeError):
        await client.invoke_method(opcode=1, payload={"bad": ...})

    assert not client._pending


async def test_disconnect_fails_pending_futures(make_client):
    client = await make_client(RawClient, auto_reply=False)
    task = asyncio.create_task(client.invoke_method(opcode=1, payload={}))
    await wait_until(lambda: client._pending)

    await client.disconnect()

    with pytest.raises(ConnectionError):
        await asyncio.wait_for(task, timeout=1)
    assert not client._pending


async def test_recv_loop_death_fails_pending_futures(make_client):
    client = await make_client(RawClient, auto_reply=False)
    task = asyncio.create_task(client.invoke_method(opcode=1, payload={}))
    await wait_until(lambda: client._pending)

    client._connection.close_from_server()

    with pytest.raises(ConnectionError):
        await asyncio.wait_for(task, timeout=1)
    assert not client._pending


@pytest.mark.parametrize(
    "pending_attr", ["_pending", "_video_pending", "_file_pending"]
)
async def test_disconnect_fails_all_pending_futures(make_client, pending_attr):
    client = await make_client(RawClient, auto_reply=False)
    future = asyncio.get_running_loop().create_future()
    getattr(client, pending_attr)[7] = future

    await client.disconnect()

    assert not getattr(client, pending_attr)
    with pytest.raises(ConnectionError):
        future.result()


async def test_recv_loop_survives_malformed_packets(make_client):
    client = await make_client(RawClient, responses=[{"payload": {"ok": True}}])
    received = []

    async def callback(client, packet):
        received.append(packet)

    client.set_packet_callback(callback)
    fake = client._connection
    fake.push_raw(b"\x0a")
    fake.push_raw(b"\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x01\xc1")
    fake.push_raw("text frame")
    fake.push_packet({"opcode": 128, "payload": {"text": "hi"}})

    await wait_until(lambda: received)

    response = await asyncio.wait_for(
        client.invoke_method(opcode=1, payload={}),
        timeout=1,
    )

    assert response == {
        "ver": 10,
        "cmd": 1,
        "seq": 1,
        "opcode": 1,
        "payload": {"ok": True},
    }
    assert received == [
        {"ver": 10, "cmd": 0, "seq": 0, "opcode": 128, "payload": {"text": "hi"}}
    ]


async def test_recv_loop_survives_malformed_opcode_136_payload(make_client):
    client = await make_client(RawClient, responses=[{"payload": {"ok": True}}])
    received = []

    async def callback(client, packet):
        received.append(packet)

    client.set_packet_callback(callback)
    client._connection.push_packet({"opcode": 136, "payload": None})

    await wait_until(lambda: received)

    response = await asyncio.wait_for(
        client.invoke_method(opcode=1, payload={}),
        timeout=1,
    )

    assert response["payload"] == {"ok": True}
    assert received == [{"ver": 10, "cmd": 0, "seq": 0, "opcode": 136, "payload": None}]


async def test_done_future_in_pending_does_not_kill_loop(make_client):
    client = await make_client(RawClient, responses=[{"payload": {"ok": True}}])
    future = asyncio.get_running_loop().create_future()
    client._pending[42] = future
    future.cancel()

    client._connection.push_packet({"seq": 42, "payload": {}})
    await wait_until(lambda: 42 not in client._pending)

    response = await asyncio.wait_for(
        client.invoke_method(opcode=1, payload={}),
        timeout=1,
    )
    assert response["payload"] == {"ok": True}


async def test_raising_callback_is_logged_and_loop_survives(make_client, caplog):
    client = await make_client(RawClient, responses=[{"payload": {"ok": True}}])

    async def callback(client, packet):
        raise ValueError("boom")

    client.set_packet_callback(callback)
    with caplog.at_level(logging.ERROR, logger="vkmax.raw_client"):
        client._connection.push_packet({"opcode": 128, "payload": {}})
        await wait_until(lambda: caplog.records)

    assert any(r.exc_info for r in caplog.records)
    response = await asyncio.wait_for(
        client.invoke_method(opcode=1, payload={}),
        timeout=1,
    )
    assert response["payload"] == {"ok": True}
    assert not client._callback_tasks


async def test_disconnect_is_idempotent(make_client):
    client = await make_client(RawClient)

    await client.disconnect()
    await client.disconnect()

    assert client._connection is None
    assert client._recv_task is None


async def test_disconnect_without_connection_is_noop():
    client = RawClient()

    await client.disconnect()

    assert client._connection is None


async def test_disconnect_resets_session_state(make_client):
    client = await make_client(RawClient)
    client._is_logged_in = True
    await client.invoke_method(opcode=1, payload={})
    keepalive = asyncio.create_task(asyncio.sleep(3600))
    client._keepalive_task = keepalive

    await client.disconnect()

    assert client._is_logged_in is False
    assert next(client._seq) == 1
    assert client._keepalive_task is None
    assert keepalive.done()


async def test_disconnect_stops_keepalive(make_client):
    client = await make_client(RawClient)
    await client._start_keepalive_task()
    task = client._keepalive_task
    await wait_until(lambda: client._connection.sent)

    await client.disconnect()

    assert task.done()
    assert client._keepalive_task is None


async def test_keepalive_survives_rpc_timeout(make_client):
    client = await make_client(RawClient, auto_reply=False)
    client.request_timeout = 0.05
    await client._start_keepalive_task()
    task = client._keepalive_task
    await wait_until(lambda: client._connection.sent)
    await asyncio.sleep(0.1)

    assert not task.done()

    await client.disconnect()


async def test_start_keepalive_is_idempotent(make_client):
    client = await make_client(RawClient)
    await client._start_keepalive_task()
    task = client._keepalive_task

    await client._start_keepalive_task()

    assert client._keepalive_task is task

    await client.disconnect()


async def test_reconnect_after_disconnect(make_client, monkeypatch):
    client = await make_client(RawClient)
    await client.disconnect()
    fake = FakeWebSocket([{"payload": {"ok": True}}])

    async def fake_connect(*args, **kwargs):
        return fake

    monkeypatch.setattr("vkmax.raw_client.websockets.connect", fake_connect)

    await client.connect()
    response = await asyncio.wait_for(
        client.invoke_method(opcode=1, payload={}),
        timeout=1,
    )

    assert response == {
        "ver": 10,
        "cmd": 1,
        "seq": 1,
        "opcode": 1,
        "payload": {"ok": True},
    }


async def test_reconnect_serializes_concurrent_callers(make_client):
    client = await make_client(RawClient)
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def reconnect():
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        client._reconnect_generation += 1  # simulates a successful connect()

    client.set_reconnect_callback(reconnect)
    first = asyncio.create_task(client.reconnect())
    await asyncio.wait_for(started.wait(), timeout=1)
    second = asyncio.create_task(client.reconnect())
    await asyncio.sleep(0)
    release.set()
    await asyncio.wait_for(asyncio.gather(first, second), timeout=1)

    assert calls == 1


async def test_reconnect_retries_after_failed_attempt(make_client):
    client = await make_client(RawClient)
    calls = 0

    async def reconnect():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("proxy down")

    client.set_reconnect_callback(reconnect)
    with pytest.raises(ConnectionError):
        await client.reconnect()
    await client.reconnect()

    assert calls == 2


async def test_reconnect_without_callback_is_noop(make_client):
    client = await make_client(RawClient)

    await client.reconnect()


async def test_recv_loop_reconnects_on_clean_close(make_client):
    client = await make_client(RawClient)
    client._is_logged_in = True
    called = asyncio.Event()

    async def reconnect():
        called.set()

    client.set_reconnect_callback(reconnect)
    client._connection.close_from_server()

    await asyncio.wait_for(called.wait(), timeout=1)


async def test_recv_loop_clean_close_without_login_stays_closed(make_client):
    client = await make_client(RawClient)
    called = asyncio.Event()

    async def reconnect():
        called.set()

    client.set_reconnect_callback(reconnect)
    client._connection.close_from_server()
    await asyncio.wait_for(client._recv_task, timeout=1)
    await asyncio.sleep(0)

    assert not called.is_set()
