
"""
HTML parser/unparser for converting between formatted HTML text and
(clean_text, elements) pairs suitable for messaging/rich-text APIs.

UTF-16 code unit offsets are used throughout, as many APIs (especially
mobile/messaging ones) count string positions this way to handle emojis correctly.
"""

import io
from html import escape
from html.parser import HTMLParser

from vkmax.types.formatting import Element


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maps HTML tags → element type
_TAG_TO_TYPE: dict[str, str] = {
    "a": "LINK",
    "b": "STRONG",
    "strong": "STRONG",
    "i": "EMPHASIZED",
    "em": "EMPHASIZED",
    "u": "UNDERLINE",
    "ins": "UNDERLINE",
    "s": "STRIKETHROUGH",
    "strike": "STRIKETHROUGH",
    "del": "STRIKETHROUGH",
    "blockquote": "QUOTE",
}

# Maps element type → preferred HTML tag for unparsing
_TYPE_TO_TAG: dict[str, str] = {
    "LINK": "a",
    "STRONG": "b",
    "EMPHASIZED": "i",
    "UNDERLINE": "u",
    "STRIKETHROUGH": "s",
    "QUOTE": "blockquote",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _char_utf16_units(ch: str) -> int:
    """Return the number of UTF-16 code units a single character occupies.

    BMP characters (U+0000–U+FFFF) → 1 unit (2 bytes).
    Supplementary characters (U+10000+, e.g. most emoji) → 2 units (4 bytes).
    """
    return 2 if ord(ch) > 0xFFFF else 1


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _HTMLParser(HTMLParser):
    """Internal stateful parser; create a fresh instance per parse call."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._text_buf = io.StringIO()
        self._utf16_pos: int = 0  # incrementally tracked; avoids re-encoding
        self.elements: list[Element] = []
        self._stack: list[dict] = []  # open-tag frames waiting to be closed

    # ------------------------------------------------------------------
    # HTMLParser callbacks
    # ------------------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element_type = _TAG_TO_TYPE.get(tag)
        if element_type is None:
            return

        frame: dict = {"type": element_type, "from": self._utf16_pos}

        if tag == "a":
            for attr_name, attr_value in attrs:
                if attr_name == "href" and attr_value is not None:
                    frame["attributes"] = {"url": attr_value}
                    break

        self._stack.append(frame)

    def handle_endtag(self, tag: str) -> None:
        element_type = _TAG_TO_TYPE.get(tag)
        if element_type is None:
            return

        # Find the most-recently opened frame of the same type and close it.
        # Iterating in reverse handles nested identical tags correctly.
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["type"] == element_type:
                frame = self._stack.pop(i)
                frame["length"] = self._utf16_pos - frame.get("from", 0)
                self.elements.append(frame)  # type: ignore[arg-type]
                break

    def handle_data(self, data: str) -> None:
        self._text_buf.write(data)
        # Update position incrementally — O(len(data)) per call, not O(total text).
        for ch in data:
            self._utf16_pos += _char_utf16_units(ch)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_text(html: str) -> tuple[str, list[Element]]:
    """Parse *html* and return ``(clean_text, elements)``.

    *clean_text* is the plain text with all HTML tags stripped.
    *elements* is a list of formatting elements sorted by their ``from`` offset,
    using UTF-16 code unit positions so that multi-codepoint characters (emoji)
    are counted the same way JavaScript / most mobile runtimes would.
    """
    parser = _HTMLParser()
    parser.feed(html)
    clean_text = parser._text_buf.getvalue()
    elements = sorted(parser.elements, key=lambda e: (e.get("from", 0), e["length"]))
    return clean_text, elements


def unparse_text(clean_text: str, elements: list[Element]) -> str:
    """Reconstruct an HTML string from *clean_text* and *elements*.

    This is the inverse of :func:`parse_text`.  HTML special characters in the
    plain text are escaped; URLs in link attributes are also escaped.

    Nesting is handled by emitting close tags before open tags at the same
    position, and opening wider (longer) spans before narrower ones so that
    the resulting HTML is as well-formed as possible.
    """
    if not elements:
        return escape(clean_text)

    # Build a flat event list: (utf16_pos, sort_key, html_fragment).
    #
    # Sort order at the same position:
    #   1. Closes before opens  (0 < 1)
    #   2. Among closes:  shorter spans close first (inner-most out first)
    #   3. Among opens:   longer spans open first  (outer-most in first)
    #
    # Tuple: (pos, open_flag, tiebreak, fragment)
    events: list[tuple[int, int, int, str]] = []

    for elem in elements:
        tag = _TYPE_TO_TAG[elem["type"]]
        start = elem.get("from", 0)
        end = start + elem["length"]
        length = elem["length"]

        if elem["type"] == "LINK":
            url = escape(elem.get("attributes", {}).get("url", ""), quote=True)
            open_frag = f'<a href="{url}">'
        else:
            open_frag = f"<{tag}>"
        close_frag = f"</{tag}>"

        events.append((start, 1, -length, open_frag))  # open:  wider spans first
        events.append((end, 0, length, close_frag))  # close: shorter spans first

    events.sort(key=lambda e: (e[0], e[1], e[2]))

    # Walk through clean_text, injecting HTML fragments at the right UTF-16 offsets.
    result: list[str] = []
    utf16_pos = 0
    event_idx = 0
    total_events = len(events)

    for ch in clean_text:
        # Flush all events whose position equals the current UTF-16 cursor.
        while event_idx < total_events and events[event_idx][0] == utf16_pos:
            result.append(events[event_idx][3])
            event_idx += 1

        result.append(escape(ch))
        utf16_pos += _char_utf16_units(ch)

    # Flush any trailing events (tags that close at the very end of the string).
    while event_idx < total_events:
        result.append(events[event_idx][3])
        event_idx += 1

    return "".join(result)


# ---------------------------------------------------------------------------
# Demo / smoke-test
# ---------------------------------------------------------------------------


def main() -> None:
    import ujson as json

    sample_html = (
        "Тестовый пост\n\n"
        "<a href='https://google.com'>Ссылка\n🐭 тут</a>\n\n\n"
        "<b>Жирный текст 😄тут</b>\n\n"
        "<i>Италик 😵‍💫тут</i>\n\n"
        "<u>Подчеркнутый💪💪 тут</u>\n\n"
        "<s>Зачеркнутый тут</s>\n"
        "<blockquote>Цита🦁та тут</blockquote>\n"
        "test"
    )

    print("=== PARSE ===")
    clean_text, elements = parse_text(sample_html)
    print(
        json.dumps(
            {"text": clean_text, "elements": elements},
            ensure_ascii=False,
            indent=4,
        ),
    )

    print("\n=== UNPARSE (round-trip) ===")
    reconstructed = unparse_text(clean_text, elements)
    print(reconstructed)

    print("\n=== ROUND-TRIP CHECK ===")
    clean_text2, elements2 = parse_text(reconstructed)
    match = clean_text2 == clean_text and elements2 == elements
    print(f"clean_text match : {clean_text2 == clean_text}")
    print(f"elements  match  : {elements2 == elements}")
    print(f"Full round-trip  : {'✓ OK' if match else '✗ MISMATCH'}")


if __name__ == "__main__":
    main()
