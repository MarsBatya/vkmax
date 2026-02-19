
from vkmax.raw_client import MaxClient as RawClient

class UserMethods(RawClient):
    async def resolve_users(
        self,
        user_id: list,
    ):
        """Resolving users via userid"""

        return await self.invoke_method(
            opcode=32,
            payload={
                "contactIds": user_id,
            },
        )

    async def add_to_contacts(self, user_id: int):
        """Adding user to contacts via userid"""

        return await self.invoke_method(
            opcode=34,
            payload={
                "contactId":user_id,
                "action":"ADD",
            },
        )


    async def ban(self, user_id: int):
        """Banhammer to user's head"""

        return await self.invoke_method(
            opcode=34,
            payload={
                "contactId":user_id,
                "action":"BLOCK",
            },
        )
