from typing import Optional


from vkmax.raw_client import MaxClient as RawClient


class ProfileMethods(RawClient):
    async def change_online_status_visibility(
        self,
        hidden: bool,
    ):
        """Hide or show you last online status"""

        return await self.invoke_method(
            opcode=22,
            payload={
                "settings": {
                    "user": {
                        "HIDDEN": hidden,
                    },
                },
            },
        )

    async def set_is_findable_by_phone(
        self,
        findable: bool,
    ):
        """You can make your profile findable by phone or not"""

        return await self.invoke_method(
            opcode=22,
            payload={
                "settings": {
                    "user": {
                        "SEARCH_BY_PHONE": "ALL" if findable else "CONTACTS",
                    },
                },
            },
        )

    async def set_calls_privacy(
        self,
        can_be_called: bool,
    ):
        """You can enable or disable calls for everyone"""

        return await self.invoke_method(
            opcode=22,
            payload={
                "settings": {
                    "user": {
                        "INCOMING_CALL": "ALL" if can_be_called else "CONTACTS",
                    },
                },
            },
        )

    async def invite_privacy(
        self,
        invitable: bool,
    ):
        """Changes the possibility of inviting you to other chats"""

        return await self.invoke_method(
            opcode=22,
            payload={
                "settings": {
                    "user": {
                        "CHATS_INVITE": "ALL" if invitable else "CONTACTS",
                    },
                },
            },
        )

    async def change_profile(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        bio: Optional[str] = None,
    ):
        """Changes your public profile"""

        return await self.invoke_method(
            opcode=16,
            payload={
                "firstName": first_name,
                "lastName": last_name,
                "description": bio,
            },
        )
