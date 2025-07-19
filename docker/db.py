import asyncpg
from typing import Dict, List, Optional

async def create_pool():
    return await asyncpg.create_pool(
        user='root',
        password='rapitta122',
        database='doner_db',
        host='localhost'
    )

async def get_user_by_phone(pool, phone: str) -> Optional[Dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM doner_tabss WHERE number_phone = $1", 
            phone
        )
        return dict(row) if row else None

async def get_user_by_tg_id(pool, tg_id: int) -> Optional[Dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM doner_tabss WHERE tg_id = $1",
            tg_id
        )
        return dict(row) if row else None

async def create_user(pool, user_data: Dict) -> Optional[Dict]:
    async with pool.acquire() as conn:
        try:
            query = """
            INSERT INTO doner_tabss 
            (fio, number_phone, user_type, tg_id)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """
            row = await conn.fetchrow(
                query,
                user_data["fio"],
                user_data["number_phone"],
                user_data["user_type"],
                user_data.get("tg_id")
            )
            return dict(row)
        except asyncpg.exceptions.UndefinedColumnError:
            # Если столбца tg_id нет, используем альтернативный запрос
            query = """
            INSERT INTO doner_tabss 
            (fio, number_phone, user_type)
            VALUES ($1, $2, $3)
            RETURNING *
            """
            row = await conn.fetchrow(
                query,
                user_data["fio"],
                user_data["number_phone"],
                user_data["user_type"]
            )
            return dict(row)

# Остальные функции остаются без изменений...

async def get_available_events(pool, organizer_id: int):
    """Получает доступные даты для записи к конкретному организатору"""
    async with pool.acquire() as conn:
        query = """
        SELECT id, date, organizer 
        FROM events 
        WHERE organizer = $1 AND date > CURRENT_DATE 
        ORDER BY date
        """
        rows = await conn.fetch(query, organizer_id)
        return [dict(row) for row in rows]

async def create_appointment(pool, data: Dict):
    """Создает запись на прием"""
    async with pool.acquire() as conn:
        query = """
        INSERT INTO appointments (user_id, event_id, status) 
        VALUES ($1, $2, 0)
        RETURNING *
        """
        return await conn.fetchrow(query, data['user_id'], data['event_id'])

async def get_event_by_id(pool, event_id: int):
    """Получает информацию о мероприятии по ID"""
    async with pool.acquire() as conn:
        query = """
        SELECT id, date, organizer 
        FROM events 
        WHERE id = $1
        """
        row = await conn.fetchrow(query, event_id)
        return dict(row) if row else None

async def get_user_appointments(pool, user_id: int):
    """Получает все записи пользователя"""
    async with pool.acquire() as conn:
        query = """
        SELECT a.id, a.event_id, a.status, a.created_at,
               e.date, e.organizer
        FROM appointments a
        JOIN events e ON a.event_id = e.id
        WHERE a.user_id = $1
        ORDER BY e.date DESC
        """
        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]

async def create_event(pool, event_data: Dict):
    """Создает новое мероприятие"""
    async with pool.acquire() as conn:
        query = """
        INSERT INTO events (date, organizer)
        VALUES ($1, $2)
        RETURNING *
        """
        return await conn.fetchrow(
            query, 
            event_data["date"],
            event_data["organizer"]
        )
    
async def get_user_by_tg_id(pool, tg_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM doner_tabss WHERE tg_id = $1", 
            tg_id
        )
        return dict(row) if row else None