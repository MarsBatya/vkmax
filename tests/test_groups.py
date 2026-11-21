import pytest


@pytest.mark.parametrize(
    ("deleting_messages", "control_participants", "control_admins", "permissions"),
    [
        (False, False, False, 120),
        (True, False, False, 121),
        (False, True, False, 250),
        (True, True, False, 251),
        (False, False, True, 124),
        (True, False, True, 125),
        (False, True, True, 254),
        (True, True, True, 255),
    ],
)
async def test_add_admin_permissions(
    make_client,
    deleting_messages,
    control_participants,
    control_admins,
    permissions,
):
    client = await make_client()

    await client.add_admin(
        123,
        [456],
        deleting_messages=deleting_messages,
        control_participants=control_participants,
        control_admins=control_admins,
    )

    packet = client._connection.sent[0]
    assert packet["opcode"] == 77
    assert packet["payload"] == {
        "chatId": 123,
        "userIds": [456],
        "type": "ADMIN",
        "operation": "add",
        "permissions": permissions,
    }


async def test_remove_admin_requires_admin_ids(make_client):
    client = await make_client()

    with pytest.raises(TypeError, match="admin_ids"):
        client.remove_admin(123)


async def test_remove_admin_payload(make_client):
    client = await make_client()

    await client.remove_admin(123, [456, 789])

    assert client._connection.sent == [
        {
            "cmd": 0,
            "seq": 1,
            "opcode": 77,
            "payload": {
                "chatId": 123,
                "userIds": [456, 789],
                "type": "ADMIN",
                "operation": "remove",
            },
        },
    ]


@pytest.mark.parametrize(
    ("new_group_name", "new_description", "expected_fields"),
    [
        ("New name", None, {"theme": "New name"}),
        (None, "New description", {"description": "New description"}),
        (
            "New name",
            "New description",
            {"theme": "New name", "description": "New description"},
        ),
        ("", "", {"theme": "", "description": ""}),
    ],
)
async def test_change_group_profile_payload(
    make_client,
    new_group_name,
    new_description,
    expected_fields,
):
    client = await make_client()

    await client.change_group_profile(
        123,
        new_group_name=new_group_name,
        new_description=new_description,
    )

    assert len(client._connection.sent) == 1
    packet = client._connection.sent[0]
    assert packet["opcode"] == 55
    assert packet["payload"] == {"chatId": 123, **expected_fields}


async def test_change_group_profile_without_fields_sends_nothing(make_client):
    client = await make_client()

    result = await client.change_group_profile(123)

    assert result is None
    assert client._connection.sent == []


async def test_join_group_only_subscribes_to_joined_chat(make_client):
    client = await make_client(
        responses=[{"payload": {"chat": {"id": 123, "cid": 456}}}],
    )

    await client.join_group_by_link("invite-hash")

    assert [
        (packet["opcode"], packet["payload"]) for packet in client._connection.sent
    ] == [
        (57, {"link": "join/invite-hash"}),
        (75, {"chatId": 123, "subscribe": True}),
        (
            49,
            {
                "chatId": 123,
                "from": 456,
                "forward": 0,
                "backward": 30,
                "getMessages": True,
            },
        ),
    ]
