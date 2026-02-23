from dataclasses import dataclass
from typing import Any, Optional

from adaptix import Retort, NameStyle, name_mapping

from vkmax.types.messages import Message, Link, DelayedAttributes
from vkmax.types.attaches import Attachment, Button, Preview
from vkmax.types.elements import MessageElement, AnimojiAttributes


@dataclass(slots=True)
class Payload:
    chat_id: int
    message: Message
    unread: Optional[int] = None
    mark: Optional[int] = None
    ttl: Optional[bool] = None
    prev_message_id: Optional[str] = None  # for personal chats looks like

    # for scheduled msgs
    last_delayed_update_time: Optional[int] = None
    update_type_id: Optional[int] = None
    user_id: Optional[int] = None


# ---------------- Packet ----------------


@dataclass(slots=True)
class Packet:
    ver: int
    cmd: int
    seq: int
    opcode: int
    payload: Payload

    @classmethod
    def from_dict(cls, data: dict):
        return _retort.load(data, cls)

    def to_dict(self) -> dict:
        return _retort.dump(self)

    @classmethod
    def part_to_dict(cls, anything: Any) -> dict:
        return _retort.dump(anything)

_retort = Retort(
    recipe=[
        # Global snake_case <-> camelCase conversion
        name_mapping(
            Packet,
            name_style=NameStyle.CAMEL,
        ),
        name_mapping(
            Payload,
            name_style=NameStyle.CAMEL,
            omit_default=True,
        ),
        name_mapping(
            DelayedAttributes,
            name_style=NameStyle.CAMEL,
            omit_default=True,
        ),
        *(
            name_mapping(
                _type,
                name_style=NameStyle.CAMEL,
                map={"_type": "_type"},
            )
            for _type in Preview.__args__
        ),
        *(
            name_mapping(
                _type,
                name_style=NameStyle.CAMEL,
                map={"_type": "_type"},
                omit_default=True,
            )
            for _type in Attachment.__args__
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
            for _type in Message.__args__
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
            for _type in MessageElement.__args__
        ),
        name_mapping(
            AnimojiAttributes,
            name_style=NameStyle.CAMEL,
        ),
    ],
)