import logging
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio
from datetime import datetime, timedelta

# Конфигурация
BOT_TOKEN = "7262869145:AAH6sKvsW76To6hJ8N0XXTifeFJ5LnfIsGQ"
DATA_FILE = "support_bot_data.json"
TIMEOUT_MINUTES = 0.2

# Инициализация бота
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Загрузка данных
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    "support_ids": set(map(int, data.get("support_ids", [2113625271, 6358923796]))),
                    "active_dialogs": {int(k): {
                        'support_id': v['support_id'],
                        'last_activity': datetime.fromisoformat(v['last_activity']) if isinstance(v['last_activity'], str) else v['last_activity'],
                        'sleep_after': v.get('sleep_after', False)
                    } for k, v in data.get("active_dialogs", {}).items()},
                    "user_to_support": {int(k): v for k, v in data.get("user_to_support", {}).items()},
                    "support_to_user": {int(k): v for k, v in data.get("support_to_user", {}).items()},
                    "request_queue": data.get("request_queue", []),
                    "active_supports": set(map(int, data.get("active_supports", [2113625271, 6358923796]))),
                    "busy_supports": set(map(int, data.get("busy_supports", []))),
                    "sleeping_supports": set(map(int, data.get("sleeping_supports", []))),
                    "processed_users": set(map(int, data.get("processed_users", [])))
                }
        except Exception as e:
            logging.error(f"Ошибка загрузки данных: {e}")
            os.remove(DATA_FILE)
    
    return {
        "support_ids": {2113625271, 6358923796},
        "active_dialogs": {},
        "user_to_support": {},
        "support_to_user": {},
        "request_queue": [],
        "active_supports": {2113625271, 6358923796},
        "busy_supports": set(),
        "sleeping_supports": set(),
        "processed_users": set()
    }

# Сохранение данных
def save_data():
    data = {
        "support_ids": list(support_ids),
        "active_dialogs": {str(k): {
            'support_id': v['support_id'],
            'last_activity': v['last_activity'].isoformat(),
            'sleep_after': v.get('sleep_after', False)
        } for k, v in active_dialogs.items()},
        "user_to_support": {str(k): v for k, v in user_to_support.items()},
        "support_to_user": {str(k): v for k, v in support_to_user.items()},
        "request_queue": request_queue,
        "active_supports": list(active_supports),
        "busy_supports": list(busy_supports),
        "sleeping_supports": list(sleeping_supports),
        "processed_users": list(processed_users)
    }
    
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения данных: {e}")

# Инициализация состояний
data = load_data()
support_ids = data["support_ids"]
active_dialogs = data["active_dialogs"]
user_to_support = data["user_to_support"]
support_to_user = data["support_to_user"]
request_queue = data["request_queue"]
active_supports = data["active_supports"]
busy_supports = data["busy_supports"]
sleeping_supports = data["sleeping_supports"]
processed_users = data["processed_users"]

# Таймеры для таймаута
timeout_tasks = {}

async def start_timeout(user_id):
    if user_id in timeout_tasks:
        timeout_tasks[user_id].cancel()
    
    async def timeout_task():
        try:
            await asyncio.sleep(TIMEOUT_MINUTES * 60)
            if user_id in active_dialogs:
                last_activity = active_dialogs[user_id]['last_activity']
                if (datetime.now() - last_activity) >= timedelta(minutes=TIMEOUT_MINUTES):
                    support_id = active_dialogs[user_id]['support_id']
                    await close_dialog(user_id, support_id, timeout=True)
        except Exception as e:
            logging.error(f"Ошибка в таймере для пользователя {user_id}: {e}")
    
    timeout_tasks[user_id] = asyncio.create_task(timeout_task())

def cancel_timeout(user_id):
    if user_id in timeout_tasks:
        timeout_tasks[user_id].cancel()
        del timeout_tasks[user_id]

async def reset_timeout(user_id):
    if user_id in active_dialogs:
        active_dialogs[user_id]['last_activity'] = datetime.now()
        await start_timeout(user_id)

async def restore_timeouts():
    for user_id in list(active_dialogs.keys()):
        await start_timeout(user_id)

# Клавиатуры
def get_user_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/help")]],
        resize_keyboard=True
    )

def get_dialog_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/thank")]],
        resize_keyboard=True
    )

def get_support_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/active"), KeyboardButton(text="/sleep")],
            [KeyboardButton(text="/add_support")]
        ],
        resize_keyboard=True
    )

def get_support_dialog_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/break")],
            [KeyboardButton(text="/sleep")]
        ],
        resize_keyboard=True
    )

# Обработчики команд
@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    
    if user_id in support_ids:
        if user_id in support_to_user:
            await message.answer(
                "👨‍💻 Вы в активном диалоге с пользователем",
                reply_markup=get_support_dialog_keyboard()
            )
        else:
            await message.answer(
                "👨‍💻 Вы оператор поддержки. Доступные команды:",
                reply_markup=get_support_keyboard()
            )
    else:
        if user_id in active_dialogs:
            await message.answer(
                "ℹ️ Вы уже в диалоге с оператором",
                reply_markup=get_dialog_keyboard()
            )
        else:
            await message.answer(
                "👋 Добро пожаловать! Нажмите кнопку ниже для связи с поддержкой",
                reply_markup=get_user_keyboard()
            )

@dp.message(Command("help"))
async def help_command(message: Message):
    user_id = message.from_user.id
    
    if user_id in support_ids:
        if user_id in support_to_user:
            await message.answer(
                "ℹ️ Вы в активном диалоге. Используйте кнопки ниже:",
                reply_markup=get_support_dialog_keyboard()
            )
        else:
            await message.answer(
                "ℹ️ Команды оператора:",
                reply_markup=get_support_keyboard()
            )
        return
    
    if user_id in active_dialogs:
        await message.answer(
            "ℹ️ Вы уже подключены к оператору. Продолжайте общение в этом чате.",
            reply_markup=get_dialog_keyboard()
        )
        return
    
    if user_id in processed_users:
        await message.answer(
            "🔄 Ваш запрос уже в обработке. Пожалуйста, подождите подключения оператора.",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    request_queue.append({
        'user_id': user_id,
        'username': message.from_user.username or "Без username",
        'time': datetime.now().isoformat()
    })
    processed_users.add(user_id)
    save_data()
    
    await message.answer(
        "🔄 Ищем свободного оператора...",
        reply_markup=ReplyKeyboardRemove()
    )
    await assign_support()

@dp.message(Command("thank"))
async def thank_command(message: Message):
    user_id = message.from_user.id
    
    if user_id in active_dialogs:
        support_id = active_dialogs[user_id]['support_id']
        await close_dialog(user_id, support_id, closed_by_user=True)
        await message.answer(
            "✅ Диалог с оператором завершен. Спасибо за обращение!",
            reply_markup=get_user_keyboard()
        )
    else:
        await message.answer(
            "ℹ️ У вас нет активного диалога с оператором",
            reply_markup=get_user_keyboard()
        )

@dp.message(Command("add_support"))
async def add_support(message: Message):
    if message.from_user.id not in support_ids:
        return
    
    if not message.reply_to_message or not message.reply_to_message.forward_from:
        await message.answer("❌ Ответьте (reply) на пересланное сообщение пользователя, которого хотите добавить как оператора")
        return
    
    new_support_id = message.reply_to_message.forward_from.id
    if new_support_id in support_ids:
        await message.answer("ℹ️ Этот пользователь уже является оператором")
        return
    
    support_ids.add(new_support_id)
    active_supports.add(new_support_id)
    save_data()
    
    await message.answer(f"✅ Пользователь {new_support_id} добавлен как оператор")
    await bot.send_message(
        chat_id=new_support_id,
        text="🎉 Вас добавили как оператора поддержки!",
        reply_markup=get_support_keyboard()
    )

@dp.message(Command("break"))
async def break_command(message: Message):
    if message.from_user.id not in support_ids:
        return
    
    support_id = message.from_user.id
    
    if support_id in support_to_user:
        user_id = support_to_user[support_id]
        await close_dialog(user_id, support_id, closed_by_support=True)
        await message.answer(
            "⏸ Вы завершили текущий диалог",
            reply_markup=get_support_keyboard()
        )
    else:
        await message.answer(
            "ℹ️ У вас нет активных диалогов",
            reply_markup=get_support_keyboard()
        )

@dp.message(Command("sleep"))
async def sleep_mode(message: Message):
    if message.from_user.id not in support_ids:
        return
    
    support_id = message.from_user.id
    
    if support_id in sleeping_supports:
        await message.answer("ℹ️ Вы уже в режиме сна")
        return
    
    if support_id in support_to_user:
        user_id = support_to_user[support_id]
        active_dialogs[user_id]['sleep_after'] = True
        save_data()
        await message.answer("⏳ После завершения текущего диалога вы автоматически перейдёте в режим сна.")
    else:
        sleeping_supports.add(support_id)
        active_supports.discard(support_id)
        save_data()
        await message.answer(
            "💤 Вы перешли в режим сна и не будете получать новые запросы",
            reply_markup=get_support_keyboard()
        )

@dp.message(Command("active"))
async def active_mode(message: Message):
    if message.from_user.id not in support_ids:
        return
    
    support_id = message.from_user.id
    
    if support_id not in sleeping_supports:
        await message.answer("ℹ️ Вы уже в активном режиме")
        return
    
    sleeping_supports.remove(support_id)
    active_supports.add(support_id)
    save_data()
    
    await message.answer(
        "✅ Вы вернулись в активный режим и будете получать новые запросы",
        reply_markup=get_support_keyboard() if support_id not in support_to_user else get_support_dialog_keyboard()
    )
    
    if support_id not in support_to_user and request_queue:
        await assign_support()

@dp.message()
async def handle_message(message: Message):
    user_id = message.from_user.id
    
    if user_id in active_dialogs:
        await process_user_message(message)
    elif user_id in support_ids and user_id in support_to_user:
        await process_support_message(message)
    else:
        # Обработка сообщений, когда нет активного диалога
        if user_id in support_ids:
            await message.answer(
                "ℹ️ У вас нет активного диалога. Используйте команды поддержки:",
                reply_markup=get_support_keyboard()
            )
        else:
            await message.answer(
                "ℹ️ У вас нет активного диалога с оператором. Нажмите /help для связи",
                reply_markup=get_user_keyboard()
            )

async def process_user_message(message: Message):
    user_id = message.from_user.id
    dialog = active_dialogs[user_id]
    support_id = dialog['support_id']
    
    dialog['last_activity'] = datetime.now()
    await reset_timeout(user_id)
    save_data()
    
    await bot.send_message(
        chat_id=support_id,
        text=f"👤 Сообщение от пользователя:\n{message.text}"
    )

async def process_support_message(message: Message):
    support_id = message.from_user.id
    user_id = support_to_user[support_id]
    
    active_dialogs[user_id]['last_activity'] = datetime.now()
    await reset_timeout(user_id)
    save_data()
    
    await bot.send_message(
        chat_id=user_id,
        text=f"👨‍💻 Ответ оператора:\n{message.text}"
    )

async def assign_support():
    try:
        queue_copy = request_queue.copy()
        
        for request in queue_copy:
            available_supports = active_supports - busy_supports - sleeping_supports
            if not available_supports:
                break
            
            user_id = request['user_id']
            
            if user_id in active_dialogs:
                if request in request_queue:
                    request_queue.remove(request)
                if user_id in processed_users:
                    processed_users.discard(user_id)
                continue
                
            support_id = min(available_supports)
            
            active_dialogs[user_id] = {
                'support_id': support_id,
                'last_activity': datetime.now(),
                'sleep_after': False
            }
            user_to_support[user_id] = support_id
            support_to_user[support_id] = user_id
            busy_supports.add(support_id)
            
            if request in request_queue:
                request_queue.remove(request)
            if user_id in processed_users:
                processed_users.discard(user_id)
            save_data()
            
            await bot.send_message(
                chat_id=user_id,
                text=f"✅ Вы подключены к оператору!\n\n"
                     f"🔹 Если вы не отвечаете более {TIMEOUT_MINUTES} минут, диалог будет закрыт",
                reply_markup=get_dialog_keyboard()
            )
            
            await bot.send_message(
                chat_id=support_id,
                text=f"📩 Новый диалог с @{request['username']}\n\n"
                     f"🔹 Отвечайте в этом чате\n"
                     f"🔹 Диалог автоматически закроется через {TIMEOUT_MINUTES} мин неактивности",
                reply_markup=get_support_dialog_keyboard()
            )
            
            await start_timeout(user_id)
    except Exception as e:
        logging.error(f"Ошибка в assign_support: {e}")

# async def close_dialog(user_id, support_id, closed_by_user=False, closed_by_support=False, timeout=False):
#     sleep_after = active_dialogs.get(user_id, {}).get('sleep_after', False)
    
#     if user_id in active_dialogs:
#         del active_dialogs[user_id]
#     if user_id in user_to_support:
#         del user_to_support[user_id]
#     if support_id in support_to_user:
#         del support_to_user[support_id]
    
#     if user_id in processed_users:
#         processed_users.discard(user_id)
    
#     busy_supports.discard(support_id)
#     cancel_timeout(user_id)
    
#     if timeout:
#         await bot.send_message(
#             chat_id=user_id,
#             text=f"⏳ Диалог автоматически закрыт из-за неактивности (более {TIMEOUT_MINUTES} минут)",
#             reply_markup=get_user_keyboard()
#         )
        
#         # Уведомляем оператора только если он не в режиме сна
#         if support_id not in sleeping_supports:
#             await bot.send_message(
#                 chat_id=support_id,
#                 text=f"⏳ Диалог был автоматически закрыт из-за неактивности пользователя",
#                 reply_markup=get_support_keyboard()
#             )
#     elif closed_by_user:
#         await bot.send_message(
#             chat_id=support_id,
#             text="ℹ️ Пользователь завершил диалог",
#             reply_markup=get_support_keyboard()
#         )
#     elif closed_by_support:
#         await bot.send_message(
#             chat_id=user_id,
#             text="ℹ️ Оператор завершил диалог",
#             reply_markup=get_user_keyboard()
#         )
    
#     if sleep_after:
#         sleeping_supports.add(support_id)
#         active_supports.discard(support_id)
#         await bot.send_message(
#             chat_id=support_id,
#             text="💤 Вы автоматически переведены в режим сна после завершения диалога",
#             reply_markup=get_support_keyboard()
#         )
    
#     save_data()
#     await assign_support()

# async def close_dialog(user_id, support_id, closed_by_user=False, closed_by_support=False, timeout=False):
#     sleep_after = active_dialogs.get(user_id, {}).get('sleep_after', False)
    
#     if user_id in active_dialogs:
#         del active_dialogs[user_id]
#     if user_id in user_to_support:
#         del user_to_support[user_id]
#     if support_id in support_to_user:
#         del support_to_user[support_id]
    
#     if user_id in processed_users:
#         processed_users.discard(user_id)
    
#     busy_supports.discard(support_id)
#     cancel_timeout(user_id)
    
#     if timeout:
#         # Уведомляем пользователя
#         await bot.send_message(
#             chat_id=user_id,
#             text=f"⏳ Диалог автоматически закрыт из-за неактивности (более {TIMEOUT_MINUTES} минут)",
#             reply_markup=get_user_keyboard()
#         )
        
#         # Уведомляем оператора (даже если он в режиме сна)
#         try:
#             await bot.send_message(
#                 chat_id=support_id,
#                 text=f"⏳ Диалог с пользователем был автоматически закрыт из-за неактивности",
#                 reply_markup=get_support_keyboard()
#             )
#         except Exception as e:
#             logging.error(f"Не удалось уведомить оператора {support_id}: {e}")
        
#     elif closed_by_user:
#         await bot.send_message(
#             chat_id=support_id,
#             text="ℹ️ Пользователь завершил диалог",
#             reply_markup=get_support_keyboard()
#         )
#     elif closed_by_support:
#         await bot.send_message(
#             chat_id=user_id,
#             text="ℹ️ Оператор завершил диалог",
#             reply_markup=get_user_keyboard()
#         )
    
#     if sleep_after:
#         sleeping_supports.add(support_id)
#         active_supports.discard(support_id)
#         await bot.send_message(
#             chat_id=support_id,
#             text="💤 Вы автоматически переведены в режим сна после завершения диалога",
#             reply_markup=get_support_keyboard()
#         )
    
#     save_data()
#     await assign_support()

# async def close_dialog(user_id, support_id, closed_by_user=False, closed_by_support=False, timeout=False):
#     sleep_after = active_dialogs.get(user_id, {}).get('sleep_after', False)
    
#     if user_id in active_dialogs:
#         del active_dialogs[user_id]
#     if user_id in user_to_support:
#         del user_to_support[user_id]
#     if support_id in support_to_user:
#         del support_to_user[support_id]
    
#     if user_id in processed_users:
#         processed_users.discard(user_id)
    
#     busy_supports.discard(support_id)
#     cancel_timeout(user_id)
    
#     if timeout:
#         # Получаем username пользователя для сообщения оператору
#         username = "пользователь"
#         for request in request_queue:
#             if request['user_id'] == user_id:
#                 username = f"@{request['username']}" if request['username'] else "пользователь"
#                 break
        
#         # Форматируем одинаковые сообщения для обеих сторон
#         timeout_message = f"⏳ Диалог автоматически закрыт из-за неактивности (более {TIMEOUT_MINUTES} минут)"
#         print('pidor')
#         # Отправляем пользователю
#         await bot.send_message(
#             chat_id=user_id,
#             text=timeout_message,
#             reply_markup=get_user_keyboard()
#         )
#         print('pidor')
        
#         # Отправляем оператору (точно такое же сообщение, но с упоминанием пользователя)
#         await bot.send_message(
#             chat_id=support_id,
#             text=f"⏳ Диалог с {username} автоматически закрыт из-за неактивности (более {TIMEOUT_MINUTES} минут)",
#             reply_markup=get_support_keyboard()
#         )
#         print('pidor')
        
#     elif closed_by_user:
#         await bot.send_message(
#             chat_id=support_id,
#             text="ℹ️ Пользователь завершил диалог",
#             reply_markup=get_support_keyboard()
#         )
#     elif closed_by_support:
#         await bot.send_message(
#             chat_id=user_id,
#             text="ℹ️ Оператор завершил диалог",
#             reply_markup=get_user_keyboard()
#         )
    
#     if sleep_after:
#         sleeping_supports.add(support_id)
#         active_supports.discard(support_id)
#         await bot.send_message(
#             chat_id=support_id,
#             text="💤 Вы автоматически переведены в режим сна после завершения диалога",
#             reply_markup=get_support_keyboard()
#         )
    
#     save_data()
#     await assign_support()

async def close_dialog(user_id, support_id, closed_by_user=False, closed_by_support=False, timeout=False):
    sleep_after = active_dialogs.get(user_id, {}).get('sleep_after', False)
    
    # Получаем данные пользователя
    username = "пользователь"
    for request in request_queue:
        if request['user_id'] == user_id:
            username = f"@{request['username']}" if request['username'] else "пользователь"
            break

    # Удаляем данные о диалоге
    if user_id in active_dialogs:
        del active_dialogs[user_id]
    if user_id in user_to_support:
        del user_to_support[user_id]
    if support_id in support_to_user:
        del support_to_user[support_id]
    
    processed_users.discard(user_id)
    busy_supports.discard(support_id)
    cancel_timeout(user_id)

    # Обработка таймаута
    if timeout:
        timeout_message = f"⏳ Диалог автоматически закрыт из-за неактивности (более {TIMEOUT_MINUTES} минут)"
        
        # 1. Сначала пытаемся отправить пользователю
        try:
            await bot.send_message(
                chat_id=user_id,
                text=timeout_message,
                reply_markup=get_user_keyboard()
            )
            
            # 2. Только если пользователь получил сообщение - отправляем оператору
            await bot.send_message(
                chat_id=support_id,
                text=f"⏳ Диалог с {username}:\n{timeout_message}",
                reply_markup=get_support_keyboard()
            )
            
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления о таймауте: {e}")
            # Если не удалось отправить пользователю, все равно пробуем оператору
            try:
                await bot.send_message(
                    chat_id=support_id,
                    text=f"⏳ Диалог с {username} был завершен, но не удалось уведомить пользователя",
                    reply_markup=get_support_keyboard()
                )
            except Exception as e:
                logging.error(f"Ошибка отправки оператору: {e}")

    # Остальные сценарии закрытия
    elif closed_by_user:
        await bot.send_message(
            chat_id=support_id,
            text=f"ℹ️ Пользователь {username} завершил диалог",
            reply_markup=get_support_keyboard()
        )
    elif closed_by_support:
        await bot.send_message(
            chat_id=user_id,
            text="ℹ️ Оператор завершил диалог",
            reply_markup=get_user_keyboard()
        )
    
    # Обработка режима сна
    if sleep_after:
        sleeping_supports.add(support_id)
        active_supports.discard(support_id)
        try:
            await bot.send_message(
                chat_id=support_id,
                text="💤 Вы переведены в режим сна после диалога",
                reply_markup=get_support_keyboard()
            )
        except Exception as e:
            logging.error(f"Ошибка уведомления о сне: {e}")

    save_data()
    await assign_support()
    
async def main():
    await restore_timeouts()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())