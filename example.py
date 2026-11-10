import asyncio
import logging
import sys
from pathlib import Path

import aiohttp

from vkmax.client import MaxClient


# setup logging with custom format and level `info`
logging.basicConfig(
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%d.%m.%Y %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.INFO
)

async def get_weather(city: str) -> str:
    async with aiohttp.ClientSession() as http:
        async with http.get(f"https://ru.wttr.in/{city}?Q&T&format=3") as response:
            return await response.text()


async def packet_callback(client: MaxClient, packet: dict):
    if packet['opcode'] == 128:
        message_text: str = packet['payload']['message']['text']
        if message_text == ".info":
            text = "Userbot connected"

        elif message_text.startswith(".weather "):
            city = message_text.removeprefix(".weather ").strip()
            if not city:
                return
            text = await get_weather(city)

        else:
            return

        await client.edit_message(
            packet["payload"]["chatId"],
            packet["payload"]["message"]["id"],
            text
        )


async def main():
    client = MaxClient()
    await client.connect()

    session_file = Path('max_session.txt')

    if not session_file.exists():
        phone_number = input('Enter your phone number: ')
        sms_token = await client.send_code(phone_number)
        sms_code = int(input('Enter SMS code: '))
        account_data = await client.sign_in(sms_token, sms_code)

        device_id = client.device_id
        login_token = account_data['payload']['tokenAttrs']['LOGIN']['token']

        # save device uuid and auth token delimited by newline
        session_file.write_text(f'{device_id}\n{login_token}')

    else:
        contents = session_file.read_text()
        device_id, login_token = contents.split('\n', maxsplit=1)
        await client.login_by_token(login_token, device_id)

    client.set_packet_callback(packet_callback)

    await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
