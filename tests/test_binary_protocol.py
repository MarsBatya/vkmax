import itertools
import time
import uuid

import msgpack
import pytest

from vkmax.packet_codec import BIGINT_EXT_TYPE, decode_packet
from vkmax.raw_client import RpcError
from vkmax.raw_client import MaxClient as RawClient

from test_packet_codec import frame_body


async def test_invoke_method_sends_binary_frames(make_client):
    client = await make_client(RawClient, responses=[{"payload": {"ok": True}}])

    await client.invoke_method(opcode=1, payload={"interactive": False})

    raw = client._connection.raw_sent[0]
    assert isinstance(raw, bytes)
    assert raw[0] == 10
    assert raw[1] == 0
    assert decode_packet(raw) == {
        "cmd": 0,
        "seq": 1,
        "opcode": 1,
        "payload": {"interactive": False},
    }


async def test_seq_wraps_at_int16_limit(make_client):
    client = await make_client(RawClient)
    client._seq = itertools.count(32767)

    await client.invoke_method(opcode=1, payload={})
    assert client._connection.sent[0]["seq"] == 32767

    await client.invoke_method(opcode=1, payload={})
    assert client._connection.sent[1]["seq"] == 1
    assert not client._pending


async def test_error_packet_raises_rpc_error(make_client):
    client = await make_client(
        RawClient,
        responses=[
            {"cmd": 3, "payload": {"error": "forbidden", "message": "no access"}}
        ],
    )

    with pytest.raises(RpcError, match="no access") as exc_info:
        await client.invoke_method(opcode=64, payload={})

    assert exc_info.value.payload["error"] == "forbidden"
    assert not client._pending


async def test_hello_payload_shape(make_client):
    client = await make_client(RawClient, responses=[{"opcode": 6, "payload": {}}])

    before = int(time.time() * 1000)
    await client._send_hello_packet()
    after = int(time.time() * 1000)

    packet = client._connection.sent[0]
    assert packet["opcode"] == 6
    payload = packet["payload"]
    assert payload["userAgent"] == client.user_agent
    uuid.UUID(payload["deviceId"])
    assert before <= payload["clientSessionId"] <= after

    raw = msgpack.unpackb(
        frame_body(client._connection.raw_sent[0]), raw=False, strict_map_key=False
    )
    ext = raw["clientSessionId"]
    assert isinstance(ext, msgpack.ExtType)
    assert ext.code == BIGINT_EXT_TYPE
    assert msgpack.unpackb(ext.data) == payload["clientSessionId"]
