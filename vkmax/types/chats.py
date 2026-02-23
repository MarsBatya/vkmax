
from dataclasses import dataclass
from typing import Optional

from vkmax.types.messages import Message


# ---------------- Chat Structures ----------------

@dataclass(slots=True)
class ChatOptions:
    SIGN_ADMIN: bool
    OFFICIAL: bool
    MESSAGE_COPY_NOT_ALLOWED: bool
    ONLY_OWNER_CAN_CHANGE_ICON_TITLE: bool
    ONLY_ADMIN_CAN_ADD_MEMBER: bool
    ONLY_ADMIN_CAN_CALL: bool
    MEMBERS_CAN_SEE_PRIVATE_LINK: bool
    SENT_BY_PHONE: bool
    A_PLUS_CHANNEL: bool
    ALL_CAN_PIN_MESSAGE: bool


@dataclass(slots=True)
class AdminParticipant:
    permissions: int
    id: int


@dataclass(slots=True)
class ChatReactions:
    is_active: bool
    update_time: int


@dataclass(slots=True)
class Chat:
    participants_count: int
    access: str
    type: str
    title: str
    last_fire_delayed_error_time: int
    last_delayed_update_time: int
    options: ChatOptions
    modified: int
    id: int
    admin_participants: dict[str, AdminParticipant]
    participants: dict[str, int]
    owner: int
    join_time: int
    created: int
    last_message: Message
    last_event_time: int
    reactions: ChatReactions
    messages_count: int
    admins: list[int]
    status: str
    cid: int
    pinned_message: Optional[Message] = None
