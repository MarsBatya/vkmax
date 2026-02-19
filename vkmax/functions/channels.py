from random import randint

from vkmax.raw_client import MaxClient as RawClient


class ChannelMethods(RawClient):
    async def resolve_channel_username(self, username: str):
        """Resolving channel by username"""

        return await self.invoke_method(
            opcode=89, payload={"link": f"https://max.ru/{username}"},
        )

    async def resolve_channel_id(self, channel_id: int):
        """Resolve channel by id"""

        return await self.invoke_method(opcode=48, payload={"chatIds": [channel_id]})

    async def join_channel(self, username: str):
        """Joining a channel and resolving"""

        return await self.invoke_method(
            opcode=57, payload={"link": f"https://max.ru/{username}"},
        )

    async def create_channel(self, channel_name: str):
        return await self.invoke_method(
            opcode=64,
            payload={
                "message": {
                    "cid": randint(1750000000000, 2000000000000),  # noqa: S311
                    "attaches": [
                        {
                            "_type": "CONTROL",
                            "event": "new",
                            "title": channel_name,
                            "chatType": "CHANNEL",
                        },
                    ],
                    "text": "",
                },
            },
        )

    async def mute_channel(self, channel_id: int, mute: bool = True):
        """Mutes or unmutes a channel"""

        return await self.invoke_method(
            opcode=22,
            payload={
                "settings": {
                    "chats": {str(channel_id): {"dontDisturbUntil": -1 if mute else 0}},
                },
            },
        )
