import asyncio
import itertools
import logging
import ssl
import sys
import time
import uuid
from copy import deepcopy
from functools import wraps
from typing import Any, Awaitable, Callable, Coroutine, Optional, TypedDict, TypeVar

if sys.version_info >= (3, 11):
    from typing import NotRequired
else:
    from typing_extensions import NotRequired

import aiohttp
import websockets
from python_socks.async_.asyncio import Proxy
from websockets.asyncio.client import ClientConnection

from vkmax.packet_codec import (
    MAX_SEQ,
    PacketDecodeError,
    decode_packet,
    encode_packet,
    pack_bigint,
)

WS_HOST = "wss://api.oneme.ru/websocket"
APP_VERSION = "26.11.9"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"  # noqa: E501

_logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = frozenset({"token", "phone", "verifyCode"})


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "<redacted>" if key in _SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


Coro = TypeVar("Coro", bound=Callable[..., Awaitable])


class RpcError(Exception):
    """Server error packet (cmd=3)."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(payload.get("message") or payload.get("error") or "RPC error")


PacketCallback = Callable[["MaxClient", dict[str, Any]], Coroutine[Any, Any, Any]]
ReconnectCallback = Callable[[], Coroutine[Any, Any, Any]]


def ensure_connected(method: Coro) -> Coro:
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if self._connection is None:
            raise RuntimeError("WebSocket not connected. Call .connect() first.")
        return method(self, *args, **kwargs)

    return wrapper  # type: ignore


class UserAgentDict(TypedDict):
    deviceType: str
    locale: str
    deviceLocale: str
    osVersion: str
    deviceName: str
    headerUserAgent: str
    appVersion: str
    screen: str
    timezone: str
    pushDeviceType: NotRequired[str]
    isPwa: NotRequired[bool]


DEFAULT_USER_AGENT_DICT = UserAgentDict(
    {
        "deviceType": "WEB",
        "pushDeviceType": "WEBPUSH",
        "locale": "ru",
        "deviceLocale": "ru",
        "osVersion": "Linux",
        "deviceName": "Chrome",
        "headerUserAgent": USER_AGENT,
        "isPwa": False,
        "appVersion": APP_VERSION,
        "screen": "1080x1920 1.0x",
        "timezone": "Europe/Moscow",
    },
)


class MaxClient:
    phone: int
    user_id: int

    def __init__(
        self,
        user_agent_dict: Optional[UserAgentDict] = None,
        proxy_url: Optional[str] = None,
        request_timeout: float = 30.0,
    ):
        self._connection: Optional[ClientConnection] = None
        self._http_pool: Optional[aiohttp.ClientSession] = None
        self._is_logged_in: bool = False
        self._device_id: Optional[str] = None
        self._seq = itertools.count(1)
        self._keepalive_task: Optional[asyncio.Task] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._incoming_event_callback: Optional[PacketCallback] = None
        self._reconnect_callback: Optional[ReconnectCallback] = None
        self._reconnect_lock = asyncio.Lock()
        self._reconnect_generation = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._video_pending: dict[int, asyncio.Future] = {}
        self._file_pending: dict[int, asyncio.Future] = {}
        self._callback_tasks: set[asyncio.Task] = set()
        self.user_agent = (
            deepcopy(DEFAULT_USER_AGENT_DICT)
            if user_agent_dict is None
            else user_agent_dict
        )
        self.proxy_url = proxy_url
        self.request_timeout = request_timeout

    # --- WebSocket connection management ---

    async def connect(self) -> ClientConnection:
        if self._connection:
            raise Exception("Already connected")

        _logger.info(f"Connecting to {WS_HOST}...")

        extra_kwargs: dict[str, Any] = {}
        if self.proxy_url:
            proxy = Proxy.from_url(self.proxy_url)
            sock = await proxy.connect(dest_host="api.oneme.ru", dest_port=443)
            extra_kwargs = {
                "sock": sock,
                # required when passing a raw socket to wss://
                "ssl": ssl.create_default_context(),
            }
        self._connection = await websockets.connect(
            WS_HOST,
            origin=websockets.Origin("https://web.max.ru"),
            user_agent_header=USER_AGENT,
            **extra_kwargs,
        )

        self._recv_task = asyncio.create_task(self._recv_loop())
        self._recv_task.add_done_callback(self._on_task_done)
        self._reconnect_generation += 1
        _logger.info("Connected. Receive task started.")
        return self._connection

    @property
    def connection(self) -> ClientConnection:
        """
        Returns the active session or raises — use inside @ensure_connected methods.
        """
        if self._connection is None:
            raise RuntimeError("WebSocket not connected. Call .connect() first.")
        return self._connection

    async def disconnect(self) -> None:
        await self._stop_keepalive_task()
        if self._recv_task:
            self._recv_task.cancel()
            await asyncio.gather(self._recv_task, return_exceptions=True)
            self._recv_task = None
        if self._connection:
            await self._connection.close()
            self._connection = None
        self._fail_pending_futures(ConnectionError("client disconnected"))
        self._is_logged_in = False
        self._seq = itertools.count(1)
        if self._http_pool:
            await self._http_pool.close()
            self._http_pool = None

    @ensure_connected
    async def invoke_method(
        self,
        opcode: int,
        payload: dict[str, Any],
        retries: int = 2,
    ) -> Optional[dict[str, Any]]:
        seq = next(self._seq)
        if seq > MAX_SEQ:
            # seq is int16 on the wire; wrap before it overflows
            self._seq = itertools.count(1)
            seq = next(self._seq)

        request = {
            "cmd": 0,
            "seq": seq,
            "opcode": opcode,
            "payload": payload,
        }
        _logger.info("-> REQUEST: opcode=%s seq=%s", opcode, seq)
        _logger.debug("-> REQUEST: %s", _redact(request))

        future = asyncio.get_running_loop().create_future()
        self._pending[seq] = future

        try:
            try:
                await self.connection.send(encode_packet(0, seq, opcode, payload))
            except websockets.exceptions.ConnectionClosed:
                future.cancel()
                _logger.warning("got ws disconnect in invoke_method")
                if self._reconnect_callback:
                    _logger.info("reconnecting")
                    await self.reconnect()
                    if retries > 0:
                        _logger.info("retrying invoke_method after reconnect")
                        return await self.invoke_method(opcode, payload, retries - 1)
                return None

            # asyncio.wait, not wait_for: on 3.10 wait_for swallows cancellation
            # when the future is already done, which livelocks task shutdown.
            done, _ = await asyncio.wait({future}, timeout=self.request_timeout)
            if not done:
                raise TimeoutError(f"no response within {self.request_timeout}s")
            response = future.result()
        finally:
            self._pending.pop(seq, None)
            if not future.done():
                future.cancel()
        response_payload = response.get("payload")
        status = (
            "error"
            if isinstance(response_payload, dict) and "error" in response_payload
            else "ok"
        )
        _logger.info(
            "<- RESPONSE: opcode=%s seq=%s status=%s",
            response.get("opcode"),
            response.get("seq"),
            status,
        )
        _logger.debug("<- RESPONSE: %s", _redact(response))

        if response.get("cmd") == 3:
            raise RpcError(response.get("payload") or {})

        return response

    async def set_callback(self, function: PacketCallback) -> None:
        import warnings

        warnings.warn(
            "switch to set_packet_callback",
            stacklevel=2,
            category=DeprecationWarning,
        )
        self.set_packet_callback(function)

    def set_packet_callback(self, function: PacketCallback) -> None:
        if not asyncio.iscoroutinefunction(function):
            raise TypeError("callback must be async")
        self._incoming_event_callback = function

    def set_reconnect_callback(self, function: ReconnectCallback) -> None:
        if not asyncio.iscoroutinefunction(function):
            raise TypeError("callback must be async")
        self._reconnect_callback = function

    async def reconnect(self) -> None:
        """Run the reconnect callback, serialized across concurrent callers.

        Callers that waited on the lock skip the callback if a reconnect
        already succeeded while they waited (generation changed). A failed
        attempt leaves the generation unchanged so the next caller retries.
        """
        if self._reconnect_callback is None:
            return
        generation = self._reconnect_generation
        async with self._reconnect_lock:
            if self._reconnect_generation != generation:
                return
            await self._reconnect_callback()

    @ensure_connected
    async def _recv_loop(self) -> None:
        try:
            while True:
                try:
                    raw_packet = await self.connection.recv()
                except websockets.exceptions.ConnectionClosed as err:
                    if not self._is_logged_in:
                        if isinstance(err, websockets.exceptions.ConnectionClosedOK):
                            # this probably means that user logged out
                            _logger.warning("connection closed: %s", err)
                            return
                        raise err
                    _logger.warning("got ws disconnect in receiver; reconnecting")
                    self._spawn_callback(self.reconnect())
                    return

                try:
                    packet = decode_packet(raw_packet)
                except PacketDecodeError:
                    _logger.warning("could not decode packet")
                    continue

                self._handle_packet(packet)
        except asyncio.CancelledError:
            _logger.info("receiver cancelled")
        finally:
            self._fail_pending_futures(ConnectionError("WebSocket connection closed"))

    def _handle_packet(self, packet: dict[str, Any]) -> None:
        seq = packet.get("seq")
        future = self._pending.pop(seq, None) if seq is not None else None
        if future is not None:
            if not future.done():
                future.set_result(packet)
            return

        if packet.get("opcode") == 136:
            payload = packet.get("payload")
            if isinstance(payload, dict):
                future = None

                if "videoId" in payload:
                    future = self._video_pending.pop(payload["videoId"], None)
                elif "fileId" in payload:
                    future = self._file_pending.pop(payload["fileId"], None)

                if future is not None and not future.done():
                    future.set_result(None)

        if self._incoming_event_callback:
            self._spawn_callback(self._incoming_event_callback(self, packet))

    def _spawn_callback(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._callback_tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return task

    def _on_task_done(self, task: asyncio.Task) -> None:
        self._callback_tasks.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            _logger.error("background task failed", exc_info=error)

    def _fail_pending_futures(self, error: ConnectionError) -> None:
        for pending in (self._pending, self._video_pending, self._file_pending):
            for future in pending.values():
                if not future.done():
                    future.set_exception(error)
            pending.clear()

    # --- Keepalive system

    @ensure_connected
    async def _send_keepalive_packet(self) -> None:
        await self.invoke_method(opcode=1, payload={"interactive": False})

    @ensure_connected
    async def _keepalive_loop(self) -> None:
        _logger.info("keepalive task started")
        try:
            while True:
                try:
                    await self._send_keepalive_packet()
                except Exception:
                    # RPC timeouts and send failures must not kill the loop;
                    # invoke_method already triggers reconnect on send errors.
                    _logger.warning("keepalive packet failed", exc_info=True)
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            _logger.info("keepalive task stopped")

    @ensure_connected
    async def _start_keepalive_task(self) -> None:
        if self._keepalive_task and not self._keepalive_task.done():
            return
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def _stop_keepalive_task(self) -> None:
        if not self._keepalive_task:
            return
        self._keepalive_task.cancel()
        await asyncio.gather(self._keepalive_task, return_exceptions=True)
        self._keepalive_task = None

    # --- Authentication ---

    @ensure_connected
    async def _send_hello_packet(
        self, device_id: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        self._device_id = device_id or f"{uuid.uuid4()}"
        return await self.invoke_method(
            opcode=6,
            payload={
                "userAgent": self.user_agent,
                "deviceId": self._device_id,
                "clientSessionId": pack_bigint(int(time.time() * 1000)),
            },
        )

    @ensure_connected
    async def send_code(self, phone: str) -> str:
        """:returns: Login token."""
        await self._send_hello_packet()
        start_auth_response = await self.invoke_method(
            opcode=17,
            payload={"phone": phone, "type": "START_AUTH", "language": "ru"},
        )
        if not start_auth_response:
            raise Exception("Failed to start auth")

        return start_auth_response["payload"]["token"]

    @ensure_connected
    async def sign_in(self, sms_token: str, sms_code: int) -> dict[str, Any]:
        """
        Auth token for further login is at ['payload']['tokenAttrs']['LOGIN']['token']
        :param login_token: Must be obtained via `send_code`.
        """
        verification_response = await self.invoke_method(
            opcode=18,
            payload={
                "token": sms_token,
                "verifyCode": str(sms_code),
                "authTokenType": "CHECK_CODE",
            },
        )

        if not verification_response:
            raise Exception("Failed to verify code")

        if "error" in verification_response["payload"]:
            raise Exception(verification_response["payload"]["error"])

        self.user_id = verification_response["payload"]["profile"]["contact"]["id"]
        self.phone = verification_response["payload"]["profile"]["contact"]["phone"]
        self._is_logged_in = True
        _logger.info("Successfully logged in (user_id=%s)", self.user_id)
        await self._start_keepalive_task()

        return verification_response

    @ensure_connected
    async def login_by_token(
        self, token: str, device_id: Optional[str] = None
    ) -> dict[str, Any]:
        await self._send_hello_packet(device_id)
        _logger.info("using session")
        login_response = await self.invoke_method(
            opcode=19,
            payload={
                "interactive": True,
                "token": token,
                "chatsSync": 0,
                "contactsSync": 0,
                "presenceSync": 0,
                "draftsSync": 0,
                "chatsCount": 40,
                "userAgent": self.user_agent,
            },
        )

        if not login_response:
            raise Exception("Failed to login")

        if "error" in login_response["payload"]:
            raise Exception(login_response["payload"]["error"])

        self.user_id = login_response["payload"]["profile"]["contact"]["id"]
        self.phone = login_response["payload"]["profile"]["contact"]["phone"]
        self._is_logged_in = True
        _logger.info("Successfully logged in (user_id=%s)", self.user_id)
        await self._start_keepalive_task()

        return login_response

    @property
    def device_id(self) -> Optional[str]:
        return self._device_id
