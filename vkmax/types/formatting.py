
from typing import Literal, NotRequired, TypedDict

class Attributes(TypedDict):
    url: NotRequired[str] # for link
    animojiSetId: NotRequired[str]
    animojiLottieUrl: NotRequired[str]


Element = TypedDict(
    "Element",
    {
        "type": Literal[
            "LINK",
            "STRONG",
            "EMPHASIZED",
            "UNDERLINE",
            "STRIKETHROUGH",
            "QUOTE",
            "ANIMOJI",
            "HEADING",
            "MONOSPACED",
            "USER_MENTION",
        ],
        "from": NotRequired[int],
        "length": int,
        "attributes": NotRequired[Attributes],
        "entityId": NotRequired[int],
        "entityName": NotRequired[str],
    },
)
