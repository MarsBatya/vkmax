from dataclasses import dataclass

from typing import Literal, Optional, Union

from vkmax.types.enums import AttachmentType, PreviewType, ButtonType

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


Attachment = Union[
    AttachedPhoto,
    AttachedSticker,
    AttachedVideo,
    AttachedFile,
    AttachedKeyboard,
]