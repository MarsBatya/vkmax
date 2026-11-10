from typing import cast

from vkmax.client import MaxClient
from vkmax.routing import Router
from vkmax.types.packets import Packet, Payload


def make_packet(opcode: int = 128) -> Packet:
    return Packet(ver=11, cmd=0, seq=1, opcode=opcode, payload=cast(Payload, object()))


async def test_process_update_returns_false_when_router_condition_fails():
    client = MaxClient()
    router = Router(condition=lambda _client, _packet: False)
    called = []

    @router.handler()
    async def handler(_client, payload):
        called.append(payload)

    assert await router.process_update(client, make_packet()) is False
    assert called == []


async def test_process_update_returns_false_when_no_handler_matches():
    client = MaxClient()
    router = Router()
    called = []

    @router.handler(lambda _client, packet: packet.opcode == 1)
    async def handler(_client, payload):
        called.append(payload)

    assert await router.process_update(client, make_packet(opcode=128)) is False
    assert called == []


async def test_process_update_returns_false_without_handlers():
    assert await Router().process_update(MaxClient(), make_packet()) is False


async def test_process_update_runs_first_matching_handler_and_returns_true():
    client = MaxClient()
    router = Router()
    called = []

    @router.handler(lambda _client, packet: packet.opcode == 1)
    async def skipped(_client, payload):
        called.append("skipped")

    @router.handler(lambda _client, packet: packet.opcode == 128)
    async def matched(_client, payload):
        called.append(payload)

    @router.handler()
    async def fallback(_client, payload):
        called.append("fallback")

    packet = make_packet()
    assert await router.process_update(client, packet) is True
    assert called == [packet.payload]


async def test_process_update_supports_async_conditions():
    client = MaxClient()

    async def router_condition(_client, packet):
        return packet.opcode == 128

    async def handler_condition(_client, packet):
        return packet.opcode == 128

    router = Router(condition=router_condition)
    called = []

    @router.handler(handler_condition)
    async def handler(_client, payload):
        called.append(payload)

    assert await router.process_update(client, make_packet()) is True
    assert len(called) == 1
