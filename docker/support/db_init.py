#!/usr/bin/env python3
import os
import logging
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from typing import Dict, List, Tuple

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация PostgreSQL
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
    'dbname': os.getenv('POSTGRES_DB', 'blood_donation_bot')
}

# Ожидаемая структура таблиц
TABLES: Dict[str, List[Tuple[str, str]]] = {
    'events': [
        ('id', 'SERIAL PRIMARY KEY'),
        ('date', 'DATE NOT NULL'),
        ('organizer', 'INTEGER NOT NULL'),
        ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    ],
    'donors': [
        ('id', 'SERIAL PRIMARY KEY'),
        ('phone', 'VARCHAR(20) NOT NULL UNIQUE'),
        ('fio', 'TEXT'),
        ('tg_id', 'TEXT')
    ]
}

def get_connection(dbname: str = None):
    """Устанавливает соединение с PostgreSQL"""
    params = DB_CONFIG.copy()
    if dbname:
        params['dbname'] = dbname
    try:
        conn = psycopg2.connect(**params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к PostgreSQL: {e}")
        raise

def check_database_exists() -> bool:
    """Проверяет существование базы данных"""
    try:
        with get_connection('postgres') as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (DB_CONFIG['dbname'],)
            )
            return bool(cursor.fetchone())
    except Exception as e:
        logger.error(f"Ошибка при проверке БД: {e}")
        return False

def create_database():
    """Создает базу данных если она не существует"""
    if not check_database_exists():
        try:
            with get_connection('postgres') as conn, conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(DB_CONFIG['dbname'])
                    )
                )
                logger.info(f"БД {DB_CONFIG['dbname']} успешно создана")
        except Exception as e:
            logger.error(f"Ошибка при создании БД: {e}")
            raise

def check_table_exists(table_name: str) -> bool:
    """Проверяет существование таблицы"""
    try:
        with get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (table_name,)
            )
            return bool(cursor.fetchone())
    except Exception as e:
        logger.error(f"Ошибка при проверке таблицы {table_name}: {e}")
        return False

def create_table(table_name: str, columns: List[Tuple[str, str]]):
    """Создает таблицу с указанными колонками"""
    try:
        with get_connection() as conn, conn.cursor() as cursor:
            columns_def = sql.SQL(', ').join(
                sql.SQL("{} {}").format(
                    sql.Identifier(col_name),
                    sql.SQL(col_type)
                ) for col_name, col_type in columns
            )
            query = sql.SQL("CREATE TABLE {} ({})").format(
                sql.Identifier(table_name),
                columns_def
            )
            cursor.execute(query)
            logger.info(f"Таблица {table_name} успешно создана")
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы {table_name}: {e}")
        raise

def initialize_database():
    """Основная функция инициализации БД"""
    logger.info("Начало инициализации PostgreSQL БД")
    
    try:
        # 1. Создаем БД если не существует
        create_database()
        
        # 2. Создаем таблицы если они не существуют
        for table_name, columns in TABLES.items():
            if not check_table_exists(table_name):
                create_table(table_name, columns)
            else:
                logger.info(f"Таблица {table_name} уже существует")
        
        logger.info("Проверка БД завершена успешно")
        return True
    except Exception as e:
        logger.error(f"Критическая ошибка инициализации БД: {e}")
        return False

if __name__ == "__main__":
    if initialize_database():
        logger.info("Инициализация БД завершена успешно")
    else:
        logger.error("Инициализация БД завершена с ошибками")
        exit(1)