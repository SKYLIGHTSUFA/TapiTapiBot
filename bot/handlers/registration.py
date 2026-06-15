from aiogram.filters import Command
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.keyboards.inline import agreement_keyboard, phone_keyboard
from bot.models.database import AsyncSessionLocal, User, UserStatus
from bot.services.encryption import encrypt
from bot.services.audit import log_action
from datetime import datetime

router = Router()

class RegState(StatesGroup):
    waiting_phone = State()
    waiting_fullname = State()
    waiting_city = State()
    waiting_birthdate = State()

@router.callback_query(F.data == "agree_pd")
async def process_agreement(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Укажите номер телефона (кнопка или вручную +7XXXXXXXXXX)",
        reply_markup=phone_keyboard()
    )
    await state.set_state(RegState.waiting_phone)
    await callback.answer()

@router.message(RegState.waiting_phone, F.contact | F.text)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
        import re
        if not re.match(r'^\+7\d{10}$', phone):
            await message.answer("Неверный формат. Используйте +7XXXXXXXXXX или кнопку.")
            return
    await state.update_data(phone=phone)
    await message.answer("Введите полное имя (Фамилия Имя Отчество):")
    await state.set_state(RegState.waiting_fullname)

@router.message(RegState.waiting_fullname)
async def process_fullname(message: Message, state: FSMContext):
    fullname = message.text.strip()
    if len(fullname.split()) < 2:
        await message.answer("Введите хотя бы фамилию и имя.")
        return
    await state.update_data(fullname=fullname)
    await message.answer("Введите город проживания:")
    await state.set_state(RegState.waiting_city)

@router.message(RegState.waiting_city)
async def process_city(message: Message, state: FSMContext):
    city = message.text.strip()
    if len(city) < 2:
        await message.answer("Название города слишком короткое.")
        return
    await state.update_data(city=city)
    await message.answer("Введите дату рождения (ДД.ММ.ГГГГ):")
    await state.set_state(RegState.waiting_birthdate)

@router.message(RegState.waiting_birthdate)
async def process_birthdate(message: Message, state: FSMContext):
    import re
    date_str = message.text.strip()
    if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
        await message.answer("Формат: ДД.ММ.ГГГГ")
        return
    try:
        birth_date = datetime.strptime(date_str, "%d.%m.%Y")
        # Проверка возраста
        today = datetime.now()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        if age < 18:
            await message.answer("Извините, участие в акции разрешено только с 18 лет.")
            await state.clear()
            return
    except ValueError:
        await message.answer("Некорректная дата.")
        return

    data = await state.get_data()
    encrypted_data = {
        "phone": encrypt(data['phone']),
        "fullname": encrypt(data['fullname']),
        "city": encrypt(data['city']),
        "birth": encrypt(date_str)
    }
    async with AsyncSessionLocal() as session:
        user = User(
            telegram_id=message.from_user.id,
            full_name=encrypted_data['fullname'],
            phone=encrypted_data['phone'],
            city=encrypted_data['city'],
            birth_date=encrypted_data['birth'],
            status=UserStatus.ACTIVE
        )
        session.add(user)
        await session.commit()
    await log_action("user_registered", message.from_user.id, {"phone": data['phone'][:5]+"***"})
    await message.answer("✅ Регистрация завершена! Теперь загружайте чеки.")
    from bot.keyboards.menu import main_menu
    await message.answer("Главное меню:", reply_markup=main_menu())
    from bot.keyboards.menu import main_menu
    await message.answer("Главное меню:", reply_markup=main_menu())
    await state.clear()

@router.message(Command("cancel"))
async def cancel_registration(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Регистрация отменена. Начните заново с /start.")
