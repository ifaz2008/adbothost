import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from app.api import BackendClient
from app.config import settings


logging.basicConfig(level=logging.INFO)
dp = Dispatcher()
api = BackendClient()


def _expiry_text(value: str | None) -> str:
    return value or "not active"


async def _token_for(message: Message) -> str:
    user = message.from_user
    display = user.full_name if user else None
    telegram_id = user.id if user else 0
    return await api.telegram_login(telegram_id, display)


@dp.message(Command("start"))
async def start(message: Message) -> None:
    await _token_for(message)
    await message.answer(
        "Welcome to AdBotHost. This control bot is for small Telegram bot hosting only.\n\n"
        "Use /mybots to check status, /credits to view balance, /addbot to open the dashboard, and /help for rules."
    )


@dp.message(Command("mybots"))
async def mybots(message: Message) -> None:
    token = await _token_for(message)
    bots = await api.get_bots(token)
    if not bots:
        await message.answer("You do not have any bots yet. Use /addbot to open the dashboard and upload a ZIP.")
        return
    lines = ["Your bots:"]
    for bot in bots:
        lines.append(
            f"- {bot['name']}: {bot['status']} (active until: {_expiry_text(bot.get('active_until'))}, start: {bot['start_command']})"
        )
    await message.answer("\n".join(lines))


@dp.message(Command("credits"))
async def credits(message: Message) -> None:
    token = await _token_for(message)
    summary = await api.get_credits(token)
    await message.answer(
        f"Credit balance: {summary['balance']:.4f}\n"
        f"Plan: {summary.get('plan_name') or 'unknown'} ({summary.get('credit_multiplier', 1)}x)\n"
        "Redeem credits in the dashboard to activate or extend a bot."
    )


@dp.message(Command("addbot"))
async def addbot(message: Message) -> None:
    await message.answer(
        f"Open the dashboard to create a bot and upload a ZIP:\n{settings.public_base_url}\n\n"
        "MVP uploads are dashboard-only so ZIP scanning and env-var masking stay consistent."
    )


@dp.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "AdBotHost hosts small Python or Node.js Telegram bots only.\n\n"
        "Blocked: AI model hosting, crypto mining, proxies/VPNs, browser automation, scraping, spam/mass DM, phishing, malware, custom Dockerfiles, and shell access.\n\n"
        "Commands: /mybots, /addbot, /credits"
    )


@dp.message(F.text)
async def fallback(message: Message) -> None:
    await message.answer("Use /mybots, /credits, /addbot, or /help.")


async def main() -> None:
    if not settings.telegram_control_bot_token:
        logging.warning("TELEGRAM_CONTROL_BOT_TOKEN is empty; control bot will idle.")
        while True:
            await asyncio.sleep(3600)
    bot = Bot(token=settings.telegram_control_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
