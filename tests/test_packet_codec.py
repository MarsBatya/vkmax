import lz4.block
import msgpack
import pytest

from vkmax.packet_codec import (
    BIGINT_EXT_TYPE,
    COMPRESS_THRESHOLD,
    HEADER_SIZE,
    PROTOCOL_VERSION,
    PacketDecodeError,
    decode_packet,
    encode_packet,
    pack_bigint,
)


def frame_body(frame: bytes) -> bytes:
    n = int.from_bytes(frame[7:10], "big")
    body = frame[HEADER_SIZE : HEADER_SIZE + n]
    if frame[6]:
        body = lz4.block.decompress(body, uncompressed_size=n * frame[6])
    return body


def test_round_trip_uncompressed():
    payload = {"interactive": False}
    frame = encode_packet(0, 1, 1, payload)

    assert frame[0] == PROTOCOL_VERSION
    assert frame[1] == 0
    assert frame[6] == 0
    assert decode_packet(frame) == {
        "ver": PROTOCOL_VERSION,
        "cmd": 0,
        "seq": 1,
        "opcode": 1,
        "payload": payload,
    }


def test_round_trip_compressed():
    payload = {"text": "hello " * 100, "items": list(range(100))}
    frame = encode_packet(0, 5, 64, payload)

    assert frame[6] > 0
    assert len(frame) - HEADER_SIZE < len(msgpack.packb(payload, use_bin_type=True))
    assert decode_packet(frame) == {
        "ver": PROTOCOL_VERSION,
        "cmd": 0,
        "seq": 5,
        "opcode": 64,
        "payload": payload,
    }


def test_compression_threshold_boundary():
    exact = "a" * (COMPRESS_THRESHOLD - 1)
    assert len(msgpack.packb(exact, use_bin_type=True)) == COMPRESS_THRESHOLD
    assert encode_packet(0, 0, 0, exact)[6] == 0

    over = b"a" * (COMPRESS_THRESHOLD - 1)
    assert len(msgpack.packb(over, use_bin_type=True)) == COMPRESS_THRESHOLD + 1
    frame = encode_packet(0, 0, 0, over)
    assert frame[6] > 0
    assert decode_packet(frame)["payload"] == over


def test_ratio_is_capped_at_255():
    payload = b"\x00" * 1000000
    frame = encode_packet(0, 0, 0, payload)

    assert frame[6] == 255
    assert decode_packet(frame)["payload"] == payload


@pytest.mark.parametrize("value", [0, 1732000000000, 2**53, 2**62, -(2**62)])
def test_bigint_ext_round_trip(value):
    frame = encode_packet(0, 0, 6, {"clientSessionId": pack_bigint(value)})

    assert decode_packet(frame)["payload"] == {"clientSessionId": value}


def test_bigint_is_ext_type_1_on_wire():
    value = 1732000000000
    frame = encode_packet(0, 0, 6, {"clientSessionId": pack_bigint(value)})

    raw = msgpack.unpackb(frame_body(frame), raw=False, strict_map_key=False)
    ext = raw["clientSessionId"]
    assert isinstance(ext, msgpack.ExtType)
    assert ext.code == BIGINT_EXT_TYPE
    assert msgpack.unpackb(ext.data) == value


def test_seq_and_opcode_are_signed_int16():
    frame = encode_packet(0, 32767, 6, {})
    assert frame[2:4] == b"\x7f\xff"
    assert decode_packet(frame)["seq"] == 32767

    frame = encode_packet(1, -1, -2, {})
    assert decode_packet(frame) == {
        "ver": PROTOCOL_VERSION,
        "cmd": 1,
        "seq": -1,
        "opcode": -2,
        "payload": {},
    }


def test_seq_overflow_is_rejected():
    with pytest.raises(OverflowError):
        encode_packet(0, 32768, 6, {})


def test_decode_tolerates_integer_map_keys():
    frame = encode_packet(1, 0, 6, {1: "x", 2: {"y": 1}})

    assert decode_packet(frame)["payload"] == {1: "x", 2: {"y": 1}}


def test_empty_body_decodes_to_none():
    frame = bytes([PROTOCOL_VERSION, 1, 0, 0, 0, 6, 0, 0, 0, 0])

    assert decode_packet(frame) == {
        "ver": PROTOCOL_VERSION,
        "cmd": 1,
        "seq": 0,
        "opcode": 6,
        "payload": None,
    }


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x0a",
        "text frame",
        b"\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x05abc",
        b"\x0a\x00\x00\x00\x00\x00\x00\x00\x00\x01\xc1",
        b"\x0a\x00\x00\x00\x00\x00\x01\x00\x00\x02\xff\xff",
    ],
)
def test_malformed_frames_raise(data):
    with pytest.raises(PacketDecodeError):
        decode_packet(data)
