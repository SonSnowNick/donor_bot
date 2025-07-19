-- Создание таблиц (если не существуют)
CREATE TABLE IF NOT EXISTS doner_tabs (
  id SERIAL PRIMARY KEY,
  FIO VARCHAR(50), 
  "Group" VARCHAR(15),
  cnt_gov INTEGER NULL,
  cnt_fmba INTEGER NULL,
  cnt_sm INTEGER NULL,
  last_date_gov DATE NULL,
  last_date_fmba DATE NULL,
  Contacts_social VARCHAR(50) NULL,
  Number_phone BIGINT,
  Blood_group VARCHAR(2),
  Age SMALLINT,
  tg_id INTEGER NULL
);

CREATE TABLE IF NOT EXISTS doner_flags (
  id INTEGER PRIMARY KEY REFERENCES doner_tabs(id) ON DELETE CASCADE,
  is_verified BOOLEAN DEFAULT FALSE,
  is_active BOOLEAN DEFAULT TRUE
);

-- Добавление и удаление тестовых данных
DO $$
DECLARE
  test_id INTEGER;
BEGIN
  -- Добавляем тестовые данные только если их нет
  IF NOT EXISTS (SELECT 1 FROM doner_tabs WHERE FIO = 'TEST_USER_DELETE_ME') THEN
    -- Вставляем тестовую запись
    INSERT INTO doner_tabs (FIO, "Group", Number_phone) 
    VALUES ('TEST_USER_DELETE_ME', 'TEST', 70000000000)
    RETURNING id INTO test_id;
    
    -- Добавляем связанные флаги
    INSERT INTO doner_flags (id, is_verified, is_active)
    VALUES (test_id, TRUE, FALSE);
    
    RAISE NOTICE 'Тестовые данные добавлены (ID: %)', test_id;
    
    -- Сразу удаляем тестовые данные
    DELETE FROM doner_flags WHERE id = test_id;
    DELETE FROM doner_tabs WHERE id = test_id;
    
    RAISE NOTICE 'Тестовые данные удалены';
  END IF;
END $$;