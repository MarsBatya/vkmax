import pytest
from adaptix.load_error import AggregateLoadError

from vkmax.packet_codec import (
    PROTOCOL_VERSION,
    decode_packet,
    encode_packet,
    pack_bigint,
)
from vkmax.raw_client import MaxClient as RawClient
from vkmax.types.chats import Chat, ChatOptions, ChatReactions
from vkmax.types.enums import MessageType
from vkmax.types.messages import UserMessage
from vkmax.types.packets import ChatPayload, DeletedPayload, Packet, Payload

from test_lifecycle import wait_until

MESSAGE_ID = 117654281530966271
PREV_MESSAGE_ID = 117654269276531361


def push_payload(message_id=MESSAGE_ID, prev_message_id=PREV_MESSAGE_ID):
    return {
        "chatId": 230653550,
        "message": {
            "id": message_id,
            "time": 1795261864181,
            "type": "USER",
            "sender": 233458789,
            "text": "hi",
            "attaches": [],
        },
        "prevMessageId": prev_message_id,
        "ttl": False,
        "unread": 3,
        "mark": 1795025017874,
    }


def packet_dict(payload):
    return {
        "ver": PROTOCOL_VERSION,
        "cmd": 0,
        "seq": 5,
        "opcode": 128,
        "payload": payload,
    }


def test_push_packet_with_bigint_ids_loads():
    packet = Packet.from_dict(packet_dict(push_payload()))

    assert packet.ver == PROTOCOL_VERSION
    assert packet.opcode == 128
    assert isinstance(packet.payload, Payload)
    assert packet.payload.chat_id == 230653550
    assert packet.payload.message.message_id == str(MESSAGE_ID)
    assert packet.payload.prev_message_id == str(PREV_MESSAGE_ID)
    assert packet.payload.unread == 3
    assert packet.payload.ttl is False


def test_binary_push_frame_round_trip():
    payload = push_payload()
    payload["message"]["id"] = pack_bigint(MESSAGE_ID)
    payload["prevMessageId"] = pack_bigint(PREV_MESSAGE_ID)
    frame = encode_packet(cmd=0, seq=5, opcode=128, payload=payload)

    decoded = decode_packet(frame)
    assert decoded["ver"] == PROTOCOL_VERSION

    packet = Packet.from_dict(decoded)
    assert isinstance(packet.payload, Payload)
    assert packet.payload.message.message_id == str(MESSAGE_ID)
    assert packet.payload.prev_message_id == str(PREV_MESSAGE_ID)


def test_deleted_payload_accepts_int_message_ids():
    payload = {"chatId": 230653550, "messageIds": [MESSAGE_ID, str(PREV_MESSAGE_ID)]}

    packet = Packet.from_dict(packet_dict(payload))

    assert isinstance(packet.payload, DeletedPayload)
    assert packet.payload.message_ids == [str(MESSAGE_ID), str(PREV_MESSAGE_ID)]


def chat_payload():
    message = UserMessage(
        sender=233458789,
        message_id=str(MESSAGE_ID),
        timestamp=1795261864181,
        text="hi",
        message_type=MessageType.USER,
        attaches=[],
    )
    chat = Chat(
        participants_count=2,
        access="PUBLIC",
        type="CHAT",
        title="test",
        last_fire_delayed_error_time=0,
        last_delayed_update_time=0,
        options=ChatOptions(
            SIGN_ADMIN=False,
            OFFICIAL=False,
            MESSAGE_COPY_NOT_ALLOWED=False,
            ONLY_OWNER_CAN_CHANGE_ICON_TITLE=False,
            ONLY_ADMIN_CAN_ADD_MEMBER=False,
            ONLY_ADMIN_CAN_CALL=False,
            MEMBERS_CAN_SEE_PRIVATE_LINK=False,
            SENT_BY_PHONE=False,
            A_PLUS_CHANNEL=False,
            ALL_CAN_PIN_MESSAGE=False,
        ),
        modified=0,
        id=230653550,
        admin_participants={},
        participants={},
        owner=233458789,
        join_time=0,
        created=0,
        last_message=message,
        last_event_time=0,
        reactions=ChatReactions(is_active=False, update_time=0),
        messages_count=1,
        admins=[],
        status="ACTIVE",
        cid=1,
    )
    data = Packet.part_to_dict(chat)
    data["lastMessage"]["id"] = MESSAGE_ID
    return {
        "chat": data,
        "chatId": 230653550,
        "prevMessageId": PREV_MESSAGE_ID,
    }


def test_chat_payload_accepts_int_prev_message_id():
    packet = Packet.from_dict(packet_dict(chat_payload()))

    assert isinstance(packet.payload, ChatPayload)
    assert packet.payload.prev_message_id == str(PREV_MESSAGE_ID)
    assert packet.payload.chat.last_message.message_id == str(MESSAGE_ID)


def test_string_ids_still_load():
    payload = push_payload(
        message_id=str(MESSAGE_ID), prev_message_id=str(PREV_MESSAGE_ID)
    )

    packet = Packet.from_dict(packet_dict(payload))

    assert isinstance(packet.payload, Payload)
    assert packet.payload.message.message_id == str(MESSAGE_ID)
    assert packet.payload.prev_message_id == str(PREV_MESSAGE_ID)


def test_non_id_str_field_still_rejects_int():
    payload = push_payload()
    payload["message"]["text"] = 5

    with pytest.raises(AggregateLoadError):
        Packet.from_dict(packet_dict(payload))


async def test_push_event_parses_from_binary_frame(make_client):
    client = await make_client(RawClient, auto_reply=False)
    received = []

    async def callback(_client, packet):
        received.append(packet)

    client.set_packet_callback(callback)
    client._connection.push_packet(
        {"cmd": 0, "seq": 5, "opcode": 128, "payload": push_payload()}
    )

    await wait_until(lambda: received)

    packet = Packet.from_dict(received[0])
    assert isinstance(packet.payload, Payload)
    assert packet.payload.message.message_id == str(MESSAGE_ID)


async def test_send_message_result_parses_with_bigint_ids(make_client):
    client = await make_client(responses=[{"payload": push_payload()}])

    payload = await client.send_message(230653550, "hi")

    assert isinstance(payload, Payload)
    assert payload.message.message_id == str(MESSAGE_ID)
    assert payload.prev_message_id == str(PREV_MESSAGE_ID)
