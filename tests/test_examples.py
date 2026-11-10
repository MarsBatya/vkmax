import asyncio
import importlib.util
import inspect
import re
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from vkmax.client import MaxClient


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MODULES = [
    ("example.py", "packet_callback"),
    ("examples/weather-userbot/main.py", "packet_callback"),
    ("examples/ayumax/main.py", "ayumax_callback"),
]


def make_mock_client():
    client = create_autospec(MaxClient, instance=True)
    for name in ("connect", "send_code", "sign_in", "login_by_token", "edit_message", "send_message"):
        method = inspect.unwrap(getattr(MaxClient, name)).__get__(client, MaxClient)
        setattr(client, name, create_autospec(method))
    client.device_id = "device-id"
    return client


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("relative_path", "callback_name"), EXAMPLE_MODULES)
def test_example_imports(relative_path, callback_name):
    module = load_module(
        ROOT / relative_path,
        f"smoke_{relative_path.replace('/', '_')}",
    )

    assert callable(getattr(module, callback_name))


@pytest.mark.parametrize(
    ("relative_path", "callback_name", "method_name", "text", "status"),
    [
        ("example.py", "packet_callback", "edit_message", ".info", None),
        ("example.py", "packet_callback", "edit_message", ".weather London", None),
        ("example.py", "packet_callback", None, ".weather", None),
        (
            "examples/weather-userbot/main.py",
            "packet_callback",
            "edit_message",
            ".info",
            None,
        ),
        (
            "examples/weather-userbot/main.py",
            "packet_callback",
            "edit_message",
            ".weather London",
            None,
        ),
        ("examples/weather-userbot/main.py", "packet_callback", None, ".weather", None),
        ("examples/ayumax/main.py", "ayumax_callback", None, "hello", None),
        (
            "examples/ayumax/main.py",
            "ayumax_callback",
            "send_message",
            "changed",
            "EDITED",
        ),
        (
            "examples/ayumax/main.py",
            "ayumax_callback",
            "send_message",
            "removed",
            "REMOVED",
        ),
    ],
)
async def test_example_callback_uses_client_method(
    relative_path,
    callback_name,
    method_name,
    text,
    status,
    monkeypatch,
):
    module = load_module(
        ROOT / relative_path,
        f"callback_{relative_path.replace('/', '_')}",
    )
    client = make_mock_client()
    message = {"id": "2", "text": text}
    if status is not None:
        message["status"] = status
    if hasattr(module, "sql"):
        monkeypatch.setattr(module, "sql", AsyncMock(return_value=[("original",)]))
    if text.startswith(".weather"):
        monkeypatch.setattr(
            module,
            "get_weather",
            AsyncMock(return_value="Weather report"),
        )

    await getattr(module, callback_name)(
        client,
        {"opcode": 128, "payload": {"chatId": 1, "message": message}},
    )

    if method_name is None:
        client.send_message.assert_not_awaited()
        client.edit_message.assert_not_awaited()
        if hasattr(module, "sql"):
            module.sql.assert_awaited_once()
        if text == ".weather":
            module.get_weather.assert_not_awaited()
    else:
        getattr(client, method_name).assert_awaited_once()
        assert getattr(client, method_name).await_args.args[0] == 1
        if text.startswith(".weather "):
            assert getattr(client, method_name).await_args.args[-1] == "Weather report"
            module.get_weather.assert_awaited_once_with("London")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (".info", "Userbot connected"),
        (".weather London", "Weather report"),
        (".weather", None),
    ],
)
async def test_readme_callback_uses_client_method(text, expected):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    snippets = re.findall(r"```python\n(.*?)```", readme, re.DOTALL)
    assert snippets
    namespace = {"__name__": "readme_smoke"}
    client = make_mock_client()

    for source in snippets:
        exec(compile(source, "README.md", "exec"), namespace)  # noqa: S102

    namespace["get_weather"] = AsyncMock(return_value="Weather report")
    await namespace["packet_callback"](
        client,
        {"opcode": 128, "payload": {"chatId": 1, "message": {"id": "2", "text": text}}},
    )

    if expected is None:
        client.edit_message.assert_not_awaited()
    else:
        client.edit_message.assert_awaited_once_with(1, "2", expected)


def load_startup_module(relative_path):
    if relative_path != "README.md":
        return load_module(ROOT / relative_path, "startup_example")
    module = ModuleType("readme_smoke")
    readme = (ROOT / relative_path).read_text(encoding="utf-8")
    snippets = re.findall(r"```python\n(.*?)```", readme, re.DOTALL)
    assert snippets
    for source in snippets:
        exec(compile(source, relative_path, "exec"), module.__dict__)  # noqa: S102
    return module


@pytest.fixture(params=["example.py", "examples/weather-userbot/main.py", "README.md"])
def startup_example(request, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    module = load_startup_module(request.param)
    client = make_mock_client()
    client.send_code.return_value = "sms-token"
    client.sign_in.return_value = {"payload": {"tokenAttrs": {"LOGIN": {"token": "new-token"}}}}
    monkeypatch.setattr(module, "MaxClient", MagicMock(return_value=client))
    weather = request.param == "examples/weather-userbot/main.py"
    session_file = tmp_path / ("login_token.txt" if weather else "max_session.txt")
    return module, client, session_file, weather


async def run_until_registered(module, client):
    registered = asyncio.Event()
    client.set_packet_callback.side_effect = lambda callback: registered.set()
    task = asyncio.create_task(module.main())
    try:
        await asyncio.wait_for(registered.wait(), timeout=1)
        client.set_packet_callback.assert_called_once_with(module.packet_callback)
        client.connect.assert_awaited_once_with()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_example_sms_startup(startup_example, monkeypatch):
    module, client, session_file, weather = startup_example
    answers = iter(["+10000000000", "123456"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    await run_until_registered(module, client)

    client.send_code.assert_awaited_once_with("+10000000000")
    client.sign_in.assert_awaited_once_with("sms-token", 123456)
    client.login_by_token.assert_not_awaited()
    assert session_file.read_text() == ("new-token" if weather else "device-id\nnew-token")


async def test_example_saved_token_startup(startup_example, monkeypatch):
    module, client, session_file, weather = startup_example
    session_file.write_text("saved-token" if weather else "saved-device\nsaved-token")
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail("Unexpected SMS prompt"))

    await run_until_registered(module, client)

    if weather:
        client.login_by_token.assert_awaited_once_with("saved-token")
    else:
        client.login_by_token.assert_awaited_once_with("saved-token", "saved-device")
    client.send_code.assert_not_awaited()
    client.sign_in.assert_not_awaited()


async def test_example_rejected_token(startup_example, monkeypatch):
    module, client, session_file, weather = startup_example
    session_file.write_text("bad-token" if weather else "saved-device\nbad-token")
    client.login_by_token.side_effect = ValueError("Rejected token")
    answers = iter(["+10000000000", "123456"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    if weather:
        await run_until_registered(module, client)
        client.send_code.assert_awaited_once_with("+10000000000")
        client.sign_in.assert_awaited_once_with("sms-token", 123456)
        assert session_file.read_text() == "new-token"
    else:
        with pytest.raises(ValueError, match="Rejected token"):
            await asyncio.wait_for(module.main(), timeout=1)
        client.set_packet_callback.assert_not_called()
        client.send_code.assert_not_awaited()


async def test_example_failed_sms_does_not_save_session(startup_example, monkeypatch):
    module, client, session_file, weather = startup_example
    client.sign_in.side_effect = ValueError("Rejected SMS code")
    answers = iter(["+10000000000", "123456"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    with pytest.raises(ValueError, match="Rejected SMS code"):
        await asyncio.wait_for(module.main(), timeout=1)

    assert not session_file.exists()
    client.set_packet_callback.assert_not_called()


@pytest.mark.parametrize("read_fails", [False, True])
async def test_weather_request_closes_resources(startup_example, monkeypatch, read_fails):
    module, client, session_file, weather = startup_example
    response = MagicMock()
    response.__aenter__.return_value = response
    response.text = AsyncMock(return_value="Weather report")
    session = MagicMock()
    session.__aenter__.return_value = session
    session.get.return_value = response
    factory = MagicMock(return_value=session)
    monkeypatch.setattr(module.aiohttp, "ClientSession", factory)

    if read_fails:
        response.text.side_effect = ValueError("Failed response read")
        with pytest.raises(ValueError, match="Failed response read"):
            await module.get_weather("London")
    else:
        assert await module.get_weather("London") == "Weather report"

    factory.assert_called_once_with()
    session.get.assert_called_once_with("https://ru.wttr.in/London?Q&T&format=3")
    response.text.assert_awaited_once_with()
    response.__aexit__.assert_awaited_once()
    session.__aexit__.assert_awaited_once()


def test_weather_example_needs_no_requests_dependency(monkeypatch):
    monkeypatch.setitem(sys.modules, "requests", None)
    load_module(ROOT / "examples/weather-userbot/main.py", "weather_without_requests")
