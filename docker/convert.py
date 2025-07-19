import os
import pandas as pd
from sqlalchemy import create_engine, String, Integer
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from config import TOKEN, DB_CONFIG

# Настройка логгирования
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Состояния FSM
class Form(StatesGroup):
    waiting_for_date = State()
    waiting_for_file = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("Привет! Отправь дату мероприятия в формате ГГГГ-ММ-ДД (например, 2023-12-31)")
    await state.set_state(Form.waiting_for_date)

@dp.message(Form.waiting_for_date)
async def process_date(message: types.Message, state: FSMContext):
    try:
        # Проверка формата даты
        date = pd.to_datetime(message.text).strftime('%Y-%m-%d')
        await state.update_data(event_date=date)
        await message.answer(f"Дата мероприятия: {date}. Теперь отправь Excel-файл с данными.")
        await state.set_state(Form.waiting_for_file)
    except ValueError:
        await message.answer("Неверный формат даты. Попробуй еще раз в формате ГГГГ-ММ-ДД.")

@dp.message(Form.waiting_for_file, F.document)
async def process_excel(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    date = user_data['event_date']
    
    try:
        # Скачиваем файл
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        file_path = f"temp_{date}.xlsx"
        await bot.download_file(file.file_path, file_path)
        
        # Читаем Excel с явным указанием типов
        df = pd.read_excel(file_path, dtype={
            'phone_number': str,
            'source': str,
            'status': int
        })
        
        # Проверяем структуру данных
        if len(df.columns) != 3:
            raise ValueError("Файл должен содержать ровно 3 столбца")
            
        # Переименовываем столбцы
        df.columns = ['phone_number', 'source', 'status']
        
        # Проверяем значения
        valid_sources = ['Гаврилова', 'ФНБА']
        valid_statuses = [1, 2, 3]
        
        if not df['source'].isin(valid_sources).all():
            raise ValueError("Второй столбец должен содержать только 'Гаврилова' или 'ФНБА'")
            
        if not df['status'].isin(valid_statuses).all():
            raise ValueError("Третий столбец должен содержать только 1, 2 или 3")
        
        # Подключаемся к БД
        conn_str = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        engine = create_engine(conn_str)
        
        # Создаем имя таблицы
        table_name = f"event_{date.replace('-', '_')}"
        
        # Загружаем данные с явным указанием типов
        df.to_sql(
            table_name, 
            engine, 
            if_exists='replace', 
            index=False,
            dtype={
                'phone_number': String(20),
                'source': String(50),
                'status': Integer
            }
        )
        
        # Формируем статистику
        stats_message = "Статистика по статусам:\n\n"
        
        for source in ['Гаврилова', 'ФНБА']:
            source_df = df[df['source'] == source]
            stats_message += (
                f"{source}:\n"
                f"• Не пришли: {len(source_df[source_df['status'] == 1])}\n"
                f"• Не прошли по здоровью: {len(source_df[source_df['status'] == 2])}\n"
                f"• Успешно сдали кровь: {len(source_df[source_df['status'] == 3])}\n\n"
            )
        
        # Общая статистика
        stats_message += (
            "Общая статистика:\n"
            f"• Всего записей: {len(df)}\n"
            f"• Не пришли: {len(df[df['status'] == 1])}\n"
            f"• Не прошли по здоровью: {len(df[df['status'] == 2])}\n"
            f"• Успешно сдали кровь: {len(df[df['status'] == 3])}"
        )
        
        await message.answer(
            f"Данные успешно загружены в таблицу {table_name}!\n\n"
            f"{stats_message}"
        )
        
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")
        logger.error(f"Error processing Excel file: {str(e)}")
        
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        await state.clear()
        
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())