import asyncio
import logging

import aiohttp
import sys

from vkmax.client import MaxClient

from pathlib import Path

date_format = '%d.%m.%Y %H:%M:%S'
logging_format = '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'

handlers = [
    logging.StreamHandler(sys.stdout)
]

logging.basicConfig(
    format=logging_format,
    datefmt=date_format,
    handlers=handlers,
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

    login_token_file = Path('login_token.txt')

    authenticated = False
    if login_token_file.exists():
        login_token_from_file = login_token_file.read_text(encoding='utf-8').strip()
        try:
            await client.login_by_token(login_token_from_file)
            authenticated = True
        except Exception:
            print("Couldn't login by token. Falling back to SMS login")

    if not authenticated:
        phone_number = input('Enter your phone number: ')
        sms_login_token = await client.send_code(phone_number)
        sms_code = int(input('Enter SMS code: '))
        account_data = await client.sign_in(sms_login_token, sms_code)

        login_token = account_data['payload']['tokenAttrs']['LOGIN']['token']
        login_token_file.write_text(login_token, encoding='utf-8')

    client.set_packet_callback(packet_callback)

    await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
