import logging

import pytest

from vkmax.raw_client import MaxClient as RawClient

from test_lifecycle import wait_until

PHONE = "+79991234567"
SMS_TOKEN = "sms-token-secret-abc123"  # noqa: S105
SMS_CODE = "123456"
LOGIN_TOKEN = "login-token-secret-xyz789"  # noqa: S105
USER_ID = 424242

LOGGER_NAME = "vkmax.raw_client"


def logged_text(caplog, level=None):
    records = caplog.records
    if level is not None:
        records = [record for record in records if record.levelno == level]
    return "\n".join(record.getMessage() for record in records)


async def test_sms_login_info_logs_hide_credentials(make_client, caplog):
    client = await make_client(
        RawClient,
        responses=[
            {"opcode": 6, "payload": {}},
            {"opcode": 17, "payload": {"token": SMS_TOKEN}},
            {
                "opcode": 18,
                "payload": {
                    "tokenAttrs": {"LOGIN": {"token": LOGIN_TOKEN}},
                    "profile": {"contact": {"id": USER_ID, "phone": PHONE}},
                },
            },
            {"opcode": 1, "payload": {}},
        ],
    )

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        sms_token = await client.send_code(PHONE)
        response = await client.sign_in(sms_token, int(SMS_CODE))
    await client.disconnect()

    assert sms_token == SMS_TOKEN
    assert response["payload"]["tokenAttrs"]["LOGIN"]["token"] == LOGIN_TOKEN

    text = logged_text(caplog)
    for secret in (PHONE, SMS_TOKEN, LOGIN_TOKEN, SMS_CODE):
        assert secret not in text
    assert "opcode=17" in text
    assert "opcode=18" in text
    assert any(
        "Successfully logged in" in record.getMessage()
        and str(USER_ID) in record.getMessage()
        for record in caplog.records
    )


async def test_token_login_info_logs_hide_credentials(make_client, caplog):
    client = await make_client(
        RawClient,
        responses=[
            {"opcode": 6, "payload": {}},
            {
                "opcode": 19,
                "payload": {"profile": {"contact": {"id": USER_ID, "phone": PHONE}}},
            },
            {"opcode": 1, "payload": {}},
        ],
    )

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await client.login_by_token(LOGIN_TOKEN)
    await client.disconnect()

    text = logged_text(caplog)
    for secret in (PHONE, LOGIN_TOKEN):
        assert secret not in text
    assert "opcode=19" in text


@pytest.mark.parametrize(
    ("response_payload", "expected_status"),
    [({}, "ok"), ({"error": "forbidden"}, "error")],
)
async def test_info_logs_keep_metadata_without_payload(
    make_client, caplog, response_payload, expected_status
):
    client = await make_client(
        RawClient, responses=[{"opcode": 64, "payload": response_payload}]
    )

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await client.invoke_method(
            opcode=64, payload={"chatId": 1, "token": LOGIN_TOKEN}
        )

    info_text = logged_text(caplog, logging.INFO)
    assert "opcode=64" in info_text
    assert "seq=1" in info_text
    assert f"status={expected_status}" in info_text
    assert "payload" not in info_text
    assert LOGIN_TOKEN not in info_text


async def test_debug_logs_show_redacted_payloads(make_client, caplog):
    client = await make_client(
        RawClient,
        responses=[
            {
                "opcode": 19,
                "payload": {
                    "token": SMS_TOKEN,
                    "profile": {"contact": {"phone": PHONE}},
                },
            },
        ],
    )

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        await client.invoke_method(
            opcode=19,
            payload={
                "token": LOGIN_TOKEN,
                "phone": PHONE,
                "verifyCode": SMS_CODE,
                "interactive": True,
            },
        )

    text = logged_text(caplog)
    for secret in (PHONE, SMS_TOKEN, LOGIN_TOKEN, SMS_CODE):
        assert secret not in text
    debug_text = logged_text(caplog, logging.DEBUG)
    assert "<redacted>" in debug_text
    assert "interactive" in debug_text
    assert client._connection.sent[0]["payload"]["token"] == LOGIN_TOKEN


def test_redact_masks_sensitive_keys_recursively():
    from vkmax.raw_client import _redact

    payload = {
        "token": SMS_TOKEN,
        "phone": PHONE,
        "verifyCode": SMS_CODE,
        "tokenAttrs": {"LOGIN": {"token": LOGIN_TOKEN}},
        "profile": {"contact": {"id": USER_ID, "phone": PHONE}},
        "attaches": [{"token": SMS_TOKEN, "type": "video"}],
        "interactive": True,
    }

    redacted = _redact(payload)

    assert redacted == {
        "token": "<redacted>",
        "phone": "<redacted>",
        "verifyCode": "<redacted>",
        "tokenAttrs": {"LOGIN": {"token": "<redacted>"}},
        "profile": {"contact": {"id": USER_ID, "phone": "<redacted>"}},
        "attaches": [{"token": "<redacted>", "type": "video"}],
        "interactive": True,
    }
    assert payload["token"] == SMS_TOKEN
    assert payload["profile"]["contact"]["phone"] == PHONE


async def test_push_event_debug_log_is_redacted(make_client, caplog):
    client = await make_client(RawClient, auto_reply=False)
    received = []

    async def callback(_client, packet):
        received.append(packet)

    client.set_packet_callback(callback)
    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        client._connection.push_packet(
            {
                "opcode": 128,
                "payload": {
                    "chatId": 1,
                    "token": SMS_TOKEN,
                    "message": {"id": "2", "text": "hi", "phone": PHONE},
                },
            }
        )
        await wait_until(lambda: received)

    debug_text = logged_text(caplog, logging.DEBUG)
    assert "<- EVENT" in debug_text
    assert "<redacted>" in debug_text
    for secret in (PHONE, SMS_TOKEN):
        assert secret not in debug_text
    assert received[0]["payload"]["token"] == SMS_TOKEN
