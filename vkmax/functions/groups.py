from random import randint
from typing import Optional


from vkmax.raw_client import MaxClient as RawClient


class GroupMethods(RawClient):
    async def create_group(self, group_name: str, participant_ids: list[int]):
        """Creates a group"""

        return await self.invoke_method(
            opcode=64,
            payload={
                "message": {
                    "cid": randint(  # noqa: S311
                        1750000000000,
                        2000000000000,
                    ),  # TODO: fuck around and find out
                    "attaches": [
                        {
                            "_type": "CONTROL",
                            "event": "new",
                            "chatType": "CHAT",
                            "title": group_name,
                            "userIds": participant_ids,
                        },
                    ],
                },
                "notify": True,
            },
        )

    async def invite_users(
        self,
        group_id: int,
        participant_ids: list[int],
        show_history=True,
    ):
        """Invites users into group via userid"""

        return await self.invoke_method(
            opcode=77,
            payload={
                "chatId": group_id,
                "userIds": participant_ids,
                "showHistory": show_history,
                "operation": "add",
            },
        )

    async def remove_users(
        self,
        group_id: int,
        participant_ids: list[int],
        delete_messages: bool = False,
    ):
        """Removes users from group via userid"""

        return await self.invoke_method(
            opcode=77,
            payload={
                "chatId": group_id,
                "userIds": participant_ids,
                "operation": "remove",
                "cleanMsgPeriod": 0 if not delete_messages else -1,
            },
        )

    async def add_admin(
        self,
        group_id: int,
        admin_ids: list[int],
        deleting_messages: bool = False,
        control_participants: bool = False,
        control_admins: bool = False,
    ):
        """
        Adds an admin to group.
        You need to be a group owner or administrator to use this method.
        """

        # minimal admin: 120
        # minimal admin + deleting msgs: 121
        # minimal admin + deleting msgs + participants: 123
        # full_admin: 255
        # minimal admin + set_admins: 124
        # minimal admin + set_admins + deleting msgs: 125
        # minimal admin + set_admins + participants: 254
        # minimal admin + participants: 250
        # minimal admin + deletings msgs + participants: 251
        permissions = (
            120
            if not deleting_messages and not control_participants and not control_admins
            else ...
        )
        permissions = (
            121
            if deleting_messages and not control_participants and not control_admins
            else ...
        )
        permissions = (
            123
            if deleting_messages and control_participants and not control_admins
            else ...
        )
        permissions = (
            124
            if not deleting_messages and not control_participants and control_admins
            else ...
        )
        permissions = (
            125
            if deleting_messages and not control_participants and control_admins
            else ...
        )
        permissions = (
            250
            if not deleting_messages and control_participants and not control_admins
            else ...
        )
        permissions = (
            251
            if deleting_messages and control_participants and not control_admins
            else ...
        )
        permissions = (
            254
            if not deleting_messages and control_participants and control_admins
            else ...
        )
        permissions = (
            255
            if deleting_messages and control_participants and control_admins
            else ...
        )

        return await self.invoke_method(
            opcode=77,
            payload={
                "chatId": group_id,
                "userIds": admin_ids,
                "type": "ADMIN",
                "operation": "remove",
                "permissions": permissions,
            },
        )

    async def remove_admin(self, group_id: int, admin_ids=list[int]):
        """
        Removes an admin from group.
        You need to be a group owner or administrator to use this method.
        """

        return await self.invoke_method(
            opcode=77,
            payload={
                "chatId": group_id,
                "userIds": admin_ids,
                "type": "ADMIN",
                "operation": "remove",
            },
        )

    async def transfer_group_ownership(self, group_id: int, new_owner_id: int):
        """Transfers ownership of the group to a new user"""

        return await self.invoke_method(
            opcode=55,
            payload={"chatId": group_id, "changeOwnerId": new_owner_id},
        )

    async def change_group_settings(
        self,
        group_id: int,
        all_can_pin_message: bool = False,
        only_owner_can_change_icon_title: bool = True,
        only_admin_can_add_member: bool = True,
    ):
        """Changes basic group settings"""

        options = {
            "ONLY_OWNER_CAN_CHANGE_ICON_TITLE": only_owner_can_change_icon_title,
            "ALL_CAN_PIN_MESSAGE": all_can_pin_message,
            "ONLY_ADMIN_CAN_ADD_MEMBER": only_admin_can_add_member,
        }
        return await self.invoke_method(
            opcode=55,
            payload={
                "chatId": group_id,
                "options": options,
            },
        )

    async def change_group_profile(
        self,
        group_id: int,
        new_group_name: Optional[str] = None,
        new_description: Optional[str] = None,
    ):
        """Just changes a group public profile"""
        # TODO XXX Might cause a bug with theme being null. Need to test

        if new_description:
            await self.invoke_method(
                opcode=55,
                payload={
                    "chatId": group_id,
                    "theme": new_group_name,
                },
            )

        if new_group_name:
            await self.invoke_method(
                opcode=55,
                payload={
                    "chatId": group_id,
                    "theme": new_group_name,
                    "description": new_description,
                },
            )

        return

    async def get_group_members(self, group_id: int, marker=0, count=500):
        """
        Gets all the members in specified chat.
        :param marker: User ID to begin with
        """

        if count > 500:
            raise Exception("Maximum available count is 500")

        return await self.invoke_method(
            opcode=59,
            payload={
                "type": "MEMBER",
                "marker": marker,
                "chatId": group_id,
                "count": count,
            },
        )

    async def resolve_group_by_link(self, link_hash: str):
        """Gets group info by invite hash"""
        return await self.invoke_method(
            opcode=89,
            payload={"link": f"join/{link_hash}"},
        )

    async def join_group_by_link(self, link_hash: str):
        """Join group by its invite hash"""
        data = await self.invoke_method(
            opcode=57,
            payload={"link": f"join/{link_hash}"},
        )
        if not data:
            raise ValueError("Failed to join group")
        chat_id = data["payload"]["chat"]["id"]
        cid = data["payload"]["chat"]["cid"]
        await self.invoke_method(
            opcode=75,
            payload={"chatId": 381006, "subscribe": False},
        )
        await self.invoke_method(
            opcode=75,
            payload={"chatId": chat_id, "subscribe": True},
        )
        await self.invoke_method(
            opcode=49,
            payload={
                "chatId": chat_id,
                "from": cid,
                "forward": 0,
                "backward": 30,
                "getMessages": True,
            },
        )
        return

    async def react_to_message(self, group_id: int, message_id: int, reaction: str):
        """React to a message in a group"""
        await self.invoke_method(
            opcode=178,
            payload={
                "chatId": group_id,
                "messageId": str(message_id),
                "reaction": {
                    "reactionType": "EMOJI",
                    "id": reaction,
                },
            },
        )
        await self.invoke_method(
            opcode=181,
            payload={"chatId": group_id, "messageId": str(message_id), "count": 100},
        )
