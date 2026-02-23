from dataclasses import dataclass

from typing import Literal, Optional, Union

from vkmax.types.enums import LinkType, ChatAccess, MessageType, MessageStatus
from vkmax.types.attaches import Attachment
from vkmax.types.elements import MessageElement


@dataclass(slots=True)
class Link:
    link_type: LinkType
    message: "Message"
    chat_id: int

    # when forwarded from channel ig
    chat_access_type: Optional[ChatAccess] = None
    chat_icon_url: Optional[str] = None
    chat_link: Optional[str] = None
    chat_name: Optional[str] = None
    content_level: Optional[bool] = None


@dataclass(slots=True)
class Stats:
    views: int


@dataclass(slots=True)
class UserMessage:
    sender: int
    message_id: str
    timestamp: int
    text: str
    message_type: Literal[MessageType.USER]
    attaches: list[Attachment]
    stats: Optional[Stats] = None
    status: Optional[MessageStatus] = None
    update_time: Optional[int] = None
    options: Optional[int] = None
    cid: Optional[int] = None
    elements: Optional[list[MessageElement]] = None
    link: Optional[Link] = None


@dataclass(slots=True)
class ChannelMessage:
    message_id: str
    timestamp: int
    text: str
    message_type: Literal[MessageType.CHANNEL]
    attaches: list[Attachment]
    sender: Optional[int] = None
    options: Optional[int] = None
    status: Optional[MessageStatus] = None
    update_time: Optional[int] = None
    stats: Optional[Stats] = None
    cid: Optional[int] = None
    elements: Optional[list[MessageElement]] = None
    link: Optional[Link] = None


Message = Union[UserMessage, ChannelMessage]
