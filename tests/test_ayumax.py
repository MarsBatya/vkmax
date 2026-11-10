import importlib.util
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import create_autospec

import pytest

from vkmax.client import MaxClient


ROOT = Path(__file__).resolve().parents[1]
TEXTS = ["O'Brien's message", "x'); DROP TABLE messages; --"]


@pytest.fixture
def ayumax(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "ayumax_storage_test", ROOT / "examples/ayumax/main.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "main.py"))
    return module


@pytest.fixture
def client():
    return create_autospec(MaxClient, instance=True)


def packet(text, status=None, opcode=128):
    message = {"id": "2", "text": text}
    if status is not None:
        message["status"] = status
    return {"opcode": opcode, "payload": {"chatId": 1, "message": message}}


async def test_sql_initializes_pristine_database_beside_module(ayumax, tmp_path):
    database = tmp_path / "messages.db"
    assert not database.exists()

    assert await ayumax.sql("SELECT * FROM messages") == []

    assert database.is_file()
    with closing(sqlite3.connect(database)) as db:
        columns = db.execute("PRAGMA table_info(messages)").fetchall()
    assert [column[1] for column in columns] == [
        "message_id", "chat_id", "text", "edited_text", "status"
    ]
    assert await ayumax.sql("SELECT * FROM messages") == []


async def test_sql_parameters_and_committed_storage(ayumax, tmp_path):
    text = "O'Brien'); SELECT * FROM messages; --"
    assert await ayumax.sql(
        "INSERT INTO messages(message_id, chat_id, text) VALUES(?, ?, ?)",
        (2, 1, text),
    ) is None

    assert await ayumax.sql("select text from messages where message_id = ?", (2,)) == [(text,)]
    with closing(sqlite3.connect(tmp_path / "messages.db")) as db:
        assert db.execute("SELECT * FROM messages").fetchall() == [(2, 1, text, None, None)]


@pytest.mark.parametrize("fail", [False, True])
async def test_sql_closes_connection_on_success_and_error(ayumax, monkeypatch, fail):
    connect = sqlite3.connect
    connections = []

    def tracked_connect(*args, **kwargs):
        db = connect(*args, **kwargs)
        connections.append(db)
        return db

    monkeypatch.setattr(ayumax.sqlite3, "connect", tracked_connect)
    if fail:
        with pytest.raises(sqlite3.ProgrammingError):
            await ayumax.sql("INSERT INTO messages(text) VALUES(?)")
    else:
        assert await ayumax.sql("SELECT * FROM messages") == []

    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")


@pytest.mark.parametrize("text", TEXTS)
async def test_insert_edit_remove_preserves_text_and_other_messages(ayumax, text):
    edited_text = f"Edited: {text}"
    await ayumax.incoming_message(1, 2, text)
    await ayumax.incoming_message(9, 3, "untouched")
    assert await ayumax.sql("SELECT * FROM messages WHERE message_id = ?", (2,)) == [
        (2, 1, text, None, None)
    ]

    await ayumax.edited_message(2, edited_text)
    assert await ayumax.get_edited_messages(1) == [(2, 1, text, edited_text, "EDITED")]
    assert await ayumax.get_edited_messages(9) == []

    await ayumax.deleted_message(2)
    assert await ayumax.get_edited_messages(1) == []
    assert await ayumax.get_deleted_messages(1) == [(2, 1, text, edited_text, "REMOVED")]
    assert await ayumax.get_deleted_messages(9) == []
    assert await ayumax.sql("SELECT * FROM messages WHERE message_id = ?", (3,)) == [
        (3, 9, "untouched", None, None)
    ]


@pytest.mark.parametrize("operation", ["edited_message", "deleted_message"])
async def test_unseen_message_initializes_storage_and_records_status(ayumax, operation):
    text = "O'Brien'); DROP TABLE messages; --"
    if operation == "edited_message":
        await ayumax.edited_message(2, text)
        expected = (2, None, None, text, "EDITED")
    else:
        await ayumax.deleted_message(2)
        expected = (2, None, None, None, "DELETED")

    assert await ayumax.sql("SELECT * FROM messages") == [expected]


@pytest.mark.parametrize("operation", ["edited_message", "deleted_message"])
async def test_message_id_injection_cannot_update_other_rows(ayumax, operation):
    await ayumax.incoming_message(1, 1, "first")
    await ayumax.incoming_message(1, 2, "second")
    message_id = "1 OR 1=1"
    if operation == "edited_message":
        await ayumax.edited_message(message_id, "changed")
        expected = (message_id, None, None, "changed", "EDITED")
    else:
        await ayumax.deleted_message(message_id)
        expected = (message_id, None, None, None, "DELETED")

    assert await ayumax.sql("SELECT * FROM messages ORDER BY rowid") == [
        (1, 1, "first", None, None),
        (2, 1, "second", None, None),
        expected,
    ]


@pytest.mark.parametrize("getter", ["get_edited_messages", "get_deleted_messages"])
async def test_chat_id_queries_bind_values(ayumax, getter):
    await ayumax.incoming_message(1, 2, "first")
    await ayumax.incoming_message(9, 3, "second")
    for message_id in (2, 3):
        if getter == "get_edited_messages":
            await ayumax.edited_message(message_id, "changed")
        else:
            await ayumax.deleted_message(message_id)

    query = getattr(ayumax, getter)
    assert len(await query(1)) == 1
    assert len(await query(9)) == 1
    assert await query("1 OR 1=1") == []


@pytest.mark.parametrize("text", TEXTS)
async def test_callback_persists_changes_and_uses_mocked_client(ayumax, client, text):
    edited_text = f"Changed: {text}"
    await ayumax.ayumax_callback(client, packet(text))
    client.send_message.assert_not_awaited()

    await ayumax.ayumax_callback(client, packet(edited_text, "EDITED"))
    client.send_message.assert_awaited_once_with(
        1, text=f"Собеседник изменил сообщение: {text}"
    )
    assert await ayumax.get_edited_messages(1) == [(2, 1, text, edited_text, "EDITED")]

    client.send_message.reset_mock()
    await ayumax.ayumax_callback(client, packet(edited_text, "REMOVED"))
    client.send_message.assert_awaited_once_with(
        1, text=f"Собеседник удалил сообщение: {edited_text}"
    )
    assert await ayumax.get_deleted_messages(1) == [(2, 1, text, edited_text, "REMOVED")]
    client.invoke_method.assert_not_called()


@pytest.mark.parametrize("original", [None, ""])
async def test_edit_notification_handles_absent_or_empty_original(ayumax, client, original):
    edited_text = "O'Brien's changed message"
    if original is not None:
        await ayumax.incoming_message(1, 2, original)

    await ayumax.ayumax_callback(client, packet(edited_text, "EDITED"))

    expected_text = edited_text if original is None else original
    client.send_message.assert_awaited_once_with(
        1, text=f"Собеседник изменил сообщение: {expected_text}"
    )
    expected_chat = None if original is None else 1
    assert await ayumax.sql("SELECT * FROM messages") == [
        (2, expected_chat, original, edited_text, "EDITED")
    ]
    client.invoke_method.assert_not_called()


async def test_callback_ignores_unrelated_opcode_without_storage(ayumax, client, tmp_path):
    await ayumax.ayumax_callback(client, packet("ignored", opcode=0))

    assert not (tmp_path / "messages.db").exists()
    client.send_message.assert_not_awaited()
    client.invoke_method.assert_not_called()
