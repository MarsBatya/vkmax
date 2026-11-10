from typing import Any, Optional

from vkmax.raw_client import MaxClient as RawClient


class UserMethods(RawClient):
    async def resolve_users(
        self,
        user_id: list[int],
    ) -> Optional[dict[str, Any]]:
        """Resolving users via userid"""

        return await self.invoke_method(
            opcode=32,
            payload={
                "contactIds": user_id,
            },
        )

    async def add_to_contacts(self, user_id: int) -> Optional[dict[str, Any]]:
        """Adding user to contacts via userid"""

        return await self.invoke_method(
            opcode=34,
            payload={
                "contactId": user_id,
                "action": "ADD",
            },
        )

    async def ban(self, user_id: int) -> Optional[dict[str, Any]]:
        """Banhammer to user's head"""

        return await self.invoke_method(
            opcode=34,
            payload={
                "contactId": user_id,
                "action": "BLOCK",
            },
        )
