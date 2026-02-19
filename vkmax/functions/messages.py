from pathlib import Path
from random import randint
from typing import Optional, Union

from vkmax.client import MaxClient
from vkmax.functions.uploads import upload_photo, upload_file
from vkmax.types.formatting import Element

# common backward-compatible type
# for functions accepting a message id
MessageId = Union[str, int]


async def send_message(
    client: MaxClient,
    chat_id: int,
    text: str,
    notify: bool = True,
    reply_to: Optional[MessageId] = None,
    elements: list[Element] | None = None,
    attaches: list | None = None,
):
    """Sends message to specified chat"""

    if attaches is None:
        attaches = []
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

    return await client.invoke_method(
        opcode=64,
        payload=payload,
    )


async def edit_message(
    client: MaxClient,
    chat_id: int,
    message_id: MessageId,
    text: str,
    attaches: list | None = None,
    elements: list[Element] | None = None,
):
    """Edits the specified message"""

    if attaches is None:
        attaches = []

    return await client.invoke_method(
        opcode=67,
        payload={
            "chatId": chat_id,
            "messageId": f"{message_id}",
            "text": text,
            "elements": elements or [],
            "attachments": attaches,
        },
    )


async def delete_message(
    client: MaxClient,
    chat_id: int,
    message_ids: list,
    delete_for_me: bool = False,
):
    """Deletes the specified message"""

    return await client.invoke_method(
        opcode=66,
        payload={
            "chatId": chat_id,
            "messageIds": message_ids,
            "forMe": delete_for_me,
        },
    )


async def pin_message(
    client: MaxClient,
    chat_id: int,
    message_id: MessageId,
    notify: bool = False,
):
    """Pins message in the chat"""

    return await client.invoke_method(
        opcode=55,
        payload={
            "chatId": chat_id,
            "notifyPin": notify,
            "messageId": f"{message_id}",
        },
    )


async def reply_message(
    client: MaxClient,
    chat_id: int,
    text: str,
    reply_to_message_id: MessageId,
    notify: bool = True,
    elements: list[Element] | None = None,
):
    """Replies to message in the chat"""

    return await send_message(
        client,
        chat_id,
        text,
        reply_to=reply_to_message_id,
        notify=notify,
        elements=elements,
    )


async def send_photo(
    client: MaxClient,
    chat_id: int,
    image_path: str,
    caption: str,
    notify: bool = True,
    elements: list[Element] | None = None,
):
    """Sends photo to specified chat"""

    with open(image_path, "rb") as stream:
        photo = await upload_photo(client, chat_id, stream)

    return await send_message(
        client,
        chat_id,
        caption,
        notify=notify,
        attaches=[photo],
        elements=elements,
    )


async def send_file(
    client: MaxClient,
    chat_id: int,
    file_path: str,
    caption: str,
    notify: bool = True,
    elements: list[Element] | None = None,
):
    """Sends a file to the specified chat"""

    path: Path = Path(file_path)

    with path.open("rb") as stream:
        file = await upload_file(
            client,
            chat_id,
            stream,
            filename=path.name,
        )

    return await send_message(
        client,
        chat_id,
        caption,
        notify=notify,
        attaches=[file],
        elements=elements,
    )
