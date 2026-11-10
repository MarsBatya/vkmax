import asyncio
import io

import aiohttp
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


class TrackingStream(io.BytesIO):
    def __init__(self, data: bytes = b"payload"):
        super().__init__(data)
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        super().close()


class FakeResponse:
    def __init__(self, json_data=None, status=200):
        self.json_data = {} if json_data is None else json_data
        self.status = status
        self.json_calls = 0
        self.read_calls = 0
        self.close_calls = 0
        self.release_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        self.close_calls += 1

    def release(self):
        self.release_calls += 1

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(None, (), status=self.status)

    async def json(self, **kwargs):
        self.json_calls += 1
        return self.json_data

    async def read(self):
        self.read_calls += 1
        return b""


class FakeRequestContext:
    """Awaitable and async context manager, like aiohttp's request context."""

    def __init__(self, response):
        self.response = response

    def __await__(self):
        async def resolve():
            return self.response

        return resolve().__await__()

    async def __aenter__(self):
        return await self.response.__aenter__()

    async def __aexit__(self, exc_type, exc, tb):
        return await self.response.__aexit__(exc_type, exc, tb)


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return FakeRequestContext(self.response)

    async def close(self):
        pass


async def wait_until(predicate):
    async def poll():
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(poll(), timeout=1)


async def test_upload_photo_releases_response_and_keeps_stream_open(make_client):
    client = await make_client(
        responses=[
            {"payload": {"url": "https://upload.example/photo"}},
            {"payload": {}},
        ],
    )
    response = FakeResponse({"photos": {"0": {"token": "photo-token"}}})
    client._http_pool = FakeSession(response)
    stream = TrackingStream()

    attach = await client.upload_photo(123, stream)

    assert attach == {"_type": "PHOTO", "photoToken": "photo-token"}
    assert [packet["opcode"] for packet in client._connection.sent] == [80, 65]
    assert client._http_pool.requests[0][0] == "https://upload.example/photo"
    assert response.json_calls == 1
    assert response.close_calls == 1
    assert stream.close_calls == 0
    stream.close()
    assert stream.close_calls == 1


async def test_upload_video_releases_response_and_keeps_stream_open(make_client):
    client = await make_client(
        responses=[
            {
                "payload": {
                    "info": [
                        {
                            "url": "https://upload.example/video",
                            "videoId": 42,
                            "token": "video-token",
                        },
                    ],
                },
            },
            {"payload": {}},
        ],
    )
    response = FakeResponse()
    client._http_pool = FakeSession(response)
    stream = TrackingStream()

    task = asyncio.create_task(client.upload_video(123, stream))
    await wait_until(lambda: client._video_pending)
    client._connection.push_packet({"opcode": 136, "payload": {"videoId": 42}})
    attach = await asyncio.wait_for(task, timeout=1)

    assert attach == {"_type": "VIDEO", "videoId": 42, "token": "video-token"}
    assert [packet["opcode"] for packet in client._connection.sent] == [82, 65]
    assert client._http_pool.requests[0][0] == "https://upload.example/video"
    assert response.json_calls == 1
    assert response.close_calls == 1
    assert stream.close_calls == 0
    stream.close()
    assert stream.close_calls == 1


async def test_upload_file_releases_response_and_keeps_stream_open(make_client):
    client = await make_client(
        responses=[
            {"payload": {"info": [{"url": "https://upload.example/file", "fileId": 43}]}},
            {"payload": {}},
        ],
    )
    response = FakeResponse()
    client._http_pool = FakeSession(response)
    stream = TrackingStream()

    task = asyncio.create_task(client.upload_file(123, stream, filename="doc.pdf"))
    await wait_until(lambda: client._file_pending)
    client._connection.push_packet({"opcode": 136, "payload": {"fileId": 43}})
    attach = await asyncio.wait_for(task, timeout=1)

    assert attach == {"_type": "FILE", "fileId": 43}
    assert [packet["opcode"] for packet in client._connection.sent] == [87, 65]
    assert client._http_pool.requests[0][0] == "https://upload.example/file"
    assert response.json_calls == 1
    assert response.close_calls == 1
    assert stream.close_calls == 0
    stream.close()
    assert stream.close_calls == 1


async def test_upload_http_error_still_releases_response(make_client):
    client = await make_client(
        responses=[
            {"payload": {"url": "https://upload.example/photo"}},
            {"payload": {}},
        ],
    )
    response = FakeResponse(status=500)
    client._http_pool = FakeSession(response)
    stream = TrackingStream()

    with pytest.raises(aiohttp.ClientResponseError):
        await client.upload_photo(123, stream)

    assert response.json_calls == 0
    assert response.close_calls == 1
    assert stream.close_calls == 0
    stream.close()
    assert stream.close_calls == 1