import sys
from typing import Literal, TypedDict

if sys.version_info >= (3, 11):
    from typing import NotRequired
else:
    from typing_extensions import NotRequired


class Attributes(TypedDict):
    url: NotRequired[str]  # for link
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
