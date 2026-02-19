
from typing import Literal, NotRequired, TypedDict

class Attributes(TypedDict):
    url: str


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
        ],
        "from": NotRequired[int],
        "length": int,
        "attributes": NotRequired[Attributes],
    },
)