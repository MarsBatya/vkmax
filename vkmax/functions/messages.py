from pathlib import Path
from random import randint
from typing import Optional, Union

from vkmax.types.formatting import Element
from vkmax.functions.uploads import UploadMethods
from vkmax.utils.formatting import parse_text
from vkmax.types.packets import Packet

# common backward-compatible type
# for functions accepting a message id
MessageId = Union[str, int]


class MessageMethods(UploadMethods):

    async def send_message(
        self,
        chat_id: int,
        text: str,
        notify: bool = True,
        reply_to: Optional[MessageId] = None,
        elements: list[Element] | None = None,
        attaches: list | None = None,
        formatting: bool = False,
    ):
        """Sends message to specified chat"""

        if attaches is None:
            attaches = []
        
        if formatting:
            text, elements = parse_text(text)

        payload = {
            "chatId": chat_id,
            "message": {
                "text": text,
                "cid": randint(1750000000000, 2000000000000),  # noqa: S311
                "elements": elements or [],
                "link": None,
                "attaches": attaches,
            },
            "notify": notify,
        }

        if reply_to is not None:
            payload["message"]["link"] = {
                "type": "REPLY",
                "messageId": f"{reply_to}",
            }
        else:
            del payload["message"]["link"]

        result = await self.invoke_method(
            opcode=64,
            payload=payload,
        )
        if not result:
            raise ValueError("Failed to retrieve send message info")
        
        return Packet.from_dict(result).payload


    async def edit_message(
        self,
        chat_id: int,
        message_id: MessageId,
        text: str,
        attaches: list | None = None,
        elements: list[Element] | None = None,
        formatting: bool = False,
    ):
        """Edits the specified message"""

        if attaches is None:
            attaches = []

        if formatting:
            text, elements = parse_text(text)

        result = await self.invoke_method(
            opcode=67,
            payload={
                "chatId": chat_id,
                "messageId": f"{message_id}",
                "text": text,
                "elements": elements or [],
                "attachments": attaches,
            },
        )

        if not result:
            raise ValueError("Failed to retrieve edit message info")
        if not result.get("payload", {}).get("chatId"):
            result["payload"]["chatId"] = chat_id
        return Packet.from_dict(result).payload


    async def delete_message(
        self,
        chat_id: int,
        message_ids: list,
        delete_for_me: bool = False,
    ):
        """Deletes the specified message"""

        result = await self.invoke_method(
            opcode=66,
            payload={
                "chatId": chat_id,
                "messageIds": message_ids,
                "forMe": delete_for_me,
            },
        )
        if not result:
            raise ValueError("Failed to retrieve delete message info")
        return Packet.from_dict(result).payload


    async def pin_message(
        self,
        chat_id: int,
        message_id: MessageId,
        notify: bool = False,
    ):
        """Pins message in the chat"""

        result = await self.invoke_method(
            opcode=55,
            payload={
                "chatId": chat_id,
                "notifyPin": notify,
                "pinMessageId": f"{message_id}",
            },
        )

        if not result:
            raise ValueError("Failed to retrieve pin message info")
        return Packet.from_dict(result).payload


    async def reply_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: MessageId,
        notify: bool = True,
        elements: list[Element] | None = None,
        formatting: bool = False,
    ):
        """Replies to message in the chat"""

        return await self.send_message(
            chat_id,
            text,
            reply_to=reply_to_message_id,
            notify=notify,
            elements=elements,
            formatting=formatting,
        )


    async def send_photo(
        self,
        chat_id: int,
        image_path: str,
        caption: str,
        notify: bool = True,
        elements: list[Element] | None = None,
        formatting: bool = False,
    ):
        """Sends photo to specified chat"""

        with open(image_path, "rb") as stream:
            photo = await self.upload_photo(chat_id, stream)

        return await self.send_message(
            chat_id,
            caption,
            notify=notify,
            attaches=[photo],
            elements=elements,
            formatting=formatting,
        )


    async def send_file(
        self,
        chat_id: int,
        file_path: str,
        caption: str,
        notify: bool = True,
        elements: list[Element] | None = None,
        formatting: bool = False,
    ):
        """Sends a file to the specified chat"""

        path: Path = Path(file_path)

        with path.open("rb") as stream:
            file = await self.upload_file(
                chat_id,
                stream,
                filename=path.name,
            )

        return await self.send_message(
            chat_id,
            caption,
            notify=notify,
            attaches=[file],
            elements=elements,
            formatting=formatting,
        )
