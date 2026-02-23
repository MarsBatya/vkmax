from dataclasses import dataclass

from typing import Literal, Optional, Union

from vkmax.types.enums import AttributedElementType, SimpleElementType
# ---------------- Elements ----------------


@dataclass(slots=True)
class AnimojiAttributes:
    animoji_set_id: str
    animoji_lottie_url: str


@dataclass(slots=True)
class AnimojiElement:
    length: int
    entity_id: int
    attributes: AnimojiAttributes
    element_type: Literal[AttributedElementType.ANIMOJI]
    start_from: Optional[int] = None


@dataclass(slots=True)
class UrlAttributes:
    url: str


@dataclass(slots=True)
class UrlElement:
    attributes: UrlAttributes
    length: int
    element_type: Literal[AttributedElementType.LINK]
    start_from: Optional[int] = None


@dataclass(slots=True)
class TextElement:
    length: int
    element_type: SimpleElementType
    entity_id: Optional[int] = None
    start_from: Optional[int] = None
    entity_name: Optional[str] = None


MessageElement = Union[UrlElement, AnimojiElement, TextElement]
