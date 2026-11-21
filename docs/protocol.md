## Protocol
Every WebSocket frame is **binary** (no text frames), big-endian:

| offset | type   | field                                        |
|--------|--------|----------------------------------------------|
| 0      | uint8  | protocol version = 10                        |
| 1      | uint8  | `cmd`                                        |
| 2-3    | int16  | `seq` - packet incremental ID. Request and response seq match. |
| 4-5    | int16  | `opcode` - RPC method ID                     |
| 6      | uint8  | LZ4 ratio (0 = payload uncompressed)         |
| 7-9    | uint24 | payload length `n`                           |
| 10..   | n bytes| payload                                      |

The payload is MessagePack (string map keys; decoders must tolerate integer
keys, i.e. `strict_map_key=False`). MessagePack bodies larger than 32 bytes
are compressed with LZ4 block format (no size prefix); the ratio byte is
`min(ceil(original_len / compressed_len), 255)` and decompression uses
`n * ratio` as the uncompressed-size upper bound. BigInt values (e.g.
`clientSessionId`) are msgpack ext type 1 whose data is itself a
msgpack-encoded int64.

`cmd` semantics: 0 = request, 1 = response, 2 = ignored by the web client,
3 = error packet with `payload.{error,message,localizedMessage,title,description}`.
`seq` is int16: the web client starts at 0 and closes the connection at 32767;
vkmax wraps back to 1.

Reference implementation: `vkmax/packet_codec.py`.

## Authorization flow
0. Connect to websocket `wss://api.oneme.ru/websocket`
1. Send hello packet (opcode 6) with payload:
   ```python
   {
    "userAgent": {
        "deviceType": "WEB",
        "pushDeviceType": "WEBPUSH",
        "locale": "ru_RU",
        "osVersion": "macOS",
        "deviceName": "vkmax Python",
        "headerUserAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "deviceLocale": "ru-RU",
        "isPwa": False,
        "appVersion": APP_VERSION,
        "screen": "956x1470 2.0x",
        "timezone": "Asia/Vladivostok"
       },
    "deviceId": str(uuid.uuid4()),
    "clientSessionId": ExtType(1, msgpack.packb(int(time.time() * 1000)))
   }
   ```
3. Start auth (opcode 17) with payload:
   ```python
   {
      "phone":"phone",
      "type":"START_AUTH",
      "language":"ru"
   }
   ```
   After that websocket sends a packet with sms_token to client
4. Confirm SMS code (opcode 18) with payload:
   ```python
   {
    "token": sms_token,
    "verifyCode": str(sms_code),
    "authTokenType": "CHECK_CODE"
   }
   ```
   Now you are logged in.
## Client flow
Requests are sent as binary frames with `cmd=0` and an increasing `seq`;
the payload is an arbitrary MessagePack map.\
Known opcodes are listed in `opcodes.md` file.\
Example payload for sending a message (opcode 64):
```python
{
  "chatId": to_chat_id,
  "message": {
    "text": "text you need to send",
    "cid": 175xxxxxxxxxx,
    "elements": [],
    "attaches": []
  },
  "notify": true
}
```
