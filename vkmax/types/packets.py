from dataclasses import dataclass
from typing import Any, Literal, Optional, Union, get_args

from adaptix import Chain, P, Retort, NameStyle, bound, loader, name_mapping
from adaptix.load_error import TypeLoadError

from vkmax.types.messages import (
    Message,
    Link,
    DelayedAttributes,
    ReactionInfo,
    Attachment,
    Button,
    Preview,
    SimpleImage,
)
from vkmax.types.elements import MessageElement, AnimojiAttributes
from vkmax.types.chats import Chat, ChatReactions


@dataclass(slots=True)
class Payload:
    message: Message
    chat_id: int
    unread: Optional[int] = None
    mark: Optional[int] = None
    ttl: Optional[bool] = None
    prev_message_id: Optional[str] = None  # for personal chats looks like

    # for scheduled msgs
    last_delayed_update_time: Optional[int] = None
    update_type_id: Optional[int] = None
    user_id: Optional[int] = None

    # for pinned msgs looks like
    chat: Optional[Chat] = None

    _flag: Literal["_NORMAL"] = "_NORMAL"

    @classmethod
    def from_dict(cls, data: dict) -> "Payload":
        return _retort.load(data, cls)

    def to_dict(self) -> dict:
        return _retort.dump(self)

    @classmethod
    def part_to_dict(cls, anything: Any) -> dict:
        return _retort.dump(anything)


@dataclass(slots=True)
class DeletedPayload:
    chat_id: int
    message_ids: list[str]
    _flag: Literal["_DELETED"] = "_DELETED"


@dataclass(slots=True)
class ChatPayload:
    chat: Chat
    message: Optional[Message] = None
    chat_id: Optional[int] = None
    mark: Optional[int] = None
    prev_message_id: Optional[str] = None
    ttl: Optional[bool] = None
    unread: Optional[int] = None
    _flag: Literal["_CHAT"] = "_CHAT"


@dataclass(slots=True)
class EditedMessagePayload:
    message: Message
    _flag: Literal["_EDITED"] = "_EDITED"


# ---------------- Packet ----------------

PacketPayload = Union[Payload, DeletedPayload, ChatPayload, EditedMessagePayload]


@dataclass(slots=True)
class Packet:
    ver: int
    cmd: int
    seq: int
    opcode: int
    payload: PacketPayload

    @classmethod
    def from_dict(cls, data: dict) -> "Packet":
        return _retort.load(data, cls)

    def to_dict(self) -> dict:
        return _retort.dump(self)

    @classmethod
    def part_to_dict(cls, anything: Any) -> dict:
        return _retort.dump(anything)


# more control over what to load
def packet_loader(data: dict):
    if "chatId" not in data["payload"] and "message" in data["payload"]:
        data["payload"]["_flag"] = "_EDITED"
    elif "messageIds" in data["payload"]:
        data["payload"]["_flag"] = "_DELETED"
    elif "chat" in data["payload"] and "message" not in data["payload"]:
        data["payload"]["_flag"] = "_CHAT"
    else:
        data["payload"]["_flag"] = "_NORMAL"
    return data


# BigInt ids arrive as msgpack ints; the JSON era carried them as strings.
def _load_message_id(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    raise TypeLoadError(str, value)


def _load_optional_message_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    return _load_message_id(value)


def _load_message_ids(values: Any) -> list[str]:
    if not isinstance(values, list):
        raise TypeLoadError(list, values)
    return [_load_message_id(value) for value in values]


_retort = Retort(
    recipe=[
        # Global snake_case <-> camelCase conversion
        loader(Packet, packet_loader, chain=Chain.FIRST),
        *(
            bound(P[_type].message_id, loader(str, _load_message_id))
            for _type in get_args(Message)
        ),
        *(
            bound(
                P[_type].prev_message_id,
                loader(Optional[str], _load_optional_message_id),
            )
            for _type in (Payload, ChatPayload)
        ),
        bound(P[DeletedPayload].message_ids, loader(list[str], _load_message_ids)),
        *(
            name_mapping(
                _type,
                name_style=NameStyle.CAMEL,
                omit_default=True,
            )
            for _type in (
                Payload,
                DeletedPayload,
                ChatPayload,
                EditedMessagePayload,
                DelayedAttributes,
                Chat,
                ChatReactions,
                ReactionInfo,
            )
        ),
        *(
            name_mapping(
                _type,
                name_style=NameStyle.CAMEL,
                map={"_type": "_type"},
            )
            for _type in get_args(Preview)
        ),
        *(
            name_mapping(
                _type,
                name_style=NameStyle.CAMEL,
                map={"_type": "_type"},
                omit_default=True,
            )
            for _type in (*get_args(Attachment), SimpleImage)
        ),
        name_mapping(
            Link,
            name_style=NameStyle.CAMEL,
            omit_default=True,
            map={"link_type": "type"},
        ),
        name_mapping(
            Button,
            name_style=NameStyle.CAMEL,
            omit_default=True,
            map={"button_type": "type"},
        ),
        *(
            name_mapping(
                _type,
                name_style=NameStyle.CAMEL,
                omit_default=True,
                map={
                    "message_id": "id",
                    "timestamp": "time",
                    "message_type": "type",
                },
            )
            for _type in get_args(Message)
        ),
        *(
            name_mapping(
                _type,
                name_style=NameStyle.CAMEL,
                omit_default=True,
                map={
                    "element_type": "type",
                    "start_from": "from",
                },
            )
            for _type in get_args(MessageElement)
        ),
        name_mapping(
            AnimojiAttributes,
            name_style=NameStyle.CAMEL,
        ),
    ],
)
