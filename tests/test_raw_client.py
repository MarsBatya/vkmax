from copy import deepcopy

import pytest

from vkmax.client import MaxClient
from vkmax.raw_client import DEFAULT_USER_AGENT_DICT, MaxClient as RawClient


async def test_fake_websocket_round_trip(make_client):
    client = await make_client(RawClient, responses=[{"payload": {"ok": True}}])

    response = await client.invoke_method(opcode=1, payload={"interactive": False})

    assert response == {
        "ver": 10,
        "cmd": 1,
        "seq": 1,
        "opcode": 1,
        "payload": {"ok": True},
    }
    assert client._connection.sent[0]["payload"] == {"interactive": False}
    assert not client._pending


@pytest.mark.parametrize("client_class", [RawClient, MaxClient])
def test_default_user_agent_is_isolated(client_class, monkeypatch):
    monkeypatch.setitem(DEFAULT_USER_AGENT_DICT, "nested", {"values": ["original"]})
    original = deepcopy(DEFAULT_USER_AGENT_DICT)
    first = client_class()
    second = client_class()

    assert first.user_agent == original
    assert first.user_agent is not second.user_agent
    assert first.user_agent is not DEFAULT_USER_AGENT_DICT
    assert second.user_agent is not DEFAULT_USER_AGENT_DICT

    first.user_agent["deviceName"] = "Custom browser"
    first.user_agent["nested"]["values"].append("changed")

    assert second.user_agent == original
    assert DEFAULT_USER_AGENT_DICT == original


def test_explicit_user_agent_is_preserved():
    user_agent = {**DEFAULT_USER_AGENT_DICT, "deviceName": "Custom browser"}

    client = RawClient(user_agent_dict=user_agent)

    assert client.user_agent is user_agent
