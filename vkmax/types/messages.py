from dataclasses import dataclass

from typing import Literal, Optional, Union

from vkmax.types.enums import LinkType, ChatAccess, MessageType, MessageStatus, AttachmentType, PreviewType, ButtonType
from vkmax.types.elements import MessageElement




@dataclass(slots=True)
class AttachedPhoto:
    base_url: str
    photo_token: str
    width: int
    photo_id: int
    height: int
    _type: Literal[AttachmentType.PHOTO]
    preview_data: Optional[str] = None

@dataclass(slots=True)
class SimpleImage:
    _type: Literal[AttachmentType.PHOTO]
    width: int
    height: int
    url: str

@dataclass(slots=True)
class AttachedShare:
    _type: Literal[AttachmentType.SHARE]
    description: str
    content_level: bool
    share_id: int
    title: str
    url: str
    image: Optional[SimpleImage] = None

@dataclass(slots=True)
class AttachedSticker:
    author_type: str
    width: int
    set_id: int
    time: int
    sticker_type: str
    audio: bool
    lottie_url: str
    url: str
    sticker_id: int
    height: int
    _type: Literal[AttachmentType.STICKER]


@dataclass(slots=True)
class AttachedVideo:
    preview_data: str
    duration: int
    thumbnail: str
    video_type: int
    _type: Literal[AttachmentType.VIDEO]
    width: int
    video_id: int
    token: str
    height: int


@dataclass(slots=True)
class AudioPreview:
    duration: int
    preview_data: str
    album_name: str
    base_url: str
    track_id: int
    _type: Literal[PreviewType.MUSIC]
    artist_name: str
    title: str


@dataclass(slots=True)
class VideoPreview:
    duration: int
    preview_data: str
    thumbnail: str
    _type: Literal[PreviewType.VIDEO]
    width: int
    video_id: int
    height: int


@dataclass(slots=True)
class PhotoPreview:
    preview_data: str
    base_url: str
    _type: Literal[PreviewType.PHOTO]
    width: int
    photo_id: int
    height: int


Preview = Union[AudioPreview, VideoPreview, PhotoPreview]


@dataclass(slots=True)
class AttachedFile:
    size: int
    _type: Literal[AttachmentType.FILE]
    name: str
    file_id: int
    token: str
    preview: Optional[Preview] = None


@dataclass
class Button:
    button_type: ButtonType
    text: str
    url: Optional[str] = None  # for url buttons
    payload: Optional[str] = None  # for callbacks
    intent: Optional[str] = None  # for callbacks


@dataclass(slots=True)
class Keyboard:
    buttons: list[list[Button]]


@dataclass(slots=True)
class AttachedKeyboard:
    _type: Literal[AttachmentType.INLINE_KEYBOARD]
    keyboard: Keyboard
    callback_id: str

@dataclass(slots=True)
class AttachedControl:
    _type: Literal[AttachmentType.CONTROL]
    event: str
    pinned_message: "Message"

Attachment = Union[
    AttachedPhoto,
    AttachedSticker,
    AttachedVideo,
    AttachedFile,
    AttachedKeyboard,
    AttachedControl,
    AttachedShare,
]

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
class DelayedAttributes:
    notify_opponents: bool
    notify_sender: bool
    time_to_fire: int

@dataclass(slots=True)
class ReactionCounter:
    count: int
    reaction: str

@dataclass(slots=True)
class ReactionInfo:
    counters: Optional[list[ReactionCounter]] = None
    your_reaction: Optional[str] = None
    total_count: Optional[int] = None

@dataclass(slots=True)
class UserMessage:
    sender: int
    message_id: str
    timestamp: int
    text: str
    message_type: Literal[MessageType.USER]
    attaches: list[Attachment]
    reaction_info: Optional[ReactionInfo] = None
    stats: Optional[Stats] = None
    status: Optional[MessageStatus] = None
    update_time: Optional[int] = None
    options: Optional[int] = None
    cid: Optional[int] = None
    elements: Optional[list[MessageElement]] = None
    link: Optional[Link] = None
    delayed_attributes: Optional[DelayedAttributes] = None


@dataclass(slots=True)
class ChannelMessage:
    message_id: str
    timestamp: int
    text: str
    message_type: Literal[MessageType.CHANNEL]
    attaches: list[Attachment]
    reaction_info: Optional[ReactionInfo] = None
    sender: Optional[int] = None
    options: Optional[int] = None
    status: Optional[MessageStatus] = None
    update_time: Optional[int] = None
    stats: Optional[Stats] = None
    cid: Optional[int] = None
    elements: Optional[list[MessageElement]] = None
    link: Optional[Link] = None
    reaction_info: Optional[ReactionInfo] = None
    delayed_attributes: Optional[DelayedAttributes] = None


Message = Union[UserMessage, ChannelMessage]
