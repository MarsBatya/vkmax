
from enum import Enum

# ---------------- Enums ----------------


class MessageType(str, Enum):
    USER = "USER"
    CHANNEL = "CHANNEL"


class LinkType(str, Enum):
    FORWARD = "FORWARD"
    REPLY = "REPLY"


class SimpleElementType(str, Enum):
    STRONG = "STRONG"
    EMPHASIZED = "EMPHASIZED"
    UNDERLINE = "UNDERLINE"
    STRIKETHROUGH = "STRIKETHROUGH"
    QUOTE = "QUOTE"
    HEADING = "HEADING"
    MONOSPACED = "MONOSPACED"
    USER_MENTION = "USER_MENTION"


class AttributedElementType(str, Enum):
    LINK = "LINK"
    ANIMOJI = "ANIMOJI"


class AttachmentType(str, Enum):
    PHOTO = "PHOTO"
    STICKER = "STICKER"
    VIDEO = "VIDEO"
    FILE = "FILE"
    INLINE_KEYBOARD = "INLINE_KEYBOARD"
    CONTROL = "CONTROL"
    SHARE = "SHARE"


class ButtonType(str, Enum):
    MESSAGE = "MESSAGE"
    LINK = "LINK"
    TYPE = "CALLBACK"


class PreviewType(str, Enum):
    MUSIC = "MUSIC"
    VIDEO = "VIDEO"
    PHOTO = "PHOTO"


class MessageStatus(str, Enum):
    EDITED = "EDITED"
    REMOVED = "REMOVED"


class ChatAccess(str, Enum):
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"
