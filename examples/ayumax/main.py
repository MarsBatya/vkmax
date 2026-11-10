import sqlite3
import logging
from contextlib import closing
from pathlib import Path

from vkmax.client import MaxClient

_logger = logging.getLogger(__name__)


async def sql(cmd: str, params: tuple = ()):
    with closing(sqlite3.connect(Path(__file__).with_name('messages.db'))) as db:
        with db, closing(db.cursor()) as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "message_id INTEGER, chat_id INTEGER, text TEXT, edited_text TEXT, status TEXT)"
            )
            cur.execute(cmd, params)
            if cur.description is not None:
                return cur.fetchall()


async def incoming_message(chat_id: int, message_id: int, text: str):
    await sql("INSERT INTO messages(message_id, chat_id, text) VALUES(?, ?, ?)", (message_id, chat_id, text))


async def edited_message(message_id: int, edited_text: str):
    if await sql("SELECT * FROM messages WHERE message_id = ?", (message_id,)) != []:
        await sql(
            "UPDATE messages SET edited_text = ?, status = 'EDITED' WHERE message_id = ?",
            (edited_text, message_id),
        )
    else:
        await sql(
            "INSERT INTO messages(message_id, edited_text, status) VALUES(?, ?, 'EDITED')",
            (message_id, edited_text),
        )


async def deleted_message(message_id: int):
    if await sql("SELECT * FROM messages WHERE message_id = ?", (message_id,)) != []:
        await sql("UPDATE messages SET status = 'REMOVED' WHERE message_id = ?", (message_id,))
    else:
        await sql("INSERT INTO messages(message_id, status) VALUES(?, 'DELETED')", (message_id,))


async def get_edited_messages(chat_id: int):
    return await sql("SELECT * FROM messages WHERE chat_id = ? AND status = 'EDITED'", (chat_id,))


async def get_deleted_messages(chat_id: int):
    return await sql("SELECT * FROM messages WHERE chat_id = ? AND status = 'REMOVED'", (chat_id,))

async def ayumax_callback(client: MaxClient, packet: dict):
    """ аюграм подкрался незаметно... """
    if packet['opcode'] == 128:
        message_text = packet['payload']['message']['text']
        print(packet)
        if (
            'status' in packet['payload']['message']
            and packet['payload']['message']['status'] == "REMOVED"
        ):
            await deleted_message(packet['payload']['message']['id'])
            await client.send_message(
                packet["payload"]["chatId"],
                text=f"Собеседник удалил сообщение: {message_text}",
            )

        elif (
            'status' in packet['payload']['message']
            and packet['payload']['message']['status'] == "EDITED"
        ):
            await edited_message(int(packet["payload"]["message"]["id"]), message_text)
            message_id = int(packet["payload"]["message"]["id"])
            previous_message = await sql("SELECT text FROM messages WHERE message_id = ?", (message_id,))
            original_text = previous_message[0][0] if previous_message else None
            if original_text is None:
                original_text = message_text
            await client.send_message(
                packet["payload"]["chatId"],
                text=f"Собеседник изменил сообщение: {original_text}",
            )
        else:
            await incoming_message(packet["payload"]["chatId"], int(packet["payload"]["message"]["id"]), message_text)
