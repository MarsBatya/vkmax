"""Binary WebSocket framing for the MAX protocol (version 10).

Frame layout (big-endian):
    ver u8 | cmd u8 | seq i16 | opcode i16 | ratio u8 | payload length u24 | payload

The payload is MessagePack; bodies larger than 32 bytes are LZ4-block
compressed (no size prefix) and ``ratio`` is ceil(original / compressed),
capped at 255. BigInt values travel as ext type 1 wrapping a msgpack int64.
"""

from typing import Any

import lz4.block
import msgpack

PROTOCOL_VERSION = 10
HEADER_SIZE = 10
COMPRESS_THRESHOLD = 32
BIGINT_EXT_TYPE = 1
MAX_SEQ = 32767


class PacketDecodeError(ValueError):
    """A frame could not be decoded."""


def pack_bigint(value: int) -> msgpack.ExtType:
    return msgpack.ExtType(BIGINT_EXT_TYPE, msgpack.packb(value, use_bin_type=True))


def _ext_hook(code: int, data: bytes) -> Any:
    if code == BIGINT_EXT_TYPE:
        return msgpack.unpackb(data, raw=False, strict_map_key=False)
    return msgpack.ExtType(code, data)


def encode_packet(cmd: int, seq: int, opcode: int, payload: Any) -> bytes:
    body = msgpack.packb(payload, use_bin_type=True)
    ratio = 0
    if len(body) > COMPRESS_THRESHOLD:
        compressed = lz4.block.compress(body, store_size=False)
        ratio = min(-(-len(body) // len(compressed)), 255)
        body = compressed
    header = (
        bytes([PROTOCOL_VERSION, cmd])
        + seq.to_bytes(2, "big", signed=True)
        + opcode.to_bytes(2, "big", signed=True)
        + bytes([ratio])
        + len(body).to_bytes(3, "big")
    )
    return header + body


def decode_packet(data: bytes | str) -> dict[str, Any]:
    if isinstance(data, str):
        raise PacketDecodeError("expected a binary frame")
    if len(data) < HEADER_SIZE:
        raise PacketDecodeError("frame shorter than header")
    n = int.from_bytes(data[7:10], "big")
    body = data[HEADER_SIZE : HEADER_SIZE + n]
    if len(body) != n:
        raise PacketDecodeError("truncated frame")
    ratio = data[6]
    try:
        if ratio:
            body = lz4.block.decompress(body, uncompressed_size=n * ratio)
        payload = (
            msgpack.unpackb(body, raw=False, strict_map_key=False, ext_hook=_ext_hook)
            if n
            else None
        )
    except (ValueError, lz4.block.LZ4BlockError) as err:
        raise PacketDecodeError(str(err)) from err
    return {
        "ver": data[0],
        "cmd": data[1],
        "seq": int.from_bytes(data[2:4], "big", signed=True),
        "opcode": int.from_bytes(data[4:6], "big", signed=True),
        "payload": payload,
    }
