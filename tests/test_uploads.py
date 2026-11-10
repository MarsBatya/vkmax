import pytest


@pytest.mark.parametrize(
    "payload",
    [
        {
            "cache": "https://cdn.example/cache",
            "EXTERNAL": "https://external.example/video",
            "MP4_240": "https://cdn.example/240",
            "MP4_720": "https://cdn.example/720",
            "MP4_1080": "https://cdn.example/1080",
        },
        {
            "MP4_1080": "https://cdn.example/1080",
            "MP4_240": "https://cdn.example/240",
            "MP4_720": "https://cdn.example/720",
        },
    ],
)
async def test_download_video_selects_highest_resolution(make_client, payload):
    client = await make_client(responses=[{"payload": payload}])

    url = await client.download_video(123, "456", 789)

    assert url == "https://cdn.example/1080"
    assert client._connection.sent[0]["opcode"] == 83
    assert client._connection.sent[0]["payload"] == {
        "videoId": 789,
        "chatId": 123,
        "messageId": "456",
    }


@pytest.mark.parametrize(
    ("first", "second"),
    [("MP4_720", "HLS_720"), ("HLS_720", "MP4_720")],
)
async def test_download_video_resolution_tie_is_deterministic(make_client, first, second):
    urls = {"MP4_720": "https://cdn.example/mp4", "HLS_720": "https://cdn.example/hls"}
    payload = {first: urls[first], second: urls[second]}
    client = await make_client(responses=[{"payload": payload}])

    url = await client.download_video(123, "456", 789)

    assert url == "https://cdn.example/mp4"


async def test_download_video_unnumbered_keys_are_deterministic(make_client):
    payload = {
        "cache": "https://cdn.example/cache",
        "DASH": "https://cdn.example/dash",
        "HLS": "https://cdn.example/hls",
    }
    client = await make_client(responses=[{"payload": payload}])

    url = await client.download_video(123, "456", 789)

    assert url == "https://cdn.example/hls"


@pytest.mark.parametrize("payload", [{}, {"cache": "x", "EXTERNAL": "y"}])
async def test_download_video_without_formats_raises(make_client, payload):
    client = await make_client(responses=[{"payload": payload}])

    with pytest.raises(ValueError, match="no downloadable formats"):
        await client.download_video(123, "456", 789)


async def test_download_video_missing_response(make_client, monkeypatch):
    client = await make_client()

    async def invoke_method(**kwargs):
        return None

    monkeypatch.setattr(client, "invoke_method", invoke_method)

    with pytest.raises(ValueError, match="Video not found"):
        await client.download_video(123, "456", 789)