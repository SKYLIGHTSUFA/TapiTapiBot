from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from bot.config import ADMIN_IDS
from bot.dispatcher import bot

router = Router()

@router.message(Command("support"))
async def support_command(message: Message):
    await message.answer(
        "📞 Для связи с поддержкой напишите ваше сообщение ниже.\n"
        "Мы ответим в ближайшее время."
    )

@router.message(F.text & ~F.command)
async def forward_to_admins(message: Message):
    if message.from_user.id in ADMIN_IDS:
        return
    for admin_id in ADMIN_IDS:
        await bot.forward_message(admin_id, message.chat.id, message.message_id)
        await bot.send_message(admin_id, f"Пользователь @{message.from_user.username} (ID: {message.from_user.id})")
    await message.answer("Ваше сообщение отправлено операторам. Мы свяжемся с вами.")