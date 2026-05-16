import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message


TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
dp = Dispatcher()


@dp.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer("Hello from an AdBotHost Python bot.")


@dp.message()
async def echo(message: Message) -> None:
    await message.answer(f"Echo: {message.text}")


async def main() -> None:
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
