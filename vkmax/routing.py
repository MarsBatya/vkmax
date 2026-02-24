from dataclasses import dataclass
from functools import partial
from inspect import iscoroutinefunction
from typing import Awaitable, Callable, TypeVar, cast


from vkmax.client import MaxClient
from vkmax.types.packets import Packet, Payload


async def pass_all(client: MaxClient, packet: Packet) -> bool:
    return True

@dataclass
class Handler:
    condition: Callable[[MaxClient, Packet], Awaitable[bool]]
    # handlers usually don't need full packet info, proper payload is enough
    callback: Callable[[MaxClient, Payload], Awaitable]


async def awaitable_filter(
    client: MaxClient,
    packet: Packet,
    condition: Callable[[MaxClient, Packet], bool],
) -> bool:
    return condition(client, packet)

Coro = TypeVar("Coro", bound=Callable[[MaxClient, Payload], Awaitable])

class Router:
    """

    example usage:
    ```python
    router = Router(
        condition=lambda _, packet: bool(
            packet.opcode == 128 and isinstance(packet.payload, Payload),
        ),
    )

    @router.handler(
        lambda client, packet: (
            isinstance(packet.payload, Payload)
            and packet.payload.message.text == "/start"
        ),
    )
    async def start_handler(client: MaxClient, payload: Payload) -> None:
        await client.send_message(payload.chat_id, "Hello!")

    ...
    router.process_update(client, packet)
    ```
    """
    def __init__(
        self,
        condition: Callable[[MaxClient, Packet], bool | Awaitable[bool]] = pass_all,
    ) -> None:
        self.condition = (
            condition
            if iscoroutinefunction(condition)
            else partial(
                awaitable_filter,
                condition=cast(
                    Callable[[MaxClient, Packet], bool],
                    condition,
                ),
            )
        )
        self.handlers: list[Handler] = []

    def handler(
        self,
        condition: Callable[[MaxClient, Packet], bool | Awaitable[bool]] = pass_all,
    ):
        def wrapper(callback: Coro) -> Coro:
            self.handlers.append(
                Handler(
                    condition=(
                        condition
                        if iscoroutinefunction(condition)
                        else partial(
                            awaitable_filter,
                            condition=cast(
                                Callable[[MaxClient, Packet], bool],
                                condition,
                            ),
                        )
                    ),
                    callback=callback,
                ),
            )
            return callback

            # async def wrapped(client: MaxClient, packet: Packet):
            #     return await callback(client, packet)

            # return wrapped

        return wrapper

    async def process_update(self, client: MaxClient, packet: Packet):
        if await self.condition(client, packet):
            for handler in self.handlers:
                if await handler.condition(client, packet):
                    await handler.callback(client, cast(Payload, packet.payload))
                    break
