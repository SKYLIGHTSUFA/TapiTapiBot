from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    buttons = [
        [KeyboardButton(text="🎫 Мои билеты")],
        [KeyboardButton(text="📅 Ближайший розыгрыш")],
        [KeyboardButton(text="📜 Правила акции")],
        [KeyboardButton(text="🆘 Поддержка")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
