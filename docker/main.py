import asyncio
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from text_bot import *
from db import create_pool, get_user_by_phone, create_user, get_available_events, create_appointment, get_event_by_id, get_user_appointments,get_user_by_tg_id

# --- Конфигурация ---
ADMIN_IDS = {2113625271, 6358923796}  # ID администраторов

# --- Клавиатуры ---
agreement_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="Принять", callback_data="accept_agreement")],
    [types.InlineKeyboardButton(text="Отклонить", callback_data="decline_agreement")]
])

reply_group_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text='🎓 Студент (0)')],
        [types.KeyboardButton(text='💼 Сотрудник (1)')],
        [types.KeyboardButton(text='🌍 Внешний донор (2)')]
    ],
    resize_keyboard=True
)

reply_age_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text='Да'), types.KeyboardButton(text='Нет')]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

external_donor_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="Я зарегистрировался", callback_data="external_reg_complete")]
])

def get_main_menu_kb(is_admin=False):
    buttons = [
        [types.InlineKeyboardButton(text='Помощь', callback_data='menu_help')],
        [types.InlineKeyboardButton(text='Связь с волонтерами', url='https://www.gosuslugi.ru/help/faq/donor/14122022')],
        [types.InlineKeyboardButton(text='Записаться на приём', callback_data='sign_up')],
        [types.InlineKeyboardButton(text='Мои записи', callback_data='my_signs')],
        [types.InlineKeyboardButton(text='Зачем становиться донором', callback_data='why_donor')]
    ]
    if is_admin:
        buttons.append([types.InlineKeyboardButton(text='Админ-панель', callback_data='admin_panel')])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_kb():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text='Добавить админа', callback_data='add_admin')],
        [types.InlineKeyboardButton(text='Удалить админа', callback_data='remove_admin')],
        [types.InlineKeyboardButton(text='Создать мероприятие', callback_data='create_event')],
        [types.InlineKeyboardButton(text='Назад', callback_data='back_to_menu')]
    ])

# --- Состояния ---
class Reg(StatesGroup):
    agreement = State()
    telephone_number = State()
    name_surname = State()
    age = State()
    user_type = State()
    external_reg = State()

class Appointment(StatesGroup):
    choose_doctor = State()
    choose_date = State()
    confirmation = State()

class AdminStates(StatesGroup):
    add_admin = State()
    remove_admin = State()
    create_event = State()
    event_date = State()
    event_organizer = State()

# --- Хендлеры ---
router = Router()
pool = None

def normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if phone.startswith("8"): return "+7" + phone[1:]
    elif phone.startswith("7"): return "+" + phone
    return phone

def is_valid_phone(phone: str) -> bool:
    phone = normalize_phone(phone)
    return phone.startswith("+7") and len(phone) == 12 and phone[1:].isdigit()

def Name_Surname(name_surname: str) -> bool:
    parts = name_surname.split()
    return len(parts) == 3 and all(part[0].isupper() for part in parts)

async def save_user(data: dict, user_type: int, msg: types.Message, state: FSMContext):
    user_data = {
        "fio": data['name_surname'],
        "number_phone": data['telephone_number'],
        "user_type": user_type,
        "tg_id": msg.from_user.id
    }
    
    try:
        await create_user(pool, user_data)
        is_admin = msg.from_user.id in ADMIN_IDS
        await msg.answer("✅ Регистрация завершена!", reply_markup=types.ReplyKeyboardRemove())
        await msg.answer(registration_complete, reply_markup=get_main_menu_kb(is_admin))
    except Exception as e:
        print(f"DB error: {e}")
        await msg.answer("⚠️ Ошибка сохранения данных", reply_markup=types.ReplyKeyboardRemove())
    finally:
        await state.clear()

@router.message(Command("menu"))
async def menu_command(msg: Message, state: FSMContext):
    await state.clear()
    is_admin = msg.from_user.id in ADMIN_IDS
    await msg.answer("Главное меню:", reply_markup=get_main_menu_kb(is_admin))

@router.message(CommandStart())
async def Start(msg: Message, state: FSMContext):
    await msg.delete()
    await state.set_state(Reg.agreement)
    await msg.answer(user_agreement, reply_markup=agreement_kb)

@router.callback_query(Reg.agreement, F.data == "accept_agreement")
async def accept_agreement(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(agreement_accepted)
    await state.set_state(Reg.telephone_number)
    await callback.message.answer(start)

@router.message(Reg.telephone_number)
async def telephone_number_h(msg: Message, state: FSMContext):
    phone = normalize_phone(msg.text)
    if not is_valid_phone(phone):
        return await msg.answer('❌ Неверный формат номера')
    
    await msg.answer('🔍 Проверка номера...')
    try:
        if await get_user_by_phone(pool, phone):
            is_admin = msg.from_user.id in ADMIN_IDS
            await msg.answer(a1, reply_markup=get_main_menu_kb(is_admin))
            await state.clear()
        else:
            # Сохраняем и номер телефона и tg_id
            await state.update_data(telephone_number=phone, tg_id=msg.from_user.id)
            await state.set_state(Reg.name_surname)
            await msg.answer(a2)
    except Exception as e:
        print(f"DB error: {e}")
        await msg.answer('⚠️ Ошибка проверки номера')

@router.message(Reg.name_surname)
async def user_name_surname(msg: Message, state: FSMContext):
    if not Name_Surname(msg.text):
        return await msg.answer('❌ Введите ФИО правильно (Иванов Иван Иванович)')
    
    await state.update_data(name_surname=msg.text)
    await state.set_state(Reg.age)
    await msg.answer(a3, reply_markup=reply_age_kb)

@router.message(Reg.age)
async def user_age(msg: Message, state: FSMContext):
    if msg.text.lower() not in ('да', 'нет'):
        return await msg.answer('❌ Ответьте "Да" или "Нет"')
    
    if msg.text.lower() == 'нет':
        await msg.answer("❌ Вам должно быть 18+")
        await state.clear()
        return
    
    await msg.answer("✅ Принято", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Reg.user_type)
    await msg.answer("Выберите категорию:", reply_markup=reply_group_kb)

@router.message(Reg.user_type)
async def user_type_handler(msg: Message, state: FSMContext):
    type_mapping = {
        '🎓 Студент (0)': 0,
        '💼 Сотрудник (1)': 1,
        '🌍 Внешний донор (2)': 2
    }
    
    if msg.text not in type_mapping:
        return await msg.answer("❌ Выберите вариант из списка")
    
    user_type = type_mapping[msg.text]
    data = await state.get_data()
    
    if user_type == 2:  # Внешний донор
        await state.update_data(user_type=user_type)
        await state.set_state(Reg.external_reg)
        return await msg.answer(
            external_donor_message.format(link=external_donor_link),
            reply_markup=external_donor_kb
        )
    
    await save_user(data, user_type, msg, state)

@router.callback_query(Reg.external_reg, F.data == "external_reg_complete")
async def external_complete(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await save_user(data, 2, callback.message, state)
    is_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.edit_text(external_registration_complete, reply_markup=get_main_menu_kb(is_admin))

# --- Меню ---
@router.callback_query(F.data == 'menu_help')
async def menu_help(callback: CallbackQuery):
    is_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.edit_text(help, reply_markup=get_main_menu_kb(is_admin))

@router.callback_query(F.data == 'sign_up')
async def sign_up(callback: CallbackQuery, state: FSMContext):
    try:
        # Получаем список организаторов (Гаврилова и ФМБА)
        organizers = [
            {"id": 0, "name": "Гаврилова"},
            {"id": 1, "name": "ФМБА"}
        ]
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=org["name"], callback_data=f"org_{org['id']}")] 
            for org in organizers
        ])
        
        await callback.message.edit_text("Выберите организатора:", reply_markup=kb)
        await state.set_state(Appointment.choose_doctor)
    except Exception as e:
        print(f"Error in sign_up: {e}")
        await callback.message.answer("Произошла ошибка, попробуйте позже")

@router.callback_query(Appointment.choose_doctor, F.data.startswith("org_"))
async def choose_doctor(callback: CallbackQuery, state: FSMContext):
    try:
        organizer_id = int(callback.data.split("_")[1])
        await state.update_data(organizer_id=organizer_id)
        
        # Получаем доступные мероприятия из БД
        events = await get_available_events(pool, organizer_id)
        
        if not events:
            await callback.message.answer("Нет доступных мероприятий для записи")
            await state.clear()
            return
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text=f"{event['date'].strftime('%d.%m.%Y')} ({'Гаврилова' if event['organizer'] == 0 else 'ФМБА'})", 
                callback_data=f"event_{event['id']}"
            )] 
            for event in events
        ])
        
        await callback.message.edit_text("Выберите мероприятие:", reply_markup=kb)
        await state.set_state(Appointment.choose_date)
    except Exception as e:
        print(f"Error in choose_doctor: {e}")
        await callback.message.answer("Произошла ошибка, попробуйте позже")

@router.callback_query(Appointment.choose_date, F.data.startswith("event_"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    try:
        event_id = int(callback.data.split("_")[1])
        await state.update_data(event_id=event_id)
        
        data = await state.get_data()
        organizer_id = data['organizer_id']
        
        # Получаем информацию о выбранном мероприятии
        event = await get_event_by_id(pool, event_id)
        
        if not event:
            await callback.message.answer("Выбранное мероприятие больше не доступно")
            await state.clear()
            return
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Подтвердить", callback_data="confirm_appointment")],
            [types.InlineKeyboardButton(text="Отменить", callback_data="cancel_appointment")]
        ])
        
        await callback.message.edit_text(
            f"Вы выбрали:\n"
            f"Организатор: {'Гаврилова' if organizer_id == 0 else 'ФМБА'}\n"
            f"Дата: {event['date'].strftime('%d.%m.%Y')}\n\n"
            f"Подтвердите запись:",
            reply_markup=kb
        )
        await state.set_state(Appointment.confirmation)
    except Exception as e:
        print(f"Error in choose_date: {e}")
        await callback.message.answer("Произошла ошибка, попробуйте позже")

@router.callback_query(Appointment.confirmation, F.data == "confirm_appointment")
async def confirm_appointment(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        
        # Получаем пользователя либо по номеру телефона, либо по tg_id
        user = None
        if 'telephone_number' in data:
            user = await get_user_by_phone(pool, data['telephone_number'])
        elif 'tg_id' in data:
            user = await get_user_by_tg_id(pool, data['tg_id'])
        
        if not user:
            await callback.message.answer("❌ Пользователь не найден")
            await state.clear()
            return
        
        appointment_data = {
            "user_id": user['id'],
            "event_id": data['event_id']
        }
        
        await create_appointment(pool, appointment_data)
        
        event = await get_event_by_id(pool, data['event_id'])
        
        await callback.message.edit_text(
            "✅ Запись успешно создана!\n\n"
            f"Вы записаны к {'Гавриловой' if data['organizer_id'] == 0 else 'ФМБА'}\n"
            f"Дата: {event['date'].strftime('%d.%m.%Y')}\n\n"
            "Спасибо, что становитесь донором!",
            reply_markup=get_main_menu_kb(callback.from_user.id in ADMIN_IDS)
        )
        await state.clear()
    except Exception as e:
        print(f"Error in confirm_appointment: {e}")
        await callback.message.answer("Произошла ошибка при создании записи")
        
@router.callback_query(Appointment.confirmation, F.data == "cancel_appointment")
async def cancel_appointment(callback: CallbackQuery, state: FSMContext):
    is_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.edit_text("Запись отменена", reply_markup=get_main_menu_kb(is_admin))
    await state.clear()

@router.callback_query(F.data == 'my_signs')
async def my_signs(callback: CallbackQuery):
    try:
        user = await get_user_by_phone(pool, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        appointments = await get_user_appointments(pool, user['id'])
        
        if not appointments:
            await callback.message.answer("У вас нет активных записей")
            return
        
        response = "📅 Ваши записи:\n\n"
        for app in appointments:
            event = await get_event_by_id(pool, app['event_id'])
            status = {
                0: "✅ Запланировано",
                1: "❌ Не пришел",
                2: "⚠️ Не прошел медосмотр",
                3: "🎉 Успешно сдал кровь"
            }.get(app['status'], "❓ Неизвестный статус")
            
            response += (
                f"📌 Организатор: {'Гаврилова' if event['organizer'] == 0 else 'ФМБА'}\n"
                f"📅 Дата: {event['date'].strftime('%d.%m.%Y')}\n"
                f"🔹 Статус: {status}\n\n"
            )
        
        is_admin = callback.from_user.id in ADMIN_IDS
        await callback.message.answer(response, reply_markup=get_main_menu_kb(is_admin))
    except Exception as e:
        print(f"Error in my_signs: {e}")
        await callback.message.answer("Произошла ошибка при получении записей")

@router.callback_query(F.data == 'why_donor')
async def why_donor(callback: CallbackQuery):
    is_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.answer(
        "Стать донором - это возможность спасать жизни!\n\n"
        "Каждая донация может помочь спасти до 3 жизней!",
        reply_markup=get_main_menu_kb(is_admin)
    )

# --- Админ-панель ---
@router.callback_query(F.data == 'admin_panel')
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав доступа")
        return
    
    await callback.message.edit_text(
        "👨‍💻 Админ-панель:",
        reply_markup=get_admin_kb()
    )

@router.callback_query(F.data == 'add_admin')
async def add_admin(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав доступа")
        return
    
    await state.set_state(AdminStates.add_admin)
    await callback.message.edit_text(
        "Введите Telegram ID пользователя, которого хотите сделать администратором:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отмена", callback_data="cancel_admin_action")]
        ])
    )

@router.message(AdminStates.add_admin)
async def process_add_admin(msg: Message, state: FSMContext):
    try:
        new_admin_id = int(msg.text)
        ADMIN_IDS.add(new_admin_id)
        await msg.answer(f"✅ Пользователь {new_admin_id} добавлен как администратор")
        await state.clear()
        await msg.answer("👨‍💻 Админ-панель:", reply_markup=get_admin_kb())
    except ValueError:
        await msg.answer("❌ Неверный формат ID. Введите число")

@router.callback_query(F.data == 'remove_admin')
async def remove_admin(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав доступа")
        return
    
    if len(ADMIN_IDS) <= 1:
        await callback.answer("❌ Нельзя удалить последнего администратора")
        return
    
    await state.set_state(AdminStates.remove_admin)
    admins_list = "\n".join(f"🔹 {admin_id}" for admin_id in ADMIN_IDS)
    await callback.message.edit_text(
        f"Текущие администраторы:\n{admins_list}\n\n"
        "Введите Telegram ID администратора, которого хотите удалить:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отмена", callback_data="cancel_admin_action")]
        ])
    )

@router.message(AdminStates.remove_admin)
async def process_remove_admin(msg: Message, state: FSMContext):
    try:
        admin_id = int(msg.text)
        if admin_id not in ADMIN_IDS:
            await msg.answer("❌ Этот пользователь не является администратором")
            return
        
        if len(ADMIN_IDS) <= 1:
            await msg.answer("❌ Нельзя удалить последнего администратора")
            return
        
        ADMIN_IDS.remove(admin_id)
        await msg.answer(f"✅ Пользователь {admin_id} удален из администраторов")
        await state.clear()
        await msg.answer("👨‍💻 Админ-панель:", reply_markup=get_admin_kb())
    except ValueError:
        await msg.answer("❌ Неверный формат ID. Введите число")

@router.callback_query(F.data == 'create_event')
async def create_event(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав доступа")
        return
    
    await state.set_state(AdminStates.event_date)
    await callback.message.edit_text(
        "Введите дату мероприятия в формате ДД.ММ.ГГГГ:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отмена", callback_data="cancel_admin_action")]
        ])
    )

@router.message(AdminStates.event_date)
async def process_event_date(msg: Message, state: FSMContext):
    try:
        day, month, year = map(int, msg.text.split('.'))
        if not (1 <= day <= 31 and 1 <= month <= 12 and year >= 2023):
            raise ValueError
        
        await state.update_data(event_date=msg.text)
        await state.set_state(AdminStates.event_organizer)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Гаврилова", callback_data="org_0")],
            [types.InlineKeyboardButton(text="ФМБА", callback_data="org_1")]
        ])
        
        await msg.answer("Выберите организатора:", reply_markup=kb)
    except ValueError:
        await msg.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")

@router.callback_query(AdminStates.event_organizer, F.data.startswith("org_"))
async def process_event_organizer(callback: CallbackQuery, state: FSMContext):
    try:
        organizer = int(callback.data.split("_")[1])
        data = await state.get_data()
        
        # Сохраняем мероприятие в БД
        event_data = {
            "date": data['event_date'],
            "organizer": organizer
        }
        
        # Здесь должна быть функция для сохранения мероприятия в БД
        # await create_event_in_db(pool, event_data)
        
        await callback.message.edit_text(
            f"✅ Мероприятие на {data['event_date']} с организатором "
            f"{'Гаврилова' if organizer == 0 else 'ФМБА'} создано!",
            reply_markup=get_admin_kb()
        )
        await state.clear()
    except Exception as e:
        print(f"Error in process_event_organizer: {e}")
        await callback.message.answer("Произошла ошибка при создании мероприятия")

@router.callback_query(F.data == 'cancel_admin_action')
async def cancel_admin_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👨‍💻 Админ-панель:",
        reply_markup=get_admin_kb()
    )

@router.callback_query(F.data == 'back_to_menu')
async def back_to_menu(callback: CallbackQuery):
    is_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=get_main_menu_kb(is_admin)
    )

async def main():
    global pool
    pool = await create_pool()
    bot = Bot(token='6505951608:AAEj4TFQAIHFjjNEgnOFTS54wlAr8SonlDw')
    dp = Dispatcher()
    dp.include_router(router)
    
    # Устанавливаем команды бота
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Начать работу с ботом"),
        types.BotCommand(command="menu", description="Вернуться в главное меню")
    ])
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())